"""
fat16.py - odczyt partycji FAT16 i FAT12 z obrazow dyskow twardych.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Po co osobny modul, skoro mamy fat12.py
    Tamten trzyma caly obraz w pamieci i zapisuje go w calosci - dla
    dyskietki 1,44 MB to rozsadne, dla dysku 240 MB juz nie. Tutaj czytamy
    leniwie, sektor po sektorze, i tylko to, o co program pyta: zeby pokazac
    katalog glowny wystarczy blok BPB, tablica FAT i obszar katalogu.

    Drugi powod jest taki, ze dysk twardy nie jest jednym systemem plikow,
    tylko pojemnikiem na partycje. Ten modul dostaje juz wybrana partycje
    i nie wie nic o tablicy partycji - tym zajmuje sie partitions.py.

FAT16 a FAT12
    Roznia sie jednym: szerokoscia wpisu w tablicy FAT. Przy 12 bitach wpisy
    sa upakowane po poltora bajta i trzeba je rozpakowywac; przy 16 bitach
    kazdy zajmuje dwa bajty. Cala reszta - blok BPB, katalog glowny o stalym
    rozmiarze, wpisy 8.3, lancuchy klastrow - jest ta sama, wiec ten modul
    czyta oba. O tym, ktory to rodzaj, decyduje liczba klastrow, a nie napis
    w sektorze rozruchowym: DOS liczyl tak samo i zdarzaja sie partycje
    z mylacym opisem.

Tylko do odczytu
    Zapis do obrazu dysku to osobna sprawa i osobne ryzyko - nadpisanie
    obrazu w trakcie pracy maszyny wirtualnej niszczy caly system plikow,
    a nie jedna dyskietke. Proby zapisu koncza sie tu czytelnym bledem.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass

import engines
import partitions
from fat12 import ATTR_LONG_NAME, ATTR_VOLUME_ID, DirEntry

__all__ = [
    "Fat16Error",
    "FatVolume",
    "HardDiskImage",
    "looks_like_disk",
]

SEKTOR = partitions.SEKTOR
ROZMIAR_WPISU = 32
KONIEC_KATALOGU = 0x00
SKASOWANY = 0xE5

# Granica miedzy FAT12 a FAT16 wedlug liczby klastrow - tak samo liczyl DOS.
GRANICA_FAT12 = 4085


class Fat16Error(engines.ImageError):
    """Partycja nie jest czytelnym systemem plikow FAT albo jest uszkodzona."""


@dataclass(frozen=True)
class Bpb:
    """Blok parametrow z sektora rozruchowego partycji."""

    bytes_per_sector: int
    sectors_per_cluster: int
    reserved: int
    fats: int
    root_entries: int
    total_sectors: int
    media: int
    sectors_per_fat: int
    label: str
    fs_type: str

    @property
    def root_sectors(self) -> int:
        """Katalog glowny ma staly rozmiar - stad jego twardy limit wpisow."""
        return (self.root_entries * ROZMIAR_WPISU + self.bytes_per_sector - 1) \
            // self.bytes_per_sector

    @property
    def first_root(self) -> int:
        return self.reserved + self.fats * self.sectors_per_fat

    @property
    def first_data(self) -> int:
        return self.first_root + self.root_sectors

    @property
    def clusters(self) -> int:
        dane = self.total_sectors - self.first_data
        return max(0, dane // self.sectors_per_cluster)

    @property
    def bits(self) -> int:
        return 12 if self.clusters < GRANICA_FAT12 else 16

    @property
    def cluster_bytes(self) -> int:
        return self.sectors_per_cluster * self.bytes_per_sector


def parse_bpb(sektor: bytes) -> Bpb:
    """Rozbiera sektor rozruchowy partycji. Nie sprawdza jego sensu."""
    def liczba(od: int, ile: int) -> int:
        return int.from_bytes(sektor[od:od + ile], "little")

    male = liczba(0x13, 2)
    return Bpb(
        bytes_per_sector=liczba(0x0B, 2),
        sectors_per_cluster=sektor[0x0D],
        reserved=liczba(0x0E, 2),
        fats=sektor[0x10],
        root_entries=liczba(0x11, 2),
        total_sectors=male if male else liczba(0x20, 4),
        media=sektor[0x15],
        sectors_per_fat=liczba(0x16, 2),
        label=sektor[0x2B:0x36].decode("latin1").strip()
        if sektor[0x26] == 0x29 else "",
        fs_type=sektor[0x36:0x3E].decode("latin1").strip()
        if sektor[0x26] == 0x29 else "",
    )


def sensowny_bpb(bpb: Bpb, sektorow_partycji: int | None = None) -> bool:
    """
    Czy blok BPB opisuje system plikow, ktory da sie czytac.

    Sprawdzamy wartosci, nie napis "FAT16" - ten bywa mylacy albo pusty,
    a przy uszkodzonej partycji potrafi zostac po poprzednim formacie.
    """
    if bpb.bytes_per_sector not in (512, 1024, 2048, 4096):
        return False
    if bpb.sectors_per_cluster not in (1, 2, 4, 8, 16, 32, 64, 128):
        return False
    if bpb.fats not in (1, 2) or bpb.media < 0xF0:
        return False
    if bpb.root_entries <= 0:          # FAT32 ma tu zero
        return False
    if bpb.total_sectors <= bpb.first_data:
        return False
    if sektorow_partycji and bpb.total_sectors > sektorow_partycji + 1:
        return False
    return True


class FatVolume:
    """
    Partycja FAT12 albo FAT16 otwarta do odczytu.

    Dostaje zrodlo sektorow i miejsce, w ktorym zaczyna sie partycja.
    Wszystkie numery sektorow wewnatrz sa liczone od poczatku partycji,
    a przeliczenie na dysk odbywa sie w jednym miejscu.
    """

    def __init__(self, dysk, start: int = 0, sectors: int | None = None):
        self._dysk = dysk
        self._start = start
        self._sektorow = sectors
        rozruchowy = dysk.read_sector(start)
        self.bpb = parse_bpb(rozruchowy)
        if not sensowny_bpb(self.bpb, sectors):
            raise Fat16Error("partycja nie wyglada na FAT12 ani FAT16")
        self._fat: bytes | None = None

    # -- dostep do sektorow ------------------------------------------------

    def sektor(self, numer: int) -> bytes:
        return self._dysk.read_sector(self._start + numer)

    def sektory(self, od: int, ile: int) -> bytes:
        return b"".join(self.sektor(od + i) for i in range(ile))

    # -- tablica FAT -------------------------------------------------------

    @property
    def fat(self) -> bytes:
        """
        Pierwsza kopia tablicy FAT, wczytywana raz.

        Dla partycji 123 MB to okolo 127 kB - trzymanie jej w pamieci
        oszczedza setki odczytow przy kazdym wejsciu do katalogu.
        """
        if self._fat is None:
            self._fat = self.sektory(self.bpb.reserved,
                                     self.bpb.sectors_per_fat)
        return self._fat

    def next_cluster(self, klaster: int) -> int:
        """Nastepne ogniwo lancucha albo wartosc konczaca."""
        if self.bpb.bits == 16:
            miejsce = klaster * 2
            if miejsce + 2 > len(self.fat):
                return 0xFFFF
            return int.from_bytes(self.fat[miejsce:miejsce + 2], "little")
        # FAT12: dwa wpisy zajmuja razem trzy bajty, wiec polowa wartosci
        # lezy w tym samym bajcie co sasiad.
        miejsce = klaster + klaster // 2
        if miejsce + 2 > len(self.fat):
            return 0xFFF
        para = int.from_bytes(self.fat[miejsce:miejsce + 2], "little")
        return para >> 4 if klaster & 1 else para & 0x0FFF

    def _koniec(self, wartosc: int) -> bool:
        granica = 0xFFF8 if self.bpb.bits == 16 else 0xFF8
        return wartosc >= granica or wartosc == 0

    def chain(self, pierwszy: int) -> list[int]:
        """
        Lancuch klastrow pliku albo katalogu.

        Uszkodzony lancuch potrafi wskazywac sam na siebie, wiec liczba
        ogniw nie moze przekroczyc liczby klastrow partycji.
        """
        wynik: list[int] = []
        klaster = pierwszy
        widziane: set[int] = set()
        # Dwa zabezpieczenia, bo uszkodzony lancuch nie moze zapetlic
        # programu: zbior odwiedzonych i twarda granica liczba klastrow.
        while (2 <= klaster < self.bpb.clusters + 2
               and klaster not in widziane
               and len(wynik) <= self.bpb.clusters):
            widziane.add(klaster)
            wynik.append(klaster)
            nastepny = self.next_cluster(klaster)
            if self._koniec(nastepny):
                break
            klaster = nastepny
        return wynik

    def cluster_data(self, klaster: int) -> bytes:
        pierwszy = self.bpb.first_data \
            + (klaster - 2) * self.bpb.sectors_per_cluster
        return self.sektory(pierwszy, self.bpb.sectors_per_cluster)

    # -- katalogi ----------------------------------------------------------

    def _wpisy(self, surowe: bytes) -> list[DirEntry]:
        wynik: list[DirEntry] = []
        for numer in range(len(surowe) // ROZMIAR_WPISU):
            wpis = surowe[numer * ROZMIAR_WPISU:(numer + 1) * ROZMIAR_WPISU]
            if wpis[0] == KONIEC_KATALOGU:
                break
            if wpis[0] == SKASOWANY:
                continue
            atrybuty = wpis[0x0B]
            if atrybuty & ATTR_LONG_NAME == ATTR_LONG_NAME:
                continue                     # czesc dlugiej nazwy, nie plik
            if atrybuty & ATTR_VOLUME_ID:
                continue                     # etykieta wolumenu
            nazwa = wpis[0:8].decode("latin1").rstrip()
            rozszerzenie = wpis[8:11].decode("latin1").rstrip()
            if rozszerzenie:
                nazwa = f"{nazwa}.{rozszerzenie}"
            wynik.append(DirEntry(
                name=nazwa,
                attributes=atrybuty,
                first_cluster=int.from_bytes(wpis[0x1A:0x1C], "little"),
                size=int.from_bytes(wpis[0x1C:0x20], "little"),
                modified=_data(wpis),
                slot=numer,
            ))
        return wynik

    def root(self) -> list[DirEntry]:
        return self._wpisy(self.sektory(self.bpb.first_root,
                                        self.bpb.root_sectors))

    def directory(self, klaster: int) -> list[DirEntry]:
        surowe = b"".join(self.cluster_data(k) for k in self.chain(klaster))
        return self._wpisy(surowe)

    def find(self, path: str) -> DirEntry | None:
        """Wpis spod sciezki. None, gdy nie ma takiego pliku."""
        czesci = [c for c in path.replace("\\", "/").split("/") if c]
        wpisy = self.root()
        znaleziony: DirEntry | None = None
        for czesc in czesci:
            szukana = czesc.upper()
            znaleziony = next((w for w in wpisy if w.name.upper() == szukana),
                              None)
            if znaleziony is None:
                return None
            if znaleziony.is_dir:
                wpisy = self.directory(znaleziony.first_cluster)
        return znaleziony

    def listdir(self, path: str = "/") -> list[DirEntry]:
        czesci = [c for c in path.replace("\\", "/").split("/") if c]
        if not czesci:
            return [w for w in self.root() if w.name not in (".", "..")]
        wpis = self.find(path)
        if wpis is None or not wpis.is_dir:
            raise Fat16Error(f"nie ma takiego katalogu: {path}")
        return [w for w in self.directory(wpis.first_cluster)
                if w.name not in (".", "..")]

    def read_file(self, path: str) -> bytes:
        wpis = self.find(path)
        if wpis is None:
            raise Fat16Error(f"nie ma takiego pliku: {path}")
        if wpis.is_dir:
            raise Fat16Error(f"to katalog, nie plik: {path}")
        dane = b"".join(self.cluster_data(k)
                        for k in self.chain(wpis.first_cluster))
        return dane[:wpis.size]

    # -- miejsce -----------------------------------------------------------

    @property
    def total_bytes(self) -> int:
        return self.bpb.clusters * self.bpb.cluster_bytes

    @property
    def free_bytes(self) -> int:
        wolne = sum(1 for klaster in range(2, self.bpb.clusters + 2)
                    if self.next_cluster(klaster) == 0)
        return wolne * self.bpb.cluster_bytes


def _data(wpis: bytes) -> datetime.datetime | None:
    """Data zmiany z wpisu katalogu. DOS liczy lata od 1980."""
    czas = int.from_bytes(wpis[0x16:0x18], "little")
    data = int.from_bytes(wpis[0x18:0x1A], "little")
    if not data:
        return None
    try:
        return datetime.datetime(
            1980 + (data >> 9), (data >> 5) & 0x0F, data & 0x1F,
            czas >> 11, (czas >> 5) & 0x3F, (czas & 0x1F) * 2)
    except ValueError:
        return None          # uszkodzony wpis nie moze wywracac listy


class HardDiskImage:
    """
    Obraz dysku twardego otwarty w oknie programu.

    Wyglada dla reszty programu jak obraz dyskietki, tylko z dwiema
    roznicami: jest tylko do odczytu i ma partycje, wiec trzeba wskazac,
    ktora z nich pokazujemy.
    """

    def __init__(self, path: str | os.PathLike, read_only: bool = True,
                 partition: int | None = None):
        self.path = os.path.abspath(os.fspath(path))
        try:
            self._dysk = partitions.open_disk(self.path)
        except partitions.DiskError as exc:
            raise Fat16Error(str(exc)) from exc
        self.partitions = partitions.read_partitions(self._dysk)
        self.partition_index = 0
        try:
            self._otworz(partition)
        except Exception:
            self._dysk.close()
            raise

    def _otworz(self, wybrana: int | None) -> None:
        if not self.partitions:
            # Obraz bez tablicy partycji bywa jednym systemem plikow na
            # calym nosniku - probujemy czytac go wprost.
            self.volume = FatVolume(self._dysk, 0, self._dysk.sector_count)
            self.partition = None
            return
        czytelne = [p for p in self.partitions if p.readable]
        if not czytelne:
            raise Fat16Error("na dysku nie ma partycji FAT12 ani FAT16")
        if wybrana is None:
            wybor = czytelne[0]
        else:
            pasujace = [p for p in self.partitions if p.index == wybrana]
            if not pasujace:
                raise Fat16Error(f"nie ma partycji numer {wybrana}")
            wybor = pasujace[0]
        self.partition = wybor
        self.partition_index = wybor.index
        self.volume = FatVolume(self._dysk, wybor.start, wybor.sectors)

    # -- to, czego oczekuje okno -------------------------------------------

    @property
    def read_only(self) -> bool:
        return True

    @property
    def format_name(self) -> str:
        rodzaj = f"FAT{self.volume.bpb.bits}"
        if self.partition is None:
            return f"{rodzaj}  ({self._dysk.kind_name})"
        return (f"{rodzaj}  partycja {self.partition.index} "
                f"({self._dysk.kind_name})")

    @property
    def total_bytes(self) -> int:
        return self.volume.total_bytes

    @property
    def free_bytes(self) -> int:
        return self.volume.free_bytes

    def get_label(self) -> str:
        return self.volume.bpb.label

    def listdir(self, path: str = "/") -> list[DirEntry]:
        return self.volume.listdir(path)

    def exists(self, path: str) -> bool:
        return self.volume.find(path) is not None

    def stat(self, path: str) -> DirEntry:
        wpis = self.volume.find(path)
        if wpis is None:
            raise Fat16Error(f"nie ma takiego pliku: {path}")
        return wpis

    def read_file(self, path: str) -> bytes:
        return self.volume.read_file(path)

    def export_file(self, path: str, host_path: str | os.PathLike) -> None:
        with open(host_path, "wb") as fh:
            fh.write(self.read_file(path))

    def close(self) -> None:
        self._dysk.close()

    def __enter__(self) -> "HardDiskImage":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # -- pomocnicze na sciezkach, tak samo jak w FAT12 ---------------------

    @staticmethod
    def join(*parts: str) -> str:
        sklejone = "/".join(p.strip("/") for p in parts if p not in ("", "/"))
        return "/" + sklejone

    @staticmethod
    def parent(path: str) -> str:
        czesci = [c for c in path.split("/") if c]
        return "/" + "/".join(czesci[:-1])

    @staticmethod
    def short_name(name: str) -> str:
        return name.upper()[:12]

    # -- zapis: nie tutaj ---------------------------------------------------

    def _tylko_odczyt(self, *_, **__):
        raise Fat16Error(
            "obrazy dyskow twardych sa na razie tylko do odczytu")

    write_file = import_file = import_tree = _tylko_odczyt
    mkdir = remove = rename = set_label = _tylko_odczyt

    def __repr__(self) -> str:
        return f"<HardDiskImage {os.path.basename(self.path)} {self.format_name}>"


def looks_like_disk(header: bytes, size: int) -> bool:
    """
    Czy plik wyglada na obraz dysku twardego.

    Obraz VHD poznaje sie po sygnaturze - w odmianie rozszerzalnej na
    poczatku pliku lezy kopia stopki. Surowy obraz rozpoznajemy po tablicy
    partycji: sygnatura na koncu sektora i przynajmniej jeden wpis o znanym
    typie, miesczacy sie w pliku.
    """
    if header[:8] == b"conectix":
        return True
    if len(header) < 512 or header[510:512] != partitions.SYGNATURA:
        return False
    sektorow = size // SEKTOR
    for numer in range(4):
        wpis = header[446 + numer * 16:462 + numer * 16]
        typ = wpis[4]
        start = int.from_bytes(wpis[8:12], "little")
        dlugosc = int.from_bytes(wpis[12:16], "little")
        if not typ or not dlugosc:
            continue
        if typ in partitions.TYPY and 0 < start < sektorow \
                and start + dlugosc <= sektorow + 1:
            return True
    return False
