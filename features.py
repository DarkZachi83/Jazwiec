"""
features.py - wykrywanie czesci opcjonalnych.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Program dziala w kilku odmianach: podstawowej, ktora tworzy i edytuje obrazy
dyskietek, oraz rozszerzonych o obsluge stacji USB, Greaseweazle i kreator
kompletu dyskietek. Kazdy z tych dodatkow jest niezalezny od pozostalych. Tu, w jednym miejscu, rozstrzyga sie, ktore dodatki sa
obecne. Brak dodatku oznacza jedynie brak jego pozycji w menu.

Osobny modul z prostego powodu: flag potrzebuja zarowno okno glowne, jak
i budowa jego paneli, a panele sa importowane przez okno glowne. Gdyby
flagi powstawaly w oknie glownym, panele musialyby je stamtad importowac
i powstalby import cykliczny.
"""

from __future__ import annotations

# Obsluga fizycznych napedow: modul urzadzen i jego okna.
try:
    import usbfloppy
    from usbfloppy import DriveError
    from dialogs_drive import DriveDialog
    DRIVES_AVAILABLE = True
except ImportError:
    usbfloppy = None
    DriveError = OSError
    DriveDialog = None
    DRIVES_AVAILABLE = False

# Kreator kompletu dyskietek: planowanie i jego okno.
try:
    import diskset
    from dialogs_diskset import KompletDialog
    PACZKA_AVAILABLE = True
except ImportError:
    diskset = None
    KompletDialog = None
    PACZKA_AVAILABLE = False

# Greaseweazle: most do polecenia gw i jego okno. Niezalezny od stacji USB -
# dziala takze wtedy, gdy modulu usbfloppy nie ma.
try:
    import gwbridge
    from dialogs_gw import GwDialog
    GW_AVAILABLE = True
except ImportError:
    gwbridge = None
    GwDialog = None
    GW_AVAILABLE = False
