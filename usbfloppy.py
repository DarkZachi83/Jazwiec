"""
usbfloppy.py - wykrywanie fizycznych stacji dyskietek oraz odczyt i zapis
nosnikow sektor po sektorze.

Czesc projektu "RetroZachar FFD Disk Maker".

Modul obsluguje stacje podlaczone przez USB (widziane jako zwykle urzadzenia
blokowe) oraz naped na kontrolerze plyty glownej. Dziala na Linuksie
i Windowsie, korzysta wylacznie z biblioteki standardowej.

CZEGO TAKA STACJA NIE POTRAFI
    Naped USB oddaje sektory logiczne, a nie strumien magnetyczny. Nie
    odczyta wiec dyskietek z zabezpieczeniem antykopiowym, z niestandardowa
    liczba sektorow ani zapisanych w FM. W praktyce obsluguje 1,44 MB
    i 720 KB, rzadziej 1,2 MB. Do powaznej archiwizacji sluza kontrolery
    strumieniowe (Greaseweazle, KryoFlux).

UPRAWNIENIA
    Surowy dostep do urzadzenia wymaga roota na Linuksie i Administratora
    na Windowsie. Bez nich modul zglasza czytelny blad zamiast sie wykladac.

BEZPIECZENSTWO ZAPISU
    Zapis na urzadzenie fizyczne jest nieodwracalny, wiec obowiazuja cztery
    zapory naraz: nosnik musi byc wymienny, jego rozmiar musi co do bajtu
    odpowiadac jednej ze znanych geometrii dyskietek, nie moze przekraczac
    twardego limitu i nie moze byc zamontowany. Urzadzenia wieksze niz
    limit nie trafiaja nawet na liste.

Uzycie z linii polecen:
    python3 usbfloppy.py list
    python3 usbfloppy.py read /dev/sdb kopia.img
    python3 usbfloppy.py write /dev/sdb obraz.img
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

try:
    import fat12
    from fat12 import FLOPPY_FORMATS
except ImportError:                                   # dziala tez samodzielnie
    fat12 = None
    FLOPPY_FORMATS = {}

__all__ = [
    "FloppyDrive",
    "TransferReport",
    "DriveError",
    "list_drives",
    "read_to_image",
    "write_from_image",
    "format_media",
    "low_level_format",
    "low_level_tool",
    "low_level_inquire",
    "redetect",
    "report_text",
    "probe_media",
    "DeviceImage",
    "open_device_image",
    "is_elevated",
    "can_access",
    "relaunch_elevated",
    "set_language",
]

# Bajt, ktorym DOS wypelnia swiezo sformatowany nosnik. Uzywamy go tez
# w miejscu sektorow, ktorych nie udalo sie odczytac.
FILL_BYTE = 0xF6

# Twardy limit. Nic wiekszego nie jest dyskietka i nie trafia na liste,
# zeby pendrive albo dysk zewnetrzny nie mial jak sie tam znalezc.
MAX_MEDIA_BYTES = 4 * 1024 * 1024

DEFAULT_RETRIES = 3
CHUNK_SECTORS = 32          # ile sektorow czytamy naraz, gdy wszystko idzie dobrze


# --------------------------------------------------------------------------
#  Komunikaty
# --------------------------------------------------------------------------

_LANG = "pl"

MESSAGES: dict[str, dict[str, str]] = {
    "pl": {
        "need_rule": "Brak praw do urzadzenia {path}. Zainstaluj regule "
                     "udev poleceniem  sudo ./install.sh  i podlacz naped "
                     "ponownie. Doraznie mozna tez uruchomic program "
                     "przez sudo.",
        "denied": "System odmowil dostepu do {path}. Zainstaluj regule udev "
                  "(sudo ./install.sh) albo uruchom program przez sudo.",
        "need_admin": "Dostep do napedu wymaga uprawnien Administratora. "
                      "Uruchom program prawym przyciskiem, "
                      "\"Uruchom jako administrator\".",
        "no_media": "W napedzie {path} nie ma dyskietki.",
        "open_failed": "Nie udalo sie otworzyc {path}: {error}",
        "not_floppy": "Rozmiar nosnika ({size} B) nie odpowiada zadnej "
                      "znanej dyskietce. Zapis wstrzymany dla "
                      "bezpieczenstwa.",
        "too_big": "Urzadzenie ma {size} B, czyli wiecej niz dopuszczalne "
                   "{limit} B. Zapis wstrzymany - to nie jest dyskietka.",
        "mounted": "Urzadzenie {path} jest zamontowane w {mount}. "
                   "Odmontuj je przed zapisem.",
        "size_mismatch": "Obraz ma {image} B, a nosnik {media} B. "
                         "Rozmiary musza sie zgadzac co do bajtu.",
        "verify_failed": "Weryfikacja nie powiodla sie: {count} sektorow "
                         "rozni sie od obrazu.",
        "cancelled": "Operacja przerwana przez uzytkownika.",
        "unsupported": "Ten system nie jest obslugiwany "
                       "przez modul napedow ({system}).",
        "wrong_density": "Nosnik jest sformatowany na {current}, a wybrano "
                         "{wanted}. Zmiana gestosci wymaga formatowania "
                         "niskopoziomowego, ktorego zwykly naped USB nie "
                         "udostepnia przez system plikow.",
        "lowlevel_missing": "Do zmiany gestosci potrzebny jest program "
                            "ufiformat (pakiet ufiutils). Zainstaluj go "
                            "i sprobuj ponownie.",
        "lowlevel_windows": "Pod Windowsem zmiane gestosci wykonuje "
                            "wbudowane polecenie, uruchomione w wierszu "
                            "polecen jako Administrator:\n\n"
                            "    format {letter}: /F:{size}",
        "lowlevel_failed": "Formatowanie niskopoziomowe nie powiodlo sie: "
                           "{error}",
        "inquire_failed": "Nie udalo sie odpytac napedu o obslugiwane "
                          "formaty: {error}",
        "inquire_none": "Naped nie odpowiedzial na pytanie o obslugiwane "
                        "formaty.",
        "redetect_failed": "Po zmianie gestosci naped nie zglosil nowego "
                           "nosnika. Wyjmij i wloz dyskietke ponownie albo "
                           "odlacz i podlacz naped.",
        "media_ruined": "{count} uszkodzonych sektorow lezy w sektorze "
                        "rozruchowym, tablicy FAT albo katalogu glownym. "
                        "Tego nie da sie obejsc - nosnik nadaje sie "
                        "do wyrzucenia.",
        "drive_floppy": "naped dyskietek",
        "drive_usb": "USB",
        "drive_unknown": "nieznana magistrala",
        "no_drives": "Nie znaleziono zadnego napedu dyskietek.",
        "no_boot": "Nie udalo sie odczytac sektora rozruchowego z {path}.\n\n"
                   "Naped obsluguje wylacznie dyskietki zapisane w formacie "
                   "PC: 1,44 MB i 720 KB. Nosnikow Amigi nie odczyta zaden "
                   "naped PC - Amiga zapisuje 11 sektorow na sciezke we "
                   "wlasnym kodowaniu, ktorego kontroler PC nie rozumie.\n\n"
                   "Jesli to dyskietka PC, jest uszkodzona albo nie ma na "
                   "niej systemu plikow.",
        "timeout": "Naped nie odpowiada od {seconds} s. Przerwano odczyt.\n\n"
                   "Zwykle oznacza to nosnik w formacie, ktorego naped nie "
                   "rozpoznaje - ponawia wtedy proby przez kilka minut. "
                   "Wyjmij dyskietke.",
        "rep_title": "RetroZachar FFD Disk Maker - raport operacji",
        "rep_date": "Data",
        "rep_drive": "Naped",
        "rep_media": "Nosnik",
        "rep_action": "Operacja",
        "rep_file": "Plik",
        "rep_mode": "Tryb",
        "rep_mode_quick": "szybki (bez testu powierzchni)",
        "rep_mode_full": "pelny (z testem powierzchni)",
        "rep_act_read": "zgrywanie dyskietki do pliku",
        "rep_act_write": "zapis obrazu na dyskietke",
        "rep_act_format": "formatowanie dyskietki",
        "rep_sectors": "Sektorow ogolem",
        "rep_bad": "Sektorow uszkodzonych",
        "rep_bad_list": "Numery uszkodzonych sektorow",
        "rep_clusters": "Klastrow oznaczonych jako zle",
        "rep_lost": "Utracona pojemnosc",
        "rep_critical": "Uszkodzenia w obszarze systemowym",
        "rep_verify": "Weryfikacja",
        "rep_verify_ok": "zgodna",
        "rep_verify_bad": "wykryto roznice",
        "rep_verify_skip": "nie przeprowadzono",
        "rep_time": "Czas",
        "rep_none": "brak",
        "rep_summary_ok": "Nosnik jest sprawny.",
        "rep_summary_bad": "Nosnik ma uszkodzenia. Oznaczone klastry "
                           "zostaly wylaczone z uzycia, reszta dziala "
                           "normalnie.",
        "rep_summary_ruined": "Nosnik nadaje sie do wyrzucenia - "
                              "uszkodzenia dotykaja obszaru systemowego.",
    },
    "en": {
        "need_rule": "No rights to device {path}. Install the udev rule "
                     "with  sudo ./install.sh  and reconnect the drive. "
                     "As a stopgap you can also run the program "
                     "through sudo.",
        "denied": "The system refused access to {path}. Install the udev "
                  "rule (sudo ./install.sh) or run the program "
                  "through sudo.",
        "need_admin": "Access to the drive requires Administrator rights. "
                      "Right-click the program and choose "
                      "\"Run as administrator\".",
        "no_media": "There is no floppy in drive {path}.",
        "open_failed": "Could not open {path}: {error}",
        "not_floppy": "The medium size ({size} B) matches no known floppy "
                      "format. Writing has been stopped for safety.",
        "too_big": "The device holds {size} B, more than the allowed "
                   "{limit} B. Writing stopped - this is not a floppy.",
        "mounted": "Device {path} is mounted at {mount}. "
                   "Unmount it before writing.",
        "size_mismatch": "The image is {image} B but the medium is "
                         "{media} B. The sizes must match exactly.",
        "verify_failed": "Verification failed: {count} sectors differ "
                         "from the image.",
        "cancelled": "Operation cancelled by the user.",
        "unsupported": "This system is not supported by the drive "
                       "module ({system}).",
        "wrong_density": "The medium is formatted as {current} but "
                         "{wanted} was chosen. Changing density needs a "
                         "low-level format, which an ordinary USB drive "
                         "does not expose through the file system.",
        "lowlevel_missing": "Changing density needs the ufiformat program "
                            "(package ufiutils). Install it and try again.",
        "lowlevel_windows": "On Windows the density change is done by the "
                            "built-in command, run in a command prompt as "
                            "Administrator:\n\n"
                            "    format {letter}: /F:{size}",
        "lowlevel_failed": "The low-level format failed: {error}",
        "inquire_failed": "Could not ask the drive which formats it "
                          "supports: {error}",
        "inquire_none": "The drive did not answer the question about "
                        "supported formats.",
        "redetect_failed": "After the density change the drive reported no "
                           "new medium. Take the floppy out and put it back, "
                           "or unplug and reconnect the drive.",
        "media_ruined": "{count} bad sectors lie in the boot sector, the "
                        "FAT or the root directory. That cannot be worked "
                        "around - the medium belongs in the bin.",
        "drive_floppy": "floppy drive",
        "drive_usb": "USB",
        "drive_unknown": "unknown bus",
        "no_drives": "No floppy drive found.",
        "no_boot": "Could not read the boot sector from {path}.\n\n"
                   "The drive handles PC-formatted floppies only: 1.44 MB "
                   "and 720 KB. No PC drive can read Amiga media - the Amiga "
                   "writes 11 sectors per track in its own encoding, which a "
                   "PC controller does not understand.\n\n"
                   "If this is a PC floppy, it is damaged or holds no file "
                   "system.",
        "timeout": "The drive has not responded for {seconds} s. Reading "
                   "stopped.\n\nThis usually means the medium is in a "
                   "format the drive does not recognise - it then retries "
                   "for minutes. Take the floppy out.",
        "rep_title": "RetroZachar FFD Disk Maker - operation report",
        "rep_date": "Date",
        "rep_drive": "Drive",
        "rep_media": "Medium",
        "rep_action": "Operation",
        "rep_file": "File",
        "rep_mode": "Mode",
        "rep_mode_quick": "quick (no surface test)",
        "rep_mode_full": "full (with surface test)",
        "rep_act_read": "reading floppy into a file",
        "rep_act_write": "writing image onto floppy",
        "rep_act_format": "formatting floppy",
        "rep_sectors": "Sectors in total",
        "rep_bad": "Bad sectors",
        "rep_bad_list": "Bad sector numbers",
        "rep_clusters": "Clusters marked bad",
        "rep_lost": "Capacity lost",
        "rep_critical": "Damage in the system area",
        "rep_verify": "Verification",
        "rep_verify_ok": "matched",
        "rep_verify_bad": "differences found",
        "rep_verify_skip": "not performed",
        "rep_time": "Time",
        "rep_none": "none",
        "rep_summary_ok": "The medium is sound.",
        "rep_summary_bad": "The medium has defects. The marked clusters "
                           "were taken out of use; the rest works "
                           "normally.",
        "rep_summary_ruined": "The medium belongs in the bin - the damage "
                              "reaches the system area.",
    },
}


def set_language(lang: str) -> None:
    global _LANG
    _LANG = lang if lang in MESSAGES else "pl"


def _t(key: str, **kwargs) -> str:
    text = MESSAGES.get(_LANG, MESSAGES["pl"]).get(key) or MESSAGES["pl"][key]
    return text.format(**kwargs) if kwargs else text


class DriveError(Exception):
    """Blad dostepu do fizycznego napedu."""


# --------------------------------------------------------------------------
#  Opis napedu i raport z operacji
# --------------------------------------------------------------------------

@dataclass
class FloppyDrive:
    """Jeden wykryty naped."""

    path: str                    # /dev/sdb albo \\\\.\\A:
    model: str = ""              # nazwa z systemu, np. "TEAC FD-05PUB"
    size_bytes: int = 0          # 0 oznacza brak nosnika w napedzie
    sector_size: int = 512
    bus: str = "unknown"         # "usb", "floppy" albo "unknown"
    format_key: str | None = None    # pasujaca geometria z fat12

    @property
    def has_media(self) -> bool:
        return self.size_bytes > 0

    @property
    def accessible(self) -> bool:
        """Czy program moze siegnac do tego urzadzenia bez podnoszenia praw."""
        return can_access(self.path, write=False)

    @property
    def sectors(self) -> int:
        return self.size_bytes // self.sector_size if self.sector_size else 0

    def bus_name(self) -> str:
        return {
            "usb": _t("drive_usb"),
            "floppy": _t("drive_floppy"),
        }.get(self.bus, _t("drive_unknown"))

    def describe(self) -> str:
        parts = [self.path]
        if self.model:
            parts.append(self.model)
        parts.append(self.bus_name())
        if self.has_media:
            fmt = FLOPPY_FORMATS.get(self.format_key or "")
            parts.append(fmt.label.strip() if fmt
                         else f"{self.size_bytes} B")
        return "  |  ".join(parts)


@dataclass
class TransferReport:
    """Podsumowanie odczytu albo zapisu."""

    total_sectors: int = 0
    done_sectors: int = 0
    bad_sectors: list[int] = field(default_factory=list)
    elapsed: float = 0.0
    cancelled: bool = False
    verified: bool | None = None
    # Etap operacji: "read", "write", "test" albo "verify". Zapis i format
    # skladaja sie z kilku przebiegow po calym nosniku i bez tej informacji
    # pasek postepu dochodzi do konca, po czym zamiera na kolejna minute.
    stage: str = ""
    bad_clusters: int = 0
    critical: int = 0

    @property
    def ok(self) -> bool:
        return not self.cancelled and not self.bad_sectors

    @property
    def bad_bytes(self) -> int:
        return len(self.bad_sectors) * 512


# --------------------------------------------------------------------------
#  Uprawnienia
# --------------------------------------------------------------------------

def is_elevated() -> bool:
    """Czy proces ma prawo siegnac do surowego urzadzenia."""
    if os.name == "nt":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


def can_access(path: str, write: bool = False) -> bool:
    """
    Czy da sie siegnac do urzadzenia bez podnoszenia uprawnien.

    Pod Linuksem decyduja prawa samego wezla urzadzenia - z zainstalowana
    regula udev zalogowany uzytkownik ma je bez roota. Pod Windowsem surowy
    dostep do woluminu jest zastrzezony dla Administratora i nie ma sposobu,
    zeby to obejsc.
    """
    if os.name == "nt":
        return is_elevated()
    if is_elevated():
        return True
    return os.access(path, os.W_OK if write else os.R_OK)


def _require_access(path: str, write: bool) -> None:
    if can_access(path, write):
        return
    if os.name == "nt":
        raise DriveError(_t("need_admin"))
    raise DriveError(_t("need_rule", path=path))


def relaunch_elevated() -> bool:
    """
    Uruchamia program ponownie z uprawnieniami Administratora (tylko Windows).
    Zwraca True, gdy system przyjal zadanie - wtedy stara instancja powinna
    sie zamknac.
    """
    if os.name != "nt":
        return False
    import ctypes
    if getattr(sys, "frozen", False):
        executable, params = sys.executable, ""
    else:
        executable = sys.executable
        params = " ".join(f'"{arg}"' for arg in sys.argv)
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, params, None, 1)
        return int(result) > 32
    except Exception:
        return False


# --------------------------------------------------------------------------
#  Dopasowanie geometrii
# --------------------------------------------------------------------------

def _match_format(size_bytes: int, sector_size: int) -> str | None:
    """Zwraca klucz formatu o dokladnie takim rozmiarze albo None."""
    for key, fmt in FLOPPY_FORMATS.items():
        if (fmt.size_bytes == size_bytes
                and fmt.bytes_per_sector == sector_size):
            return key
    return None


# --------------------------------------------------------------------------
#  Wykrywanie napedow - Linux
# --------------------------------------------------------------------------

def _linux_drives(sysfs: str = "/sys", devdir: str = "/dev") -> list[FloppyDrive]:
    """
    Przeglada /sys/block. Bierze pod uwage tylko urzadzenia wymienne
    o rozmiarze nieprzekraczajacym limitu - dzieki temu pendrive ani dysk
    zewnetrzny nie maja jak trafic na liste.
    """
    drives: list[FloppyDrive] = []
    block = os.path.join(sysfs, "block")
    if not os.path.isdir(block):
        return drives

    for name in sorted(os.listdir(block)):
        if name.startswith(("loop", "ram", "zram", "dm-", "md", "sr", "nbd")):
            continue
        base = os.path.join(block, name)

        # Naped na kontrolerze plyty glownej rozpoznajemy po samej nazwie.
        is_fd = name.startswith("fd")

        removable = _read_sysfs(base, "removable") == "1"
        if not removable and not is_fd:
            continue

        raw = _read_sysfs(base, "size")
        size = int(raw) * 512 if raw.isdigit() else 0
        if size > MAX_MEDIA_BYTES:
            continue

        sector = _read_sysfs(base, "queue/hw_sector_size")
        sector_size = int(sector) if sector.isdigit() else 512

        vendor = _read_sysfs(base, "device/vendor")
        model = _read_sysfs(base, "device/model")
        label = " ".join(part for part in (vendor, model) if part)

        bus = "floppy" if is_fd else "unknown"
        try:
            link = os.path.realpath(base)
            if "/usb" in link:
                bus = "usb"
        except OSError:
            pass

        # Bez nosnika w napedzie rozmiar wynosi 0 - naped i tak pokazujemy,
        # zeby dalo sie wlozyc dyskietke i odswiezyc liste.
        if size == 0 and bus == "unknown" and not is_fd:
            continue

        drives.append(FloppyDrive(
            path=os.path.join(devdir, name),
            model=label,
            size_bytes=size,
            sector_size=sector_size,
            bus=bus,
            format_key=_match_format(size, sector_size),
        ))
    return drives


def _read_sysfs(base: str, relative: str) -> str:
    try:
        with open(os.path.join(base, relative), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _linux_mount_point(device: str) -> str | None:
    """Zwraca punkt montowania urzadzenia albo jego partycji."""
    try:
        with open("/proc/mounts", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[0].startswith(device):
                    return parts[1]
    except OSError:
        pass
    return None


# --------------------------------------------------------------------------
#  Wykrywanie napedow - Windows
# --------------------------------------------------------------------------

# Typy nosnika zwracane przez IOCTL_DISK_GET_DRIVE_GEOMETRY, ktore oznaczaja
# prawdziwa dyskietke. Wartosc 11 (RemovableMedia) to miedzy innymi pendrive
# i celowo jej tu nie ma.
_WINDOWS_FLOPPY_MEDIA = {
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22,
}


def _windows_drives() -> list[FloppyDrive]:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class DISK_GEOMETRY(ctypes.Structure):
        _fields_ = [
            ("Cylinders", ctypes.c_longlong),
            ("MediaType", ctypes.c_int),
            ("TracksPerCylinder", wintypes.DWORD),
            ("SectorsPerTrack", wintypes.DWORD),
            ("BytesPerSector", wintypes.DWORD),
        ]

    DRIVE_REMOVABLE = 2
    IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x00070000
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 1
    FILE_SHARE_WRITE = 2
    OPEN_EXISTING = 3
    INVALID_HANDLE = ctypes.c_void_p(-1).value

    drives: list[FloppyDrive] = []
    mask = kernel32.GetLogicalDrives()

    for index in range(26):
        if not mask & (1 << index):
            continue
        letter = chr(ord("A") + index)
        if kernel32.GetDriveTypeW(f"{letter}:\\") != DRIVE_REMOVABLE:
            continue

        path = f"\\\\.\\{letter}:"
        handle = kernel32.CreateFileW(
            path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, 0, None,
        )
        if handle == INVALID_HANDLE:
            # Naped bez dyskietki potrafi tak odpowiedziec - pokazujemy go,
            # ale bez informacji o nosniku.
            drives.append(FloppyDrive(
                path=path, model=f"{letter}:", size_bytes=0, bus="usb"))
            continue

        geometry = DISK_GEOMETRY()
        returned = wintypes.DWORD()
        ok = kernel32.DeviceIoControl(
            handle, IOCTL_DISK_GET_DRIVE_GEOMETRY, None, 0,
            ctypes.byref(geometry), ctypes.sizeof(geometry),
            ctypes.byref(returned), None,
        )
        kernel32.CloseHandle(handle)

        if not ok:
            drives.append(FloppyDrive(
                path=path, model=f"{letter}:", size_bytes=0, bus="usb"))
            continue

        sector_size = int(geometry.BytesPerSector) or 512
        size = (int(geometry.Cylinders) * int(geometry.TracksPerCylinder)
                * int(geometry.SectorsPerTrack) * sector_size)

        # Pendrive'y i karty pamieci odpadaja na obu warunkach naraz.
        if size > MAX_MEDIA_BYTES:
            continue
        if geometry.MediaType not in _WINDOWS_FLOPPY_MEDIA and size:
            continue

        drives.append(FloppyDrive(
            path=path,
            model=f"{letter}:",
            size_bytes=size,
            sector_size=sector_size,
            bus="floppy",
            format_key=_match_format(size, sector_size),
        ))
    return drives


# --------------------------------------------------------------------------
#  Wspolne wykrywanie
# --------------------------------------------------------------------------

def list_drives() -> list[FloppyDrive]:
    """Lista wykrytych napedow dyskietek. Nie wymaga uprawnien roota."""
    if os.name == "nt":
        return _windows_drives()
    if sys.platform.startswith("linux"):
        return _linux_drives()
    raise DriveError(_t("unsupported", system=sys.platform))


# --------------------------------------------------------------------------
#  Otwieranie urzadzenia
# --------------------------------------------------------------------------

def _open_device(path: str, write: bool):
    """
    Otwiera urzadzenie bez buforowania. Pod Windowsem wolumin trzeba
    dodatkowo zablokowac i odmontowac, inaczej system moze podmienic
    zapisywane dane wlasnymi buforami.
    """
    if os.name != "nt":
        try:
            flags = os.O_RDWR if write else os.O_RDONLY
            fd = os.open(path, flags)
            return os.fdopen(fd, "rb+" if write else "rb", buffering=0), None
        except PermissionError as exc:
            raise DriveError(_t("denied", path=path)) from exc
        except OSError as exc:
            raise DriveError(_t("open_failed", path=path, error=exc)) from exc

    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 1
    FILE_SHARE_WRITE = 2
    OPEN_EXISTING = 3
    FSCTL_LOCK_VOLUME = 0x00090018
    FSCTL_DISMOUNT_VOLUME = 0x00090020
    INVALID_HANDLE = ctypes.c_void_p(-1).value

    access = GENERIC_READ | (GENERIC_WRITE if write else 0)
    handle = kernel32.CreateFileW(
        path, access, FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, 0, None,
    )
    if handle == INVALID_HANDLE:
        raise DriveError(_t("open_failed", path=path,
                            error=ctypes.get_last_error()))

    if write:
        # Bez blokady i odmontowania system moze podmienic zapisywane dane
        # wlasnymi buforami. Gdy blokada sie nie uda, wolumin jest w uzyciu -
        # zapis mimo wszystko probujemy, ale odmontowanie juz pomijamy, zeby
        # nie wyrywac nosnika spod dzialajacego programu.
        returned = wintypes.DWORD()
        locked = kernel32.DeviceIoControl(
            handle, FSCTL_LOCK_VOLUME, None, 0,
            None, 0, ctypes.byref(returned), None)
        if locked:
            kernel32.DeviceIoControl(handle, FSCTL_DISMOUNT_VOLUME, None, 0,
                                     None, 0, ctypes.byref(returned), None)

    fd = msvcrt.open_osfhandle(handle, 0 if write else os.O_RDONLY)
    stream = os.fdopen(fd, "rb+" if write else "rb", buffering=0)
    return stream, handle


def _probe_size(stream) -> int:
    """Rozmiar nosnika ustalony przez przewiniecie na koniec."""
    try:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(0)
        return size
    except OSError:
        return 0


# --------------------------------------------------------------------------
#  Odczyt
# --------------------------------------------------------------------------

def read_stream(stream, total_sectors: int, sector_size: int = 512,
                progress=None, retries: int = DEFAULT_RETRIES,
                fill: int = FILL_BYTE,
                stage: str = "read") -> tuple[bytearray, TransferReport]:
    """
    Czyta caly nosnik z otwartego strumienia.

    Dopoki wszystko idzie gladko, czytamy calymi porcjami - to szybkie.
    Dopiero gdy porcja sie wyloży, schodzimy do pojedynczych sektorow, zeby
    ustalic, ktore konkretnie sa uszkodzone. Sektory nieodczytane wypelniamy
    bajtem 0xF6 i zapisujemy ich numery w raporcie, wiec z dyskietki
    uszkodzonej w kilku miejscach odzyskujemy cala reszte.

    Funkcja jest celowo oddzielona od otwierania urzadzenia - dzieki temu da
    sie ja przetestowac na zwyklym pliku albo na atrapie zglaszajacej bledy.
    """
    report = TransferReport(total_sectors=total_sectors, stage=stage)
    data = bytearray()
    started = time.monotonic()
    sector = 0

    while sector < total_sectors:
        count = min(CHUNK_SECTORS, total_sectors - sector)
        block = _read_block(stream, sector, count, sector_size)

        if block is None:
            # Porcja sie nie udala - sprawdzamy sektor po sektorze.
            for offset in range(count):
                index = sector + offset
                single = None
                for _ in range(max(1, retries)):
                    single = _read_block(stream, index, 1, sector_size)
                    if single is not None:
                        break
                if single is None:
                    single = bytes([fill]) * sector_size
                    report.bad_sectors.append(index)
                data += single
        else:
            data += block

        sector += count
        report.done_sectors = sector
        if progress and not progress(report):
            report.cancelled = True
            break

    report.elapsed = time.monotonic() - started
    return data, report


def _read_block(stream, sector: int, count: int, sector_size: int):
    """Zwraca dane albo None, gdy odczyt sie nie powiodl."""
    want = count * sector_size
    try:
        stream.seek(sector * sector_size)
        chunk = stream.read(want)
    except OSError:
        return None
    if chunk is None or len(chunk) != want:
        return None
    return chunk


def read_to_image(drive: FloppyDrive, dest: str, progress=None,
                  retries: int = DEFAULT_RETRIES,
                  fill: int = FILL_BYTE) -> TransferReport:
    """Zgrywa dyskietke z napedu do pliku .img."""
    _require_access(drive.path, write=False)
    stream, handle = _open_device(drive.path, write=False)
    try:
        size = drive.size_bytes or _probe_size(stream)
        if size <= 0:
            raise DriveError(_t("no_media", path=drive.path))
        if size > MAX_MEDIA_BYTES:
            raise DriveError(_t("too_big", size=size, limit=MAX_MEDIA_BYTES))

        sector_size = drive.sector_size or 512
        data, report = read_stream(
            stream, size // sector_size, sector_size, progress, retries, fill)
    finally:
        _close_device(stream, handle)

    if report.cancelled:
        return report

    partial = dest + ".part"
    with open(partial, "wb") as fh:
        fh.write(data)
    os.replace(partial, dest)
    return report


# --------------------------------------------------------------------------
#  Zapis
# --------------------------------------------------------------------------

def check_writable(drive: FloppyDrive) -> None:
    """
    Cztery zapory przed zapisaniem czegokolwiek na urzadzenie fizyczne.
    Kazda z nich jest w stanie samodzielnie zatrzymac operacje.
    """
    if not drive.has_media:
        raise DriveError(_t("no_media", path=drive.path))
    if drive.size_bytes > MAX_MEDIA_BYTES:
        raise DriveError(
            _t("too_big", size=drive.size_bytes, limit=MAX_MEDIA_BYTES))
    if drive.format_key is None:
        raise DriveError(_t("not_floppy", size=drive.size_bytes))
    if os.name != "nt":
        mount = _linux_mount_point(drive.path)
        if mount:
            raise DriveError(_t("mounted", path=drive.path, mount=mount))


def write_from_image(drive: FloppyDrive, source: str, progress=None,
                     verify: bool = True) -> TransferReport:
    """
    Zapisuje obraz na fizyczna dyskietke. Rozmiar obrazu musi zgadzac sie
    z rozmiarem nosnika co do bajtu - to ostatnia zapora przed pomylka.
    """
    _require_access(drive.path, write=True)
    check_writable(drive)

    with open(source, "rb") as fh:
        payload = fh.read()
    if len(payload) != drive.size_bytes:
        raise DriveError(_t("size_mismatch", image=len(payload),
                            media=drive.size_bytes))

    sector_size = drive.sector_size or 512
    started = time.monotonic()

    stream, handle = _open_device(drive.path, write=True)
    try:
        report = write_stream(stream, payload, sector_size, progress)
    finally:
        _close_device(stream, handle)

    if verify and not report.cancelled:
        report.verified = _verify(drive, payload, progress, report)

    report.elapsed = time.monotonic() - started
    return report


def write_stream(stream, payload: bytes, sector_size: int = 512,
                 progress=None, stage: str = "write") -> TransferReport:
    """
    Zapisuje dane na otwarty nosnik.

    Po kazdej porcji wymuszamy zrzut buforow. Bez tego system przyjmuje caly
    obraz w ulamek sekundy i odklada prawdziwe pisanie na koniec, przez co
    pasek postepu dobiega do konca, zanim cokolwiek trafilo na dyskietke.
    """
    total = len(payload) // sector_size
    report = TransferReport(total_sectors=total, stage=stage)
    sector = 0

    while sector < total:
        count = min(CHUNK_SECTORS, total - sector)
        start = sector * sector_size
        try:
            stream.seek(start)
            stream.write(payload[start:start + count * sector_size])
            _sync(stream)
        except OSError:
            # Porcja sie nie udala - schodzimy do pojedynczych sektorow,
            # zeby ustalic, ktore konkretnie sa uszkodzone.
            for offset in range(count):
                index = sector + offset
                begin = index * sector_size
                try:
                    stream.seek(begin)
                    stream.write(payload[begin:begin + sector_size])
                    _sync(stream)
                except OSError:
                    report.bad_sectors.append(index)
        sector += count
        report.done_sectors = sector
        if progress and not progress(report):
            report.cancelled = True
            break

    _sync(stream)
    return report


def _sync(stream) -> None:
    """Wypycha bufory az na nosnik."""
    try:
        stream.flush()
        os.fsync(stream.fileno())
    except (OSError, ValueError, AttributeError):
        pass


def _verify(drive: FloppyDrive, payload: bytes, progress,
            report: TransferReport) -> bool:
    """
    Czyta nosnik z powrotem i porownuje z obrazem. Odczyt trwa tyle samo co
    zapis, wiec ma wlasny etap na pasku postepu.
    """
    stream, handle = _open_device(drive.path, write=False)
    try:
        sector_size = drive.sector_size or 512
        # Tyle samo prob co przy zwyklym odczycie. Weryfikacja odpowiada na
        # pytanie "czy zapis sie udal", a sektor odczytany dopiero za drugim
        # podejsciem zostal zapisany poprawnie. Jedna proba zglaszala takie
        # sektory jako uszkodzone i zawyzala liczbe bledow.
        written, _ = read_stream(
            stream, len(payload) // sector_size, sector_size,
            progress=progress, retries=DEFAULT_RETRIES, stage="verify")
    finally:
        _close_device(stream, handle)

    differing = [
        index for index in range(len(payload) // sector_size)
        if written[index * sector_size:(index + 1) * sector_size]
        != payload[index * sector_size:(index + 1) * sector_size]
    ]
    if differing:
        for index in differing:
            if index not in report.bad_sectors:
                report.bad_sectors.append(index)
    return not differing


def _close_device(stream, handle) -> None:
    """
    Zamyka urzadzenie dokladnie raz.

    Pod Windowsem os.fdopen przejmuje uchwyt na wlasnosc, wiec stream.close()
    zamyka go samodzielnie. Osobne wywolanie CloseHandle bylo wiec drugim
    zamknieciem tego samego uchwytu - a numery uchwytow sa w systemie
    ponownie uzywane, wiec przy pechowym zbiegu okolicznosci zamykalibysmy
    cudzy zasob otwarty w miedzyczasie przez inny watek.

    Blokade woluminu zdejmujemy jawnie, jeszcze zanim uchwyt straci waznosc.
    """
    if handle is not None and os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            returned = wintypes.DWORD()
            kernel32.DeviceIoControl(handle, 0x0009001C, None, 0,
                                     None, 0, ctypes.byref(returned), None)
        except Exception:
            pass
    try:
        stream.close()
    except OSError:
        pass



# --------------------------------------------------------------------------
#  Formatowanie nosnika
# --------------------------------------------------------------------------

# Wzorzec testu powierzchni. Kazdy sektor dostaje inna zawartosc, dzieki
# czemu wykrywamy nie tylko sektory nieczytelne, ale i takie, ktore zwracaja
# dane spod innego adresu.
def _test_pattern(sector: int, size: int) -> bytes:
    seed = bytes([
        sector & 0xFF, (sector >> 8) & 0xFF, 0xB6, 0x49,
    ])
    return (seed * (size // len(seed) + 1))[:size]


def surface_test(stream, total_sectors: int, sector_size: int,
                 progress=None) -> list[int]:
    """
    Zapisuje na calym nosniku wzorzec kontrolny i czyta go z powrotem.
    Zwraca numery sektorow, ktore nie przyjely zapisu albo oddaly co innego,
    niz na nie trafilo.
    """
    payload = b"".join(
        _test_pattern(n, sector_size) for n in range(total_sectors))

    written = write_stream(stream, payload, sector_size, progress,
                           stage="test")
    if written.cancelled:
        return [-1]

    # Tu jedna proba jest zamierzona. Test powierzchni sluzy do wskazania
    # sektorow slabych, a nie tylko calkiem martwych. Sektor wymagajacy
    # ponowienia jest na granicy czytelnosci i lepiej oznaczyc go jako zly,
    # niz zlozyc na nim dane. Tak samo postepuje DOS-owy FORMAT.
    readback, _ = read_stream(stream, total_sectors, sector_size,
                              progress=progress, retries=1, stage="scan")

    bad = set(written.bad_sectors)
    for index in range(total_sectors):
        start = index * sector_size
        if readback[start:start + sector_size] != \
                payload[start:start + sector_size]:
            bad.add(index)
    return sorted(bad)


def format_media(drive: FloppyDrive, format_key: str | None = None,
                 mode: str = "full", label: str = "",
                 progress=None) -> TransferReport:
    """
    Formatuje dyskietke w napedzie.

    mode="quick"  zapisuje sam system plikow - szybkie, kasuje zawartosc,
                  ale nie sprawdza stanu nosnika,
    mode="full"   najpierw przechodzi cala powierzchnie wzorcem kontrolnym,
                  a wykryte uszkodzone klastry oznacza w tablicy FAT, zeby
                  system przestal ich uzywac. Tak dziala DOS-owy FORMAT.

    Zmiana gestosci (na przyklad 1,44 MB na 720 KB) nie jest tu mozliwa -
    wymaga formatowania niskopoziomowego, patrz low_level_format().
    """
    _require_access(drive.path, write=True)
    check_writable(drive)

    key = format_key or drive.format_key
    fmt = FLOPPY_FORMATS.get(key or "")
    if fmt is None:
        raise DriveError(_t("not_floppy", size=drive.size_bytes))
    if fmt.size_bytes != drive.size_bytes:
        current = FLOPPY_FORMATS.get(drive.format_key or "")
        raise DriveError(_t(
            "wrong_density",
            current=current.label.strip() if current else drive.size_bytes,
            wanted=fmt.label.strip()))

    sector_size = fmt.bytes_per_sector
    total = fmt.total_sectors
    started = time.monotonic()
    bad: list[int] = []

    stream, handle = _open_device(drive.path, write=True)
    try:
        if mode == "full":
            bad = surface_test(stream, total, sector_size, progress)
            if bad and bad[0] == -1:
                report = TransferReport(total_sectors=total, cancelled=True)
                report.elapsed = time.monotonic() - started
                return report

        image = fat12_build(fmt, label)
        clusters, critical = fat12_mark(image, fmt, bad)

        report = write_stream(stream, bytes(image), sector_size, progress)
        report.bad_sectors = sorted(set(report.bad_sectors) | set(bad))
        report.bad_clusters = clusters
    finally:
        _close_device(stream, handle)

    if not report.cancelled:
        report.verified = _verify(drive, bytes(image), progress, report)
    report.elapsed = time.monotonic() - started
    report.critical = critical
    return report


def low_level_tool() -> str | None:
    """Sciezka do narzedzia zmiany gestosci albo None."""
    if os.name == "nt":
        return None                     # wbudowany format uruchamia uzytkownik
    import shutil
    return shutil.which("ufiformat")


def low_level_inquire(drive: FloppyDrive) -> str:
    """
    Pyta naped, jakie pojemnosci obsluguje, i zwraca surowa odpowiedz.

    Polecenie FORMAT UNIT potrafi zawiesic tanszy naped, ktory zglasza sie
    jako UFI, ale nie implementuje go poprawnie. Dlatego przed wyslaniem
    czegokolwiek destrukcyjnego odpytujemy urzadzenie i pokazujemy odpowiedz
    uzytkownikowi - niech sam zobaczy, czy jego naped w ogole deklaruje
    obsluge zadanej gestosci.

    Odpowiedzi nie parsujemy. Format wyjscia ufiformat bywa rozny miedzy
    wersjami, a zgadywanie jego znaczenia byloby gorsze niz pokazanie
    surowego tekstu.
    """
    tool = low_level_tool()
    if tool is None:
        raise DriveError(_t("lowlevel_missing"))

    import subprocess
    for option in ("-i", "--inquire"):
        try:
            result = subprocess.run(
                [tool, option, drive.path],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DriveError(_t("inquire_failed", error=exc)) from exc
        text = (result.stdout or "").strip() or (result.stderr or "").strip()
        if result.returncode == 0 and text:
            return text
    return _t("inquire_none")


def redetect(path: str, expected: int, attempts: int = 8) -> FloppyDrive | None:
    """
    Czeka, az naped zglosi nosnik o oczekiwanym rozmiarze.

    Po zmianie gestosci urzadzenie potrzebuje chwili na ponowne rozpoznanie
    nosnika. Odczyt geometrii od razu po formatowaniu zwraca stara wartosc
    albo zero.
    """
    for _ in range(attempts):
        for drive in list_drives():
            if drive.path == path and drive.size_bytes == expected:
                return drive
        time.sleep(1.0)
    return None


def low_level_format(drive: FloppyDrive, format_key: str) -> str:
    """
    Zmienia gestosc zapisu nosnika, na przyklad z 1,44 MB na 720 KB.

    Naped USB nie udostepnia tego przez system plikow - trzeba wydac
    polecenie FORMAT UNIT protokolu UFI. Robi to program ufiformat, wiec
    zamiast powtarzac jego prace, po prostu go wywolujemy. Pod Windowsem
    to samo potrafi wbudowane polecenie format, ale wymaga wlasnego okna,
    wiec podajemy uzytkownikowi gotowa komende.
    """
    fmt = FLOPPY_FORMATS.get(format_key)
    if fmt is None:
        raise DriveError(_t("not_floppy", size=drive.size_bytes))
    size = fmt.size_kb if fmt.size_kb != 1440 else 1440

    if os.name == "nt":
        letter = drive.path.replace("\\\\.\\", "").rstrip(":")
        raise DriveError(_t("lowlevel_windows", letter=letter, size=size))

    tool = low_level_tool()
    if tool is None:
        raise DriveError(_t("lowlevel_missing"))

    import subprocess
    try:
        result = subprocess.run(
            [tool, "-f", str(size), drive.path],
            capture_output=True, text=True, timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DriveError(_t("lowlevel_failed", error=exc)) from exc
    if result.returncode != 0:
        raise DriveError(_t(
            "lowlevel_failed",
            error=(result.stderr or result.stdout).strip()[:200]))
    return (result.stdout or "").strip()


# Nazwy skrocone, zeby nie mieszac ich z funkcjami tego modulu.
def fat12_build(fmt, label):
    import fat12 as _f
    return _f.build_image(fmt, label)


def fat12_mark(image, fmt, sectors):
    import fat12 as _f
    return _f.mark_bad_clusters(image, fmt, sectors)



def report_text(report: TransferReport, drive: FloppyDrive, action: str,
                file_path: str = "", mode: str = "") -> str:
    """
    Zamienia raport na czytelny tekst, gotowy do pokazania w oknie
    i do zapisania w pliku .txt.
    """
    import datetime

    fmt = FLOPPY_FORMATS.get(drive.format_key or "")
    width = 34
    lines = [
        _t("rep_title"),
        "=" * 62,
        "",
    ]

    def row(key: str, value) -> None:
        lines.append(f"{_t(key) + ':':<{width}}{value}")

    row("rep_date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    row("rep_action", _t("rep_act_" + action))
    row("rep_drive", f"{drive.path}"
                     + (f"  ({drive.model})" if drive.model else ""))
    row("rep_media", fmt.label.strip() if fmt else f"{drive.size_bytes} B")
    if file_path:
        row("rep_file", file_path)
    if mode:
        row("rep_mode", _t("rep_mode_" + mode))

    lines.append("")
    row("rep_sectors", report.total_sectors)
    row("rep_bad", len(report.bad_sectors) or _t("rep_none"))

    if report.bad_sectors:
        lines.append("")
        lines.append(_t("rep_bad_list") + ":")
        text = _format_ranges(report.bad_sectors)
        while text:
            lines.append("  " + text[:58])
            text = text[58:]

    if action == "format":
        lines.append("")
        row("rep_clusters", report.bad_clusters)
        if fmt:
            lost = report.bad_clusters * fmt.sectors_per_cluster \
                * fmt.bytes_per_sector
            row("rep_lost", f"{lost} B")
        if report.critical:
            row("rep_critical", report.critical)

    lines.append("")
    row("rep_verify", {
        True: _t("rep_verify_ok"),
        False: _t("rep_verify_bad"),
        None: _t("rep_verify_skip"),
    }[report.verified])
    row("rep_time", f"{report.elapsed:.1f} s")

    lines.append("")
    lines.append("-" * 62)
    if report.critical:
        lines.append(_t("rep_summary_ruined"))
    elif report.bad_sectors:
        lines.append(_t("rep_summary_bad"))
    else:
        lines.append(_t("rep_summary_ok"))
    return "\n".join(lines)



# --------------------------------------------------------------------------
#  Diagnostyka nosnika i napedu
# --------------------------------------------------------------------------

def probe_media(drive: FloppyDrive, sample: int = 16) -> dict:
    """
    Sprawdza, czy naped i nosnik odpowiadaja, nie zakladajac przy tym
    obecnosci systemu plikow.

    Rozroznia trzy sytuacje, ktore z zewnatrz wygladaja identycznie:
      * nosnik czyta sie poprawnie, brakuje tylko systemu plikow - wystarczy
        go sformatowac, sprzet jest sprawny;
      * nosnik nie oddaje danych - niezgodna gestosc albo zla dyskietka;
      * naped nie zglasza nosnika - pusty albo zawieszony sterownik.
    """
    result = {
        "path": drive.path,
        "model": drive.model,
        "size": drive.size_bytes,
        "sector_size": drive.sector_size,
        "format": drive.format_key,
        "accessible": drive.accessible,
        "readable": 0,
        "failed": 0,
        "boot_signature": False,
        "filesystem": None,
        "blank": None,
        "diagnosis": "no_media",
    }
    if not drive.has_media:
        return result

    stream, handle = _open_device(drive.path, write=False)
    try:
        first = None
        for index in range(min(sample, drive.sectors)):
            block = _read_block(stream, index, 1, drive.sector_size)
            if block is None:
                result["failed"] += 1
                continue
            result["readable"] += 1
            if index == 0:
                first = block
    finally:
        _close_device(stream, handle)

    if first:
        result["boot_signature"] = first[510:512] == bytes([0x55, 0xAA])
        result["blank"] = len(set(first)) <= 1
        if result["boot_signature"]:
            label = first[0x36:0x3E].decode("cp437", "replace").strip()
            result["filesystem"] = label or None

    result["diagnosis"] = _diagnose(result)
    return result


# Formaty wysokiej gestosci. Dyskietki dla nich maja w obudowie dodatkowy
# otwor, po ktorym naped rozpoznaje gestosc jeszcze przed odczytem.
HIGH_DENSITY_KEYS = {"1440", "2880", "1200"}


def _diagnose(info: dict) -> str:
    """
    Nazywa stan nosnika na podstawie tego, co naped zglosil.

    Rozroznienie jest celowo zgrubne. Z poziomu urzadzenia blokowego widac
    tylko, ile sektorow sie odczytalo - a to za malo, zeby odroznic
    uszkodzona dyskietke od zapisanej w niezgodnej gestosci. Obie sytuacje
    wygladaja tak samo: zero odczytanych sektorow. Dlatego przy calkowitym
    braku odczytu zwracamy jedno rozpoznanie i wymieniamy uzytkownikowi
    mozliwe przyczyny, zamiast wskazywac jedna i sie mylic.
    """
    if not info["size"]:
        return "no_media"
    if info["readable"] == 0 and info["failed"]:
        return "unreadable"
    if info["failed"]:
        return "partial"
    if not info["boot_signature"]:
        return "no_filesystem"
    return "ok"


# Wyjasnienia do wynikow probe_media, wypisywane w wierszu polecen.
DIAGNOSIS_HELP: dict[str, tuple[str, ...]] = {
    "ok": (
        "Naped i nosnik dzialaja poprawnie.",
    ),
    "no_filesystem": (
        "Nosnik czyta sie poprawnie, brakuje tylko systemu plikow.",
        "Wystarczy go sformatowac - naped i dyskietka sa sprawne.",
    ),
    "partial": (
        "Czesc sektorow nie chce sie odczytac, ale reszta owszem.",
        "Zgrywanie odzyska to, co da sie odczytac, a formatowanie",
        "w trybie pelnym oznaczy uszkodzone klastry i wylaczy je",
        "z uzycia.",
    ),
    "unreadable": (
        "Naped zglasza obecnosc dyskietki, ale nie oddaje ani jednego",
        "sektora. Z poziomu systemu nie da sie rozstrzygnac, ktora",
        "z przyczyn zachodzi. Mozliwosci, od najczestszej:",
        "",
        "  1. Dyskietka jest uszkodzona albo nigdy nie byla",
        "     sformatowana niskopoziomowo.",
        "",
        "  2. Zapis jest w innej gestosci, niz naped wybral. Naped",
        "     rozpoznaje gestosc po otworze w rogu obudowy, a nie po",
        "     zawartosci, wiec nosnik HD zapisany jako 720 KB bedzie",
        "     nieczytelny, dopoki otwor pozostaje odsloniety.",
        "",
        "  3. Naped nie poradzil sobie z rozpoznaniem nosnika i podal",
        "     domyslna pojemnosc zamiast rzeczywistej. Zdarza sie to",
        "     przy dyskietkach DD w napedach HD.",
        "",
        "Rozstrzyga jedna proba: wloz inna, na pewno sprawna dyskietke.",
        "Jesli sie odczyta, naped jest caly, a problem lezy w nosniku.",
        "Jesli nie - przyczyna jest w napedzie.",
    ),
    "no_media": (
        "Naped nie zglasza dyskietki. Oznacza to pusty naped albo",
        "zawieszony sterownik. Wloz dyskietke; jesli nic sie nie",
        "zmieni, odlacz i podlacz naped, zeby odciac mu zasilanie.",
    ),
}


# --------------------------------------------------------------------------
#  Podglad zawartosci dyskietki
# --------------------------------------------------------------------------

class DeviceImage(fat12.Fat12Image):
    """
    System plikow dyskietki czytany wprost z napedu, sektor po sektorze,
    dopiero gdy dany fragment jest potrzebny.

    Zeby pokazac liste plikow, wystarczy obszar systemowy: sektor rozruchowy,
    tablice FAT i katalog glowny. Dla dyskietki 1,44 MB to 33 sektory zamiast
    2880. Ma to znaczenie przy nosnikach w kiepskim stanie - podglad nie
    meczy calej powierzchni, a wypakowanie pliku siega tylko po jego wlasne
    klastry.

    Obraz jest tylko do odczytu. Zapis na dyskietke idzie osobna droga,
    przez write_from_image, gdzie obowiazuja wszystkie zapory.
    """

    def __init__(self, drive: "FloppyDrive", timeout: float = 20.0):
        self.drive = drive
        self.sector_size = drive.sector_size or 512
        self.loaded: set[int] = set()
        self.unreadable: set[int] = set()
        # Naped, ktory nie rozpoznaje nosnika, ponawia kazdy odczyt przez
        # kilkadziesiat sekund. Bez wlasnego limitu czasu podglad 33 sektorow
        # zajalby kilkanascie minut i zablokowal program.
        self.timeout = timeout
        self.timed_out = False

        stream, handle = _open_device(drive.path, write=False)
        try:
            self._deadline = time.monotonic() + self.timeout
            buffer = bytearray([FILL_BYTE]) * drive.size_bytes
            boot = _read_block(stream, 0, 1, self.sector_size)
            if boot is None:
                raise DriveError(_t("denied", path=drive.path)
                                 if not drive.accessible
                                 else _t("no_boot", path=drive.path))
            buffer[0:self.sector_size] = boot
            self.loaded.add(0)

            # Rozmiar obszaru systemowego wynika z samego sektora
            # rozruchowego, wiec najpierw musimy miec jego tresc.
            reserved = int.from_bytes(boot[0x0E:0x10], "little") or 1
            num_fats = boot[0x10] or 2
            spf = int.from_bytes(boot[0x16:0x18], "little")
            root_entries = int.from_bytes(boot[0x11:0x13], "little")
            root_sectors = (root_entries * 32 + self.sector_size - 1) \
                // self.sector_size
            system_sectors = reserved + num_fats * spf + root_sectors
            if not 1 < system_sectors < drive.sectors:
                raise DriveError(_t("no_boot", path=drive.path))

            self._fill(stream, buffer, 1, system_sectors - 1)
            self.path = ""
            self.read_only = True
            self.data = buffer
            self._parse_bpb()
        finally:
            _close_device(stream, handle)

    def _fill(self, stream, buffer: bytearray, first: int, count: int) -> None:
        """Wczytuje zakres sektorow do bufora, znoszac bledy pojedynczych."""
        for index in range(first, first + count):
            if index in self.loaded or index in self.unreadable:
                continue
            if time.monotonic() > self._deadline:
                self.timed_out = True
                self.unreadable.add(index)
                continue
            block = _read_block(stream, index, 1, self.sector_size)
            if block is None:
                self.unreadable.add(index)
                continue
            offset = index * self.sector_size
            buffer[offset:offset + self.sector_size] = block
            self.loaded.add(index)

    def ensure_sectors(self, first: int, count: int) -> None:
        """Dociaga z napedu sektory, ktorych jeszcze nie mamy."""
        missing = [
            index for index in range(first, first + count)
            if index not in self.loaded and index not in self.unreadable
        ]
        if not missing:
            return
        stream, handle = _open_device(self.drive.path, write=False)
        try:
            self._deadline = time.monotonic() + self.timeout
            self._fill(stream, self.data, missing[0],
                       missing[-1] - missing[0] + 1)
        finally:
            _close_device(stream, handle)

    def _read_chain(self, first: int) -> bytearray:
        """
        Przed odczytem lancucha dociaga jego klastry z napedu.

        Ten jeden punkt wystarcza: korzysta z niego i odczyt pliku,
        i wejscie do podkatalogu.
        """
        for cluster in self._chain(first):
            sector = self.data_start + (cluster - 2) * self.sectors_per_cluster
            self.ensure_sectors(sector, self.sectors_per_cluster)
        return super()._read_chain(first)

    @property
    def damaged_sectors(self) -> list[int]:
        return sorted(self.unreadable)


def open_device_image(drive: FloppyDrive,
                      timeout: float = 20.0) -> DeviceImage:
    """Otwiera system plikow dyskietki do przegladania i wypakowywania."""
    _require_access(drive.path, write=False)
    if not drive.has_media:
        raise DriveError(_t("no_media", path=drive.path))
    return DeviceImage(drive, timeout)


# --------------------------------------------------------------------------
#  Wiersz polecen
# --------------------------------------------------------------------------

def _format_ranges(sectors: list[int]) -> str:
    """Zwiezly zapis listy numerow: 12-19, 44, 300-302."""
    if not sectors:
        return ""
    ranges, start, previous = [], sectors[0], sectors[0]
    for value in sectors[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append((start, previous))
        start = previous = value
    ranges.append((start, previous))
    return ", ".join(
        str(a) if a == b else f"{a}-{b}" for a, b in ranges)


def _cli(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="usbfloppy",
        description="Odczyt i zapis fizycznych dyskietek sektor po sektorze.",
    )
    parser.add_argument("--lang", choices=sorted(MESSAGES), default="pl")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="pokaz wykryte napedy")

    p = sub.add_parser("probe", help="sprawdz stan napedu i nosnika")
    p.add_argument("device")

    p = sub.add_parser("read", help="zgraj dyskietke do pliku .img")
    p.add_argument("device")
    p.add_argument("output")
    p.add_argument("--retries", type=int, default=DEFAULT_RETRIES)

    p = sub.add_parser("write", help="zapisz obraz na dyskietke")
    p.add_argument("device")
    p.add_argument("image")
    p.add_argument("--no-verify", action="store_true")
    p.add_argument("--yes", action="store_true", help="bez pytania")

    args = parser.parse_args(argv)
    set_language(args.lang)

    def show(report: TransferReport) -> bool:
        done = report.done_sectors
        total = report.total_sectors or 1
        print(f"\r  {done * 100 // total:3d}%  "
              f"sektor {done}/{total}  bledow: {len(report.bad_sectors)}",
              end="", flush=True)
        return True

    try:
        drives = {d.path: d for d in list_drives()}

        if args.command == "list":
            if not drives:
                print(_t("no_drives"))
                return 1
            for drive in drives.values():
                print(" ", drive.describe())
            blocked = [d for d in drives.values() if not d.accessible]
            if blocked:
                print()
                for drive in blocked:
                    print(_t("need_admin") if os.name == "nt"
                          else _t("need_rule", path=drive.path))
                    break
            return 0

        drive = drives.get(args.device)
        if drive is None:
            print(f"Nie znaleziono napedu {args.device}. "
                  f"Dostepne: {', '.join(drives) or 'brak'}")
            return 1

        if args.command == "probe":
            info = probe_media(drive)
            print(f"  urzadzenie       : {info['path']}  {info['model']}")
            print(f"  dostep           : "
                  f"{'jest' if info['accessible'] else 'BRAK PRAW'}")
            if not info["size"]:
                print("  nosnik           : naped nie zglasza dyskietki")
                print()
                print("  Oznacza to pusty naped albo zawieszony sterownik.")
                print("  Wloz dyskietke; jesli nic sie nie zmieni, odlacz")
                print("  i podlacz naped, zeby odciac mu zasilanie.")
                return 0
            fmt = FLOPPY_FORMATS.get(info["format"] or "")
            print(f"  pojemnosc        : {info['size']} B"
                  f" ({info['size'] // 1024} KB)"
                  + (f"  = {fmt.label.strip()}" if fmt
                     else "  - nie pasuje do znanej dyskietki"))
            print(f"  rozmiar sektora  : {info['sector_size']} B")
            print(f"  odczyt probny    : {info['readable']} sektorow OK, "
                  f"{info['failed']} bledow")
            print(f"  sygnatura 0x55AA : "
                  f"{'jest' if info['boot_signature'] else 'brak'}")
            if info["filesystem"]:
                print(f"  system plikow    : {info['filesystem']}")
            print(f"  rozpoznanie      : {info['diagnosis']}")
            print()
            for line in DIAGNOSIS_HELP.get(
                    info["diagnosis"], ("",)):
                print("  " + line if line else "")
            return 0

        if args.command == "read":
            report = read_to_image(drive, args.output, show, args.retries)
            print()
            if report.bad_sectors:
                print(f"Uszkodzone sektory ({len(report.bad_sectors)}): "
                      f"{_format_ranges(report.bad_sectors)}")
            print(f"Zapisano {args.output} w {report.elapsed:.1f} s")
            return 0 if report.ok else 2

        if args.command == "write":
            check_writable(drive)
            if not args.yes:
                print(f"UWAGA: caly nosnik w {drive.path} zostanie "
                      f"nadpisany przez {args.image}.")
                if input("Wpisz TAK, aby kontynuowac: ").strip() != "TAK":
                    print(_t("cancelled"))
                    return 1
            report = write_from_image(
                drive, args.image, show, verify=not args.no_verify)
            print()
            if report.bad_sectors:
                print(f"Problemy w sektorach: "
                      f"{_format_ranges(report.bad_sectors)}")
            if report.verified is False:
                print(_t("verify_failed", count=len(report.bad_sectors)))
            print(f"Gotowe w {report.elapsed:.1f} s")
            return 0 if report.ok else 2

    except DriveError as exc:
        print(f"Blad: {exc}")
        return 1
    except KeyboardInterrupt:
        print()
        print(_t("cancelled"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
