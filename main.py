#!/usr/bin/env python3
"""
main.py - punkt startowy programu.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Uruchomienie:
    python3 main.py

Plik jest celowo krotki. Jego jedynym zadaniem jest sprawdzic, czy da sie
wystartowac okno, i powiedziec po ludzku, czego brakuje, zanim uzytkownik
zobaczy surowy slad wyjatku. Wlasciwy interfejs zyje w gui_main.py.

Najczestsza przyczyna klopotow to brak modulu tkinter. Pod Windowsem jest
w standardowej instalacji Pythona z python.org, ale wiele dystrybucji Linuksa
wydziela go do osobnego pakietu: python3-tk w Debianie i Ubuntu, python3-tkinter
we Fedorze, tk w Archu.
"""

import sys


def main() -> int:
    try:
        import tkinter  # noqa: F401 - sprawdzamy sama obecnosc
    except ImportError:
        from languages import DEFAULT_LANGUAGE, translate
        print(translate(DEFAULT_LANGUAGE, "error_no_tk"))
        return 1

    import gui_main
    return gui_main.main()


if __name__ == "__main__":
    sys.exit(main())
