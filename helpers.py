"""
Narzedzia pomocnicze dla testow.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Najwazniejsza rzecza jest tu AtrapaNapedu: udaje urzadzenie blokowe i pozwala
zadac, ktore sektory maja byc martwe, a ktore slabe - czyli wracajace dopiero
przy kolejnej probie odczytu. Bez tego nie da sie sprawdzic ani izolacji
uszkodzonych sektorow, ani roznicy miedzy testem powierzchni a weryfikacja.

Uwaga na pulapke, ktora raz juz uniewaznila caly zestaw sprawdzen: program
czyta porcjami po kilkadziesiat sektorow naraz, wiec atrapa musi patrzec na
CALY zakres odczytu, a nie tylko na jego pierwszy sektor. Atrapa sprawdzajaca
sam poczatek przepuszczala wszystko i testy "przechodzily", nie sprawdzajac
niczego.
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import unittest

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KORZEN not in sys.path:
    sys.path.insert(0, KORZEN)

# Testy nie moga dotykac ustawien uzytkownika. Program trzyma je w pliku
# w katalogu domowym, a testy okna zapisuja tam jezyk, ostatnie katalogi,
# wybrany naped Greaseweazle. Bez tej izolacji zestaw testow zmienial
# prawdziwe ustawienia - i sam sobie przeszkadzal, bo wybor zapisany przez
# jeden test zmienial punkt wyjscia nastepnego przy kolejnym uruchomieniu.
#
# Katalog domowy podmieniamy, zanim ktorykolwiek modul programu ustali
# sciezke pliku ustawien. Gdyby modul systemowy byl juz wczytany, jego
# sciezke poprawiamy wprost.
_DOM_TESTOW = tempfile.mkdtemp(prefix="jazwiec-dom-")
os.environ["HOME"] = _DOM_TESTOW
os.environ["USERPROFILE"] = _DOM_TESTOW
os.environ.pop("SUDO_USER", None)
for _nazwa in ("system", "gui_main"):
    _modul = sys.modules.get(_nazwa)
    if _modul is not None and hasattr(_modul, "CONFIG_FILE"):
        from pathlib import Path as _Path
        _modul.CONFIG_FILE = _Path(_DOM_TESTOW) / ".retrozachar.json"
PLIK_USTAWIEN_TESTOW = os.path.join(_DOM_TESTOW, ".retrozachar.json")

SEKTOR = 512


def czy_jest(polecenie: str) -> bool:
    """Czy narzedzie zewnetrzne jest dostepne w systemie."""
    return shutil.which(polecenie) is not None


def fsck_czysty(sciezka: str) -> bool:
    """
    Czy fsck.fat nie ma zastrzezen do obrazu.

    Uzywane jako niezalezne potwierdzenie poprawnosci - nasz wlasny silnik
    nie moze byc jedynym sedzia w swojej sprawie.
    """
    import subprocess
    wynik = subprocess.run(["fsck.fat", "-n", sciezka],
                           capture_output=True, text=True)
    podejrzane = ("Auto-renaming", "Expected", "Deleting", "FSCK")
    return wynik.returncode == 0 and not any(
        s in wynik.stdout for s in podejrzane)


class AtrapaNapedu(io.RawIOBase):
    """
    Plik udajacy urzadzenie blokowe, z zadanymi uszkodzeniami.

    martwe  - sektory, ktore nigdy sie nie odczytaja,
    slabe   - sektory, ktore zawodza kilka pierwszych razy i wracaja przy
              kolejnej probie,
    gubione - sektory, ktore przyjmuja zapis, ale zapisuja zera; sluza do
              sprawdzenia, czy weryfikacja wylapuje rozjazd tresci.
    """

    def __init__(self, sciezka: str, do_zapisu: bool = False,
                 martwe=frozenset(), slabe=frozenset(),
                 gubione=frozenset(), niepowodzenia: int = 1):
        self.plik = open(sciezka, "rb+" if do_zapisu else "rb")
        self.martwe = set(martwe)
        self.slabe = set(slabe)
        self.gubione = set(gubione)
        # Ile razy sektor slaby ma zawiesc, zanim odda dane. Ma znaczenie,
        # bo odczyt porcji zuzywa jedna probe, zanim program zejdzie do
        # pojedynczych sektorow.
        self.niepowodzenia = niepowodzenia
        self.proby: dict[tuple, int] = {}

    # -- polozenie ---------------------------------------------------------

    def seek(self, offset, skad=0):
        return self.plik.seek(offset, skad)

    def tell(self):
        return self.plik.tell()

    def fileno(self):
        return self.plik.fileno()

    def flush(self):
        self.plik.flush()

    def close(self):
        self.plik.close()

    # -- odczyt i zapis ----------------------------------------------------

    def _zakres(self, ile_bajtow: int) -> range:
        pierwszy = self.plik.tell() // SEKTOR
        return range(pierwszy, pierwszy + max(1, ile_bajtow // SEKTOR))

    def read(self, ile=-1):
        zakres = self._zakres(ile if ile > 0 else SEKTOR)
        if any(s in self.martwe for s in zakres):
            raise OSError(5, "Input/output error")
        trafione = tuple(s for s in zakres if s in self.slabe)
        if trafione:
            self.proby[trafione] = self.proby.get(trafione, 0) + 1
            if self.proby[trafione] <= self.niepowodzenia:
                raise OSError(5, "Input/output error")
        return self.plik.read(ile)

    def write(self, dane):
        pierwszy = self.plik.tell() // SEKTOR
        for numer in range(len(dane) // SEKTOR):
            fragment = dane[numer * SEKTOR:(numer + 1) * SEKTOR]
            if pierwszy + numer in self.gubione:
                fragment = b"\x00" * SEKTOR
            self.plik.write(fragment)
        return len(dane)


def podstaw_naped(usbfloppy, **uszkodzenia):
    """Podmienia otwieranie urzadzenia na atrape o zadanych uszkodzeniach."""
    def otworz(sciezka, write):
        return AtrapaNapedu(sciezka, write, **uszkodzenia), None
    usbfloppy._open_device = otworz


def wyczysc_ustawienia() -> None:
    """Usuwa plik ustawien testow - nastepne okno startuje od domyslnych."""
    try:
        os.remove(PLIK_USTAWIEN_TESTOW)
    except FileNotFoundError:
        pass


class CzystyStart(unittest.TestCase):
    """
    Kazdy test zaczyna od pustych ustawien.

    Izolacja od ustawien uzytkownika nie wystarczala: testy dzielily jeden
    plik ustawien miedzy soba. Test zapamietywania wyboru zostawial format
    720 KB i nastepny test, zapisujacy obraz 1,44 MB, zaczynal od zlego
    formatu - wynik zalezal od kolejnosci testow.
    """

    def setUp(self):
        wyczysc_ustawienia()
        super().setUp()


class PrzypadekZKatalogiem(CzystyStart):
    """Wspolna baza dla testow potrzebujacych katalogu roboczego."""

    def setUp(self):
        super().setUp()
        self.katalog = tempfile.mkdtemp(prefix="jazwiec-test-")
        self.addCleanup(shutil.rmtree, self.katalog, ignore_errors=True)

    def sciezka(self, *czesci) -> str:
        return os.path.join(self.katalog, *czesci)

    def zbuduj_drzewo(self, opis: dict) -> str:
        """
        Zaklada drzewo katalogow z opisu.

        Klucz to sciezka wzgledna, wartosc to zawartosc pliku albo None
        dla katalogu pustego.
        """
        korzen = self.sciezka("zrodlo")
        os.makedirs(korzen, exist_ok=True)
        for wzgledna, tresc in opis.items():
            pelna = os.path.join(korzen, wzgledna)
            if tresc is None:
                os.makedirs(pelna, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(pelna), exist_ok=True)
            with open(pelna, "wb") as fh:
                fh.write(tresc)
        return korzen


def podstaw_gw(przypadek, odczyt: str = "", zapis: str = "",
               opoznienie: float = 0.0, tworzy_obraz: bool = True,
               kod_wyjscia: int = 0) -> str:
    """
    Podstawia atrape polecenia gw na poczatku PATH.

    Odtwarza podane wyjscie odczytu albo zapisu i przy odczycie tworzy obraz
    pelnego rozmiaru, jak prawdziwe urzadzenie. Z tworzy_obraz=False obrazu
    nie tworzy - tak konczy sie praca przerwana bledem, na przyklad po
    wyjeciu przewodu USB. Zapisuje tez argumenty
    ostatniego wywolania, zeby test mogl sprawdzic, z czym gw zostal
    uruchomiony. Zwraca sciezke pliku z tymi argumentami.
    """
    import stat
    import textwrap
    from gw_samples import GW_INFO_URZADZENIE

    katalog = os.path.join(przypadek.katalog, "atrapa-gw")
    os.makedirs(katalog, exist_ok=True)
    pliki = {}
    for nazwa, tresc in (("odczyt", odczyt), ("zapis", zapis)):
        pliki[nazwa] = os.path.join(katalog, nazwa + ".txt")
        with open(pliki[nazwa], "w") as fh:
            fh.write(tresc)
    argumenty = os.path.join(katalog, "argumenty.txt")
    sciezka = os.path.join(katalog, "gw")
    with open(sciezka, "w") as fh:
        fh.write(textwrap.dedent(f"""\
            #!{sys.executable}
            import sys, time
            with open({argumenty!r}, "w") as a:
                a.write(chr(10).join(sys.argv[1:]))
            if sys.argv[1] == "info":
                print({GW_INFO_URZADZENIE!r}, end="")
                sys.exit(0)
            obraz = sys.argv[-1]
            zrodlo = {pliki["zapis"]!r}
            if sys.argv[1] == "read":
                if {tworzy_obraz!r}:
                    open(obraz, "wb").write(bytes(1474560))
                zrodlo = {pliki["odczyt"]!r}
            for linia in open(zrodlo):
                print(linia, end="", flush=True)
                time.sleep({opoznienie})
            sys.exit({kod_wyjscia})
        """))
    os.chmod(sciezka, os.stat(sciezka).st_mode | stat.S_IEXEC)
    stara = os.environ.get("PATH", "")
    os.environ["PATH"] = katalog + os.pathsep + stara
    przypadek.addCleanup(os.environ.__setitem__, "PATH", stara)
    return argumenty
