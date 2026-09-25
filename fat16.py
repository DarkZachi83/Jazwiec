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
    "open_read_only",
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

    @staticmethod
    def _to_samo(nazwa: str, wpisana: str) -> bool:
        """
        Czy to ta sama nazwa - takze po skroceniu do postaci 8.3.

        Plik zapisany jako "DO_USUNIECIA.TXT" lezy na dysku pod nazwa
        "DO_USUNI.TXT". Bez tego porownania program nie odnajdywalby pliku,
        ktory przed chwila sam zapisal.
        """
        if nazwa.upper() == wpisana.upper():
            return True
        rdzen, rozszerzenie = nazwa_83(nazwa)
        skrocona = rdzen.decode("latin1").rstrip()
        koncowka = rozszerzenie.decode("latin1").rstrip()
        if koncowka:
            skrocona = f"{skrocona}.{koncowka}"
        return skrocona.upper() == wpisana.upper()

    def find(self, path: str) -> DirEntry | None:
        """Wpis spod sciezki. None, gdy nie ma takiego pliku."""
        czesci = [c for c in path.replace("\\", "/").split("/") if c]
        wpisy = self.root()
        znaleziony: DirEntry | None = None
        for czesc in czesci:
            znaleziony = next(
                (w for w in wpisy if self._to_samo(czesc, w.name)), None)
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

    # -- zapis -------------------------------------------------------------

    def _pisz_sektor(self, numer: int, dane: bytes) -> None:
        self._dysk.write_sector(self._start + numer, dane)

    def _pisz_wpis_fat(self, klaster: int, wartosc: int) -> None:
        """
        Zmienia jeden wpis w tablicy FAT - w pamieci i w obu kopiach na
        dysku. Kopie musza byc zgodne, inaczej DOS zglasza blad dysku.
        """
        fat = bytearray(self.fat)
        if self.bpb.bits == 16:
            miejsce = klaster * 2
            fat[miejsce:miejsce + 2] = (wartosc & 0xFFFF).to_bytes(2, "little")
        else:
            miejsce = klaster + klaster // 2
            para = int.from_bytes(fat[miejsce:miejsce + 2], "little")
            if klaster & 1:
                para = (para & 0x000F) | ((wartosc & 0xFFF) << 4)
            else:
                para = (para & 0xF000) | (wartosc & 0xFFF)
            fat[miejsce:miejsce + 2] = para.to_bytes(2, "little")
        self._fat = bytes(fat)
        # Zapisujemy tylko sektory, ktore sie zmienily - wpis moze lezec na
        # granicy dwoch.
        pierwszy = miejsce // self.bpb.bytes_per_sector
        ostatni = (miejsce + 1) // self.bpb.bytes_per_sector
        for numer in range(pierwszy, ostatni + 1):
            od = numer * self.bpb.bytes_per_sector
            kawalek = self._fat[od:od + self.bpb.bytes_per_sector]
            for kopia in range(self.bpb.fats):
                self._pisz_sektor(
                    self.bpb.reserved + kopia * self.bpb.sectors_per_fat
                    + numer, kawalek)

    def wolne_klastry(self, ile: int) -> list[int]:
        """Numery wolnych klastrow. Blad, gdy na partycji brak miejsca."""
        wynik: list[int] = []
        for klaster in range(2, self.bpb.clusters + 2):
            if self.next_cluster(klaster) == 0:
                wynik.append(klaster)
                if len(wynik) == ile:
                    return wynik
        raise Fat16Error("brak miejsca na partycji")

    def zapisz_dane(self, dane: bytes) -> int:
        """
        Zapisuje tresc w nowych klastrach i zwraca pierwszy z lancucha.

        Pusty plik nie zajmuje zadnego klastra - tak samo robi DOS.
        """
        rozmiar = self.bpb.cluster_bytes
        if not dane:
            return 0
        potrzeba = (len(dane) + rozmiar - 1) // rozmiar
        klastry = self.wolne_klastry(potrzeba)
        for numer, klaster in enumerate(klastry):
            kawalek = dane[numer * rozmiar:(numer + 1) * rozmiar]
            kawalek = kawalek.ljust(rozmiar, b"\x00")
            pierwszy = (self.bpb.first_data
                        + (klaster - 2) * self.bpb.sectors_per_cluster)
            for i in range(self.bpb.sectors_per_cluster):
                od = i * self.bpb.bytes_per_sector
                self._pisz_sektor(pierwszy + i,
                                  kawalek[od:od + self.bpb.bytes_per_sector])
        # Lancuch wiazemy dopiero po zapisaniu danych: przerwanie w polowie
        # zostawia wtedy niewykorzystane klastry, a nie wpis wskazujacy na
        # przypadkowa tresc.
        koniec = 0xFFFF if self.bpb.bits == 16 else 0xFFF
        for numer, klaster in enumerate(klastry):
            self._pisz_wpis_fat(klaster, koniec if numer == len(klastry) - 1
                                else klastry[numer + 1])
        return klastry[0]

    def zwolnij_lancuch(self, pierwszy: int) -> None:
        for klaster in self.chain(pierwszy):
            self._pisz_wpis_fat(klaster, 0)

    # -- katalogi: zapis ---------------------------------------------------

    def _sektory_katalogu(self, klaster: int | None) -> list[int]:
        """Numery sektorow katalogu - glownego albo ze wskazanego klastra."""
        if klaster is None:
            return list(range(self.bpb.first_root,
                              self.bpb.first_root + self.bpb.root_sectors))
        wynik = []
        for k in self.chain(klaster):
            pierwszy = (self.bpb.first_data
                        + (k - 2) * self.bpb.sectors_per_cluster)
            wynik += list(range(pierwszy,
                                pierwszy + self.bpb.sectors_per_cluster))
        return wynik

    def _zapisz_wpis(self, klaster: int | None, pozycja: int,
                     dane: bytes) -> None:
        sektory = self._sektory_katalogu(klaster)
        na_sektor = self.bpb.bytes_per_sector // ROZMIAR_WPISU
        numer, w_sektorze = divmod(pozycja, na_sektor)
        if numer >= len(sektory):
            raise Fat16Error("katalog nie ma juz miejsca na wpisy")
        tresc = bytearray(self.sektor(sektory[numer]))
        od = w_sektorze * ROZMIAR_WPISU
        tresc[od:od + ROZMIAR_WPISU] = dane
        self._pisz_sektor(sektory[numer], bytes(tresc))

    def _wolna_pozycja(self, klaster: int | None) -> int:
        """
        Pierwsza wolna pozycja w katalogu.

        Katalog glowny ma staly rozmiar i konczy sie twardym limitem;
        podkatalog mozna powiekszyc o kolejny klaster.
        """
        sektory = self._sektory_katalogu(klaster)
        na_sektor = self.bpb.bytes_per_sector // ROZMIAR_WPISU
        for numer, sektor in enumerate(sektory):
            tresc = self.sektor(sektor)
            for i in range(na_sektor):
                pierwszy = tresc[i * ROZMIAR_WPISU]
                if pierwszy in (KONIEC_KATALOGU, SKASOWANY):
                    return numer * na_sektor + i
        if klaster is None:
            raise Fat16Error(
                f"katalog glowny jest pelny ({self.bpb.root_entries} pozycji)")
        return self._powieksz_katalog(klaster) * na_sektor

    def _powieksz_katalog(self, klaster: int) -> int:
        """Dokłada katalogowi klaster i zwraca numer pierwszego sektora."""
        lancuch = self.chain(klaster)
        nowy = self.wolne_klastry(1)[0]
        pusty = bytes(self.bpb.cluster_bytes)
        pierwszy = (self.bpb.first_data
                    + (nowy - 2) * self.bpb.sectors_per_cluster)
        for i in range(self.bpb.sectors_per_cluster):
            od = i * self.bpb.bytes_per_sector
            self._pisz_sektor(pierwszy + i,
                              pusty[od:od + self.bpb.bytes_per_sector])
        koniec = 0xFFFF if self.bpb.bits == 16 else 0xFFF
        self._pisz_wpis_fat(nowy, koniec)
        self._pisz_wpis_fat(lancuch[-1], nowy)
        return len(lancuch) * self.bpb.sectors_per_cluster

    # -- operacje na plikach ------------------------------------------------

    def _katalog_sciezki(self, path: str) -> tuple[int | None, str]:
        """Klaster katalogu, w ktorym lezy sciezka, i sama nazwa."""
        czesci = [c for c in path.replace("\\", "/").split("/") if c]
        if not czesci:
            raise Fat16Error("pusta sciezka")
        nazwa = czesci[-1]
        if len(czesci) == 1:
            return None, nazwa
        rodzic = self.find("/".join(czesci[:-1]))
        if rodzic is None or not rodzic.is_dir:
            raise Fat16Error("nie ma takiego katalogu: "
                             + "/".join(czesci[:-1]))
        return rodzic.first_cluster, nazwa

    def _pozycja_wpisu(self, klaster: int | None, nazwa: str) -> int | None:
        """Numer pozycji wpisu o tej nazwie albo None."""
        sektory = self._sektory_katalogu(klaster)
        na_sektor = self.bpb.bytes_per_sector // ROZMIAR_WPISU
        for numer, sektor in enumerate(sektory):
            tresc = self.sektor(sektor)
            for i in range(na_sektor):
                wpis = tresc[i * ROZMIAR_WPISU:(i + 1) * ROZMIAR_WPISU]
                if wpis[0] == KONIEC_KATALOGU:
                    return None
                if wpis[0] == SKASOWANY:
                    continue
                if wpis[0x0B] & ATTR_LONG_NAME == ATTR_LONG_NAME:
                    continue
                rdzen = wpis[0:8].decode("latin1").rstrip()
                rozsz = wpis[8:11].decode("latin1").rstrip()
                pelna = f"{rdzen}.{rozsz}" if rozsz else rdzen
                if self._to_samo(nazwa, pelna):
                    return numer * na_sektor + i
        return None

    def write_file(self, path: str, dane: bytes) -> None:
        """Zapisuje plik, nadpisujac istniejacy o tej samej nazwie."""
        klaster_katalogu, nazwa = self._katalog_sciezki(path)
        stary = self.find(path)
        if stary is not None and stary.is_dir:
            raise Fat16Error(f"to katalog, nie plik: {path}")
        pierwszy = self.zapisz_dane(dane)
        wpis = _buduj_wpis(nazwa, 0x20, pierwszy, len(dane))
        pozycja = self._pozycja_wpisu(klaster_katalogu, nazwa)
        if pozycja is None:
            pozycja = self._wolna_pozycja(klaster_katalogu)
        self._zapisz_wpis(klaster_katalogu, pozycja, wpis)
        if stary is not None and stary.first_cluster >= 2:
            self.zwolnij_lancuch(stary.first_cluster)

    def mkdir(self, path: str) -> None:
        klaster_katalogu, nazwa = self._katalog_sciezki(path)
        if self.find(path) is not None:
            raise Fat16Error(f"juz istnieje: {path}")
        nowy = self.wolne_klastry(1)[0]
        koniec = 0xFFFF if self.bpb.bits == 16 else 0xFFF
        # Katalog zaczyna sie od wpisow "." i ".." - bez nich DOS nie
        # potrafi z niego wyjsc, a fsck zglasza blad.
        tresc = bytearray(self.bpb.cluster_bytes)
        kropka = bytearray(_buduj_wpis("X", 0x10, nowy, 0))
        kropka[0:11] = b".          "
        dwie = bytearray(_buduj_wpis("X", 0x10,
                                     klaster_katalogu or 0, 0))
        dwie[0:11] = b"..         "
        tresc[0:ROZMIAR_WPISU] = kropka
        tresc[ROZMIAR_WPISU:2 * ROZMIAR_WPISU] = dwie
        pierwszy = (self.bpb.first_data
                    + (nowy - 2) * self.bpb.sectors_per_cluster)
        for i in range(self.bpb.sectors_per_cluster):
            od = i * self.bpb.bytes_per_sector
            self._pisz_sektor(pierwszy + i,
                              bytes(tresc[od:od + self.bpb.bytes_per_sector]))
        self._pisz_wpis_fat(nowy, koniec)
        pozycja = self._wolna_pozycja(klaster_katalogu)
        self._zapisz_wpis(klaster_katalogu, pozycja,
                          _buduj_wpis(nazwa, 0x10, nowy, 0))

    def remove(self, path: str, recursive: bool = False) -> None:
        klaster_katalogu, nazwa = self._katalog_sciezki(path)
        wpis = self.find(path)
        if wpis is None:
            raise Fat16Error(f"nie ma takiego pliku: {path}")
        if wpis.is_dir:
            zawartosc = [w for w in self.directory(wpis.first_cluster)
                         if w.name not in (".", "..")]
            if zawartosc and not recursive:
                raise Fat16Error(f"katalog nie jest pusty: {path}")
            for w in zawartosc:
                self.remove(f"{path.rstrip('/')}/{w.name}", recursive=True)
        pozycja = self._pozycja_wpisu(klaster_katalogu, nazwa)
        if pozycja is None:
            raise Fat16Error(f"nie ma takiego pliku: {path}")
        # Najpierw wpis, potem klastry: przerwanie zostawia wtedy niezajete
        # miejsce, a nie plik wskazujacy na zwolniona tresc.
        sektory = self._sektory_katalogu(klaster_katalogu)
        na_sektor = self.bpb.bytes_per_sector // ROZMIAR_WPISU
        numer, w_sektorze = divmod(pozycja, na_sektor)
        tresc = bytearray(self.sektor(sektory[numer]))
        tresc[w_sektorze * ROZMIAR_WPISU] = SKASOWANY
        self._pisz_sektor(sektory[numer], bytes(tresc))
        if wpis.first_cluster >= 2:
            self.zwolnij_lancuch(wpis.first_cluster)

    def rename(self, path: str, nowa_nazwa: str) -> None:
        klaster_katalogu, nazwa = self._katalog_sciezki(path)
        wpis = self.find(path)
        if wpis is None:
            raise Fat16Error(f"nie ma takiego pliku: {path}")
        pozycja = self._pozycja_wpisu(klaster_katalogu, nazwa)
        sektory = self._sektory_katalogu(klaster_katalogu)
        na_sektor = self.bpb.bytes_per_sector // ROZMIAR_WPISU
        numer, w_sektorze = divmod(pozycja, na_sektor)
        tresc = bytearray(self.sektor(sektory[numer]))
        od = w_sektorze * ROZMIAR_WPISU
        rdzen, rozszerzenie = nazwa_83(nowa_nazwa)
        tresc[od:od + 8] = rdzen
        tresc[od + 8:od + 11] = rozszerzenie
        self._pisz_sektor(sektory[numer], bytes(tresc))

    def set_label(self, etykieta: str) -> None:
        """
        Etykieta wolumenu: wpis w katalogu glownym i pole w bloku BPB.

        DOS czyta ja z katalogu, a narzedzia rozne - wiec zmieniamy obie,
        zeby nie pokazywaly czegos innego.
        """
        tekst = etykieta.upper()[:11].ljust(11)
        sektory = self._sektory_katalogu(None)
        na_sektor = self.bpb.bytes_per_sector // ROZMIAR_WPISU
        pozycja = None
        for numer, sektor in enumerate(sektory):
            tresc = self.sektor(sektor)
            for i in range(na_sektor):
                wpis = tresc[i * ROZMIAR_WPISU:(i + 1) * ROZMIAR_WPISU]
                if wpis[0] == KONIEC_KATALOGU:
                    break
                if wpis[0] != SKASOWANY and wpis[0x0B] == ATTR_VOLUME_ID:
                    pozycja = numer * na_sektor + i
                    break
            if pozycja is not None:
                break
        nowy = bytearray(_buduj_wpis("X", ATTR_VOLUME_ID, 0, 0))
        nowy[0:11] = tekst.encode("latin1")
        if pozycja is None:
            pozycja = self._wolna_pozycja(None)
        self._zapisz_wpis(None, pozycja, bytes(nowy))
        rozruchowy = bytearray(self.sektor(0))
        if rozruchowy[0x26] == 0x29:
            rozruchowy[0x2B:0x36] = tekst.encode("latin1")
            self._pisz_sektor(0, bytes(rozruchowy))
        self.bpb = parse_bpb(bytes(rozruchowy))

    # -- miejsce -----------------------------------------------------------

    @property
    def total_bytes(self) -> int:
        return self.bpb.clusters * self.bpb.cluster_bytes

    @property
    def free_bytes(self) -> int:
        wolne = sum(1 for klaster in range(2, self.bpb.clusters + 2)
                    if self.next_cluster(klaster) == 0)
        return wolne * self.bpb.cluster_bytes


def _pola_daty(kiedy: datetime.datetime | None = None) -> bytes:
    """Cztery bajty czasu i daty we wpisie katalogu. DOS liczy od 1980."""
    kiedy = kiedy or datetime.datetime.now()
    rok = max(1980, min(2107, kiedy.year))
    czas = (kiedy.hour << 11) | (kiedy.minute << 5) | (kiedy.second // 2)
    data = ((rok - 1980) << 9) | (kiedy.month << 5) | kiedy.day
    return czas.to_bytes(2, "little") + data.to_bytes(2, "little")


def nazwa_83(nazwa: str) -> tuple[bytes, bytes]:
    """
    Nazwa w postaci 8.3, jakiej wymaga wpis katalogu.

    Znaki niedozwolone zamieniamy na podkreslenie, zamiast odrzucac plik -
    tak samo robily narzedzia z epoki przy kopiowaniu z dluzszych nazw.
    """
    zakazane = set('"*+,/:;<=>?[\\]|')
    rdzen, _, rozszerzenie = nazwa.rpartition(".")
    if not rdzen:
        rdzen, rozszerzenie = nazwa, ""

    def oczysc(tekst: str, ile: int) -> str:
        # Kropki posrednie znikaja, bo w polu nazwy sa niedozwolone: DOS
        # zapisuje "a.b.c.txt" jako "ABC.TXT". Spacje tak samo.
        wynik = "".join("_" if z in zakazane or ord(z) < 0x20 or ord(z) > 0xFF
                        else z for z in tekst.upper())
        return wynik.replace(" ", "").replace(".", "")[:ile]

    return (oczysc(rdzen, 8).ljust(8).encode("latin1"),
            oczysc(rozszerzenie, 3).ljust(3).encode("latin1"))


def _buduj_wpis(nazwa: str, atrybuty: int, klaster: int, rozmiar: int,
                kiedy: datetime.datetime | None = None) -> bytes:
    rdzen, rozszerzenie = nazwa_83(nazwa)
    wpis = bytearray(ROZMIAR_WPISU)
    wpis[0:8] = rdzen
    wpis[8:11] = rozszerzenie
    wpis[0x0B] = atrybuty
    wpis[0x16:0x1A] = _pola_daty(kiedy)
    wpis[0x1A:0x1C] = (klaster & 0xFFFF).to_bytes(2, "little")
    wpis[0x1C:0x20] = (rozmiar & 0xFFFFFFFF).to_bytes(4, "little")
    return bytes(wpis)


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

    Wyglada dla reszty programu jak obraz dyskietki, z jedna roznica: ma
    partycje, wiec trzeba wskazac, ktora pokazujemy. Otwiera sie domyslnie
    tylko do odczytu - zapis wymaga wyraznego zadania.
    """

    def __init__(self, path: str | os.PathLike, read_only: bool = True,
                 partition: int | None = None):
        self.path = os.path.abspath(os.fspath(path))
        # Domyslnie tylko do odczytu: zapis do obrazu dysku wymaga
        # wyraznego zadania, bo pomylka kosztuje caly system plikow
        # maszyny, a nie jedna dyskietke.
        self._read_only = bool(read_only)
        try:
            self._dysk = partitions.open_disk(self.path,
                                              read_only=self._read_only)
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
        return self._read_only

    def _wymaga_zapisu(self) -> None:
        if self._read_only:
            raise Fat16Error(
                "obraz otwarty tylko do odczytu - otworz go do zapisu, "
                "zeby zmieniac zawartosc")

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
        """
        Nazwa w postaci, w jakiej naprawde wyladuje na dysku.

        Obcinanie do dwunastu znakow dawalo napisy ze spacjami w rodzaju
        "SID MEIERS C" - raport pokazywal wtedy nazwe, ktora nigdzie nie
        istniala, bo wpis katalogu i tak przechodzi przez postac 8.3.
        """
        rdzen, rozszerzenie = nazwa_83(name)
        podstawa = rdzen.decode("latin1").rstrip()
        koncowka = rozszerzenie.decode("latin1").rstrip()
        return f"{podstawa}.{koncowka}" if koncowka else podstawa

    # -- zapis --------------------------------------------------------------

    def write_file(self, path: str, dane: bytes) -> None:
        self._wymaga_zapisu()
        self.volume.write_file(path, dane)
        self._dysk.flush()

    def import_file(self, host_path: str | os.PathLike,
                    dest: str = "/") -> str:
        """Wnosi plik z komputera. Zwraca sciezke, pod ktora wyladowal."""
        self._wymaga_zapisu()
        with open(host_path, "rb") as fh:
            dane = fh.read()
        nazwa = os.path.basename(os.fspath(host_path))
        cel = self.join(dest, self.short_name(nazwa))
        self.volume.write_file(cel, dane)
        self._dysk.flush()
        return cel

    def import_tree(self, host_path: str | os.PathLike, dest_dir: str = "/",
                    include_root: bool = True, on_item=None) -> dict:
        """
        Kopiuje katalog z komputera na dysk wraz z cala zawartoscia.

        Ten sam zestaw parametrow i to samo podsumowanie co przy dyskietce -
        okno wola obie drogi tak samo i nie moze ich odrozniac.

        on_item dostaje sciezke kazdego kopiowanego pliku; zwrocenie False
        przerywa kopiowanie. Przy trzech tysiacach plikow to jedyny sposob,
        zeby okno pokazalo postep i dalo sie zatrzymac.
        """
        self._wymaga_zapisu()
        host_path = os.fspath(host_path)
        if not os.path.isdir(host_path):
            raise Fat16Error(f"to nie jest katalog: {host_path}")

        raport = {"files": 0, "dirs": 0, "bytes": 0,
                  "renamed": [], "failed": []}
        cel = dest_dir
        if include_root:
            nazwa = os.path.basename(os.path.normpath(host_path))
            krotka = self.short_name(nazwa)
            if not self.exists(self.join(dest_dir, krotka)):
                self.volume.mkdir(self.join(dest_dir, krotka))
            if krotka.upper() != nazwa.upper():
                raport["renamed"].append(f"{nazwa} -> {krotka}")
            raport["dirs"] += 1
            cel = self.join(dest_dir, krotka)

        self._kopiuj_drzewo(host_path, cel, raport, on_item)
        self._dysk.flush()
        return raport

    def _kopiuj_drzewo(self, zrodlo: str, cel: str, raport: dict,
                       on_item) -> bool:
        """Zwraca False, gdy kopiowanie zostalo przerwane."""
        try:
            pozycje = sorted(os.scandir(zrodlo), key=lambda w: w.name)
        except OSError as exc:
            raport["failed"].append(f"{zrodlo}: {exc}")
            return True
        for pozycja in pozycje:
            if pozycja.is_symlink():
                continue            # na dysku nie ma odpowiednika dowiazan
            if on_item is not None and on_item(pozycja.path) is False:
                return False
            krotka = self.short_name(pozycja.name)
            if krotka.upper() != pozycja.name.upper():
                raport["renamed"].append(f"{pozycja.name} -> {krotka}")
            docelowa = self.join(cel, krotka)
            try:
                if pozycja.is_dir():
                    if not self.exists(docelowa):
                        self.volume.mkdir(docelowa)
                    raport["dirs"] += 1
                    if not self._kopiuj_drzewo(pozycja.path, docelowa,
                                               raport, on_item):
                        return False
                else:
                    with open(pozycja.path, "rb") as fh:
                        dane = fh.read()
                    self.volume.write_file(docelowa, dane)
                    raport["files"] += 1
                    raport["bytes"] += len(dane)
            except (Fat16Error, OSError) as exc:
                raport["failed"].append(f"{pozycja.name}: {exc}")
        return True

    def mkdir(self, path: str) -> None:
        self._wymaga_zapisu()
        self.volume.mkdir(path)
        self._dysk.flush()

    def remove(self, path: str, recursive: bool = False) -> None:
        self._wymaga_zapisu()
        self.volume.remove(path, recursive=recursive)
        self._dysk.flush()

    def rename(self, path: str, nowa_nazwa: str) -> None:
        self._wymaga_zapisu()
        self.volume.rename(path, nowa_nazwa)
        self._dysk.flush()

    def set_label(self, etykieta: str) -> None:
        self._wymaga_zapisu()
        self.volume.set_label(etykieta)
        self._dysk.flush()

    def __repr__(self) -> str:
        return f"<HardDiskImage {os.path.basename(self.path)} {self.format_name}>"


def open_read_only(path: str | os.PathLike, read_only: bool = True,
                   partition: int | None = None) -> HardDiskImage:
    """
    Otwiera obraz dysku zawsze tylko do odczytu.

    Ta droga prowadzi przez warstwe silnikow, czyli z menu programu.
    Zapis do obrazu dysku wymaga wyraznej decyzji, wiec siega sie po niego
    wprost, a nie przy zwyklym otwarciu pliku - inaczej pomylka kosztuje
    caly system plikow maszyny.
    """
    return HardDiskImage(path, read_only=True, partition=partition)


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
