"""
gwbridge.py - most do Greaseweazle.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Co to jest
    Greaseweazle podlacza do komputera prawdziwy naped dyskietek - taki
    z epoki, na tasmie 34-zylowej - i czyta strumien magnetyczny prosto
    z glowicy. Obsluguje sie go poleceniem gw. Ten modul uruchamia gw, czyta
    jego wyjscie na biezaco i zamienia je na raport, ktory rozumie reszta
    programu.

Dlaczego polecenie, a nie biblioteka
    Pakiet greaseweazle bywa instalowany przez pipx, czyli w osobnym
    srodowisku, a jego wnetrze nie jest udokumentowanym interfejsem.
    Polecenie gw jest. Z tego samego powodu modul nie nazywa sie
    greaseweazle.py - przy instalacji pakietu w tym samym srodowisku
    przeslonilby prawdziwy.

Co wyjscie gw mowi wiecej niz stacja USB
    Stacja USB na nieczytelna sciezke odpowiada "blad sektora" i nic wiecej.
    Greaseweazle mowi, dlaczego. Rozrozniamy tu trzy rzeczy, ktore na
    stacji USB wygladalyby identycznie:

      * sciezka martwa    - glowica stoi dobrze, ale zadnego sektora nie da
                            sie odkodowac; uszkodzony nosnik,
      * sektory z obcego  - naglowki sektorow podaja inny cylinder niz ten,
        cylindra            na ktorym glowica powinna stac; glowica nie
                            dojechala, czyli problem napedu, a nie nosnika,
      * glowica milczy    - jedna strona nie czyta niczego na zadnej
                            sciezce, choc druga czyta; uszkodzona albo
                            brudna glowica.

    Rozroznienie ma znaczenie praktyczne. Naped z uszkodzona glowica nie
    tylko zle czyta - potrafi zetrzec sciezke, nad ktora stoi.

Czego ten modul jeszcze nie umie
    Pierwsza wersja. Formaty ograniczone do czterech popularnych, ktorych
    nazwy w gw sa pewne. Nieudana weryfikacja zapisu nie byla jeszcze
    widziana na prawdziwym urzadzeniu - rozpoznajemy ja po braku zdania
    potwierdzajacego i po kodzie wyjscia.

Wiersz polecen
    python3 gwbridge.py info
    python3 gwbridge.py read  obraz.img --format 1440 [--drive A]
    python3 gwbridge.py write obraz.img --format 1440 [--drive A]
    python3 gwbridge.py parse zapis.txt --format 1440
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable

import fat12

__all__ = [
    "GwError",
    "GwStatus",
    "TrackResult",
    "GwReport",
    "GwParser",
    "GW_FORMATS",
    "NOSNIKI",
    "RODZINY",
    "Nosnik",
    "nosniki_rodziny",
    "DRIVES",
    "find_gw",
    "set_tool_path",
    "tool_path",
    "probe",
    "read_to_image",
    "write_image",
    "format_disk",
    "parse_log",
    "set_language",
]

@dataclass(frozen=True)
class Nosnik:
    """
    Opis nosnika: geometria i nazwa formatu w gw.

    Nie zalezy od systemu plikow. Dyskietka Amigi ma 11 sektorow na sciezke
    i zaden system plikow, ktory znamy, jej nie czyta - a mimo to potrafimy
    ja zgrac i zapisac, wiec musimy znac jej geometrie. Formaty pecetowe
    bierzemy z tablicy FAT12, zeby nie powielac jednej prawdy w dwoch
    miejscach.
    """

    klucz: str
    rodzina: str                  # pc, amiga, atari
    etykieta: str
    gw_format: str
    cylindry: int
    glowice: int
    sektory: int                  # na sciezke
    bajty_sektora: int = 512
    rozszerzenie: str = ".img"    # gw wybiera przeksztalcenie po nim

    @property
    def rozmiar(self) -> int:
        return (self.cylindry * self.glowice * self.sektory
                * self.bajty_sektora)

    @property
    def sciezki(self) -> int:
        return self.cylindry * self.glowice

    @property
    def nasz_system_plikow(self) -> bool:
        """
        Czy program umie sam zbudowac pusty obraz tego nosnika.

        Tylko formaty pecetowe - na nich stoi nasz silnik FAT12. Bez tego
        nie ma jak sformatowac dyskietki, bo formatowanie polega u nas na
        zapisaniu pustego obrazu.
        """
        return self.rodzina == "pc"


def _nosniki_pc() -> list[Nosnik]:
    """Formaty pecetowe z tablicy FAT12, z nazwami gw sprawdzonymi w help."""
    nazwy = {
        "180": "ibm.180", "320": "ibm.320", "360": "ibm.360",
        "720": "ibm.720", "1200": "ibm.1200", "1250": "pc98.2hd",
        "1440": "ibm.1440", "2880": "ibm.2880",
    }
    wynik = []
    for klucz, nazwa in nazwy.items():
        fmt = fat12.FLOPPY_FORMATS[klucz]
        wynik.append(Nosnik(
            klucz=klucz, rodzina="pc", etykieta=fmt.label.strip(),
            gw_format=nazwa,
            cylindry=fmt.total_sectors // (fmt.sectors_per_track * fmt.heads),
            glowice=fmt.heads, sektory=fmt.sectors_per_track,
            bajty_sektora=fmt.bytes_per_sector, rozszerzenie=".img"))
    return wynik


# Amiga i Atari ST: geometria stala, wiec wchodza bez zadnych wyjatkow.
# Commodore 1541 zapisuje rozna liczbe sektorow na sciezke zaleznie od
# strefy - to wymaga osobnej obslugi i czeka na swoja kolej.
NOSNIKI: dict[str, Nosnik] = {n.klucz: n for n in _nosniki_pc() + [
    Nosnik("amiga880", "amiga", 'Amiga  880 KB (DD)', "amiga.amigados",
           80, 2, 11, 512, ".adf"),
    Nosnik("amiga1760", "amiga", 'Amiga  1,76 MB (HD)', "amiga.amigados_hd",
           80, 2, 22, 512, ".adf"),
    Nosnik("atarist360", "atari", 'Atari ST  360 KB (SS)', "atarist.360",
           80, 1, 9, 512, ".st"),
    Nosnik("atarist720", "atari", 'Atari ST  720 KB (DS)', "atarist.720",
           80, 2, 9, 512, ".st"),
    Nosnik("atarist800", "atari", 'Atari ST  800 KB (10 sektorow)',
           "atarist.800", 80, 2, 10, 512, ".st"),
    Nosnik("atarist880", "atari", 'Atari ST  880 KB (11 sektorow)',
           "atarist.880", 80, 2, 11, 512, ".st"),
]}

# Kolejnosc zakladek w oknie i ich nazwy.
RODZINY: dict[str, str] = {
    "pc": "PC / DOS",
    "amiga": "Amiga",
    "atari": "Atari ST",
}


# Nazwy formatow gw wedlug naszych kluczy - widok na tablice nosnikow.
GW_FORMATS: dict[str, str] = {k: n.gw_format for k, n in NOSNIKI.items()}


def nosniki_rodziny(rodzina: str) -> list[Nosnik]:
    return [n for n in NOSNIKI.values() if n.rodzina == rodzina]


def rodzina_nosnika(klucz: str) -> str:
    return NOSNIKI[klucz].rodzina if klucz in NOSNIKI else "pc"


# Wybor napedu. A i B to zlacze IBM/PC (tasma ze skrzyzowaniem i prosta),
# 0-2 to linie wyboru w trybie Shugart. Model F1 obsluguje tylko jeden naped.
DRIVES = ("A", "B", "0", "1", "2")
DEFAULT_DRIVE = "A"

# Prawidlowa predkosc napedu 3,5" i 5,25" DD/HD to 300 obr./min, poza
# napedami 5,25" HD, ktore kreca sie 360 obr./min.
RPM_TOLERANCE = 0.02


class GwError(Exception):
    """Blad komunikacji z Greaseweazle albo z samym poleceniem gw."""


# --------------------------------------------------------------------------
#  Napisy
# --------------------------------------------------------------------------

_T = {
    "pl": {
        "no_gw": "Nie znaleziono polecenia gw. Zainstaluj narzedzia "
                 "Greaseweazle (pipx install greaseweazle) albo wskaz plik "
                 "gw recznie.",
        "bad_tool": "Wskazany plik nie istnieje: {path}",
        "no_device": "Narzedzie gw jest, ale nie widzi urzadzenia "
                     "Greaseweazle. Sprawdz przewod USB.",
        "bad_format": "Format {key} nie jest jeszcze obslugiwany przez most "
                      "do Greaseweazle.",
        "no_format_for": "Formatowania {fmt} program nie wykona: umie budowac "
                         "puste obrazy tylko dla dyskietek pecetowych.\n"
                         "Dyskietke tego rodzaju sformatuj na maszynie "
                         "docelowej albo zapisz na nia gotowy obraz.",
        "bad_drive": "Nieznany naped {drive}. Dozwolone: {allowed}.",
        "title": "RetroZachar - Jazwiec - raport z Greaseweazle",
        "operation": "Operacja:",
        "op_read": "odczyt dyskietki",
        "op_write": "zapis obrazu na dyskietke",
        "op_format": "formatowanie dyskietki",
        "op_parse": "analiza zapisu wyjscia gw",
        "drive": "Naped:",
        "format": "Format:",
        "image": "Obraz:",
        "rpm": "Predkosc obrotowa:",
        "rpm_value": "{rpm:.1f} obr./min",
        "rpm_off": "{rpm:.1f} obr./min - POZA NORMA (oczekiwane {nom})",
        "sectors": "Sektorow odczytanych:",
        "sectors_value": "{found} z {total}",
        "bad": "Sektorow nieczytelnych:",
        "tracks_dead": "Sciezki martwe:",
        "tracks_misplaced": "Sciezki z sektorami z obcego cylindra:",
        "heads": "Odczytane sciezki wg glowic:",
        "head_line": "  strona {head}: {ok} z {total}",
        "bad_list": "Numery nieczytelnych sektorow (logiczne):",
        "diagnosis": "Rozpoznanie:",
        "d_ok": "Dyskietka odczytana w calosci.",
        "d_nothing": "Ani jedna sciezka nie dala zadnego sektora, a glowica "
                     "stala wlasciwie.\nNajczestsza przyczyna to inny format "
                     "niz wybrany: dyskietki Amigi, Atari ST\ni Commodore "
                     "zapisuja sciezki inaczej niz PC. Drugie wytlumaczenie "
                     "to\nnosnik niesformatowany albo skasowany. Sprawdz "
                     "wybrany format.",
        "d_media": "Czesci sektorow nie da sie odkodowac, choc glowica "
                   "stala wlasciwie.\nNie musi to znaczyc uszkodzonej "
                   "powierzchni: sciezka zapisana slabo albo\nrozmagnesowana "
                   "wyglada tak samo, a sformatowanie i ponowny zapis\n"
                   "przywracaja ja do uzytku. Dopiero gdy sektory zostaja "
                   "nieczytelne po\nswiezym zapisie, nosnik jest naprawde "
                   "uszkodzony. Najpierw zgraj z niego,\nco sie da - "
                   "formatowanie kasuje zawartosc.",
        "d_positioning": "PROBLEM NAPEDU: glowica nie dojezdza na wlasciwy "
                         "cylinder. Naglowki sektorow podaja inny cylinder "
                         "niz zadany. Lista nieczytelnych sektorow nie "
                         "odpowiada stanowi nosnika.",
        "d_head": "PROBLEM NAPEDU: strona {head} nie czyta niczego, choc "
                  "druga czyta. Glowica jest uszkodzona albo brudna. Nie "
                  "wkladaj do tego napedu cennych dyskietek - uszkodzona "
                  "glowica potrafi zetrzec sciezke.",
        "d_fatal": "Polecenie gw przerwalo prace: {msg}",
        "d_cancelled": "Operacja przerwana.",
        "d_write_ok": "Obraz zapisany i zweryfikowany.",
        "d_write_fail": "Zapis nie powiodl sie (kod wyjscia {code}).",
        "no_map": "gw nie wypisalo mapy sektorow - lista nieczytelnych "
                  "sektorow moze byc niepelna.",
        "none": "brak",
        "file_error": "Nie mozna otworzyc pliku {name}: {reason}",
        "size_mismatch": "Obraz {name} ma {size} B, a format {fmt} "
                         "wymaga {need} B.",
        "map_title": "Mapa sektorow (jak w gw):",
        "map_legend": "  .  sektor odczytany      X  sektor nieczytelny",
        "map_tracks_title": "Mapa sciezek:",
        "map_tracks_legend": "  .  sciezka zapisana      X  sciezka "
                             "niezapisana",
        "map_tracks_note": "gw zapisuje cale sciezki naraz i nie wypisuje "
                           "mapy sektorow.\nPonizsza mapa pokazuje wiec "
                           "sciezki, nie pojedyncze sektory.",
        "date": "Data:",
        "date_parse": "Data analizy:",
        "verify": "Weryfikacja:",
        "verify_ok": "zgodna (gw potwierdzil wszystkie sciezki)",
        "verify_none": "brak potwierdzenia od gw",
        "tracks_written": "Sciezek zapisanych:",
        "d_write_unverified": "Obraz zapisany, ale gw nie potwierdzil "
                              "weryfikacji. Sprawdz dyskietke odczytem.",
        "d_format_ok": "Dyskietka sformatowana i zweryfikowana.",
        "d_format_unverified": "Dyskietka sformatowana, ale gw nie "
                               "potwierdzil weryfikacji.",
        "d_format_fail": "Formatowanie nie powiodlo sie (kod wyjscia {code}).",
    },
    "en": {
        "no_gw": "The gw command was not found. Install the Greaseweazle "
                 "tools (pipx install greaseweazle), or point to the gw "
                 "file manually.",
        "bad_tool": "The chosen file does not exist: {path}",
        "no_device": "The gw tool is present but sees no Greaseweazle "
                     "device. Check the USB cable.",
        "bad_format": "Format {key} is not supported by the Greaseweazle "
                      "bridge yet.",
        "no_format_for": "The program cannot format {fmt}: it can only build "
                         "blank images for PC floppies.\nFormat such a disk "
                         "on the target machine, or write a ready image "
                         "to it.",
        "bad_drive": "Unknown drive {drive}. Allowed: {allowed}.",
        "title": "RetroZachar - Jazwiec - Greaseweazle report",
        "operation": "Operation:",
        "op_read": "reading a floppy",
        "op_write": "writing an image to a floppy",
        "op_format": "formatting a floppy",
        "op_parse": "analysing saved gw output",
        "drive": "Drive:",
        "format": "Format:",
        "image": "Image:",
        "rpm": "Rotation speed:",
        "rpm_value": "{rpm:.1f} rpm",
        "rpm_off": "{rpm:.1f} rpm - OUT OF RANGE (expected {nom})",
        "sectors": "Sectors read:",
        "sectors_value": "{found} of {total}",
        "bad": "Unreadable sectors:",
        "tracks_dead": "Dead tracks:",
        "tracks_misplaced": "Tracks with sectors from another cylinder:",
        "heads": "Tracks read per head:",
        "head_line": "  side {head}: {ok} of {total}",
        "bad_list": "Unreadable sector numbers (logical):",
        "diagnosis": "Diagnosis:",
        "d_ok": "The floppy was read in full.",
        "d_nothing": "Not a single track yielded any sector, and the head "
                     "was positioned correctly.\nThe usual cause is a format "
                     "other than the one selected: Amiga, Atari ST\nand "
                     "Commodore floppies lay out tracks differently from a "
                     "PC. The other\nexplanation is an unformatted or erased "
                     "medium. Check the chosen format.",
        "d_media": "Some sectors cannot be decoded, although the head was "
                   "positioned correctly.\nThis need not mean a damaged "
                   "surface: a weakly written or demagnetised\ntrack looks "
                   "the same, and formatting plus a fresh write brings it "
                   "back.\nOnly if sectors stay unreadable after a fresh "
                   "write is the medium truly\ndamaged. Read off whatever "
                   "you can first - formatting erases everything.",
        "d_positioning": "DRIVE PROBLEM: the head does not reach the right "
                         "cylinder. Sector headers report a different "
                         "cylinder than requested. The list of unreadable "
                         "sectors does not reflect the media.",
        "d_head": "DRIVE PROBLEM: side {head} reads nothing while the "
                  "other side does. The head is damaged or dirty. Do not "
                  "put valuable floppies in this drive - a damaged head "
                  "can wipe the track it rests on.",
        "d_fatal": "The gw command stopped: {msg}",
        "d_cancelled": "Operation cancelled.",
        "d_write_ok": "Image written and verified.",
        "d_write_fail": "Writing failed (exit code {code}).",
        "no_map": "gw printed no sector map - the list of unreadable "
                  "sectors may be incomplete.",
        "none": "none",
        "file_error": "Cannot open file {name}: {reason}",
        "size_mismatch": "Image {name} is {size} B, but format {fmt} "
                         "needs {need} B.",
        "map_title": "Sector map (as printed by gw):",
        "map_legend": "  .  sector read           X  sector unreadable",
        "map_tracks_title": "Track map:",
        "map_tracks_legend": "  .  track written          X  track not "
                             "written",
        "map_tracks_note": "gw writes whole tracks at a time and prints no "
                           "sector map.\nThe map below therefore shows "
                           "tracks, not individual sectors.",
        "date": "Date:",
        "date_parse": "Analysed on:",
        "verify": "Verification:",
        "verify_ok": "passed (gw confirmed all tracks)",
        "verify_none": "no confirmation from gw",
        "tracks_written": "Tracks written:",
        "d_write_unverified": "Image written, but gw did not confirm "
                              "verification. Check the floppy by reading it.",
        "d_format_ok": "Floppy formatted and verified.",
        "d_format_unverified": "Floppy formatted, but gw did not confirm "
                               "verification.",
        "d_format_fail": "Formatting failed (exit code {code}).",
    },
}

_lang = "pl"


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in _T else "pl"


def _t(klucz: str, **kwargs) -> str:
    tekst = _T[_lang].get(klucz) or _T["pl"].get(klucz, klucz)
    return tekst.format(**kwargs) if kwargs else tekst


# --------------------------------------------------------------------------
#  Wykrywanie
# --------------------------------------------------------------------------

@dataclass
class GwStatus:
    """Wynik gw info. Narzedzie i urzadzenie wykrywane sa osobno."""

    tool: str | None = None             # sciezka do gw, None gdy brak
    tool_version: str = ""
    device_found: bool = False
    port: str = ""
    model: str = ""
    firmware: str = ""
    raw: str = ""

    @property
    def ready(self) -> bool:
        return bool(self.tool) and self.device_found

    def problem(self) -> str | None:
        """Czytelny opis tego, czego brakuje, albo None."""
        if not self.tool:
            return _t("no_gw")
        if not self.device_found:
            return _t("no_device")
        return None


# Sciezka wskazana przez uzytkownika. Pod Windowsem to czesto jedyna droga:
# narzedzia Greaseweazle rozpakowuje sie do dowolnego katalogu, a jesli nie
# trafi on do zmiennej PATH, polecenie dziala tylko w tym jednym folderze.
# Program uruchomiony z Eksploratora ma inny katalog roboczy i nie widzi go
# wcale - a takze nie zobaczy zmian w PATH sprzed ponownego zalogowania.
_wskazane: str | None = None


def set_tool_path(sciezka: str | None) -> None:
    """Zapamietuje sciezke do gw wskazana recznie. None wraca do szukania."""
    global _wskazane
    _wskazane = str(sciezka) if sciezka else None


def tool_path() -> str | None:
    return _wskazane


def find_gw() -> str | None:
    """Sciezka do polecenia gw: najpierw wskazana recznie, potem z PATH."""
    if _wskazane and os.path.isfile(_wskazane):
        return _wskazane
    return shutil.which("gw")


def _uruchom(argumenty: list[str], **kwargs) -> subprocess.Popen:
    """
    Uruchamia gw z polaczonym wyjsciem.

    Pod Windowsem bez znacznika CREATE_NO_WINDOW kazde wywolanie z okna
    programu wyswietlaloby na moment czarne okno konsoli.
    """
    dodatki = {}
    if os.name == "nt":
        dodatki["creationflags"] = 0x08000000        # CREATE_NO_WINDOW
    return subprocess.Popen(
        argumenty, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
        **dodatki, **kwargs)


def parse_info(tekst: str, tool: str | None = None) -> GwStatus:
    """
    Rozbiera wyjscie gw info.

        Host Tools: 1.23
        Device:
          Port:     /dev/ttyACM0
          Model:    Greaseweazle V4.1
          Firmware: 1.6

    Gdy urzadzenia nie ma, pod "Device:" stoi samo "Not found".
    """
    stan = GwStatus(tool=tool, raw=tekst)
    for linia in tekst.splitlines():
        klucz, _, wartosc = linia.strip().partition(":")
        wartosc = wartosc.strip()
        if klucz == "Host Tools":
            stan.tool_version = wartosc
        elif klucz == "Port":
            stan.port = wartosc
            stan.device_found = True
        elif klucz == "Model":
            stan.model = wartosc
        elif klucz == "Firmware":
            stan.firmware = wartosc
    return stan


def probe(timeout: float = 15.0) -> GwStatus:
    """Sprawdza, czy jest narzedzie gw i czy widzi urzadzenie."""
    sciezka = find_gw()
    if not sciezka:
        return GwStatus()
    try:
        proces = _uruchom([sciezka, "info"])
        wyjscie, _ = proces.communicate(timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return GwStatus(tool=sciezka, raw=str(exc))
    return parse_info(wyjscie, tool=sciezka)


# --------------------------------------------------------------------------
#  Wynik pojedynczej sciezki
# --------------------------------------------------------------------------

@dataclass
class TrackResult:
    cyl: int
    head: int
    found: int = 0                      # z ostatniej proby
    total: int = 0
    attempts: int = 0
    gave_up: bool = False
    missing_reported: int = 0           # z linii "Giving up"
    unexpected: list[tuple[int, int, int, int]] = field(default_factory=list)
    flux: int = 0                       # z pierwszej proby
    ms: float = 0.0                     # z pierwszej proby
    written: bool = False               # zapis: sciezka zapisana

    @property
    def misplaced(self) -> bool:
        """Czy trafiono na sektory z innego cylindra - glowica nie dojechala."""
        return any(c != self.cyl for c, _, _, _ in self.unexpected)

    @property
    def state(self) -> str:
        """
        Stan do pokazania na mapie sciezek.

        ok         - odczytana za pierwszym razem albo zapisana,
        retried    - odczytana w calosci, ale dopiero po ponownych probach;
                     sciezka jeszcze dziala, lecz slabnie,
        bad        - czesci sektorow nie dalo sie odkodowac,
        misplaced  - sektory z obcego cylindra, czyli problem napedu,
        active     - proby jeszcze trwaja.
        """
        if self.written:
            return "ok"
        if self.misplaced:
            return "misplaced"
        if self.total and self.found == self.total:
            return "retried" if self.attempts > 1 else "ok"
        if self.gave_up:
            return "bad"
        return "active"

    @property
    def diagnosis(self) -> str:
        if self.misplaced:
            return "misplaced"
        if self.total and self.found == self.total:
            return "ok"
        if self.found == 0:
            return "dead"
        return "partial"


# --------------------------------------------------------------------------
#  Raport
# --------------------------------------------------------------------------

@dataclass
class GwReport:
    operation: str                      # read, write, parse
    format_key: str
    gw_format: str = ""
    drive: str = DEFAULT_DRIVE
    image_path: str = ""
    revs: float = 2.0
    tracks: dict[tuple[int, int], TrackResult] = field(default_factory=dict)
    total_tracks: int = 0
    map_rows: dict[tuple[int, int], str] = field(default_factory=dict)
    found_sectors: int | None = None
    total_sectors: int | None = None
    fatal: str | None = None
    returncode: int | None = None
    cancelled: bool = False
    # gw write weryfikuje zapis sam i potwierdza to jednym zdaniem na koncu:
    # "All tracks verified". Bez tego zdania nie wiemy, czy weryfikacja byla.
    verified: bool = False
    log: list[str] = field(default_factory=list)
    started: datetime.datetime = field(default_factory=datetime.datetime.now)
    finished: datetime.datetime | None = None

    # -- geometria ---------------------------------------------------------

    @property
    def fmt(self) -> Nosnik:
        return NOSNIKI[self.format_key]

    def lba(self, cyl: int, head: int, indeks: int) -> int:
        """Numer logiczny sektora; indeks liczony od zera, jak w mapie gw."""
        fmt = self.fmt
        return (cyl * fmt.glowice + head) * fmt.sektory + indeks

    # -- wnioski -----------------------------------------------------------

    @property
    def done_tracks(self) -> int:
        return len(self.tracks)

    @property
    def cylinders(self) -> int:
        return self.fmt.cylindry

    def snapshot(self) -> dict:
        """
        Migawka stanu sciezek do narysowania mapy.

        Wolana w watku, ktory prowadzi operacje, czyli tym samym, ktory
        zmienia raport - dzieki temu okno dostaje spojna kopie, zamiast
        czytac slownik, do ktorego w tej chwili ktos dopisuje.
        """
        return {
            klucz: (s.state, s.found, s.total, s.attempts,
                    tuple(sorted({c for c, _, _, _ in s.unexpected
                                  if c != s.cyl})))
            for klucz, s in self.tracks.items()
        }

    @property
    def has_map(self) -> bool:
        return bool(self.map_rows)

    @property
    def bad_sectors(self) -> list[int]:
        """
        Numery logiczne nieczytelnych sektorow.

        Z mapy na koncu wyjscia, bo tylko ona podaje dokladne pozycje. Gdy
        mapy nie ma - przerwany odczyt - bierzemy chociaz calkiem martwe
        sciezki, gdzie brakuje wszystkich sektorow.
        """
        if self.map_rows:
            zle = []
            for (glowica, indeks), wiersz in self.map_rows.items():
                for cyl, znak in enumerate(wiersz):
                    if znak != ".":
                        zle.append(self.lba(cyl, glowica, indeks))
            return sorted(zle)
        zle = []
        for sciezka in self.tracks.values():
            if sciezka.diagnosis == "dead" and sciezka.gave_up:
                zle.extend(self.lba(sciezka.cyl, sciezka.head, i)
                           for i in range(self.fmt.sektory))
        return sorted(zle)

    @property
    def rpm(self) -> float | None:
        """
        Predkosc obrotowa z czasow pierwszych prob odczytu.

        Proby ponowne czytaja wiecej obrotow, a z samej linii nie wiadomo
        ile - dlatego tylko pierwsze, dla ktorych liczba obrotow jest znana
        z naglowka.
        """
        czasy = [s.ms for s in self.tracks.values() if s.ms > 0]
        if not czasy or not self.revs:
            return None
        return 60000.0 * self.revs / statistics.median(czasy)

    @property
    def nominal_rpm(self) -> int:
        return 360 if self.format_key == "1200" else 300

    @property
    def rpm_ok(self) -> bool:
        if self.rpm is None:
            return True
        return abs(self.rpm - self.nominal_rpm) / self.nominal_rpm \
            <= RPM_TOLERANCE

    def head_stats(self) -> dict[int, tuple[int, int]]:
        """Dla kazdej strony: (sciezki odczytane, sciezki probowane)."""
        wynik: dict[int, list[int]] = {}
        for s in self.tracks.values():
            dobre, wszystkie = wynik.setdefault(s.head, [0, 0])
            wynik[s.head] = [dobre + (s.found > 0), wszystkie + 1]
        return {h: tuple(v) for h, v in sorted(wynik.items())}

    @property
    def silent_head(self) -> int | None:
        """
        Strona, ktora nie odczytala niczego, podczas gdy druga czyta.

        Wymagamy kilku probowanych sciezek, zeby pojedyncza martwa sciezka
        nie zostala uznana za martwa glowice.
        """
        statystyka = self.head_stats()
        if len(statystyka) < 2:
            return None
        milczace = [h for h, (ok, n) in statystyka.items() if ok == 0 and n >= 3]
        czytajace = [h for h, (ok, _) in statystyka.items() if ok > 0]
        return milczace[0] if milczace and czytajace else None

    @property
    def diagnosis(self) -> str:
        if self.fatal:
            return "fatal"
        if self.cancelled:
            return "cancelled"
        if self.operation in ("write", "format"):
            if self.returncode != 0:
                return self.operation + "_fail"
            return self.operation + (
                "_ok" if self.verified else "_unverified")
        if any(s.misplaced for s in self.tracks.values()):
            return "positioning"
        if self.silent_head is not None:
            return "head"
        # Zero sektorow na wszystkich sciezkach to nie uszkodzenie nosnika.
        # Tak wyglada dyskietka zapisana w innym formacie - na przyklad
        # amigowa czytana jako pecetowa - albo niesformatowana.
        if len(self.tracks) >= 3 and all(s.found == 0
                                         for s in self.tracks.values()):
            return "nothing"
        if self.bad_sectors:
            return "media"
        return "ok"

    # -- mapa sektorow -----------------------------------------------------

    def _naglowek_mapy(self, kolumny: int, opis: str) -> list[str]:
        podzialka = "".join(f"{c // 10:<10}" for c in range(0, kolumny, 10))
        return ["Cyl-> " + podzialka[:kolumny],
                opis + ("0123456789" * (kolumny // 10 + 1))[:kolumny]]

    def track_map_lines(self) -> list[str]:
        """
        Mapa sciezek - jeden znak na sciezke, po wierszu na strone.

        Przy zapisie gw nie wypisuje mapy sektorow, bo zapisuje cale
        sciezki naraz. Wiemy tylko, ktore sciezki zostaly zapisane, i tyle
        ta mapa pokazuje. Nazwana inaczej niz mapa sektorow, zeby nie
        sugerowala dokladnosci, ktorej nie ma.
        """
        if not self.tracks:
            return []
        kolumny = self.cylinders
        wiersze = self._naglowek_mapy(kolumny, "H. C: ")
        for glowica in range(self.fmt.glowice):
            znaki = "".join(
                "." if (c, glowica) in self.tracks else "X"
                for c in range(kolumny))
            wiersze.append(f"H{glowica}:   {znaki}")
        return wiersze

    def sector_map_lines(self) -> list[str]:
        """
        Mapa sektorow w ukladzie, w jakim wypisuje ja gw.

        Kolumna to cylinder, wiersz to strona i numer sektora; kropka to
        sektor odczytany, X nieczytelny. Uklad celowo identyczny z gw, zeby
        wygladal znajomo i dal sie porownac z wyjsciem samego polecenia.
        Pusta lista, gdy gw mapy nie wypisalo - na przyklad przy przerwaniu.
        """
        if not self.map_rows:
            return []
        kolumny = max(len(w) for w in self.map_rows.values())
        wiersze = self._naglowek_mapy(kolumny, "H. S: ")
        for (glowica, sektor), znaki in sorted(self.map_rows.items()):
            wiersze.append(f"{glowica}.{sektor:>2}: {znaki}")
        return wiersze

    # -- raport tekstowy ---------------------------------------------------

    def text(self) -> str:
        # Szerokosc kolumny z najdluzszej etykiety - tlumaczenia maja rozne
        # dlugosci, a sztywna wartosc skleja dluzsze etykiety z wartoscia.
        szer = 2 + max(len(_t(k)) for k in (
            "operation", "drive", "format", "image", "rpm", "sectors",
            "bad", "tracks_dead", "tracks_misplaced", "date_parse",
            "verify", "tracks_written"))
        wiersze = [_t("title"), "=" * 62, ""]

        def pole(etykieta, wartosc):
            wiersze.append(f"{etykieta:<{szer}}{wartosc}")

        # Zapis wyjscia gw nie zawiera czasu, wiec przy analizie znamy tylko
        # chwile analizy - i tak musi byc opisana, zeby nie udawala daty
        # odczytu dyskietki.
        pole(_t("date_parse" if self.operation == "parse" else "date"),
             f"{self.started:%Y-%m-%d %H:%M:%S}")
        pole(_t("operation"), _t("op_" + self.operation))
        if self.operation != "parse":
            pole(_t("drive"), self.drive)
        pole(_t("format"), f"{self.fmt.etykieta}  ({self.gw_format})")
        if self.image_path:
            pole(_t("image"), self.image_path)

        if self.rpm is not None:
            pole(_t("rpm"), _t("rpm_value" if self.rpm_ok else "rpm_off",
                               rpm=self.rpm, nom=self.nominal_rpm))

        if self.operation in ("write", "format"):
            pole(_t("tracks_written"),
                 f"{self.done_tracks} / {self.total_tracks}")
            pole(_t("verify"),
                 _t("verify_ok" if self.verified else "verify_none"))
            mapa = self.track_map_lines()
            if mapa:
                wiersze += ["", _t("map_tracks_note"), "",
                            _t("map_tracks_title"),
                            _t("map_tracks_legend"), ""]
                wiersze += mapa
        else:
            if self.found_sectors is not None:
                pole(_t("sectors"), _t("sectors_value",
                                       found=self.found_sectors,
                                       total=self.total_sectors))
            pole(_t("bad"), len(self.bad_sectors))
            martwe = [f"C{s.cyl} H{s.head}" for s in self.tracks.values()
                      if s.diagnosis == "dead"]
            obce = [f"C{s.cyl} H{s.head}" for s in self.tracks.values()
                    if s.misplaced]
            pole(_t("tracks_dead"), ", ".join(martwe) or _t("none"))
            if obce:
                pole(_t("tracks_misplaced"), ", ".join(obce))
            wiersze.append("")
            wiersze.append(_t("heads"))
            for glowica, (ok, n) in self.head_stats().items():
                wiersze.append(_t("head_line", head=glowica, ok=ok, total=n))
            if self.bad_sectors:
                wiersze += ["", _t("bad_list")]
                numery = self.bad_sectors
                for i in range(0, len(numery), 12):
                    wiersze.append("  " + " ".join(
                        f"{n:>4}" for n in numery[i:i + 12]))
            if not self.has_map and not self.cancelled and not self.fatal:
                wiersze += ["", _t("no_map")]
            mapa = self.sector_map_lines()
            if mapa:
                wiersze += ["", _t("map_title"), _t("map_legend"), ""]
                wiersze += mapa

        wiersze += ["", "-" * 62, _t("diagnosis")]
        rozpoznanie = self.diagnosis
        if rozpoznanie == "fatal":
            wiersze.append(_t("d_fatal", msg=self.fatal))
        elif rozpoznanie == "head":
            wiersze.append(_t("d_head", head=self.silent_head))
        elif rozpoznanie in ("write_fail", "format_fail"):
            wiersze.append(_t("d_" + rozpoznanie, code=self.returncode))
        else:
            wiersze.append(_t("d_" + rozpoznanie))
        return "\n".join(wiersze)


# --------------------------------------------------------------------------
#  Rozbior wyjscia gw
# --------------------------------------------------------------------------

# Liczba obrotow bywa ulamkowa: przy AmigaDOS gw czyta "revs=1.1", czyli
# jeden obrot z zapasem. Wzorzec na liczbe calkowita nie rozpoznawalby tej
# linii i predkosc obrotowa wychodzilaby prawie dwa razy za wysoka.
_NAGLOWEK = re.compile(
    r"^Reading c=(\d+)-(\d+):h=(\d+)-(\d+) revs=([\d.]+)")
_NAGLOWEK_ZAPISU = re.compile(r"^Writing c=(\d+)-(\d+):h=(\d+)-(\d+)")
_ZAPIS_SCIEZKI = re.compile(r"^T(\d+)\.(\d+): Writing Track")
_ZWERYFIKOWANO = "All tracks verified"
_SCIEZKA = re.compile(
    r"^T(\d+)\.(\d+): .*?\((\d+)/(\d+) sectors\) from Raw Flux "
    r"\((\d+) flux in ([\d.]+)ms\)(?: \(Retry #[\d.]+\))?")
_PORZUCONA = re.compile(r"^T(\d+)\.(\d+): Giving up: (\d+) sectors missing")
_OBCY = re.compile(
    r"^T(\d+)\.(\d+): Ignoring unexpected sector "
    r"C:(\d+) H:(\d+) R:(\d+) N:(\d+)")
_DOWOLNA_SCIEZKA = re.compile(r"^T(\d+)\.(\d+):")
_WIERSZ_MAPY = re.compile(r"^\s*(\d+)\.\s*(\d+):\s(\S+)\s*$")
_ZNALEZIONO = re.compile(r"^Found (\d+) sectors of (\d+)")
_KRYTYCZNY = "** FATAL ERROR:"


class GwParser:
    """
    Czyta wyjscie gw linia po linii.

    Ten sam kod sluzy do sledzenia pracy na biezaco i do analizy zapisanego
    wyjscia - dzieki temu testy na prawdziwych zapisach sprawdzaja dokladnie
    to, co dziala przy podlaczonym urzadzeniu.
    """

    def __init__(self, raport: GwReport):
        self.r = raport
        self._po_bledzie = False
        raport.total_tracks = raport.fmt.sciezki

    def feed(self, linia: str) -> bool:
        """
        Przyjmuje linie. Zwraca True, gdy zmienil sie stan jakiejs sciezki.

        Nie tylko przy nowej sciezce - takze przy kazdej ponownej probie,
        rezygnacji i sektorze z obcego cylindra. Inaczej mapa sciezek nie
        pokazalaby na zywo, ze naped meczy sie z jedna ze sciezek.
        """
        r = self.r
        linia = linia.rstrip("\r\n")
        r.log.append(linia)

        if self._po_bledzie and linia.strip():
            r.fatal = linia.strip()
            self._po_bledzie = False
            return False
        if linia.startswith(_KRYTYCZNY):
            reszta = linia[len(_KRYTYCZNY):].strip()
            if reszta:
                r.fatal = reszta
            else:
                self._po_bledzie = True
            return False

        if m := _NAGLOWEK.match(linia):
            c0, c1, h0, h1 = (int(x) for x in m.groups()[:4])
            r.revs = float(m[5])
            r.total_tracks = (c1 - c0 + 1) * (h1 - h0 + 1)
            return False

        if m := _NAGLOWEK_ZAPISU.match(linia):
            c0, c1, h0, h1 = map(int, m.groups())
            r.total_tracks = (c1 - c0 + 1) * (h1 - h0 + 1)
            return False

        if linia.strip() == _ZWERYFIKOWANO:
            r.verified = True
            return False

        if m := _ZAPIS_SCIEZKI.match(linia):
            self._sciezka(int(m[1]), int(m[2])).written = True
            return True

        if m := _OBCY.match(linia):
            sciezka = self._sciezka(int(m[1]), int(m[2]))
            wpis = tuple(int(x) for x in m.groups()[2:])
            if wpis not in sciezka.unexpected:
                sciezka.unexpected.append(wpis)
                return True
            return False

        if m := _PORZUCONA.match(linia):
            sciezka = self._sciezka(int(m[1]), int(m[2]))
            sciezka.gave_up = True
            sciezka.missing_reported = int(m[3])
            return True

        if m := _SCIEZKA.match(linia):
            sciezka = self._sciezka(int(m[1]), int(m[2]))
            sciezka.found, sciezka.total = int(m[3]), int(m[4])
            sciezka.attempts += 1
            if sciezka.attempts == 1:
                sciezka.flux, sciezka.ms = int(m[5]), float(m[6])
            return True

        if m := _WIERSZ_MAPY.match(linia):
            r.map_rows[(int(m[1]), int(m[2]))] = m[3]
            return False

        if m := _ZNALEZIONO.match(linia):
            r.found_sectors, r.total_sectors = int(m[1]), int(m[2])
            return False

        # Linie sciezek w nieznanym jeszcze formacie - na przyklad z zapisu -
        # licza sie przynajmniej do postepu.
        if m := _DOWOLNA_SCIEZKA.match(linia):
            klucz = (int(m[1]), int(m[2]))
            if klucz not in r.tracks:
                self._sciezka(*klucz)
                return True
        return False

    def _sciezka(self, cyl: int, head: int) -> TrackResult:
        klucz = (cyl, head)
        if klucz not in self.r.tracks:
            self.r.tracks[klucz] = TrackResult(cyl, head)
        return self.r.tracks[klucz]


def parse_log(tekst: str, format_key: str) -> GwReport:
    """Analizuje zapisane wyjscie gw read."""
    raport = GwReport(operation="parse", format_key=format_key,
                      gw_format=GW_FORMATS.get(format_key, ""))
    parser = GwParser(raport)
    for linia in tekst.splitlines():
        parser.feed(linia)
    raport.finished = datetime.datetime.now()
    return raport


# --------------------------------------------------------------------------
#  Odczyt i zapis
# --------------------------------------------------------------------------

def _sprawdz(format_key: str, drive: str) -> str:
    if format_key not in GW_FORMATS:
        raise GwError(_t("bad_format", key=format_key))
    if drive not in DRIVES:
        raise GwError(_t("bad_drive", drive=drive,
                         allowed=", ".join(DRIVES)))
    return GW_FORMATS[format_key]


def _wykonaj(operacja: str, obraz: str, format_key: str, drive: str,
             progress: Callable[[GwReport], bool] | None,
             opis: str | None = None) -> GwReport:
    gw_format = _sprawdz(format_key, drive)
    sciezka = find_gw()
    if not sciezka:
        raise GwError(_t("no_gw"))

    raport = GwReport(operation=opis or operacja, format_key=format_key,
                      gw_format=gw_format, drive=drive,
                      image_path="" if opis == "format"
                      else os.path.abspath(obraz))
    parser = GwParser(raport)
    try:
        proces = _uruchom([sciezka, operacja, "--drive", drive,
                           "--format", gw_format, obraz])
    except OSError as exc:
        raise GwError(str(exc)) from exc

    try:
        for linia in proces.stdout:
            if parser.feed(linia) and progress is not None:
                if progress(raport) is False:
                    raport.cancelled = True
                    break
    finally:
        if raport.cancelled and proces.poll() is None:
            proces.terminate()
            try:
                proces.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proces.kill()
        raport.returncode = proces.wait()
        proces.stdout.close()
        raport.finished = datetime.datetime.now()
    return raport


def read_to_image(obraz: str, format_key: str = "1440",
                  drive: str = DEFAULT_DRIVE,
                  progress: Callable[[GwReport], bool] | None = None
                  ) -> GwReport:
    """
    Czyta dyskietke przez gw read i zwraca raport.

    progress dostaje raport po kazdej nowej sciezce i moze zwrocic False,
    zeby przerwac. Obraz powstaly do tej chwili zostaje na dysku.
    """
    return _wykonaj("read", obraz, format_key, drive, progress)


def write_image(obraz: str, format_key: str = "1440",
                drive: str = DEFAULT_DRIVE,
                progress: Callable[[GwReport], bool] | None = None
                ) -> GwReport:
    """
    Zapisuje obraz na dyskietke przez gw write.

    Przy obrazach IMG gw sam sprawdza zapis odczytem. Nie wypisuje tego
    sciezka po sciezce - potwierdza calosc jednym zdaniem na koncu, "All
    tracks verified". Zapis uznajemy za udany dopiero z tym zdaniem.
    """
    nosnik = NOSNIKI.get(format_key)
    if nosnik is not None and os.path.getsize(obraz) != nosnik.rozmiar:
        raise GwError(_t("size_mismatch", name=os.path.basename(obraz),
                         size=os.path.getsize(obraz),
                         fmt=nosnik.etykieta, need=nosnik.rozmiar))
    return _wykonaj("write", obraz, format_key, drive, progress)


def format_disk(format_key: str = "1440", drive: str = DEFAULT_DRIVE,
                label: str = "",
                progress: Callable[[GwReport], bool] | None = None
                ) -> GwReport:
    """
    Formatuje dyskietke: buduje pusty obraz FAT12 i zapisuje go przez gw.

    Greaseweazle zapisuje cala sciezke naraz, razem z naglowkami sektorow,
    wiec zapis pustego obrazu jest formatowaniem niskopoziomowym - bez
    zadnego osobnego polecenia i bez nowego kodu obslugi urzadzenia.
    """
    import tempfile
    _sprawdz(format_key, drive)
    nosnik = NOSNIKI[format_key]
    if not nosnik.nasz_system_plikow:
        raise GwError(_t("no_format_for", fmt=nosnik.etykieta))
    fmt = fat12.FLOPPY_FORMATS[format_key]
    uchwyt, tymczasowy = tempfile.mkstemp(suffix=".img", prefix="jazwiec-")
    os.close(uchwyt)
    try:
        fat12.format_image(tymczasowy, fmt, label, overwrite=True)
        return _wykonaj("write", tymczasowy, format_key, drive, progress,
                        opis="format")
    finally:
        try:
            os.remove(tymczasowy)
        except OSError:
            pass


# --------------------------------------------------------------------------
#  Wiersz polecen
# --------------------------------------------------------------------------

def _postep_konsoli(raport: GwReport) -> bool:
    print(f"\r  {raport.done_tracks}/{raport.total_tracks}", end="",
          flush=True)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gwbridge", description="Most do Greaseweazle.")
    parser.add_argument("--lang", choices=sorted(_T), default="pl")
    parser.add_argument("--gw", metavar="SCIEZKA",
                        help="sciezka do polecenia gw, gdy nie ma go w PATH")
    pod = parser.add_subparsers(dest="cmd", required=True)
    pod.add_parser("info")
    for nazwa in ("read", "write"):
        p = pod.add_parser(nazwa)
        p.add_argument("image")
        p.add_argument("--format", default="1440", choices=sorted(GW_FORMATS))
        p.add_argument("--drive", default=DEFAULT_DRIVE, choices=DRIVES)
    p = pod.add_parser("parse")
    p.add_argument("log")
    p.add_argument("--format", default="1440", choices=sorted(GW_FORMATS))
    arg = parser.parse_args(argv)
    set_language(arg.lang)
    if arg.gw:
        if not os.path.isfile(arg.gw):
            print(_t("bad_tool", path=arg.gw), file=sys.stderr)
            return 1
        set_tool_path(arg.gw)

    try:
        if arg.cmd == "info":
            stan = probe()
            print(stan.raw.strip() or "-")
            problem = stan.problem()
            if problem:
                print(problem)
                return 1
            return 0
        if arg.cmd == "parse":
            with open(arg.log, encoding="utf-8", errors="replace") as fh:
                print(parse_log(fh.read(), arg.format).text())
            return 0
        wykonaj = read_to_image if arg.cmd == "read" else write_image
        raport = wykonaj(arg.image, arg.format, arg.drive,
                         progress=_postep_konsoli)
        print()
        print(raport.text())
        return 0 if raport.diagnosis in ("ok", "write_ok") else 1
    except GwError as exc:
        print(exc, file=sys.stderr)
        return 1
    except OSError as exc:
        # Brak pliku, brak uprawnien, katalog zamiast pliku - wszystko to
        # uzytkownik ma zobaczyc jako zdanie, a nie slad wyjatku.
        nazwa = exc.filename or getattr(arg, "log", "") or getattr(arg, "image", "")
        print(_t("file_error", name=nazwa, reason=exc.strerror or exc),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
