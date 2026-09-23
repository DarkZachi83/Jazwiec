"""
system.py - wspolpraca z systemem operacyjnym.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Praca pod sudo, katalog domowy wlasciwego uzytkownika, plik ustawien,
odnajdywanie ikon i grafiki oraz drobne pomocnicze operacje na plikach.
Nic tu nie zalezy od okna, wiec moduly dialogowe moga z tego korzystac
bez ryzyka importow cyklicznych.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
#  Praca pod sudo
# --------------------------------------------------------------------------
#  Dostep do fizycznego napedu wymaga roota, ale nie ma powodu, zeby placil
#  za to caly program. Gdy dziala przez sudo, ustawienia trafiaja do katalogu
#  domowego wlasciwego uzytkownika, a tworzone pliki dostaja jego wlasciciela
#  - inaczej zostalyby obrazy .img, ktorych bez sudo nie da sie edytowac.

def _sudo_ids() -> tuple[int, int] | None:
    """UID i GID uzytkownika, ktory wywolal sudo, albo None."""
    if os.name == "nt":
        return None
    try:
        if os.geteuid() != 0:
            return None
    except AttributeError:
        return None
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if uid and gid and uid.isdigit() and gid.isdigit():
        return int(uid), int(gid)
    return None


def _real_home() -> Path:
    """Katalog domowy uzytkownika, nie roota."""
    user = os.environ.get("SUDO_USER")
    if user and _sudo_ids():
        try:
            import pwd
            return Path(pwd.getpwnam(user).pw_dir)
        except (ImportError, KeyError):
            pass
    return Path.home()


def hand_back(path) -> None:
    """Oddaje swiezo utworzony plik uzytkownikowi spod sudo."""
    ids = _sudo_ids()
    if not ids:
        return
    try:
        os.chown(path, *ids)
    except OSError:
        pass


CONFIG_FILE = _real_home() / ".retrozachar.json"


def _znajdz_ikone(nazwa: str) -> str | None:
    """
    Szuka pliku ikony obok programu albo w miejscu instalacji systemowej.

    Dzieki temu ikona dziala i przy uruchomieniu z katalogu ze zrodlami,
    i po zainstalowaniu przez install.sh.
    """
    miejsca = [
        Path(__file__).resolve().parent / nazwa,
        Path("/usr/local/lib/retrozachar") / nazwa,
        Path("/usr/lib/retrozachar") / nazwa,
    ]
    for sciezka in miejsca:
        if sciezka.is_file():
            return str(sciezka)
    return None


def _stamp(path) -> tuple | None:
    """Odcisk stanu pliku: czas modyfikacji i rozmiar."""
    try:
        info = os.stat(path)
        return (info.st_mtime_ns, info.st_size)
    except OSError:
        return None


def _human(size: int) -> str:
    """Rozmiar w bajtach z nierozdzielajaca spacja co trzy cyfry."""
    return f"{size:,}".replace(",", "\u00a0")


def _measure_folder(root: Path) -> tuple[int, int, int]:
    """Liczy pliki, podkatalogi i sumaryczny rozmiar przed kopiowaniem."""
    files = dirs = total = 0
    for current, subdirs, names in os.walk(root, followlinks=False):
        dirs += len(subdirs)
        for name in names:
            path = Path(current) / name
            if path.is_symlink() or not path.is_file():
                continue
            files += 1
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return files, dirs, total
