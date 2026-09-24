"""
partitions.py - tablica partycji i dostep do obrazu dysku twardego.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Obraz dysku twardego nie jest jednym systemem plikow, tylko pojemnikiem na
kilka. Pierwszy sektor to tablica partycji: cztery wpisy po 16 bajtow,
kazdy z typem, poczatkiem i dlugoscia.

Cztery wpisy szybko przestawaly wystarczac, wiec w DOS-ie przyjal sie
wybieg: jedna z pozycji opisuje **partycje rozszerzona**, ktora sama
zawiera lancuch dalszych wpisow. Stad na dysku z epoki dysk C: bywa
podstawowy, a D: i E: leza wewnatrz rozszerzonej. Modul przechodzi ten
lancuch, zeby pokazac wszystkie naraz.

Dostep do sektorow dostajemy z zewnatrz: z pliku VHD albo z surowego
obrazu. Tablica partycji wyglada w obu tak samo.

Wiersz polecen:
    python3 partitions.py dysk.vhd
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import vhd

__all__ = [
    "DiskError",
    "Partition",
    "RawDisk",
    "open_disk",
    "read_partitions",
    "TYPY",
    "SEKTOR",
]

SEKTOR = vhd.SEKTOR
SYGNATURA = b"\x55\xaa"
ROZSZERZONE = (0x05, 0x0F, 0x85)

# Typy partycji spotykane na dyskach z epoki. Pusty wpis ma typ 0.
TYPY: dict[int, str] = {
    0x01: "FAT12",
    0x04: "FAT16 (do 32 MB)",
    0x05: "rozszerzona",
    0x06: "FAT16",
    0x07: "HPFS / NTFS",
    0x0B: "FAT32",
    0x0C: "FAT32 (LBA)",
    0x0E: "FAT16 (LBA)",
    0x0F: "rozszerzona (LBA)",
    0x83: "Linux",
    0x85: "rozszerzona (Linux)",
}

# Te, ktore umiemy przeczytac naszym silnikiem.
CZYTELNE = (0x01, 0x04, 0x06, 0x0E)

# Dysk z epoki bywa podzielony gesto, ale lancuch rozszerzonych z bledem
# potrafi sie zapetlic - konczymy po rozsadnej liczbie ogniw.
MAKS_LOGICZNYCH = 32


class DiskError(Exception):
    """Obraz nie da sie otworzyc albo nie ma w nim tablicy partycji."""


@dataclass(frozen=True)
class Partition:
    """Jedna partycja: gdzie sie zaczyna, ile ma i co w niej jest."""

    index: int                 # numer porzadkowy, od 1
    type_id: int
    start: int                 # pierwszy sektor, liczony od poczatku dysku
    sectors: int
    bootable: bool
    logical: bool = False      # czy lezy wewnatrz partycji rozszerzonej

    @property
    def type_name(self) -> str:
        return TYPY.get(self.type_id, f"nieznany (0x{self.type_id:02X})")

    @property
    def size(self) -> int:
        return self.sectors * SEKTOR

    @property
    def readable(self) -> bool:
        """Czy nasz silnik umie pokazac jej zawartosc."""
        return self.type_id in CZYTELNE

    @property
    def label(self) -> str:
        mega = self.size / 1048576
        opis = f"{mega:.0f} MB" if mega >= 1 else f"{self.size} B"
        return f"{self.index}. {self.type_name}, {opis}"


class RawDisk:
    """
    Surowy obraz dysku: sektory leza po kolei, bez zadnego naglowka.

    Ten sam zestaw metod co VhdImage, zeby reszcie programu bylo wszystko
    jedno, skad pochodza sektory.
    """

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self._plik = open(self.path, "rb")
        self.size = os.path.getsize(self.path)

    @property
    def sector_count(self) -> int:
        return self.size // SEKTOR

    @property
    def kind_name(self) -> str:
        return "surowy obraz"

    def read_sector(self, lba: int) -> bytes:
        if not 0 <= lba < self.sector_count:
            raise DiskError(f"sektor {lba} poza dyskiem "
                            f"({self.sector_count} sektorow)")
        self._plik.seek(lba * SEKTOR)
        dane = self._plik.read(SEKTOR)
        return dane if len(dane) == SEKTOR else dane + bytes(SEKTOR - len(dane))

    def read(self, lba: int, count: int = 1) -> bytes:
        return b"".join(self.read_sector(lba + i) for i in range(count))

    def close(self) -> None:
        if not self._plik.closed:
            self._plik.close()

    def __enter__(self) -> "RawDisk":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<RawDisk {os.path.basename(self.path)} {self.size} B>"


def open_disk(path: str):
    """
    Otwiera obraz dysku - VHD albo surowy - do odczytu sektorow.

    O rodzaju decyduje zawartosc pliku, nie jego nazwa: obraz VHD poznaje
    sie po stopce na koncu.
    """
    if not os.path.isfile(path):
        raise DiskError(f"nie ma takiego pliku: {path}")
    if vhd.looks_like_vhd(path):
        try:
            return vhd.open_image(path)
        except vhd.VhdError as exc:
            raise DiskError(str(exc)) from exc
    if os.path.getsize(path) < SEKTOR:
        raise DiskError("plik jest za krotki na obraz dysku")
    return RawDisk(path)


def _wpis(dane: bytes, numer: int) -> tuple[int, int, int, bool]:
    """Jeden z czterech wpisow tablicy: (typ, poczatek, dlugosc, startowa)."""
    w = dane[446 + numer * 16:446 + (numer + 1) * 16]
    return (w[4],
            int.from_bytes(w[8:12], "little"),
            int.from_bytes(w[12:16], "little"),
            w[0] == 0x80)


def read_partitions(dysk) -> list[Partition]:
    """
    Lista partycji obrazu, razem z logicznymi z partycji rozszerzonej.

    Pusta lista oznacza brak tablicy partycji - na przyklad gdy obraz jest
    jednym wielkim systemem plikow bez podzialu.
    """
    mbr = dysk.read_sector(0)
    if mbr[510:512] != SYGNATURA:
        return []

    wynik: list[Partition] = []
    rozszerzona: int | None = None
    for numer in range(4):
        typ, poczatek, dlugosc, startowa = _wpis(mbr, numer)
        if not typ or not dlugosc:
            continue
        if typ in ROZSZERZONE:
            rozszerzona = poczatek
            continue
        wynik.append(Partition(len(wynik) + 1, typ, poczatek, dlugosc,
                               startowa))

    if rozszerzona is not None:
        wynik += _logiczne(dysk, rozszerzona, len(wynik))
    return wynik


def _logiczne(dysk, poczatek_rozszerzonej: int, ile_juz: int) -> list[Partition]:
    """
    Przechodzi lancuch partycji logicznych wewnatrz rozszerzonej.

    Kazde ogniwo ma wlasna tablice: pierwszy wpis opisuje partycje, drugi
    wskazuje nastepne ogniwo. Przesuniecia w pierwszym wpisie licza sie od
    ogniwa, a w drugim od poczatku calej partycji rozszerzonej - pomylenie
    tych dwoch daje partycje w zupelnie zlym miejscu.
    """
    wynik: list[Partition] = []
    ogniwo = poczatek_rozszerzonej
    odwiedzone: set[int] = set()
    while ogniwo not in odwiedzone and len(wynik) < MAKS_LOGICZNYCH:
        odwiedzone.add(ogniwo)
        try:
            tablica = dysk.read_sector(ogniwo)
        except Exception:
            break
        if tablica[510:512] != SYGNATURA:
            break
        typ, wzgledny, dlugosc, startowa = _wpis(tablica, 0)
        if typ and dlugosc:
            wynik.append(Partition(ile_juz + len(wynik) + 1, typ,
                                   ogniwo + wzgledny, dlugosc, startowa,
                                   logical=True))
        nastepny_typ, nastepny, _, _ = _wpis(tablica, 1)
        if not nastepny_typ or not nastepny:
            break
        ogniwo = poczatek_rozszerzonej + nastepny
    return wynik


def describe(path: str) -> str:
    """Czytelny opis obrazu i jego partycji, do wiersza polecen i raportow."""
    with open_disk(path) as dysk:
        wiersze = [f"{os.path.basename(path)}: {dysk.kind_name}, "
                   f"{dysk.size} B ({dysk.size // 1048576} MB), "
                   f"{dysk.sector_count} sektorow"]
        partycje = read_partitions(dysk)
        if not partycje:
            wiersze.append("  brak tablicy partycji")
            return "\n".join(wiersze)
        for p in partycje:
            wiersze.append(
                f"  {p.index}. typ 0x{p.type_id:02X} {p.type_name:<18}"
                f" od {p.start:>9} przez {p.sectors:>9} sektorow"
                f"  ({p.size // 1048576} MB)"
                f"{'  startowa' if p.bootable else ''}"
                f"{'  logiczna' if p.logical else ''}"
                f"{'' if p.readable else '  [nieobslugiwana]'}")
        return "\n".join(wiersze)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="partitions", description="Tablica partycji obrazu dysku.")
    parser.add_argument("plik")
    arg = parser.parse_args(argv)
    try:
        print(describe(arg.plik))
        return 0
    except (DiskError, vhd.VhdError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
