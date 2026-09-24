"""
vhd.py - obrazy dyskow twardych w formacie VHD.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

86Box, PCem i maszyny wirtualne Microsoftu trzymaja dyski twarde w plikach
VHD. To nie jest surowy obraz: na koncu pliku siedzi stopka z geometria
i rozmiarem, a odmiana rozszerzalna dokłada do tego tablice blokow.

Trzy odmiany formatu:

  stala          - dane po kolei, jak w surowym obrazie, plus stopka na
                   koncu pliku,
  rozszerzalna   - dane w blokach po 2 MB, kazdy z wlasna bitmapa, a
                   kolejnosc blokow w pliku opisuje tablica. Bloki, do
                   ktorych nigdy nic nie zapisano, nie istnieja w pliku
                   i czytaja sie jako zera. Dzieki temu dysk 245 MB miesci
                   sie w pliku o ulamku tego rozmiaru,
  roznicowa      - zapisuje tylko roznice wobec innego pliku. Nie
                   obslugujemy; program mowi to wprost, zamiast pokazywac
                   nieprawdziwa zawartosc.

Modul tylko czyta. Zapis do obrazu dysku to osobna sprawa i osobne ryzyko.

Wiersz polecen:
    python3 vhd.py info dysk.vhd
    python3 vhd.py read dysk.vhd --lba 0 --count 1
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from dataclasses import dataclass

__all__ = [
    "VhdError",
    "VhdImage",
    "Footer",
    "open_image",
    "SEKTOR",
]

SEKTOR = 512
KOSMYK_STOPKI = b"conectix"
KOSMYK_NAGLOWKA = b"cxsparse"
NIEZAJETY = 0xFFFFFFFF

STALA = 2
ROZSZERZALNA = 3
ROZNICOWA = 4

NAZWY_ODMIAN = {
    STALA: "stala",
    ROZSZERZALNA: "rozszerzalna",
    ROZNICOWA: "roznicowa",
}


class VhdError(Exception):
    """Plik nie jest obrazem VHD albo jest w odmianie, ktorej nie czytamy."""


@dataclass(frozen=True)
class Footer:
    """Stopka VHD - 512 bajtow na koncu pliku, i jej kopia na poczatku."""

    kind: int
    size: int                  # rozmiar dysku w bajtach
    cylinders: int
    heads: int
    sectors: int               # na sciezke
    data_offset: int           # gdzie zaczyna sie naglowek odmiany
    creator: str
    checksum_ok: bool

    @property
    def kind_name(self) -> str:
        return NAZWY_ODMIAN.get(self.kind, f"nieznana ({self.kind})")

    @property
    def sector_count(self) -> int:
        return self.size // SEKTOR


def _suma(dane: bytes) -> int:
    """
    Suma kontrolna VHD: dopelnienie sumy bajtow, z pominieciem samego pola.

    Liczona tak samo dla stopki i dla naglowka odmiany rozszerzalnej.
    """
    return (~sum(dane)) & 0xFFFFFFFF


def parse_footer(dane: bytes) -> Footer:
    """Rozbiera stopke. Nie sprawdza, czy plik ma sens jako calosc."""
    if len(dane) < 512 or dane[:8] != KOSMYK_STOPKI:
        raise VhdError("brak sygnatury VHD")
    zapisana = struct.unpack(">I", dane[64:68])[0]
    policzona = _suma(dane[:64] + b"\x00" * 4 + dane[68:512])
    cyl, glowic, sekt = struct.unpack(">HBB", dane[56:60])
    return Footer(
        kind=struct.unpack(">I", dane[60:64])[0],
        size=struct.unpack(">Q", dane[48:56])[0],
        cylinders=cyl, heads=glowic, sectors=sekt,
        data_offset=struct.unpack(">Q", dane[16:24])[0],
        creator=dane[28:32].decode("latin1").strip(),
        checksum_ok=zapisana == policzona,
    )


class VhdImage:
    """
    Obraz dysku VHD otwarty do odczytu.

    Czyta sie z niego sektorami, jak z dysku. Skad dane sie biora - z ciagu
    bajtow czy z rozproszonych blokow - zostaje wewnatrz.
    """

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self._plik = open(self.path, "rb")
        try:
            self._wczytaj()
        except Exception:
            self._plik.close()
            raise

    # -- otwarcie ----------------------------------------------------------

    def _wczytaj(self) -> None:
        rozmiar_pliku = os.path.getsize(self.path)
        if rozmiar_pliku < 1024:
            raise VhdError("plik jest za krotki na obraz VHD")
        self._plik.seek(rozmiar_pliku - SEKTOR)
        self.footer = parse_footer(self._plik.read(SEKTOR))

        if self.footer.kind == ROZNICOWA:
            raise VhdError("obraz roznicowy - zapisuje tylko roznice wobec "
                           "innego pliku, ktorego tu nie ma")
        if self.footer.kind not in (STALA, ROZSZERZALNA):
            raise VhdError(f"nieznana odmiana VHD: {self.footer.kind}")

        self._bat: list[int] = []
        self._blok = 0
        self._bitmapa = 0
        if self.footer.kind == ROZSZERZALNA:
            self._wczytaj_tablice()

    def _wczytaj_tablice(self) -> None:
        """Naglowek odmiany rozszerzalnej i tablica blokow."""
        self._plik.seek(self.footer.data_offset)
        naglowek = self._plik.read(1024)
        if naglowek[:8] != KOSMYK_NAGLOWKA:
            raise VhdError("brak naglowka obrazu rozszerzalnego")
        tablica_od = struct.unpack(">Q", naglowek[16:24])[0]
        wpisow = struct.unpack(">I", naglowek[28:32])[0]
        self._blok = struct.unpack(">I", naglowek[32:36])[0]
        if self._blok <= 0 or self._blok % SEKTOR:
            raise VhdError(f"bledny rozmiar bloku: {self._blok}")
        # Bitmapa ma bit na sektor bloku i jest dopelniana do pelnych
        # sektorow - dane bloku zaczynaja sie dopiero za nia.
        bitow = self._blok // SEKTOR
        self._bitmapa = ((bitow + 7) // 8 + SEKTOR - 1) // SEKTOR * SEKTOR
        self._plik.seek(tablica_od)
        surowa = self._plik.read(4 * wpisow)
        if len(surowa) < 4 * wpisow:
            raise VhdError("tablica blokow jest ucieta")
        self._bat = list(struct.unpack(f">{wpisow}I", surowa))

    # -- odczyt ------------------------------------------------------------

    @property
    def size(self) -> int:
        return self.footer.size

    @property
    def sector_count(self) -> int:
        return self.footer.sector_count

    @property
    def kind_name(self) -> str:
        return self.footer.kind_name

    def read_sector(self, lba: int) -> bytes:
        """
        Jeden sektor spod podanego numeru.

        Sektor w bloku, ktorego w pliku nie ma, czyta sie jako zera - tak
        wyglada obszar dysku, do ktorego nigdy nic nie zapisano.
        """
        if not 0 <= lba < self.sector_count:
            raise VhdError(f"sektor {lba} poza dyskiem "
                           f"({self.sector_count} sektorow)")
        if self.footer.kind == STALA:
            self._plik.seek(lba * SEKTOR)
            return self._dopelnij(self._plik.read(SEKTOR))

        blok, w_bloku = divmod(lba, self._blok // SEKTOR)
        if blok >= len(self._bat) or self._bat[blok] == NIEZAJETY:
            return bytes(SEKTOR)
        self._plik.seek(self._bat[blok] * SEKTOR + self._bitmapa
                        + w_bloku * SEKTOR)
        return self._dopelnij(self._plik.read(SEKTOR))

    def read(self, lba: int, count: int = 1) -> bytes:
        """Kilka kolejnych sektorow naraz."""
        return b"".join(self.read_sector(lba + i) for i in range(count))

    @staticmethod
    def _dopelnij(dane: bytes) -> bytes:
        """Plik uciety w polowie sektora nie moze wywracac odczytu."""
        return dane if len(dane) == SEKTOR else dane + bytes(SEKTOR - len(dane))

    # -- porzadki ----------------------------------------------------------

    def close(self) -> None:
        if not self._plik.closed:
            self._plik.close()

    def __enter__(self) -> "VhdImage":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def __repr__(self) -> str:
        return (f"<VhdImage {os.path.basename(self.path)} "
                f"{self.kind_name} {self.size} B>")


def open_image(path: str) -> VhdImage:
    return VhdImage(path)


def looks_like_vhd(path: str) -> bool:
    """Czy plik ma stopke VHD. Rozszerzenie nie decyduje - zawartosc tak."""
    try:
        rozmiar = os.path.getsize(path)
        if rozmiar < 1024:
            return False
        with open(path, "rb") as fh:
            fh.seek(rozmiar - SEKTOR)
            return fh.read(8) == KOSMYK_STOPKI
    except OSError:
        return False


# --------------------------------------------------------------------------
#  Wiersz polecen
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vhd", description="Odczyt obrazow dyskow VHD.")
    pod = parser.add_subparsers(dest="cmd", required=True)
    p = pod.add_parser("info")
    p.add_argument("plik")
    p = pod.add_parser("read")
    p.add_argument("plik")
    p.add_argument("--lba", type=int, default=0)
    p.add_argument("--count", type=int, default=1)
    arg = parser.parse_args(argv)

    try:
        with open_image(arg.plik) as obraz:
            if arg.cmd == "info":
                s = obraz.footer
                print(f"odmiana:   {s.kind_name}")
                print(f"rozmiar:   {s.size} B ({s.size // 1048576} MB)")
                print(f"geometria: {s.cylinders} x {s.heads} x {s.sectors}")
                print(f"sektorow:  {s.sector_count}")
                print(f"tworca:    {s.creator}")
                print(f"suma kontrolna stopki: "
                      f"{'zgodna' if s.checksum_ok else 'NIEZGODNA'}")
                return 0
            sys.stdout.buffer.write(obraz.read(arg.lba, arg.count))
            return 0
    except (VhdError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
