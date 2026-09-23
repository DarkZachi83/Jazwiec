"""
engines.py - wybor silnika systemu plikow dla otwieranego obrazu.

Czesc projektu "RetroZachar FFD Disk Maker".

Po co ta warstwa
    Interfejs nie powinien wiedziec, ze czyta akurat FAT12. Dzieki temu
    dolozenie obslugi kolejnego systemu plikow - w planach AmigaDOS, czyli
    pliki ADF - sprowadza sie do napisania nowego modulu i zarejestrowania
    go tutaj, zamiast przerabiania calego okna.

    Sam wybor idzie po zawartosci pliku, nie po rozszerzeniu. Rozszerzenie
    sluzy najwyzej do rozstrzygania remisow: nazwa .img nie mowi nic
    o formacie, a .adf i .img bywaja uzywane zamiennie.

Jak dolozyc silnik
    Nowy modul musi udostepniac klase obrazu o tym samym zestawie metod,
    ktorego uzywa interfejs: listdir, read_file, write_file, import_file,
    import_tree, export_file, mkdir, remove, rename, stat, exists,
    get_label, set_label, close, wlasciwosci free_bytes, total_bytes,
    format_name, read_only oraz pomocnicze join, parent i short_name.

    Potem wystarczy dopisac ponizej rejestracje, na wzor tej dla FAT12:

        def _amigados() -> Engine:
            import amigados
            return Engine(
                key="amigados",
                label="AmigaDOS (OFS/FFS)",
                extensions=(".adf",),
                detect=amigados.looks_like_adf,
                open=amigados.AdfImage,
            )

        _FACTORIES.append(_amigados)

    Import silnika siedzi wewnatrz funkcji celowo. Brak modulu ma oznaczac
    brak jednej pozycji na liscie, a nie wywrocenie calego programu -
    dokladnie tak, jak dzis dziala brak obslugi napedow.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

__all__ = [
    "ImageError",
    "UnknownFormat",
    "Engine",
    "engines",
    "detect",
    "open_image",
    "describe_supported",
]

# Naglowek wystarczajacy kazdemu znanemu silnikowi do rozpoznania formatu.
HEADER_BYTES = 1024


class ImageError(Exception):
    """
    Wspolny przodek bledow wszystkich silnikow.

    Interfejs lapie ten jeden typ i nie musi znac klas wyjatkow
    poszczegolnych modulow.
    """


class UnknownFormat(ImageError):
    """Zadna z zarejestrowanych obsług nie rozpoznaje tego pliku."""


@dataclass(frozen=True)
class Engine:
    """Jeden system plikow, ktory program potrafi otworzyc."""

    key: str
    label: str
    extensions: tuple[str, ...]
    detect: Callable[[bytes, int], bool]
    open: Callable[..., object]

    def matches_extension(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in self.extensions


# --------------------------------------------------------------------------
#  Rejestracja silnikow
# --------------------------------------------------------------------------

def _fat12() -> Engine:
    import fat12

    def rozpoznaj(header: bytes, size: int) -> bool:
        """
        FAT12 poznajemy po sektorze rozruchowym: sygnaturze na koncu
        pierwszego sektora i sensownych wartosciach w bloku BPB.
        """
        if len(header) < 512:
            return False
        if header[510:512] != bytes([0x55, 0xAA]):
            return False
        bytes_per_sector = int.from_bytes(header[0x0B:0x0D], "little")
        sectors_per_cluster = header[0x0D]
        num_fats = header[0x10]
        root_entries = int.from_bytes(header[0x11:0x13], "little")
        media = header[0x15]
        return (
            bytes_per_sector in (512, 1024, 2048, 4096)
            and sectors_per_cluster in (1, 2, 4, 8, 16, 32, 64, 128)
            and num_fats in (1, 2)
            and root_entries > 0          # FAT32 ma tu zero
            and media >= 0xF0
        )

    return Engine(
        key="fat12",
        label="FAT12 (DOS)",
        extensions=(".img", ".ima", ".vfd", ".dsk", ".flp"),
        detect=rozpoznaj,
        open=fat12.Fat12Image,
    )


# Kolejnosc ma znaczenie tylko przy remisie w rozpoznawaniu.
_FACTORIES: list[Callable[[], Engine]] = [_fat12]

_cache: list[Engine] | None = None


def engines() -> list[Engine]:
    """Silniki dostepne w tej instalacji programu."""
    global _cache
    if _cache is None:
        gotowe = []
        for factory in _FACTORIES:
            try:
                gotowe.append(factory())
            except ImportError:
                continue          # brak modulu to po prostu brak silnika
        _cache = gotowe
    return _cache


def describe_supported() -> str:
    """Lista obslugiwanych systemow plikow, do komunikatow i okien."""
    return ", ".join(engine.label for engine in engines())


def all_extensions() -> tuple[str, ...]:
    """Rozszerzenia wszystkich silnikow, do filtrow w oknie wyboru pliku."""
    razem: list[str] = []
    for engine in engines():
        for suffix in engine.extensions:
            if suffix not in razem:
                razem.append(suffix)
    return tuple(razem)


# --------------------------------------------------------------------------
#  Rozpoznawanie i otwieranie
# --------------------------------------------------------------------------

def detect(path: str | os.PathLike) -> Engine | None:
    """
    Ustala, ktory silnik obsluzy dany plik.

    Decyduje zawartosc. Gdy pasuje wiecej niz jeden silnik - co dzis sie nie
    zdarza, ale zdarzy sie przy formatach o podobnych naglowkach - rozstrzyga
    zgodnosc rozszerzenia, a w ostatniej kolejnosci kolejnosc rejestracji.
    """
    path = os.fspath(path)
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            header = fh.read(HEADER_BYTES)
    except OSError as exc:
        raise ImageError(str(exc)) from exc

    pasujace = [e for e in engines() if e.detect(header, size)]
    if not pasujace:
        return None
    if len(pasujace) == 1:
        return pasujace[0]
    po_rozszerzeniu = [e for e in pasujace if e.matches_extension(path)]
    return (po_rozszerzeniu or pasujace)[0]


def open_image(path: str | os.PathLike, read_only: bool = False):
    """
    Otwiera obraz silnikiem odpowiednim do jego zawartosci.

    Zglasza UnknownFormat, gdy zaden silnik nie rozpoznaje pliku - dzieki
    czemu interfejs moze powiedziec uzytkownikowi, co w ogole obsluguje,
    zamiast wypisywac blad parsowania bloku BPB.
    """
    engine = detect(path)
    if engine is None:
        raise UnknownFormat(os.fspath(path))
    return engine.open(path, read_only=read_only)
