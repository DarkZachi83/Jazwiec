"""
optical.py - zgrywanie plyt CD i DVD do pliku .iso.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Co robi, a czego nie
    Zgrywa zawartosc plyty z danymi do obrazu .iso. Nie wypala - od tego sa
    narzedzia systemowe i nie ma sensu ich powielac.

Czego .iso nie pomiesci
    Plyta bywa czyms wiecej niz jednym ciagiem sektorow z danymi. Sciezki
    CD-Audio, tak czeste w grach z lat dziewiecdziesiatych, leza poza
    systemem plikow i do obrazu .iso nie wchodza - taki obraz da gre bez
    muzyki. Podobnie plyta wielosesyjna: .iso zachowa tylko jedna sesje.
    Program rozpoznaje oba przypadki przed zgrywaniem i mowi o tym wprost,
    zamiast po cichu zapisac obraz niepelny.

Ile naprawde ma plyta
    Rozmiar urzadzenia potrafi byc zawyzony o sektory wyrownujace i cisze na
    koncu. Prawdziwa dlugosc danych podaje sama plyta: w sektorze 16 lezy
    opis wolumenu ISO 9660 z liczba blokow. Bierzemy ja, gdy jest sensowna,
    a rozmiar urzadzenia traktujemy jako granice.

Wiersz polecen:
    python3 optical.py list
    python3 optical.py probe /dev/sr0
    python3 optical.py read /dev/sr0 plyta.iso
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
from dataclasses import dataclass, field

__all__ = [
    "OpticalError",
    "OpticalDrive",
    "DiscInfo",
    "ReadReport",
    "list_drives",
    "probe",
    "read_to_iso",
    "opis_plyty",
    "opis_raportu",
    "sciezka_z_danymi",
    "wpis_toc",
    "SEKTOR",
]

# Sektor plyty z danymi ma 2048 bajtow uzytecznych - inaczej niz 512 na
# dyskietce czy dysku twardym.
SEKTOR = 2048
OPIS_WOLUMENU = 16            # numer sektora z opisem ISO 9660
SYGNATURA_ISO = b"CD001"

# Domyslna liczba prob odczytu sektora. Plyty rysuja sie inaczej niz
# dyskietki: uszkodzenie bywa miejscowe, a kolejne podejscie czesto pomaga.
DOMYSLNE_PROBY = 3
PORCJA = 256                  # sektorow na jedno siegniecie do napedu (512 kB)
POCZATKOWE_BLEDY = 64         # tyle nieudanych sektorow z rzedu na poczatku
                              # oznacza, ze to nie jest plyta z danymi

# Linux: polecenia sterownika CD-ROM
CDROM_DRIVE_STATUS = 0x5326
CDROM_DISC_STATUS = 0x5327
CDROMREADTOCHDR = 0x5305
CDROMREADTOCENTRY = 0x5306
CDS_NO_DISC, CDS_TRAY_OPEN, CDS_DRIVE_NOT_READY, CDS_DISC_OK = 1, 2, 3, 4
CDS_AUDIO, CDS_DATA_1, CDS_DATA_2 = 100, 101, 102
CDS_XA_2_1, CDS_XA_2_2, CDS_MIXED = 103, 104, 105
CDROM_LBA = 0x01              # adresowanie w sektorach logicznych
ROZMIAR_WPISU_TOC = 12        # struktura wpisu spisu tresci, z wyrownaniem


class OpticalError(Exception):
    """Naped optyczny jest niedostepny albo plyty nie da sie zgrac."""


@dataclass
class OpticalDrive:
    """Jeden wykryty naped optyczny."""

    path: str
    model: str = ""

    def __str__(self) -> str:
        return f"{self.path}  {self.model}".strip()


@dataclass
class DiscInfo:
    """Co wiemy o plycie w napedzie, zanim zaczniemy ja zgrywac."""

    present: bool = False
    tray_open: bool = False
    data_tracks: int = 0
    audio_tracks: int = 0
    sectors: int = 0              # dlugosc danych w sektorach 2048 B
    device_sectors: int = 0       # ile widzi urzadzenie
    label: str = ""
    system_id: str = ""
    iso: bool = False             # czy widac opis wolumenu ISO 9660
    sessions: int = 1
    notes: list[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        return self.sectors * SEKTOR

    @property
    def has_audio(self) -> bool:
        return self.audio_tracks > 0

    @property
    def audio_only(self) -> bool:
        """
        Plyta z sama muzyka - bez ani jednej sciezki z danymi.

        Takiej nie da sie zgrac do .iso i nie jest to kwestia jakosci
        nosnika: muzyka nie lezy w sektorach po 2048 bajtow, wiec naped
        odmawia czytania jej jak danych.
        """
        return self.audio_tracks > 0 and self.data_tracks == 0

    @property
    def readable(self) -> bool:
        return self.present and self.sectors > 0 and not self.audio_only


@dataclass
class ReadReport:
    """Wynik zgrywania plyty."""

    device: str = ""
    path: str = ""
    sectors: int = 0
    done: int = 0
    bad: list[int] = field(default_factory=list)
    cancelled: bool = False
    seconds: float = 0.0
    info: DiscInfo | None = None

    @property
    def complete(self) -> bool:
        return not self.cancelled and self.done == self.sectors and not self.bad


# --------------------------------------------------------------------------
#  Wykrywanie napedow
# --------------------------------------------------------------------------

def _linux_drives() -> list[OpticalDrive]:
    """
    Napedy optyczne z /sys/block.

    Sterownik zaznacza je plikiem "capability" z ustawionym bitem CD-ROM,
    ale prostsze i pewniejsze jest to, ze wszystkie nazywaja sie sr*.
    """
    wynik: list[OpticalDrive] = []
    katalog = "/sys/block"
    if not os.path.isdir(katalog):
        return wynik
    for nazwa in sorted(os.listdir(katalog)):
        if not nazwa.startswith("sr"):
            continue
        model = ""
        for plik in ("device/model", "device/vendor"):
            sciezka = os.path.join(katalog, nazwa, plik)
            try:
                with open(sciezka, encoding="latin1") as fh:
                    model = (fh.read().strip() + " " + model).strip()
            except OSError:
                pass
        wynik.append(OpticalDrive(f"/dev/{nazwa}", model))
    return wynik


def _windows_drives() -> list[OpticalDrive]:
    """Litery dyskow, ktore system uznaje za napedy optyczne."""
    wynik: list[OpticalDrive] = []
    try:
        kernel32 = ctypes.windll.kernel32           # type: ignore[attr-defined]
    except AttributeError:
        return wynik
    DRIVE_CDROM = 5
    maska = kernel32.GetLogicalDrives()
    for numer in range(26):
        if not maska & (1 << numer):
            continue
        litera = f"{chr(ord('A') + numer)}:\\"
        if kernel32.GetDriveTypeW(litera) == DRIVE_CDROM:
            wynik.append(OpticalDrive(f"\\\\.\\{litera[:2]}", "CD/DVD"))
    return wynik


def list_drives() -> list[OpticalDrive]:
    return _windows_drives() if os.name == "nt" else _linux_drives()


# --------------------------------------------------------------------------
#  Rozpoznanie plyty
# --------------------------------------------------------------------------

def _ioctl(uchwyt: int, polecenie: int, arg) -> bool:
    """Wywolanie sterownika; False, gdy sterownik go nie obsluguje."""
    import fcntl
    try:
        fcntl.ioctl(uchwyt, polecenie, arg)
        return True
    except (OSError, AttributeError):
        return False


def wpis_toc(numer: int) -> bytearray:
    """
    Bufor zapytania o jedna sciezke spisu tresci.

    Uklad pol: numer sciezki, bajt adresowania i pola kontrolnego, znacznik
    formatu adresu, potem sam adres wyrownany do czterech bajtow i tryb
    danych. Znacznik pod zlym indeksem albo za krotki bufor sprawiaja, ze
    sterownik odmawia, a plyta wyglada jak plyta bez sciezek - czego bez
    prawdziwego napedu nie widac.
    """
    wpis = bytearray(ROZMIAR_WPISU_TOC)
    wpis[0] = numer
    wpis[2] = CDROM_LBA
    return wpis


def sciezka_z_danymi(adr_ctrl: int) -> bool:
    """
    Czy wpis spisu tresci opisuje sciezke z danymi, czy audio.

    W jednym bajcie siedza dwa pola po cztery bity: mlodsze to sposob
    adresowania, starsze to pole kontrolne. Bit 2 pola kontrolnego
    oznacza dane - jego brak oznacza sciezke audio.
    """
    return bool((adr_ctrl >> 4) & 0x04)


def _sciezki_plyty(uchwyt: int, info: DiscInfo) -> None:
    """
    Liczy sciezki z danymi i sciezki audio.

    Spis tresci plyty czyta sie osobnym poleceniem sterownika. Gdy sie nie
    uda - inny system, obraz w pliku, brak uprawnien - zostawiamy zera
    i program traktuje plyte jak zwykle dane.
    """
    if os.name == "nt":
        return
    naglowek = bytearray(2)
    if not _ioctl(uchwyt, CDROMREADTOCHDR, naglowek):
        return
    pierwsza, ostatnia = naglowek[0], naglowek[1]
    for numer in range(pierwsza, ostatnia + 1):
        # Struktura sterownika: numer sciezki, bajt adr|ctrl, znacznik
        # formatu adresu, potem sam adres wyrownany do czterech bajtow
        # i tryb danych - razem dwanascie bajtow. Krotszy bufor sprawia,
        # ze wywolanie zawodzi i spis tresci nie wczytuje sie wcale.
        wpis = wpis_toc(numer)
        if not _ioctl(uchwyt, CDROMREADTOCENTRY, wpis):
            continue
        if sciezka_z_danymi(wpis[1]):
            info.data_tracks += 1
        else:
            info.audio_tracks += 1


def _rozmiar_urzadzenia(uchwyt: int) -> int:
    """Rozmiar nosnika w bajtach, bez czytania jego zawartosci."""
    try:
        obecne = os.lseek(uchwyt, 0, os.SEEK_CUR)
        koniec = os.lseek(uchwyt, 0, os.SEEK_END)
        os.lseek(uchwyt, obecne, os.SEEK_SET)
        return koniec
    except OSError:
        return 0


def _opis_wolumenu(dane: bytes, info: DiscInfo) -> None:
    """
    Rozbiera opis wolumenu ISO 9660 z sektora 16.

    Stad bierze sie etykieta plyty i - co wazniejsze - prawdziwa liczba
    blokow z danymi, zwykle mniejsza niz to, co podaje urzadzenie.
    """
    if len(dane) < 2048 or dane[1:6] != SYGNATURA_ISO:
        return
    info.iso = True
    info.system_id = dane[8:40].decode("latin1").strip()
    info.label = dane[40:72].decode("latin1").strip()
    blokow = int.from_bytes(dane[80:84], "little")
    rozmiar_bloku = int.from_bytes(dane[128:130], "little") or SEKTOR
    if blokow > 0 and rozmiar_bloku > 0:
        info.sectors = blokow * rozmiar_bloku // SEKTOR


def probe(device: str) -> DiscInfo:
    """
    Sprawdza, co jest w napedzie, nie zgrywajac plyty.

    Dziala takze na zwyklym pliku - wtedy rozpoznaje sam obraz ISO. Dzieki
    temu ta sama droga sluzy do sprawdzenia gotowego pliku .iso.
    """
    info = DiscInfo()
    try:
        uchwyt = os.open(device, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except OSError as exc:
        raise OpticalError(f"{device}: {exc.strerror or exc}") from exc
    try:
        if os.name != "nt" and os.path.exists(device):
            stan = _stan_napedu(uchwyt)
            if stan is not None:
                info.present = stan == CDS_DISC_OK
                info.tray_open = stan == CDS_TRAY_OPEN
                if not info.present:
                    return info
            _sciezki_plyty(uchwyt, info)
        rozmiar = _rozmiar_urzadzenia(uchwyt)
        info.device_sectors = rozmiar // SEKTOR
        info.sectors = info.device_sectors
        info.present = info.present or rozmiar > 0
        try:
            os.lseek(uchwyt, OPIS_WOLUMENU * SEKTOR, os.SEEK_SET)
            _opis_wolumenu(os.read(uchwyt, SEKTOR), info)
        except OSError:
            pass
        if info.sectors > info.device_sectors > 0:
            # Opis wolumenu bywa uszkodzony; nie czytamy poza nosnik.
            info.sectors = info.device_sectors
            info.notes.append("opis wolumenu podaje wiecej blokow, niz ma "
                              "nosnik - bierzemy rozmiar urzadzenia")
    finally:
        os.close(uchwyt)

    if info.audio_only:
        info.notes.append(
            f"to plyta z sama muzyka ({info.audio_tracks} sciezek audio) - "
            "nie da sie jej zgrac do .iso, bo muzyka nie lezy w sektorach "
            "z danymi. Do plyt audio sluza programy zgrywajace do WAV "
            "albo FLAC")
    elif info.audio_tracks:
        info.notes.append(
            f"plyta ma {info.audio_tracks} sciezek audio - obraz .iso ich "
            "nie pomiesci, wiec gra dostanie dane bez muzyki")
    if info.present and not info.iso:
        info.notes.append("brak opisu wolumenu ISO 9660 - obraz powstanie, "
                          "ale system plikow moze byc inny niz spodziewany")
    return info


def _stan_napedu(uchwyt: int) -> int | None:
    """Stan napedu wedlug sterownika: plyta, pusta szuflada, brak."""
    import fcntl
    try:
        return fcntl.ioctl(uchwyt, CDROM_DRIVE_STATUS, 0)
    except (OSError, AttributeError):
        return None


# --------------------------------------------------------------------------
#  Zgrywanie
# --------------------------------------------------------------------------

def read_to_iso(device: str, path: str, progress=None,
                retries: int = DOMYSLNE_PROBY,
                info: DiscInfo | None = None,
                chunk: int = PORCJA) -> ReadReport:
    """
    Zgrywa plyte do pliku .iso.

    Czyta porcjami; dopiero gdy porcja zawiedzie, schodzi do pojedynczych
    sektorow, zeby ustalic dokladnie, ktorych brakuje. Sektorow nieczytelnych
    nie pomijamy - wypelniamy zerami i wypisujemy w raporcie, zeby z plyty
    porysowanej w kilku miejscach odzyskac cala reszte.

    progress dostaje raport po kazdej porcji i moze zwrocic False, zeby
    przerwac.
    """
    info = info or probe(device)
    if info.audio_only:
        raise OpticalError(
            f"plyta ma same sciezki audio ({info.audio_tracks}) - do pliku "
            ".iso nie da sie jej zgrac. Naped odmawia czytania muzyki jak "
            "danych, wiec zgrywanie mieliloby godzinami i dalo plik bez "
            "zadnej wartosci")
    if not info.readable:
        raise OpticalError("w napedzie nie ma plyty z danymi")

    raport = ReadReport(device=device, path=os.path.abspath(path),
                        sectors=info.sectors, info=info)
    poczatek = time.monotonic()
    try:
        uchwyt = os.open(device, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except OSError as exc:
        raise OpticalError(f"{device}: {exc.strerror or exc}") from exc
    try:
        with open(path, "wb") as wynik:
            numer = 0
            while numer < info.sectors:
                ile = min(max(1, chunk), info.sectors - numer)
                dane = _czytaj_porcje(uchwyt, numer, ile, retries, raport)
                # Gdy nie udaje sie nic od samego poczatku, dalsze mielenie
                # nie ma sensu: tak zachowuje sie plyta w zlym formacie
                # albo naped, ktory jej nie obsluguje.
                if len(raport.bad) >= POCZATKOWE_BLEDY \
                        and len(raport.bad) == numer + ile:
                    raise OpticalError(
                        f"naped nie oddal ani jednego z pierwszych "
                        f"{len(raport.bad)} sektorow - to nie wyglada na "
                        "plyte z danymi w formacie, ktory umiemy czytac")
                wynik.write(dane)
                numer += ile
                raport.done = numer
                if progress is not None and progress(raport) is False:
                    raport.cancelled = True
                    break
    finally:
        os.close(uchwyt)
        raport.seconds = time.monotonic() - poczatek
    return raport


def _czytaj_porcje(uchwyt: int, od: int, ile: int, proby: int,
                   raport: ReadReport) -> bytes:
    """Porcja sektorow; przy bledzie schodzi do pojedynczych."""
    dane = _czytaj(uchwyt, od, ile)
    if dane is not None:
        return dane
    wynik = bytearray()
    for numer in range(od, od + ile):
        sektor = None
        for _ in range(max(1, proby)):
            sektor = _czytaj(uchwyt, numer, 1)
            if sektor is not None:
                break
        if sektor is None:
            raport.bad.append(numer)
            sektor = bytes(SEKTOR)
        wynik += sektor
    return bytes(wynik)


def _czytaj(uchwyt: int, od: int, ile: int) -> bytes | None:
    """
    Odczyt sektorow albo None, gdy naped nie oddal wszystkiego.

    Krotszy odczyt tez jest niepowodzeniem. Wczesniej dopelnialem reszte
    zerami i uznawalem porcje za udana - czyli po cichu wstawialem puste
    miejsca w obraz. Teraz zglaszamy blad, a wyzej program schodzi do
    pojedynczych sektorow i ustala dokladnie, ktorych brakuje.
    """
    try:
        os.lseek(uchwyt, od * SEKTOR, os.SEEK_SET)
        dane = os.read(uchwyt, ile * SEKTOR)
    except OSError:
        return None
    return dane if len(dane) == ile * SEKTOR else None


def opis_raportu(raport: ReadReport) -> str:
    """
    Raport z zgrywania - ten sam tekst w oknie i w wierszu polecen.

    Zawiera to, co po latach moze byc wazne przy ocenie obrazu: skad
    pochodzi, ile sektorow odzyskano i ktorych nie.
    """
    info = raport.info or DiscInfo()
    wiersze = ["RetroZachar - Jazwiec - raport ze zgrywania plyty",
               "=" * 62, ""]
    szer = 26

    def pole(etykieta: str, wartosc) -> None:
        wiersze.append(f"{etykieta:<{szer}}{wartosc}")

    pole("Data:", time.strftime("%Y-%m-%d %H:%M:%S"))
    pole("Naped:", raport.device)
    if info.label:
        pole("Etykieta plyty:", info.label)
    if info.system_id:
        pole("System:", info.system_id)
    pole("Obraz:", raport.path)
    pole("Sektorow:", f"{raport.done} z {raport.sectors}")
    pole("Rozmiar:", f"{raport.done * SEKTOR} B "
                     f"({raport.done * SEKTOR / 1048576:.0f} MB)")
    if info.data_tracks or info.audio_tracks:
        pole("Sciezki:", f"{info.data_tracks} z danymi, "
                         f"{info.audio_tracks} audio")
    pole("Czas:", f"{raport.seconds:.0f} s"
                  + (f"   ({raport.done * SEKTOR / 1048576 / raport.seconds:.1f}"
                     " MB/s)" if raport.seconds > 0 else ""))
    pole("Sektorow nieczytelnych:", len(raport.bad))

    if raport.bad:
        wiersze += ["", "Numery nieczytelnych sektorow:"]
        pokazane = raport.bad[:120]
        for i in range(0, len(pokazane), 10):
            wiersze.append("  " + " ".join(f"{n:>7}" for n in pokazane[i:i + 10]))
        if len(raport.bad) > len(pokazane):
            wiersze.append(f"  ... i {len(raport.bad) - len(pokazane)} dalszych")

    if info.notes:
        wiersze += ["", "Uwagi:"]
        wiersze += [f"  {u}" for u in info.notes]

    wiersze += ["", "-" * 62, "Rozpoznanie:"]
    if raport.cancelled:
        wiersze.append("Zgrywanie przerwane - obraz jest niepelny.")
    elif raport.complete:
        wiersze.append("Plyta zgrana w calosci.")
    else:
        wiersze.append(
            f"Nie udalo sie odczytac {len(raport.bad)} sektorow. Miejsca "
            "te sa w obrazie wypelnione zerami,\na reszta plyty zostala "
            "odzyskana. Warto sprobowac ponownie po wyczyszczeniu plyty.")
    return "\n".join(wiersze)


def opis_plyty(info: DiscInfo) -> str:
    """Czytelny opis do okna i do wiersza polecen."""
    if info.tray_open:
        return "szuflada otwarta"
    if not info.present:
        return "brak plyty w napedzie"
    czesci = []
    if info.label:
        czesci.append(f'"{info.label}"')
    czesci.append(f"{info.size / 1048576:.0f} MB ({info.sectors} sektorow)")
    if info.data_tracks or info.audio_tracks:
        czesci.append(f"sciezki: {info.data_tracks} z danymi, "
                      f"{info.audio_tracks} audio")
    if info.system_id:
        czesci.append(info.system_id)
    return "  |  ".join(czesci)


# --------------------------------------------------------------------------
#  Wiersz polecen
# --------------------------------------------------------------------------

def _postep(raport: ReadReport) -> bool:
    procent = raport.done * 100 // max(1, raport.sectors)
    ogon = f"   nieczytelnych: {len(raport.bad)}" if raport.bad else ""
    print(f"\r  {raport.done}/{raport.sectors} sektorow ({procent}%){ogon}",
          end="", flush=True)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="optical", description="Zgrywanie plyt CD i DVD do pliku .iso.")
    pod = parser.add_subparsers(dest="cmd", required=True)
    pod.add_parser("list")
    p = pod.add_parser("probe")
    p.add_argument("device")
    p = pod.add_parser("read")
    p.add_argument("device")
    p.add_argument("plik")
    p.add_argument("--retries", type=int, default=DOMYSLNE_PROBY)
    p.add_argument("--chunk", type=int, default=PORCJA,
                   help=f"sektorow na jeden odczyt (domyslnie {PORCJA})")
    arg = parser.parse_args(argv)

    try:
        if arg.cmd == "list":
            napedy = list_drives()
            if not napedy:
                print("nie znaleziono napedow optycznych")
                return 1
            for naped in napedy:
                print(naped)
            return 0
        if arg.cmd == "probe":
            info = probe(arg.device)
            print(opis_plyty(info))
            for uwaga in info.notes:
                print("  uwaga:", uwaga)
            return 0 if info.readable else 1
        try:
            raport = read_to_iso(arg.device, arg.plik, progress=_postep,
                                 retries=arg.retries, chunk=arg.chunk)
        except KeyboardInterrupt:
            # Ctrl+C przy zgrywaniu plyty to normalna droga wyjscia, a nie
            # awaria - slad wyjatku tylko zaciemnia to, co juz zgrane.
            print()
            print("przerwano", file=sys.stderr)
            return 1
        print()
        print(opis_raportu(raport))
        return 0 if raport.complete else 1
    except (OpticalError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
