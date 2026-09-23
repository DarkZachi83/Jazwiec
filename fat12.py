"""
fat12.py - obsluga obrazow dyskietek FAT12 w czystym Pythonie.

Czesc projektu "RetroZachar FFD Disk Maker".

Modul nie wymaga zadnych zewnetrznych bibliotek ani uprawnien administratora.
Nie korzysta z mkfs.fat ani z montowania - caly system plikow (sektor
rozruchowy, tablice FAT, katalogi, obszar danych) jest zapisywany bajt po
bajcie, dzieki czemu dziala identycznie na Linuksie i na Windowsie.

Obslugiwane operacje:
    - formatowanie obrazu (360 KB, 1,2 MB, 720 KB, 1,44 MB),
    - odczyt i zapis plikow wewnatrz obrazu,
    - tworzenie i usuwanie katalogow,
    - zmiana nazwy, usuwanie, odczyt wolnego miejsca,
    - odczyt i zmiana etykiety wolumenu.

Uzycie z linii polecen:
    python3 fat12.py create dysk.img --format 1440 --label DANE
    python3 fat12.py list dysk.img
    python3 fat12.py add dysk.img plik.txt
    python3 fat12.py extract dysk.img PLIK.TXT ./plik.txt
"""

from __future__ import annotations

import datetime
import os
import struct
from dataclasses import dataclass, field
from typing import Iterator

__all__ = [
    "Fat12Error",
    "build_image",
    "mark_bad_clusters",
    "data_start_sector",
    "set_language",
    "get_language",
    "FloppyFormat",
    "FLOPPY_FORMATS",
    "DirEntry",
    "Fat12Image",
    "format_image",
    "to_short_name",
]

# --------------------------------------------------------------------------
#  Stale formatu FAT
# --------------------------------------------------------------------------

BYTES_PER_SECTOR = 512
DIR_ENTRY_SIZE = 32

ATTR_READ_ONLY = 0x01
ATTR_HIDDEN = 0x02
ATTR_SYSTEM = 0x04
ATTR_VOLUME_ID = 0x08
ATTR_DIRECTORY = 0x10
ATTR_ARCHIVE = 0x20
ATTR_LONG_NAME = 0x0F

ENTRY_FREE = 0x00        # koniec katalogu - dalej nic nie ma
ENTRY_DELETED = 0xE5     # wpis skasowany, mozna go nadpisac

FAT_FREE = 0x000
FAT_BAD = 0xFF7
FAT_EOC = 0xFFF          # koniec lancucha klastrow

# Znaki niedozwolone w nazwach 8.3
ILLEGAL_83 = set('"*+,./:;<=>?[\\]|')


# --------------------------------------------------------------------------
#  Komunikaty w dwoch jezykach
# --------------------------------------------------------------------------

_LANG = "pl"

MESSAGES: dict[str, dict[str, str]] = {
    "pl": {
        "noname": "BEZ NAZWY",
        "exists": "Plik {path} juz istnieje. Operacja przerwana, "
                  "zeby nie nadpisac danych.",
        "no_unique_83": "Nie udalo sie wygenerowac unikalnej nazwy 8.3.",
        "too_small": "Plik jest za maly, by byl obrazem dyskietki.",
        "no_signature": "Brak sygnatury 0x55AA - to nie jest obraz dyskietki.",
        "odd_sector": "Nietypowy rozmiar sektora ({size} B).",
        "bad_bpb": "Uszkodzony blok BPB w sektorze rozruchowym.",
        "looks_fat32": "Obraz wyglada na FAT32 - obslugiwany jest FAT12.",
        "fat_loop": "Wykryto petle w tablicy FAT - obraz jest uszkodzony.",
        "not_fat12": "Obraz uzywa FAT16 lub FAT32. "
                     "Program obsluguje tylko FAT12.",
        "truncated": "Plik jest krotszy niz deklaruje BPB "
                     "({actual} B zamiast {expected} B).",
        "root_full": "Katalog glowny jest pelny.",
        "root_full_limit": "Katalog glowny jest pelny (limit {limit} "
                           "pozycji). Utworz podkatalog.",
        "no_dir": "Nie ma katalogu: {path}",
        "not_a_dir": "{name} jest plikiem, nie katalogiem.",
        "is_a_dir": "{name} jest katalogiem.",
        "no_file": "Nie ma pliku: {path}",
        "no_entry": "Nie ma pozycji: {path}",
        "file_exists": "Plik {name} juz istnieje.",
        "entry_exists": "Pozycja {name} juz istnieje.",
        "no_clusters": "Brak miejsca na dyskietce - potrzeba {needed} "
                       "klastrow, wolnych jest {free}.",
        "no_space": "Za malo miejsca: plik potrzebuje {needed}, "
                    "wolne jest {free}.",
        "too_big": "Plik ma {size} i nie zmiesci sie na nosniku "
                   "o pojemnosci {capacity}.",
        "dir_not_empty": "Katalog {name} nie jest pusty ({count} pozycji).",
        "not_a_folder": "{path} nie jest katalogiem.",
        "read_only": "Obraz otwarty tylko do odczytu.",
        # --- wiersz polecen ---
        "cli_desc": "Obrazy dyskietek FAT12 bez montowania i bez sudo.",
        "cli_lang": "jezyk komunikatow: pl albo en",
        "cli_create": "utworz i sformatuj obraz",
        "cli_force": "nadpisz istniejacy",
        "cli_list": "pokaz zawartosc",
        "cli_add": "skopiuj plik na dyskietke",
        "cli_extract": "skopiuj plik z dyskietki",
        "cli_mkdir": "utworz katalog",
        "cli_addtree": "skopiuj katalog z podkatalogami",
        "cli_tree": "Skopiowano {files} plikow "
                    "i {dirs} katalogow ({bytes} B)",
        "cli_rm": "usun plik lub katalog",
        "cli_created": "Utworzono {path} ({fmt})",
        "cli_media": "Nosnik: {fmt}",
        "cli_label": "   Etykieta: {label}",
        "cli_dir": "<KAT>",
        "cli_free": "Wolne: {free} z {total}",
        "cli_mkdir_ok": "Utworzono katalog {name}",
        "cli_removed": "Usunieto {path}",
        "cli_error": "Blad: {msg}",
        "cli_io_error": "Blad wejscia/wyjscia: {msg}",
    },
    "en": {
        "noname": "NO NAME",
        "exists": "File {path} already exists. Operation cancelled "
                  "so that no data is overwritten.",
        "no_unique_83": "Could not generate a unique 8.3 name.",
        "too_small": "File is too small to be a floppy image.",
        "no_signature": "No 0x55AA signature - this is not a floppy image.",
        "odd_sector": "Unusual sector size ({size} B).",
        "bad_bpb": "Damaged BPB block in the boot sector.",
        "looks_fat32": "Image looks like FAT32 - only FAT12 is supported.",
        "fat_loop": "Loop detected in the FAT - the image is damaged.",
        "not_fat12": "Image uses FAT16 or FAT32. "
                     "This program only supports FAT12.",
        "truncated": "File is shorter than the BPB declares "
                     "({actual} B instead of {expected} B).",
        "root_full": "The root directory is full.",
        "root_full_limit": "The root directory is full (limit {limit} "
                           "entries). Create a subdirectory.",
        "no_dir": "No such directory: {path}",
        "not_a_dir": "{name} is a file, not a directory.",
        "is_a_dir": "{name} is a directory.",
        "no_file": "No such file: {path}",
        "no_entry": "No such entry: {path}",
        "file_exists": "File {name} already exists.",
        "entry_exists": "Entry {name} already exists.",
        "no_clusters": "Not enough room on the floppy - {needed} clusters "
                       "needed, only {free} free.",
        "no_space": "Not enough room: the file needs {needed}, "
                    "{free} free.",
        "too_big": "The file is {size} and will not fit on a "
                   "{capacity} medium.",
        "dir_not_empty": "Directory {name} is not empty ({count} entries).",
        "not_a_folder": "{path} is not a directory.",
        "read_only": "Image opened read-only.",
        # --- command line ---
        "cli_desc": "FAT12 floppy images without mounting and without sudo.",
        "cli_lang": "message language: pl or en",
        "cli_create": "create and format an image",
        "cli_force": "overwrite an existing file",
        "cli_list": "show contents",
        "cli_add": "copy a file onto the floppy",
        "cli_extract": "copy a file off the floppy",
        "cli_mkdir": "create a directory",
        "cli_addtree": "copy a folder with its subfolders",
        "cli_tree": "Copied {files} files "
                    "and {dirs} folders ({bytes} B)",
        "cli_rm": "delete a file or directory",
        "cli_created": "Created {path} ({fmt})",
        "cli_media": "Medium: {fmt}",
        "cli_label": "   Label: {label}",
        "cli_dir": "<DIR>",
        "cli_free": "Free: {free} of {total}",
        "cli_mkdir_ok": "Created directory {name}",
        "cli_removed": "Removed {path}",
        "cli_error": "Error: {msg}",
        "cli_io_error": "I/O error: {msg}",
    },
}


def set_language(lang: str) -> None:
    """Ustawia jezyk komunikatow i etykiet formatow ("pl" albo "en")."""
    global _LANG
    _LANG = lang if lang in MESSAGES else "pl"


def get_language() -> str:
    return _LANG


def _t(key: str, **kwargs) -> str:
    """Komunikat w biezacym jezyku, z awaryjnym powrotem do polskiego."""
    text = MESSAGES.get(_LANG, MESSAGES["pl"]).get(key) or MESSAGES["pl"][key]
    return text.format(**kwargs) if kwargs else text


try:
    from engines import ImageError as _ImageError
except ImportError:          # fat12 dziala takze bez reszty projektu
    _ImageError = Exception


class Fat12Error(_ImageError):
    """
    Blad operacji na obrazie dyskietki.

    Dziedziczy po wspolnym przodku bledow silnikow, zeby interfejs mogl
    lapac jeden typ niezaleznie od tego, ktory system plikow otworzyl.
    """


# --------------------------------------------------------------------------
#  Definicje formatow dyskietek
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class FloppyFormat:
    """Parametry geometryczne jednego typu dyskietki."""

    key: str
    label_pl: str            # opis dla uzytkownika po polsku
    label_en: str            # to samo po angielsku
    total_sectors: int
    sectors_per_cluster: int
    root_entries: int
    media_descriptor: int
    sectors_per_fat: int
    sectors_per_track: int
    heads: int
    bytes_per_sector: int = BYTES_PER_SECTOR
    group: str = "popular"      # "popular" albo "other" - podzial w interfejsie

    @property
    def label(self) -> str:
        """Opis formatu w jezyku ustawionym przez set_language()."""
        return self.label_en if _LANG == "en" else self.label_pl

    @property
    def size_bytes(self) -> int:
        return self.total_sectors * self.bytes_per_sector

    @property
    def size_kb(self) -> int:
        return self.size_bytes // 1024


# Parametry zgodne z oryginalnymi dyskietkami IBM PC. Wartosci sectors_per_fat,
# media_descriptor i root_entries sa historyczne - DOS rozpoznaje nosnik takze
# po samym deskryptorze nosnika, wiec musza sie zgadzac co do bajtu.
FLOPPY_FORMATS: dict[str, FloppyFormat] = {
    "360": FloppyFormat(
        key="360",
        label_pl='5,25" 360 KB  (PC/XT)',
        label_en='5.25" 360 KB  (PC/XT)',
        total_sectors=720,
        sectors_per_cluster=2,
        root_entries=112,
        media_descriptor=0xFD,
        sectors_per_fat=2,
        sectors_per_track=9,
        heads=2,
    ),
    "1200": FloppyFormat(
        key="1200",
        label_pl='5,25" 1,2 MB  (AT/286)',
        label_en='5.25" 1.2 MB  (AT/286)',
        total_sectors=2400,
        sectors_per_cluster=1,
        root_entries=224,
        media_descriptor=0xF9,
        sectors_per_fat=7,
        sectors_per_track=15,
        heads=2,
    ),
    "720": FloppyFormat(
        key="720",
        label_pl='3,5"  720 KB  (Double Density)',
        label_en='3.5"  720 KB  (Double Density)',
        total_sectors=1440,
        sectors_per_cluster=2,
        root_entries=112,
        media_descriptor=0xF9,
        sectors_per_fat=3,
        sectors_per_track=9,
        heads=2,
    ),
    "1440": FloppyFormat(
        key="1440",
        label_pl='3,5"  1,44 MB (High Density)',
        label_en='3.5"  1.44 MB (High Density)',
        total_sectors=2880,
        sectors_per_cluster=1,
        root_entries=224,
        media_descriptor=0xF0,
        sectors_per_fat=9,
        sectors_per_track=18,
        heads=2,
    ),

    # --- formaty rzadsze, wczesne i nietypowe --------------------------
    "180": FloppyFormat(
        key="180",
        label_pl='5,25" 180 KB  (jednostronna)',
        label_en='5.25" 180 KB  (single-sided)',
        total_sectors=360,
        sectors_per_cluster=1,
        root_entries=64,
        media_descriptor=0xFC,
        sectors_per_fat=2,
        sectors_per_track=9,
        heads=1,
        group="other",
    ),
    "320": FloppyFormat(
        key="320",
        label_pl='5,25" 320 KB  (8 sektorow)',
        label_en='5.25" 320 KB  (8 sectors)',
        total_sectors=640,
        sectors_per_cluster=2,
        root_entries=112,
        media_descriptor=0xFF,
        sectors_per_fat=1,
        sectors_per_track=8,
        heads=2,
        group="other",
    ),
    "360_35": FloppyFormat(
        key="360_35",
        label_pl='3,5"  360 KB  (jednostronna DD)',
        label_en='3.5"  360 KB  (single-sided DD)',
        total_sectors=720,
        sectors_per_cluster=2,
        root_entries=112,
        media_descriptor=0xF8,
        sectors_per_fat=2,
        sectors_per_track=9,
        heads=1,
        group="other",
    ),
    "1250": FloppyFormat(
        key="1250",
        label_pl='3,5"  1,25 MB (NEC PC-98)',
        label_en='3.5"  1.25 MB (NEC PC-98)',
        total_sectors=1232,
        sectors_per_cluster=1,
        root_entries=192,
        media_descriptor=0xFE,
        sectors_per_fat=2,
        sectors_per_track=8,
        heads=2,
        bytes_per_sector=1024,
        group="other",
    ),
    "2880": FloppyFormat(
        key="2880",
        label_pl='3,5"  2,88 MB (Extra Density)',
        label_en='3.5"  2.88 MB (Extra Density)',
        total_sectors=5760,
        sectors_per_cluster=2,
        root_entries=240,
        media_descriptor=0xF0,
        sectors_per_fat=9,
        sectors_per_track=36,
        heads=2,
        group="other",
    ),
}


# --------------------------------------------------------------------------
#  Sektor rozruchowy
# --------------------------------------------------------------------------

def _boot_code(message: bytes) -> bytes:
    """
    Minimalny kod rozruchowy 16-bit: wypisuje komunikat przez INT 10h
    i zatrzymuje procesor. Zaczyna sie pod offsetem 0x3E sektora, czyli
    pod adresem 0x7C3E po zaladowaniu przez BIOS.
    """
    msg_addr = 0x7C00 + 0x5D
    code = bytes([
        0xFA,                          # cli
        0x31, 0xC0,                    # xor  ax, ax
        0x8E, 0xD8,                    # mov  ds, ax
        0x8E, 0xD0,                    # mov  ss, ax
        0xBC, 0x00, 0x7C,              # mov  sp, 0x7C00
        0xFB,                          # sti
        0xBE, msg_addr & 0xFF, msg_addr >> 8,   # mov si, msg
        0xAC,                          # .loop: lodsb
        0x08, 0xC0,                    # or   al, al
        0x74, 0x09,                    # jz   .halt
        0xB4, 0x0E,                    # mov  ah, 0x0E
        0xBB, 0x07, 0x00,              # mov  bx, 0x0007
        0xCD, 0x10,                    # int  0x10
        0xEB, 0xF2,                    # jmp  .loop
        0xF4,                          # .halt: hlt
        0xEB, 0xFD,                    # jmp  .halt
    ])
    return code + message + b"\x00"


def _build_boot_sector(fmt: FloppyFormat, volume_label: str,
                       volume_id: int | None = None) -> bytes:
    """Buduje 512-bajtowy sektor rozruchowy z blokiem BPB."""
    if volume_id is None:
        now = datetime.datetime.now()
        volume_id = ((now.year & 0xFF) << 24) | (now.month << 16) \
            | (now.day << 8) | (now.second & 0xFF)
        volume_id ^= (now.microsecond & 0xFFFF)

    sector = bytearray(fmt.bytes_per_sector)

    # Skok do kodu rozruchowego pod 0x3E + nazwa producenta
    sector[0x00:0x03] = bytes([0xEB, 0x3C, 0x90])
    sector[0x03:0x0B] = b"RETROZAC"

    # BPB (BIOS Parameter Block), DOS 4.0
    struct.pack_into("<H", sector, 0x0B, fmt.bytes_per_sector)
    sector[0x0D] = fmt.sectors_per_cluster
    struct.pack_into("<H", sector, 0x0E, 1)          # sektory zarezerwowane
    sector[0x10] = 2                                 # liczba kopii FAT
    struct.pack_into("<H", sector, 0x11, fmt.root_entries)
    struct.pack_into("<H", sector, 0x13, fmt.total_sectors)
    sector[0x15] = fmt.media_descriptor
    struct.pack_into("<H", sector, 0x16, fmt.sectors_per_fat)
    struct.pack_into("<H", sector, 0x18, fmt.sectors_per_track)
    struct.pack_into("<H", sector, 0x1A, fmt.heads)
    struct.pack_into("<I", sector, 0x1C, 0)          # sektory ukryte
    struct.pack_into("<I", sector, 0x20, 0)          # total_sectors_32

    # Rozszerzony blok rozruchowy
    sector[0x24] = 0x00                              # numer napedu (A:)
    sector[0x25] = 0x00
    sector[0x26] = 0x29                              # sygnatura rozszerzenia
    struct.pack_into("<I", sector, 0x27, volume_id & 0xFFFFFFFF)
    sector[0x2B:0x36] = _pad_label(volume_label)
    sector[0x36:0x3E] = b"FAT12   "

    code = _boot_code(b"Nosnik nie jest startowy.\r\n"
                      b"RetroZachar FFD Disk Maker\r\n")
    sector[0x3E:0x3E + len(code)] = code

    sector[0x1FE] = 0x55
    sector[0x1FF] = 0xAA
    return bytes(sector)


def _pad_label(label: str) -> bytes:
    """Zamienia etykiete wolumenu na 11 bajtow ASCII, wielkimi literami."""
    clean = "".join(
        ch for ch in label.upper()
        if ch not in ILLEGAL_83 and 0x20 <= ord(ch) < 0x7F
    )
    if not clean:
        # Zapis na nosniku nie moze zalezec od jezyka interfejsu.
        # DOS w takiej sytuacji wpisuje zawsze "NO NAME".
        clean = "NO NAME"
    return clean[:11].ljust(11).encode("ascii", "replace")


# --------------------------------------------------------------------------
#  Formatowanie
# --------------------------------------------------------------------------

def build_image(fmt: FloppyFormat, volume_label: str = "") -> bytearray:
    """
    Buduje w pamieci kompletny, pusty system plikow FAT12: sektor rozruchowy,
    obie kopie tablicy FAT, katalog glowny i wyzerowany obszar danych.

    Wydzielone z format_image, bo formatowanie fizycznej dyskietki potrzebuje
    obrazu w pamieci - zeby przed zapisem oznaczyc w tablicy FAT klastry,
    ktore nie przeszly testu powierzchni.
    """
    image = bytearray(fmt.size_bytes)
    image[0:fmt.bytes_per_sector] = _build_boot_sector(fmt, volume_label)

    # Obie kopie tablicy FAT. Pierwsze dwa wpisy sa zarezerwowane:
    # wpis 0 przechowuje deskryptor nosnika, wpis 1 jest zawsze 0xFFF.
    fat = bytearray(fmt.sectors_per_fat * fmt.bytes_per_sector)
    fat[0] = fmt.media_descriptor
    fat[1] = 0xFF
    fat[2] = 0xFF
    for copy in range(2):
        start = (1 + copy * fmt.sectors_per_fat) * fmt.bytes_per_sector
        image[start:start + len(fat)] = fat

    # Etykieta wolumenu jako pierwszy wpis w katalogu glownym
    if volume_label.strip():
        root_start = (1 + 2 * fmt.sectors_per_fat) * fmt.bytes_per_sector
        entry = bytearray(DIR_ENTRY_SIZE)
        entry[0x00:0x0B] = _pad_label(volume_label)
        entry[0x0B] = ATTR_VOLUME_ID
        t, d = _encode_datetime(datetime.datetime.now())
        struct.pack_into("<HH", entry, 0x16, t, d)
        image[root_start:root_start + DIR_ENTRY_SIZE] = entry

    return image


def data_start_sector(fmt: FloppyFormat) -> int:
    """Numer pierwszego sektora obszaru danych, czyli poczatku klastra 2."""
    root_sectors = (
        fmt.root_entries * DIR_ENTRY_SIZE + fmt.bytes_per_sector - 1
    ) // fmt.bytes_per_sector
    return 1 + 2 * fmt.sectors_per_fat + root_sectors


def mark_bad_clusters(image: bytearray, fmt: FloppyFormat,
                      sectors: list[int]) -> tuple[int, int]:
    """
    Oznacza w obu tablicach FAT klastry zawierajace wskazane sektory jako
    uszkodzone (0xFF7), tak jak robi to DOS-owy FORMAT. System nie bedzie
    juz probowal ich uzyc.

    Zwraca liczbe oznaczonych klastrow oraz liczbe uszkodzonych sektorow
    lezacych poza obszarem danych. Te ostatnie trafiaja w sektor rozruchowy,
    tablice FAT albo katalog glowny i nie da sie ich obejsc - taki nosnik
    nadaje sie do wyrzucenia.
    """
    first_data = data_start_sector(fmt)
    total_clusters = (
        fmt.total_sectors - first_data
    ) // fmt.sectors_per_cluster

    critical = 0
    clusters: set[int] = set()
    for sector in sectors:
        if sector < first_data:
            critical += 1
            continue
        cluster = (sector - first_data) // fmt.sectors_per_cluster + 2
        if 2 <= cluster <= total_clusters + 1:
            clusters.add(cluster)

    for cluster in clusters:
        for copy in range(2):
            base = (1 + copy * fmt.sectors_per_fat) * fmt.bytes_per_sector
            index = base + cluster + (cluster >> 1)
            pair = image[index] | (image[index + 1] << 8)
            if cluster & 1:
                pair = (pair & 0x000F) | (FAT_BAD << 4)
            else:
                pair = (pair & 0xF000) | FAT_BAD
            image[index] = pair & 0xFF
            image[index + 1] = (pair >> 8) & 0xFF

    return len(clusters), critical


def format_image(path: str | os.PathLike, fmt: FloppyFormat,
                 volume_label: str = "", overwrite: bool = False) -> None:
    """
    Tworzy nowy obraz dyskietki i zapisuje na nim pusty system plikow FAT12.

    Odpowiednik `dd if=/dev/zero ... && mkfs.fat -F 12`, ale bez wywolywania
    czegokolwiek z zewnatrz. Domyslnie odmawia nadpisania istniejacego pliku.
    """
    path = os.fspath(path)
    if os.path.exists(path) and not overwrite:
        raise Fat12Error(_t("exists", path=path))

    image = build_image(fmt, volume_label)
    tmp = path + ".part"
    with open(tmp, "wb") as fh:
        fh.write(image)
    os.replace(tmp, path)


# --------------------------------------------------------------------------
#  Nazwy 8.3 oraz daty
# --------------------------------------------------------------------------

def to_short_name(name: str, taken: set[str] | None = None) -> str:
    """
    Zamienia dowolna nazwe pliku na nazwe 8.3 akceptowana przez DOS.

    Znaki niedozwolone zastepuje podkresleniem, skraca zbyt dlugie czlony
    i - jesli nazwa juz zajeta - dokleja tylde z numerem (PLIK~1.TXT).
    """
    taken = {n.upper() for n in (taken or set())}
    name = name.strip().rstrip(".")
    if not name:
        name = "PLIK"

    base, dot, ext = name.rpartition(".")
    if not dot:
        base, ext = name, ""

    def clean(part: str) -> str:
        out = []
        for ch in part.upper():
            if ch in ILLEGAL_83 or ord(ch) < 0x20:
                out.append("_")
            elif ord(ch) > 0x7E:
                out.append("_")
            elif ch == " ":
                continue
            else:
                out.append(ch)
        return "".join(out)

    base = clean(base) or "PLIK"
    ext = clean(ext)[:3]

    def compose(stem: str) -> str:
        return f"{stem}.{ext}" if ext else stem

    candidate = compose(base[:8])
    if candidate.upper() not in taken:
        return candidate

    for n in range(1, 1000):
        suffix = f"~{n}"
        stem = base[:8 - len(suffix)] + suffix
        candidate = compose(stem)
        if candidate.upper() not in taken:
            return candidate
    raise Fat12Error(_t("no_unique_83"))


def _encode_datetime(dt: datetime.datetime) -> tuple[int, int]:
    """Koduje date i czas w formacie FAT (rozdzielczosc 2 sekundy)."""
    year = max(1980, min(2107, dt.year))
    time_val = (dt.hour << 11) | (dt.minute << 5) | (dt.second // 2)
    date_val = ((year - 1980) << 9) | (dt.month << 5) | dt.day
    return time_val, date_val


def _decode_datetime(time_val: int, date_val: int) -> datetime.datetime | None:
    if date_val == 0:
        return None
    try:
        return datetime.datetime(
            1980 + ((date_val >> 9) & 0x7F),
            max(1, (date_val >> 5) & 0x0F),
            max(1, date_val & 0x1F),
            (time_val >> 11) & 0x1F,
            (time_val >> 5) & 0x3F,
            (time_val & 0x1F) * 2,
        )
    except ValueError:
        return None


# --------------------------------------------------------------------------
#  Wpis katalogowy
# --------------------------------------------------------------------------

@dataclass
class DirEntry:
    """Pojedynczy wpis w katalogu obrazu."""

    name: str                       # nazwa w postaci 8.3, np. AUTOEXEC.BAT
    attributes: int
    first_cluster: int
    size: int
    modified: datetime.datetime | None
    slot: int = field(default=-1, repr=False)   # indeks wpisu w katalogu

    @property
    def is_dir(self) -> bool:
        return bool(self.attributes & ATTR_DIRECTORY)

    @property
    def is_readonly(self) -> bool:
        return bool(self.attributes & ATTR_READ_ONLY)

    @property
    def is_hidden(self) -> bool:
        return bool(self.attributes & (ATTR_HIDDEN | ATTR_SYSTEM))

    def attr_string(self) -> str:
        flags = [
            "R" if self.attributes & ATTR_READ_ONLY else "-",
            "H" if self.attributes & ATTR_HIDDEN else "-",
            "S" if self.attributes & ATTR_SYSTEM else "-",
            "A" if self.attributes & ATTR_ARCHIVE else "-",
        ]
        return "".join(flags)


def _parse_entry(raw: bytes, slot: int) -> DirEntry:
    stem = raw[0:8].decode("cp437").rstrip()
    ext = raw[8:11].decode("cp437").rstrip()
    name = f"{stem}.{ext}" if ext else stem
    attributes = raw[0x0B]
    time_val, date_val = struct.unpack_from("<HH", raw, 0x16)
    cluster = struct.unpack_from("<H", raw, 0x1A)[0]
    size = struct.unpack_from("<I", raw, 0x1C)[0]
    return DirEntry(
        name=name,
        attributes=attributes,
        first_cluster=cluster,
        size=size,
        modified=_decode_datetime(time_val, date_val),
        slot=slot,
    )


def _build_entry(name: str, attributes: int, cluster: int, size: int,
                 modified: datetime.datetime | None = None) -> bytes:
    raw = bytearray(DIR_ENTRY_SIZE)
    if name in (".", ".."):
        # Wpisy "." i ".." zajmuja cale 11-bajtowe pole nazwy i nie dziela
        # sie na rdzen i rozszerzenie - inaczej fsck uznaje katalog za wadliwy.
        raw[0:11] = name.ljust(11).encode("ascii")
    else:
        stem, _, ext = name.partition(".")
        raw[0:8] = stem[:8].upper().ljust(8).encode("cp437", "replace")
        raw[8:11] = ext[:3].upper().ljust(3).encode("cp437", "replace")
    raw[0x0B] = attributes
    t, d = _encode_datetime(modified or datetime.datetime.now())
    struct.pack_into("<HH", raw, 0x0E, t, d)     # data utworzenia
    struct.pack_into("<H", raw, 0x12, d)         # data ostatniego dostepu
    struct.pack_into("<HH", raw, 0x16, t, d)     # data modyfikacji
    struct.pack_into("<H", raw, 0x1A, cluster)
    struct.pack_into("<I", raw, 0x1C, size)
    return bytes(raw)


# --------------------------------------------------------------------------
#  Obraz dyskietki
# --------------------------------------------------------------------------

class Fat12Image:
    """
    Otwarty obraz dyskietki FAT12.

    Caly obraz (najwyzej 1,44 MB) trzymany jest w pamieci; kazda operacja
    zapisu od razu zrzuca zmiany na dysk, wiec przerwanie programu nie
    zostawia obrazu w polowicznym stanie.

    Sciezki wewnatrz obrazu zapisuje sie z ukosnikiem, np. "/DOS/COMMAND.COM".
    """

    def __init__(self, path: str | os.PathLike, read_only: bool = False):
        self.path = os.fspath(path)
        self.read_only = read_only
        with open(self.path, "rb") as fh:
            self.data = bytearray(fh.read())
        self._parse_bpb()

    @classmethod
    def from_bytes(cls, data: bytearray, name: str = "",
                   read_only: bool = True) -> "Fat12Image":
        """
        Buduje obraz na gotowym buforze, bez pliku na dysku.

        Uzywane przy podgladzie fizycznej dyskietki: bufor jest wypelniany
        sektorami czytanymi z napedu na zadanie, wiec do wyswietlenia listy
        plikow wystarczy sam obszar systemowy zamiast calego nosnika.
        """
        image = cls.__new__(cls)
        image.path = name
        image.read_only = read_only
        image.data = data
        image._parse_bpb()
        return image

    # -- kontekst ----------------------------------------------------------

    def __enter__(self) -> "Fat12Image":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.data = bytearray()

    # -- odczyt BPB --------------------------------------------------------

    def _parse_bpb(self) -> None:
        d = self.data
        if len(d) < 512:
            raise Fat12Error(_t("too_small"))
        if d[0x1FE] != 0x55 or d[0x1FF] != 0xAA:
            raise Fat12Error(_t("no_signature"))

        self.bytes_per_sector = struct.unpack_from("<H", d, 0x0B)[0]
        self.sectors_per_cluster = d[0x0D]
        self.reserved_sectors = struct.unpack_from("<H", d, 0x0E)[0]
        self.num_fats = d[0x10]
        self.root_entries = struct.unpack_from("<H", d, 0x11)[0]
        total16 = struct.unpack_from("<H", d, 0x13)[0]
        self.media_descriptor = d[0x15]
        self.sectors_per_fat = struct.unpack_from("<H", d, 0x16)[0]
        self.sectors_per_track = struct.unpack_from("<H", d, 0x18)[0]
        self.heads = struct.unpack_from("<H", d, 0x1A)[0]
        total32 = struct.unpack_from("<I", d, 0x20)[0]
        self.total_sectors = total16 or total32

        if self.bytes_per_sector not in (512, 1024, 2048, 4096):
            raise Fat12Error(
                _t("odd_sector", size=self.bytes_per_sector))
        if self.sectors_per_cluster == 0 or self.num_fats == 0:
            raise Fat12Error(_t("bad_bpb"))
        if self.root_entries == 0:
            raise Fat12Error(_t("looks_fat32"))

        self.root_dir_sectors = (
            self.root_entries * DIR_ENTRY_SIZE + self.bytes_per_sector - 1
        ) // self.bytes_per_sector
        self.root_dir_start = (
            self.reserved_sectors + self.num_fats * self.sectors_per_fat
        )
        self.data_start = self.root_dir_start + self.root_dir_sectors
        self.cluster_count = (
            self.total_sectors - self.data_start
        ) // self.sectors_per_cluster
        self.max_cluster = self.cluster_count + 1     # numeracja od 2

        if self.cluster_count >= 4085:
            raise Fat12Error(_t("not_fat12"))
        expected = self.total_sectors * self.bytes_per_sector
        if len(self.data) < expected:
            raise Fat12Error(_t(
                "truncated", actual=len(self.data), expected=expected))

    # -- wlasciwosci -------------------------------------------------------

    @property
    def cluster_size(self) -> int:
        return self.sectors_per_cluster * self.bytes_per_sector

    @property
    def total_bytes(self) -> int:
        return self.cluster_count * self.cluster_size

    @property
    def free_bytes(self) -> int:
        free = sum(
            1 for c in range(2, self.max_cluster + 1)
            if self._fat_get(c) == FAT_FREE
        )
        return free * self.cluster_size

    @property
    def used_bytes(self) -> int:
        return self.total_bytes - self.free_bytes

    @property
    def format_name(self) -> str:
        kb = self.total_sectors * self.bytes_per_sector // 1024
        for fmt in FLOPPY_FORMATS.values():
            if fmt.size_kb == kb:
                return fmt.label
        return f"{kb} KB"

    def get_label(self) -> str:
        """Etykieta wolumenu z katalogu glownego, a w razie braku - z BPB."""
        for slot, raw in self._raw_entries(self._root_bytes()):
            if raw[0] in (ENTRY_FREE, ENTRY_DELETED):
                continue
            if raw[0x0B] == ATTR_VOLUME_ID:
                return raw[0:11].decode("cp437").rstrip()
        if self.data[0x26] == 0x29:
            return self.data[0x2B:0x36].decode("cp437").rstrip()
        return ""

    def set_label(self, label: str) -> None:
        self._check_writable()
        padded = _pad_label(label)
        root = self._root_bytes()
        target = None
        for slot, raw in self._raw_entries(root):
            if raw[0] in (ENTRY_FREE, ENTRY_DELETED):
                if target is None:
                    target = slot
                if raw[0] == ENTRY_FREE:
                    break
                continue
            if raw[0x0B] == ATTR_VOLUME_ID:
                target = slot
                break
        if target is None:
            raise Fat12Error(_t("root_full"))

        entry = bytearray(DIR_ENTRY_SIZE)
        entry[0x00:0x0B] = padded
        entry[0x0B] = ATTR_VOLUME_ID
        t, d = _encode_datetime(datetime.datetime.now())
        struct.pack_into("<HH", entry, 0x16, t, d)
        root[target * DIR_ENTRY_SIZE:(target + 1) * DIR_ENTRY_SIZE] = entry
        self._write_root(root)
        self.data[0x2B:0x36] = padded
        self._flush()

    # -- tablica FAT -------------------------------------------------------

    def _fat_offset(self, copy: int = 0) -> int:
        return (
            self.reserved_sectors + copy * self.sectors_per_fat
        ) * self.bytes_per_sector

    def _fat_get(self, cluster: int) -> int:
        base = self._fat_offset()
        idx = base + cluster + (cluster >> 1)      # cluster * 1.5
        pair = self.data[idx] | (self.data[idx + 1] << 8)
        return (pair >> 4) if (cluster & 1) else (pair & 0x0FFF)

    def _fat_set(self, cluster: int, value: int) -> None:
        value &= 0x0FFF
        for copy in range(self.num_fats):
            base = self._fat_offset(copy)
            idx = base + cluster + (cluster >> 1)
            pair = self.data[idx] | (self.data[idx + 1] << 8)
            if cluster & 1:
                pair = (pair & 0x000F) | (value << 4)
            else:
                pair = (pair & 0xF000) | value
            self.data[idx] = pair & 0xFF
            self.data[idx + 1] = (pair >> 8) & 0xFF

    def _chain(self, first: int) -> list[int]:
        """Zwraca liste klastrow tworzacych lancuch, z ochrona przed petla."""
        chain: list[int] = []
        seen: set[int] = set()
        cluster = first
        while 2 <= cluster <= self.max_cluster:
            if cluster in seen:
                raise Fat12Error(_t("fat_loop"))
            seen.add(cluster)
            chain.append(cluster)
            cluster = self._fat_get(cluster)
            if cluster >= FAT_BAD:
                break
        return chain

    def _free_clusters(self) -> Iterator[int]:
        for c in range(2, self.max_cluster + 1):
            if self._fat_get(c) == FAT_FREE:
                yield c

    def _allocate(self, count: int) -> list[int]:
        chain: list[int] = []
        for cluster in self._free_clusters():
            chain.append(cluster)
            if len(chain) == count:
                break
        if len(chain) < count:
            raise Fat12Error(
                _t("no_clusters", needed=count, free=len(chain)))
        for i, cluster in enumerate(chain):
            nxt = chain[i + 1] if i + 1 < len(chain) else FAT_EOC
            self._fat_set(cluster, nxt)
        return chain

    def _release(self, first: int) -> None:
        for cluster in self._chain(first):
            self._fat_set(cluster, FAT_FREE)

    # -- obszar danych -----------------------------------------------------

    def _cluster_offset(self, cluster: int) -> int:
        sector = self.data_start + (cluster - 2) * self.sectors_per_cluster
        return sector * self.bytes_per_sector

    def _read_chain(self, first: int) -> bytearray:
        out = bytearray()
        for cluster in self._chain(first):
            off = self._cluster_offset(cluster)
            out += self.data[off:off + self.cluster_size]
        return out

    def _write_chain(self, first: int, payload: bytes) -> None:
        """Zapisuje dane w istniejacym lancuchu (musi byc dosc dlugi)."""
        chunks = [
            payload[i:i + self.cluster_size]
            for i in range(0, max(len(payload), 1), self.cluster_size)
        ]
        for cluster, chunk in zip(self._chain(first), chunks):
            off = self._cluster_offset(cluster)
            self.data[off:off + self.cluster_size] = \
                chunk.ljust(self.cluster_size, b"\x00")

    # -- katalogi ----------------------------------------------------------

    def _root_bytes(self) -> bytearray:
        start = self.root_dir_start * self.bytes_per_sector
        end = start + self.root_dir_sectors * self.bytes_per_sector
        return bytearray(self.data[start:end])

    def _write_root(self, buf: bytes) -> None:
        start = self.root_dir_start * self.bytes_per_sector
        self.data[start:start + len(buf)] = buf

    @staticmethod
    def _raw_entries(buf: bytes) -> Iterator[tuple[int, bytes]]:
        for slot in range(len(buf) // DIR_ENTRY_SIZE):
            off = slot * DIR_ENTRY_SIZE
            yield slot, buf[off:off + DIR_ENTRY_SIZE]

    def _dir_bytes(self, cluster: int) -> bytearray:
        """Zawartosc katalogu: glownego (cluster == 0) albo podkatalogu."""
        return self._root_bytes() if cluster == 0 \
            else self._read_chain(cluster)

    def _write_dir(self, cluster: int, buf: bytes) -> None:
        if cluster == 0:
            self._write_root(buf)
        else:
            self._write_chain(cluster, buf)

    def _resolve_dir(self, path: str) -> int:
        """Zamienia sciezke katalogu na numer jego pierwszego klastra."""
        cluster = 0
        for part in _split_path(path):
            entry = self._find_in(cluster, part)
            if entry is None:
                raise Fat12Error(_t("no_dir", path=path))
            if not entry.is_dir:
                raise Fat12Error(_t("not_a_dir", name=part))
            cluster = entry.first_cluster
        return cluster

    def _find_in(self, dir_cluster: int, name: str) -> DirEntry | None:
        wanted = name.upper()
        for entry in self._entries_in(dir_cluster):
            if entry.name.upper() == wanted:
                return entry
        return None

    def _entries_in(self, dir_cluster: int,
                    include_dots: bool = False) -> list[DirEntry]:
        out: list[DirEntry] = []
        for slot, raw in self._raw_entries(self._dir_bytes(dir_cluster)):
            first = raw[0]
            if first == ENTRY_FREE:
                break
            if first == ENTRY_DELETED:
                continue
            attributes = raw[0x0B]
            if attributes == ATTR_LONG_NAME:      # fragment dlugiej nazwy
                continue
            if attributes & ATTR_VOLUME_ID:       # etykieta wolumenu
                continue
            entry = _parse_entry(raw, slot)
            if not include_dots and entry.name in (".", ".."):
                continue
            out.append(entry)
        return out

    def _alloc_slot(self, dir_cluster: int) -> tuple[int, bytearray]:
        """
        Znajduje wolny wpis w katalogu. Podkatalog w razie potrzeby zostaje
        rozszerzony o kolejny klaster; katalog glowny ma staly rozmiar.
        """
        buf = self._dir_bytes(dir_cluster)
        for slot, raw in self._raw_entries(buf):
            if raw[0] in (ENTRY_FREE, ENTRY_DELETED):
                return slot, buf

        if dir_cluster == 0:
            raise Fat12Error(
                _t("root_full_limit", limit=self.root_entries))

        chain = self._chain(dir_cluster)
        new_cluster = self._allocate(1)[0]
        self._fat_set(chain[-1], new_cluster)
        self._fat_set(new_cluster, FAT_EOC)
        off = self._cluster_offset(new_cluster)
        self.data[off:off + self.cluster_size] = b"\x00" * self.cluster_size
        slot = len(buf) // DIR_ENTRY_SIZE
        buf += bytearray(self.cluster_size)
        return slot, buf

    def _put_entry(self, dir_cluster: int, buf: bytearray, slot: int,
                   raw: bytes) -> None:
        buf[slot * DIR_ENTRY_SIZE:(slot + 1) * DIR_ENTRY_SIZE] = raw
        self._write_dir(dir_cluster, buf)

    # -- API publiczne -----------------------------------------------------

    # -- pomocnicze operacje na sciezkach ----------------------------------
    #
    #  Wystawione jako metody obrazu, bo kazdy system plikow ma tu wlasne
    #  zasady: FAT12 tnie nazwy do 8.3, AmigaDOS dopuszcza trzydziesci
    #  znakow. Interfejs pyta o to obraz, zamiast wolac funkcje z fat12.

    @staticmethod
    def join(*parts: str) -> str:
        """Sklada sciezke wewnatrz obrazu."""
        return _join(*parts)

    @staticmethod
    def parent(path: str) -> str:
        """Katalog nadrzedny podanej sciezki."""
        return _split_parent(path)[0]

    @staticmethod
    def short_name(name: str) -> str:
        """Nazwa sprowadzona do postaci akceptowanej przez ten system."""
        return to_short_name(name)

    def listdir(self, path: str = "/") -> list[DirEntry]:
        """Zwraca zawartosc katalogu: najpierw katalogi, potem pliki."""
        cluster = self._resolve_dir(path)
        entries = self._entries_in(cluster)
        entries.sort(key=lambda e: (not e.is_dir, e.name))
        return entries

    def exists(self, path: str) -> bool:
        parent, name = _split_parent(path)
        if not name:
            return True
        try:
            return self._find_in(self._resolve_dir(parent), name) is not None
        except Fat12Error:
            return False

    def stat(self, path: str) -> DirEntry:
        parent, name = _split_parent(path)
        entry = self._find_in(self._resolve_dir(parent), name)
        if entry is None:
            raise Fat12Error(_t("no_file", path=path))
        return entry

    def read_file(self, path: str) -> bytes:
        entry = self.stat(path)
        if entry.is_dir:
            raise Fat12Error(_t("is_a_dir", name=path))
        if entry.first_cluster == 0 or entry.size == 0:
            return b""
        return bytes(self._read_chain(entry.first_cluster)[:entry.size])

    def write_file(self, path: str, payload: bytes,
                   modified: datetime.datetime | None = None,
                   overwrite: bool = True) -> str:
        """
        Zapisuje plik w obrazie. Nazwa jest w razie potrzeby skracana do 8.3.
        Zwraca faktyczna nazwe, pod jaka plik trafil na dyskietke.
        """
        self._check_writable()
        parent, raw_name = _split_parent(path)
        dir_cluster = self._resolve_dir(parent)

        existing = self._find_in(dir_cluster, raw_name)
        if existing is None:
            taken = {e.name for e in self._entries_in(dir_cluster, True)}
            name = to_short_name(raw_name, taken)
            existing = None
        else:
            if not overwrite:
                raise Fat12Error(_t("file_exists", name=raw_name))
            if existing.is_dir:
                raise Fat12Error(_t("is_a_dir", name=raw_name))
            name = existing.name

        needed = (len(payload) + self.cluster_size - 1) // self.cluster_size
        if existing is not None and existing.first_cluster:
            self._release(existing.first_cluster)
        if needed and needed > len(list(self._free_clusters())):
            if existing is not None and existing.first_cluster:
                # przywracamy stan sprzed proby - nie zostawiamy sierot
                self._reserve_chain(existing.first_cluster, existing.size)
            raise Fat12Error(_t(
                "no_space", needed=_human(len(payload)),
                free=_human(self.free_bytes)))

        first = self._allocate(needed)[0] if needed else 0
        if needed:
            self._write_chain(first, payload)

        raw = _build_entry(name, ATTR_ARCHIVE, first, len(payload), modified)
        if existing is not None:
            buf = self._dir_bytes(dir_cluster)
            slot = existing.slot
        else:
            slot, buf = self._alloc_slot(dir_cluster)
        self._put_entry(dir_cluster, buf, slot, raw)
        self._flush()
        return name

    def _reserve_chain(self, first: int, size: int) -> None:
        """Awaryjne odtworzenie lancucha klastrow po nieudanym zapisie."""
        count = max(1, (size + self.cluster_size - 1) // self.cluster_size)
        cluster = first
        for _ in range(count - 1):
            nxt = next(self._free_clusters(), None)
            if nxt is None:
                break
            self._fat_set(cluster, nxt)
            cluster = nxt
        self._fat_set(cluster, FAT_EOC)

    def import_file(self, host_path: str | os.PathLike,
                    dest_dir: str = "/") -> str:
        """Kopiuje plik z komputera na dyskietke."""
        host_path = os.fspath(host_path)
        size = os.path.getsize(host_path)
        if size > self.total_bytes:
            raise Fat12Error(_t(
                "too_big", size=_human(size),
                capacity=_human(self.total_bytes)))
        with open(host_path, "rb") as fh:
            payload = fh.read()
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(host_path))
        name = os.path.basename(host_path)
        return self.write_file(_join(dest_dir, name), payload, mtime)

    def export_file(self, path: str, host_path: str | os.PathLike) -> None:
        """Kopiuje plik z dyskietki na komputer."""
        entry = self.stat(path)
        with open(os.fspath(host_path), "wb") as fh:
            fh.write(self.read_file(path))
        if entry.modified:
            ts = entry.modified.timestamp()
            os.utime(host_path, (ts, ts))

    def ensure_dir(self, parent: str, raw_name: str) -> str:
        """
        Zwraca nazwe podkatalogu, tworzac go tylko wtedy, gdy jeszcze go nie
        ma. Przy kopiowaniu drzewa katalogow trafiamy na te same nazwy przy
        kolejnych plikach - bez tego kazdy z nich zakladalby kolejny katalog
        z tylda w nazwie.
        """
        dir_cluster = self._resolve_dir(parent)
        candidate = to_short_name(raw_name)
        existing = self._find_in(dir_cluster, candidate)
        if existing is not None and existing.is_dir:
            return existing.name
        return self.mkdir(_join(parent, raw_name))

    def import_tree(self, host_path: str | os.PathLike, dest_dir: str = "/",
                    include_root: bool = True, on_item=None) -> dict:
        """
        Kopiuje katalog z komputera na dyskietke wraz z cala zawartoscia
        i podkatalogami.

        include_root=True zaklada na dyskietce katalog o nazwie zrodlowego
        i wrzuca zawartosc do srodka; False kopiuje sama zawartosc do
        wskazanego miejsca.

        Zwraca podsumowanie: ile plikow i katalogow powstalo, ktore nazwy
        trzeba bylo skrocic i czego nie udalo sie skopiowac. Pojedyncza
        porazka - brak miejsca, pelny katalog glowny - nie przerywa calosci,
        tylko trafia do raportu, zeby uzytkownik wiedzial, czego brakuje.
        """
        self._check_writable()
        host_path = os.fspath(host_path)
        if not os.path.isdir(host_path):
            raise Fat12Error(_t("not_a_folder", path=host_path))

        report = {"files": 0, "dirs": 0, "bytes": 0,
                  "renamed": [], "failed": []}
        target = dest_dir
        if include_root:
            name = os.path.basename(os.path.normpath(host_path))
            created = self.ensure_dir(dest_dir, name)
            if created.upper() != name.upper():
                report["renamed"].append(f"{name} -> {created}")
            report["dirs"] += 1
            target = _join(dest_dir, created)

        self._copy_tree(host_path, target, report, on_item)
        return report

    def _copy_tree(self, src: str, dest: str, report: dict, on_item) -> None:
        try:
            entries = sorted(os.scandir(src), key=lambda e: e.name.lower())
        except OSError as exc:
            report["failed"].append(f"{src}: {exc}")
            return

        for entry in entries:
            # Dowiazania pomijamy - na dyskietce nie ma ich odpowiednika,
            # a podazanie za nimi grozi petla.
            if entry.is_symlink():
                continue
            if on_item:
                on_item(entry.path)
            try:
                if entry.is_dir():
                    created = self.ensure_dir(dest, entry.name)
                    if created.upper() != entry.name.upper():
                        report["renamed"].append(f"{entry.name} -> {created}")
                    report["dirs"] += 1
                    self._copy_tree(entry.path, _join(dest, created),
                                    report, on_item)
                elif entry.is_file():
                    size = entry.stat().st_size
                    final = self.import_file(entry.path, dest)
                    report["files"] += 1
                    report["bytes"] += size
                    if final.upper() != entry.name.upper():
                        report["renamed"].append(f"{entry.name} -> {final}")
            except (Fat12Error, OSError) as exc:
                report["failed"].append(f"{entry.name}: {exc}")

    def mkdir(self, path: str) -> str:
        """Tworzy katalog wraz z obowiazkowymi wpisami '.' i '..'."""
        self._check_writable()
        parent, raw_name = _split_parent(path)
        dir_cluster = self._resolve_dir(parent)
        if self._find_in(dir_cluster, raw_name):
            raise Fat12Error(_t("entry_exists", name=raw_name))

        taken = {e.name for e in self._entries_in(dir_cluster, True)}
        name = to_short_name(raw_name, taken)

        cluster = self._allocate(1)[0]
        off = self._cluster_offset(cluster)
        block = bytearray(self.cluster_size)
        now = datetime.datetime.now()
        block[0:DIR_ENTRY_SIZE] = _build_entry(
            ".", ATTR_DIRECTORY, cluster, 0, now)
        block[DIR_ENTRY_SIZE:2 * DIR_ENTRY_SIZE] = _build_entry(
            "..", ATTR_DIRECTORY, dir_cluster, 0, now)
        self.data[off:off + self.cluster_size] = block

        slot, buf = self._alloc_slot(dir_cluster)
        raw = _build_entry(name, ATTR_DIRECTORY, cluster, 0, now)
        self._put_entry(dir_cluster, buf, slot, raw)
        self._flush()
        return name

    def remove(self, path: str, recursive: bool = False) -> None:
        """Usuwa plik lub katalog."""
        self._check_writable()
        parent, name = _split_parent(path)
        dir_cluster = self._resolve_dir(parent)
        entry = self._find_in(dir_cluster, name)
        if entry is None:
            raise Fat12Error(_t("no_entry", path=path))

        if entry.is_dir:
            children = self._entries_in(entry.first_cluster)
            if children and not recursive:
                raise Fat12Error(
                    _t("dir_not_empty", name=name, count=len(children)))
            for child in children:
                self.remove(_join(path, child.name), recursive=True)

        if entry.first_cluster:
            self._release(entry.first_cluster)
        buf = self._dir_bytes(dir_cluster)
        buf[entry.slot * DIR_ENTRY_SIZE] = ENTRY_DELETED
        self._write_dir(dir_cluster, buf)
        self._flush()

    def rename(self, path: str, new_name: str) -> str:
        self._check_writable()
        parent, name = _split_parent(path)
        dir_cluster = self._resolve_dir(parent)
        entry = self._find_in(dir_cluster, name)
        if entry is None:
            raise Fat12Error(_t("no_entry", path=path))

        taken = {
            e.name for e in self._entries_in(dir_cluster, True)
            if e.slot != entry.slot
        }
        final = to_short_name(new_name, taken)
        raw = bytearray(
            self._dir_bytes(dir_cluster)[
                entry.slot * DIR_ENTRY_SIZE:(entry.slot + 1) * DIR_ENTRY_SIZE
            ]
        )
        stem, _, ext = final.partition(".")
        raw[0:8] = stem[:8].upper().ljust(8).encode("cp437", "replace")
        raw[8:11] = ext[:3].upper().ljust(3).encode("cp437", "replace")
        buf = self._dir_bytes(dir_cluster)
        self._put_entry(dir_cluster, buf, entry.slot, bytes(raw))
        self._flush()
        return final

    # -- zapis na dysk -----------------------------------------------------

    def _check_writable(self) -> None:
        if self.read_only:
            raise Fat12Error(_t("read_only"))

    def _flush(self) -> None:
        # Obraz zbudowany z bufora nie ma pliku, do ktorego moglby trafic.
        if not self.path:
            return
        with open(self.path, "r+b") as fh:
            fh.write(self.data)


# --------------------------------------------------------------------------
#  Pomocnicze operacje na sciezkach
# --------------------------------------------------------------------------

def _split_path(path: str) -> list[str]:
    return [p for p in path.replace("\\", "/").split("/") if p and p != "."]


def _split_parent(path: str) -> tuple[str, str]:
    parts = _split_path(path)
    if not parts:
        return "/", ""
    return "/" + "/".join(parts[:-1]), parts[-1]


def _join(*parts: str) -> str:
    out: list[str] = []
    for part in parts:
        out.extend(_split_path(part))
    return "/" + "/".join(out)


def _human(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    text = (f"{size / 1024:.1f} KB" if size < 1024 * 1024
            else f"{size / 1024 / 1024:.2f} MB")
    return text if _LANG == "en" else text.replace(".", ",")


# --------------------------------------------------------------------------
#  Interfejs wiersza polecen
# --------------------------------------------------------------------------

def _cli(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    # Jezyk trzeba ustalic przed zbudowaniem parsera, bo opisy pomocy
    # tez sa tlumaczone.
    args_list = list(sys.argv[1:] if argv is None else argv)
    for index, item in enumerate(args_list):
        if item == "--lang" and index + 1 < len(args_list):
            set_language(args_list[index + 1])
            del args_list[index:index + 2]
            break
        if item.startswith("--lang="):
            set_language(item.split("=", 1)[1])
            del args_list[index]
            break

    parser = argparse.ArgumentParser(prog="fat12", description=_t("cli_desc"))
    parser.add_argument("--lang", choices=sorted(MESSAGES),
                        default=get_language(), help=_t("cli_lang"))
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create", help=_t("cli_create"))
    p.add_argument("image")
    p.add_argument("--format", default="1440", choices=list(FLOPPY_FORMATS))
    p.add_argument("--label", default="")
    p.add_argument("--force", action="store_true", help=_t("cli_force"))

    p = sub.add_parser("list", help=_t("cli_list"))
    p.add_argument("image")
    p.add_argument("path", nargs="?", default="/")

    p = sub.add_parser("add", help=_t("cli_add"))
    p.add_argument("image")
    p.add_argument("files", nargs="+")
    p.add_argument("--dest", default="/")

    p = sub.add_parser("extract", help=_t("cli_extract"))
    p.add_argument("image")
    p.add_argument("path")
    p.add_argument("output")

    p = sub.add_parser("addtree", help=_t("cli_addtree"))
    p.add_argument("image")
    p.add_argument("folder")
    p.add_argument("--dest", default="/")
    p.add_argument("--contents-only", action="store_true")

    p = sub.add_parser("mkdir", help=_t("cli_mkdir"))
    p.add_argument("image")
    p.add_argument("path")

    p = sub.add_parser("rm", help=_t("cli_rm"))
    p.add_argument("image")
    p.add_argument("path")
    p.add_argument("-r", "--recursive", action="store_true")

    args = parser.parse_args(args_list)

    try:
        if args.command == "create":
            fmt = FLOPPY_FORMATS[args.format]
            format_image(args.image, fmt, args.label, overwrite=args.force)
            print(_t("cli_created", path=args.image, fmt=fmt.label))
            return 0

        with Fat12Image(args.image) as img:
            if args.command == "list":
                label = img.get_label()
                print(_t("cli_media", fmt=img.format_name)
                      + (_t("cli_label", label=label) if label else ""))
                print("-" * 52)
                for e in img.listdir(args.path):
                    kind = _t("cli_dir") if e.is_dir else f"{e.size:>9}"
                    when = e.modified.strftime("%Y-%m-%d %H:%M") \
                        if e.modified else ""
                    print(f"{e.name:<13}{kind:>10}  {when}  {e.attr_string()}")
                print("-" * 52)
                print(_t("cli_free", free=_human(img.free_bytes),
                         total=_human(img.total_bytes)))

            elif args.command == "add":
                for path in args.files:
                    name = img.import_file(path, args.dest)
                    print(f"{path} -> {_join(args.dest, name)}")

            elif args.command == "extract":
                img.export_file(args.path, args.output)
                print(f"{args.path} -> {args.output}")

            elif args.command == "addtree":
                info = img.import_tree(
                    args.folder, args.dest,
                    include_root=not args.contents_only)
                print(_t("cli_tree", files=info["files"],
                         dirs=info["dirs"], bytes=info["bytes"]))
                for line in info["renamed"][:20]:
                    print("  8.3:", line)
                for line in info["failed"][:20]:
                    print("  pominieto:", line)

            elif args.command == "mkdir":
                print(_t("cli_mkdir_ok", name=img.mkdir(args.path)))

            elif args.command == "rm":
                img.remove(args.path, recursive=args.recursive)
                print(_t("cli_removed", path=args.path))
        return 0

    except Fat12Error as exc:
        print(_t("cli_error", msg=exc))
        return 1
    except OSError as exc:
        print(_t("cli_io_error", msg=exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
