#!/usr/bin/env python3
"""
Uruchamia caly zestaw testow projektu.

    python3 tests/run.py          wszystko
    python3 tests/run.py fat12    tylko wskazany modul

Nie wymaga niczego poza biblioteka standardowa. Czesc sprawdzen potrzebuje
narzedzi albo srodowiska, ktorych moze nie byc - te sa pomijane, a nie
zglaszane jako bledy:

    fsck.fat            niezalezne potwierdzenie poprawnosci obrazow
                        (pakiet dosfstools)
    serwer graficzny    testy okna; pod Linuksem bez pulpitu pomaga
                        xvfb-run -a python3 tests/run.py
"""

import os
import sys
import unittest

KATALOG = os.path.dirname(os.path.abspath(__file__))
if KATALOG not in sys.path:
    sys.path.insert(0, KATALOG)

MODULY = [
    "test_fat12",
    "test_dostext",
    "test_diskset",
    "test_usbfloppy",
    "test_gwbridge",
    "test_vhd",
    "test_partitions",
    "test_fat16",
    "test_interfejs",
]


def main(argv: list[str]) -> int:
    wybrane = MODULY
    if argv:
        wybrane = [m for m in MODULY if any(a in m for a in argv)]
        if not wybrane:
            print(f"Nie znaleziono modulu pasujacego do {argv}.")
            print("Dostepne:", ", ".join(m.replace("test_", "")
                                         for m in MODULY))
            return 2

    ladowacz = unittest.TestLoader()
    zestaw = unittest.TestSuite(ladowacz.loadTestsFromName(m)
                                for m in wybrane)
    wynik = unittest.TextTestRunner(verbosity=2).run(zestaw)

    print()
    print("=" * 62)
    print(f"  testow: {wynik.testsRun}"
          f"   niepowodzen: {len(wynik.failures)}"
          f"   bledow: {len(wynik.errors)}"
          f"   pominietych: {len(wynik.skipped)}")
    if wynik.skipped:
        print()
        print("  pominieto:")
        widziane = set()
        for _, powod in wynik.skipped:
            if powod not in widziane:
                widziane.add(powod)
                print(f"    {powod}")
    print("=" * 62)
    return 0 if wynik.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
