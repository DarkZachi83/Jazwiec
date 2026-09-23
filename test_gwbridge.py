"""
Testy mostu do Greaseweazle.

Rozbior sprawdzany jest na prawdziwych zapisach wyjscia gw - z dyskietki
windowsowej z martwa sciezka, dyskietki referencyjnej i uszkodzonego
napedu z zablokowana glowica. Uruchamianie polecenia sprawdza podstawiony
program gw, ktory odtwarza te zapisy i zapisuje obraz jak prawdziwy.
"""

import os
import stat
import sys
import textwrap
import unittest

from helpers import PrzypadekZKatalogiem, podstaw_gw

import gw_samples as probki
import gwbridge


class WykrywanieUrzadzenia(unittest.TestCase):
    """gw info rozroznia brak narzedzia i brak urzadzenia."""

    def test_urzadzenie_podlaczone(self):
        stan = gwbridge.parse_info(probki.GW_INFO_URZADZENIE, tool="/usr/bin/gw")
        self.assertTrue(stan.ready)
        self.assertEqual(stan.model, "Greaseweazle V4.1")
        self.assertEqual(stan.firmware, "1.6")
        self.assertEqual(stan.port, "/dev/ttyACM0")
        self.assertEqual(stan.tool_version, "1.23")
        self.assertIsNone(stan.problem())

    def test_narzedzie_bez_urzadzenia(self):
        stan = gwbridge.parse_info(probki.GW_INFO_BRAK, tool="/usr/bin/gw")
        self.assertFalse(stan.ready)
        self.assertEqual(stan.tool_version, "1.23")
        gwbridge.set_language("pl")
        self.assertIn("nie widzi urzadzenia", stan.problem())

    def test_brak_narzedzia(self):
        stan = gwbridge.GwStatus()
        gwbridge.set_language("pl")
        self.assertIn("Nie znaleziono polecenia gw", stan.problem())


class OdczytCzysty(unittest.TestCase):

    def setUp(self):
        self.r = gwbridge.parse_log(probki.pelny_odczyt(), "1440")

    def test_wszystkie_sciezki_i_sektory(self):
        self.assertEqual(self.r.done_tracks, 160)
        self.assertEqual(self.r.found_sectors, 2880)
        self.assertEqual(self.r.bad_sectors, [])
        self.assertEqual(self.r.diagnosis, "ok")

    def test_predkosc_obrotowa(self):
        """400,28 ms na dwa obroty to 299,8 obr./min."""
        self.assertAlmostEqual(self.r.rpm, 299.8, places=1)
        self.assertTrue(self.r.rpm_ok)


class MartwaSciezka(unittest.TestCase):
    """Dyskietka windowsowa: martwa wylacznie sciezka C1 H1."""

    def setUp(self):
        self.r = gwbridge.parse_log(probki.pelny_odczyt({(1, 1)}), "1440")

    def test_sektory_logiczne_54_do_71(self):
        """Cylinder 1, strona 1 to sektory logiczne 54-71."""
        self.assertEqual(self.r.bad_sectors, list(range(54, 72)))

    def test_rozpoznanie_to_nosnik(self):
        self.assertEqual(self.r.diagnosis, "media")
        sciezka = self.r.tracks[(1, 1)]
        self.assertEqual(sciezka.diagnosis, "dead")
        self.assertTrue(sciezka.gave_up)
        self.assertEqual(sciezka.attempts, 4)

    def test_proby_ponowne_nie_psuja_pomiaru_predkosci(self):
        """
        Proby ponowne czytaja trzy obroty zamiast dwoch. Gdyby liczyly sie
        do predkosci, wynik bylby zafalszowany.
        """
        self.assertAlmostEqual(self.r.rpm, 299.8, places=1)
        self.assertEqual(self.r.tracks[(1, 1)].ms, 400.30)

    def test_znaleziono_z_podsumowania(self):
        self.assertEqual((self.r.found_sectors, self.r.total_sectors),
                         (2862, 2880))


class UszkodzonyNaped(unittest.TestCase):
    """
    Glowica zablokowana na cylindrze 1: naglowki sektorow podaja inny
    cylinder niz zadany. Stacja USB zglosilaby tylko "zle sektory".
    """

    def setUp(self):
        self.r = gwbridge.parse_log(probki.uszkodzony_naped(), "1440")

    def test_rozpoznaje_problem_z_pozycjonowaniem(self):
        self.assertEqual(self.r.diagnosis, "positioning")

    def test_wskazuje_sciezki_z_obcymi_sektorami(self):
        obce = sorted(k for k, s in self.r.tracks.items() if s.misplaced)
        self.assertEqual(obce, [(19, 0), (20, 0)])

    def test_obce_sektory_nie_sa_liczone_wielokrotnie(self):
        """gw powtarza te same linie przy kazdej probie."""
        self.assertEqual(len(self.r.tracks[(19, 0)].unexpected), 4)

    def test_pozycjonowanie_wazniejsze_niz_martwe_sciezki(self):
        """
        Gdy glowica nie dojezdza, lista zlych sektorow nie opisuje nosnika
        - rozpoznanie musi wskazac naped, a nie dyskietke.
        """
        self.assertIn((19, 1), self.r.tracks)
        self.assertEqual(self.r.tracks[(19, 1)].diagnosis, "dead")
        self.assertEqual(self.r.diagnosis, "positioning")

    def test_raport_ostrzega_przed_napedem(self):
        gwbridge.set_language("pl")
        tekst = self.r.text()
        self.assertIn("PROBLEM NAPEDU", tekst)
        self.assertIn("C19 H0", tekst)


class UlamkowaLiczbaObrotow(unittest.TestCase):
    """
    Przy AmigaDOS gw czyta "revs=1.1" - jeden obrot z zapasem. Wzorzec na
    liczbe calkowita nie rozpoznawal tej linii i predkosc obrotowa
    wychodzila prawie dwa razy za wysoka.
    """

    def test_naglowek_z_ulamkiem(self):
        r = gwbridge.parse_log(probki.odczyt_amigi(), "1440")
        self.assertEqual(r.revs, 1.1)

    def test_predkosc_obrotowa_amigi(self):
        """
        219,93 ms na 1,1 obrotu to 300 obr./min - tyle samo co przy IBM.
        Format podany tu tylko dla geometrii; na predkosc nie wplywa.
        """
        r = gwbridge.parse_log(probki.odczyt_amigi(), "1440")
        self.assertAlmostEqual(r.rpm, 300.1, places=1)
        self.assertTrue(r.rpm_ok)

    def test_ibm_nadal_dobrze(self):
        r = gwbridge.parse_log(probki.pelny_odczyt(), "1440")
        self.assertEqual(r.revs, 2.0)
        self.assertAlmostEqual(r.rpm, 299.8, places=1)


class NazwyFormatow(unittest.TestCase):
    """Nazwy sprawdzone na liscie z "gw read --help"."""

    def test_kazdy_nosnik_ma_spojna_geometrie(self):
        for klucz, nosnik in gwbridge.NOSNIKI.items():
            with self.subTest(nosnik=klucz):
                self.assertEqual(nosnik.klucz, klucz)
                self.assertIn(nosnik.rodzina, gwbridge.RODZINY)
                self.assertEqual(
                    nosnik.rozmiar,
                    nosnik.cylindry * nosnik.glowice * nosnik.sektory
                    * nosnik.bajty_sektora)
                self.assertEqual(nosnik.sciezki,
                                 nosnik.cylindry * nosnik.glowice)

    def test_formaty_pecetowe_zgadzaja_sie_z_silnikiem(self):
        """Geometria pecetowych nosnikow pochodzi z tablicy FAT12."""
        import fat12
        for klucz, nosnik in gwbridge.NOSNIKI.items():
            if nosnik.rodzina != "pc":
                continue
            with self.subTest(nosnik=klucz):
                fmt = fat12.FLOPPY_FORMATS[klucz]
                self.assertEqual(nosnik.rozmiar, fmt.size_bytes)
                self.assertEqual(nosnik.sektory, fmt.sectors_per_track)
                self.assertEqual(nosnik.glowice, fmt.heads)

    def test_rozmiary_nosnikow_z_epoki(self):
        self.assertEqual(gwbridge.NOSNIKI["amiga880"].rozmiar, 901120)
        self.assertEqual(gwbridge.NOSNIKI["amiga1760"].rozmiar, 1802240)
        self.assertEqual(gwbridge.NOSNIKI["atarist720"].rozmiar, 737280)
        self.assertEqual(gwbridge.NOSNIKI["amiga880"].rozszerzenie, ".adf")
        self.assertEqual(gwbridge.NOSNIKI["atarist720"].rozszerzenie, ".st")

    def test_formatowanie_tylko_dla_pecetowych(self):
        """
        Formatowanie polega u nas na zapisaniu pustego obrazu, a takiego
        nie zbudujemy dla AmigaDOS - nie mamy jego silnika.
        """
        self.assertTrue(gwbridge.NOSNIKI["1440"].nasz_system_plikow)
        self.assertFalse(gwbridge.NOSNIKI["amiga880"].nasz_system_plikow)
        gwbridge.set_language("pl")
        with self.assertRaises(gwbridge.GwError) as blad:
            gwbridge.format_disk("amiga880", "A")
        self.assertIn("tylko dla dyskietek pecetowych", str(blad.exception))

    def test_znane_odpowiedniki(self):
        self.assertEqual(gwbridge.GW_FORMATS["1440"], "ibm.1440")
        self.assertEqual(gwbridge.GW_FORMATS["2880"], "ibm.2880")
        self.assertEqual(gwbridge.GW_FORMATS["1250"], "pc98.2hd")

    def test_format_bez_odpowiednika_jest_odrzucany(self):
        """3,5" 360 KB jednostronnego gw nie ma - lepiej powiedziec wprost."""
        self.assertNotIn("360_35", gwbridge.GW_FORMATS)
        with self.assertRaises(gwbridge.GwError):
            gwbridge.read_to_image("x.img", "360_35")


class ObcyFormat(unittest.TestCase):
    """
    Dyskietka amigowa czytana jako pecetowa daje zero sektorow na kazdej
    sciezce. To nie uszkodzenie nosnika - zgloszone z prawdziwego odczytu.
    """

    def setUp(self):
        gwbridge.set_language("pl")

    def test_rozpoznanie_wskazuje_na_format(self):
        r = gwbridge.parse_log(probki.obcy_format(), "1440")
        self.assertEqual(r.diagnosis, "nothing")
        self.assertIn("inny format", r.text())
        self.assertIn("Amigi", r.text())

    def test_uszkodzony_nosnik_to_co_innego(self):
        r = gwbridge.parse_log(probki.pelny_odczyt({(1, 1)}), "1440")
        self.assertEqual(r.diagnosis, "media")

    def test_kilka_martwych_sciezek_to_jeszcze_nie_obcy_format(self):
        r = gwbridge.parse_log(
            probki.pelny_odczyt({(1, 1), (2, 0), (3, 1)}), "1440")
        self.assertEqual(r.diagnosis, "media")

    def test_dwie_sciezki_to_za_malo(self):
        """Poczatek odczytu nie moze od razu obwiniac formatu."""
        r = gwbridge.parse_log(probki.obcy_format(sciezek=2), "1440")
        self.assertNotEqual(r.diagnosis, "nothing")

    def test_problem_napedu_wazniejszy(self):
        r = gwbridge.parse_log(probki.uszkodzony_naped(), "1440")
        self.assertEqual(r.diagnosis, "positioning")

    def test_nieruchoma_glowica_to_nie_obcy_format(self):
        """
        Glowica stojaca od poczatku daje zero sektorow na kazdej sciezce -
        tak samo jak obcy format. Rozroznia je tylko cylinder w naglowkach
        znalezionych sektorow, wiec problem napedu musi byc sprawdzany
        pierwszy.
        """
        r = gwbridge.parse_log(probki.naped_stoi(), "1440")
        self.assertTrue(all(v[0] == "misplaced" for v in r.snapshot().values()))
        self.assertEqual(r.diagnosis, "positioning")


class MilczacaGlowica(unittest.TestCase):

    def test_rozpoznaje_martwa_strone(self):
        r = gwbridge.parse_log(probki.glowica_milczy(), "1440")
        self.assertEqual(r.silent_head, 1)
        self.assertEqual(r.diagnosis, "head")
        gwbridge.set_language("pl")
        self.assertIn("strona 1 nie czyta niczego", r.text())

    def test_za_malo_danych_to_nie_martwa_glowica(self):
        """
        Odczyt przerwany po dwoch sciezkach: strona 1 ma jedna, martwa.
        Jedna sciezka to za malo, zeby oskarzac glowice.
        """
        tekst = ("Reading c=0-79:h=0-1 revs=2\n"
                 "T0.0: IBM MFM (18/18 sectors) from Raw Flux "
                 "(152400 flux in 400.28ms)\n"
                 "T0.1: IBM MFM (0/18 sectors) from Raw Flux "
                 "(152400 flux in 400.28ms)\n"
                 "T0.1: Giving up: 18 sectors missing\n")
        r = gwbridge.parse_log(tekst, "1440")
        self.assertIsNone(r.silent_head)
        self.assertNotEqual(r.diagnosis, "head")

    def test_jedna_martwa_sciezka_to_nie_martwa_glowica(self):
        r = gwbridge.parse_log(probki.pelny_odczyt({(1, 1)}), "1440")
        self.assertIsNone(r.silent_head)


class BladKrytyczny(unittest.TestCase):

    def test_komunikat_z_nastepnej_linii(self):
        r = gwbridge.parse_log(probki.GW_BLAD_KRYTYCZNY, "1440")
        self.assertEqual(r.fatal, "Cannot find the Greaseweazle device")
        self.assertEqual(r.diagnosis, "fatal")


class OdczytPrzerwany(unittest.TestCase):

    def test_bez_mapy_bierze_martwe_sciezki(self):
        """Przerwany odczyt nie ma mapy - wtedy chociaz calkiem martwe."""
        pelny = probki.pelny_odczyt({(1, 1)})
        uciety = pelny[:pelny.index("T10.0:")]
        r = gwbridge.parse_log(uciety, "1440")
        self.assertFalse(r.has_map)
        self.assertEqual(r.bad_sectors, list(range(54, 72)))
        gwbridge.set_language("pl")
        self.assertIn("nie wypisalo mapy", r.text())


class Tlumaczenia(unittest.TestCase):

    def test_oba_jezyki_maja_te_same_klucze(self):
        self.assertEqual(set(gwbridge._T["pl"]), set(gwbridge._T["en"]))

    def test_raport_po_angielsku(self):
        gwbridge.set_language("en")
        try:
            tekst = gwbridge.parse_log(probki.pelny_odczyt({(1, 1)}),
                                       "1440").text()
            self.assertIn("cannot be decoded", tekst)
        finally:
            gwbridge.set_language("pl")


class Zabezpieczenia(PrzypadekZKatalogiem):
    """
    Zly format albo naped musi zostac odrzucony, zanim cokolwiek ruszy
    naped. Wczesniej ten test uzywal formatu 2880 - obslugiwanego od
    wersji 2.15 - i przechodzil tylko tam, gdzie gw nie bylo zainstalowane.
    Na komputerze z gw naprawde uruchamial odczyt prawdziwej dyskietki.
    """

    def setUp(self):
        super().setUp()
        self.argumenty = podstaw_gw(self, odczyt=probki.pelny_odczyt())

    def gw_nie_ruszyl(self):
        self.assertFalse(os.path.exists(self.argumenty),
                         "polecenie gw nie moze zostac uruchomione")

    def test_nieznany_format(self):
        """3,5" 360 KB jednostronny - gw nie ma dla niego odpowiednika."""
        with self.assertRaises(gwbridge.GwError):
            gwbridge.read_to_image(self.sciezka("x.img"), "360_35")
        self.gw_nie_ruszyl()

    def test_nieznany_naped(self):
        with self.assertRaises(gwbridge.GwError):
            gwbridge.read_to_image(self.sciezka("x.img"), "1440", drive="C")
        self.gw_nie_ruszyl()

    def test_formatowanie_amigi(self):
        with self.assertRaises(gwbridge.GwError):
            gwbridge.format_disk("amiga880", "A")
        self.gw_nie_ruszyl()

    def test_obraz_o_zlym_rozmiarze(self):
        obraz = self.sciezka("maly.img")
        with open(obraz, "wb") as fh:
            fh.write(bytes(1000))
        with self.assertRaises(gwbridge.GwError):
            gwbridge.write_image(obraz, "1440")
        self.gw_nie_ruszyl()


@unittest.skipIf(os.name == "nt", "atrapa gw jest skryptem uniksowym")
class UruchamianiePolecenia(PrzypadekZKatalogiem):
    """
    Podstawiony program gw odtwarza prawdziwy zapis i tworzy obraz, tak jak
    zrobiloby to urzadzenie. Sprawdza caly obieg: argumenty, czytanie
    wyjscia na biezaco, postep, przerwanie i kod wyjscia.
    """

    def setUp(self):
        super().setUp()
        katalog_bin = self.sciezka("bin")
        os.makedirs(katalog_bin)
        self.zapis = self.sciezka("zapis.txt")
        self.argumenty = self.sciezka("argumenty.txt")
        atrapa = os.path.join(katalog_bin, "gw")
        with open(atrapa, "w") as fh:
            fh.write(textwrap.dedent(f"""\
                #!{sys.executable}
                import sys, time
                with open({self.argumenty!r}, "w") as a:
                    a.write(" ".join(sys.argv[1:]))
                if sys.argv[1] == "info":
                    print({probki.GW_INFO_URZADZENIE!r}, end="")
                    sys.exit(0)
                obraz = sys.argv[-1]
                if sys.argv[1] == "read":
                    with open(obraz, "wb") as f:
                        f.write(bytes(1474560))
                for linia in open({self.zapis!r}):
                    print(linia, end="", flush=True)
                sys.exit(0)
            """))
        os.chmod(atrapa, os.stat(atrapa).st_mode | stat.S_IEXEC)
        stara = os.environ.get("PATH", "")
        os.environ["PATH"] = katalog_bin + os.pathsep + stara
        self.addCleanup(os.environ.__setitem__, "PATH", stara)

    def zapisz(self, tekst):
        with open(self.zapis, "w") as fh:
            fh.write(tekst)

    def test_info(self):
        stan = gwbridge.probe()
        self.assertTrue(stan.ready)
        self.assertEqual(stan.model, "Greaseweazle V4.1")

    def test_odczyt_z_postepem(self):
        self.zapisz(probki.pelny_odczyt({(1, 1)}))
        obraz = self.sciezka("dysk.img")
        widziane = []
        r = gwbridge.read_to_image(
            obraz, "1440", "A",
            progress=lambda rap: widziane.append(rap.done_tracks) or True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.diagnosis, "media")
        self.assertEqual(r.bad_sectors, list(range(54, 72)))
        self.assertEqual(os.path.getsize(obraz), 1474560)
        self.assertEqual(widziane[-1], 160)
        self.assertEqual(widziane, sorted(widziane),
                         "postep ma tylko rosnac")

    def test_argumenty_przekazane_do_gw(self):
        self.zapisz(probki.pelny_odczyt())
        gwbridge.read_to_image(self.sciezka("d.img"), "720", "B")
        with open(self.argumenty) as fh:
            argumenty = fh.read()
        self.assertIn("read", argumenty)
        self.assertIn("--drive B", argumenty)
        self.assertIn("--format ibm.720", argumenty)

    def test_przerwanie(self):
        self.zapisz(probki.pelny_odczyt())
        r = gwbridge.read_to_image(
            self.sciezka("d.img"), "1440",
            progress=lambda rap: rap.done_tracks < 20)
        self.assertTrue(r.cancelled)
        self.assertEqual(r.diagnosis, "cancelled")
        self.assertLess(r.done_tracks, 40)

    def test_zapis_obrazu(self):
        obraz = self.sciezka("wejscie.img")
        with open(obraz, "wb") as fh:
            fh.write(bytes(1474560))
        self.zapisz(probki.pelny_zapis())
        widziane = []
        r = gwbridge.write_image(
            obraz, "1440",
            progress=lambda rap: widziane.append(rap.done_tracks) or True)
        self.assertEqual(r.diagnosis, "write_ok")
        self.assertTrue(r.verified)
        self.assertEqual(r.done_tracks, 160)
        self.assertEqual(widziane[-1], 160)

    def test_zapis_odrzuca_obraz_o_zlym_rozmiarze(self):
        obraz = self.sciezka("zly.img")
        with open(obraz, "wb") as fh:
            fh.write(bytes(1000))
        with self.assertRaises(gwbridge.GwError):
            gwbridge.write_image(obraz, "1440")


class WierszPolecen(PrzypadekZKatalogiem):
    """
    Blad z pliku ma sie konczyc zdaniem, nie sladem wyjatku. Pierwsza wersja
    wyrzucala surowy wyjatek przy nieistniejacym pliku z zapisem wyjscia.
    """

    def uruchom(self, *argumenty):
        import contextlib
        import io
        wyjscie, bledy = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(wyjscie), \
                contextlib.redirect_stderr(bledy):
            kod = gwbridge.main(list(argumenty))
        gwbridge.set_language("pl")
        return kod, wyjscie.getvalue(), bledy.getvalue()

    def test_parse_nieistniejacego_pliku(self):
        kod, _, bledy = self.uruchom("parse", self.sciezka("nie_ma.txt"))
        self.assertEqual(kod, 1)
        self.assertIn("Nie mozna otworzyc pliku", bledy)
        self.assertNotIn("Traceback", bledy)

    def test_parse_katalogu_zamiast_pliku(self):
        kod, _, bledy = self.uruchom("parse", self.katalog)
        self.assertEqual(kod, 1)
        self.assertIn("Nie mozna otworzyc pliku", bledy)

    def test_parse_prawdziwego_zapisu(self):
        zapis = self.sciezka("windows.txt")
        with open(zapis, "w") as fh:
            fh.write(probki.pelny_odczyt({(1, 1)}))
        kod, wyjscie, _ = self.uruchom("parse", zapis, "--format", "1440")
        self.assertEqual(kod, 0)
        self.assertIn("C1 H1", wyjscie)
        self.assertIn("nie da sie odkodowac", wyjscie)

    def test_komunikat_po_angielsku(self):
        kod, _, bledy = self.uruchom("--lang", "en", "parse",
                                     self.sciezka("nie_ma.txt"))
        self.assertIn("Cannot open file", bledy)


class ZapisObrazu(unittest.TestCase):
    """Prawdziwe wyjscie gw write z napedu Panasonic."""

    def rozbierz(self, tekst, kod=0):
        r = gwbridge.GwReport(operation="write", format_key="1440",
                              gw_format="ibm.1440")
        parser = gwbridge.GwParser(r)
        for linia in tekst.splitlines():
            parser.feed(linia)
        r.returncode = kod
        return r

    def test_zapis_z_potwierdzeniem(self):
        r = self.rozbierz(probki.pelny_zapis())
        self.assertEqual(r.total_tracks, 160)
        self.assertEqual(r.done_tracks, 160)
        self.assertTrue(r.verified)
        self.assertEqual(r.diagnosis, "write_ok")

    def test_brak_potwierdzenia_to_nie_sukces(self):
        """Kod wyjscia 0 bez zdania potwierdzajacego - nie wiemy nic."""
        r = self.rozbierz(probki.pelny_zapis(potwierdzenie=False))
        self.assertFalse(r.verified)
        self.assertEqual(r.diagnosis, "write_unverified")
        gwbridge.set_language("pl")
        self.assertIn("nie potwierdzil", r.text())

    def test_blad_zapisu(self):
        r = self.rozbierz(probki.pelny_zapis(potwierdzenie=False), kod=1)
        self.assertEqual(r.diagnosis, "write_fail")

    def test_raport_zapisu(self):
        gwbridge.set_language("pl")
        tekst = self.rozbierz(probki.pelny_zapis()).text()
        self.assertIn("160 / 160", tekst)
        self.assertIn("zgodna", tekst)
        self.assertIn("zweryfikowany", tekst)


class DataWRaporcie(unittest.TestCase):
    """
    Zapis wyjscia gw nie zawiera czasu. Przy analizie znamy tylko chwile
    analizy i tak musi byc opisana, zeby nie udawala daty odczytu.
    """

    def test_analiza_opisana_jako_analiza(self):
        gwbridge.set_language("pl")
        tekst = gwbridge.parse_log(probki.pelny_odczyt(), "1440").text()
        self.assertIn("Data analizy:", tekst)

    def test_odczyt_opisany_jako_data(self):
        gwbridge.set_language("pl")
        r = gwbridge.GwReport(operation="read", format_key="1440")
        self.assertIn("Data:", r.text())
        self.assertNotIn("Data analizy", r.text())


@unittest.skipIf(os.name == "nt", "atrapa gw jest skryptem uniksowym")
class Formatowanie(PrzypadekZKatalogiem):
    """Formatowanie to zapis pustego obrazu FAT12 przez gw write."""

    def test_formatowanie_zapisuje_pusty_obraz(self):
        from helpers import podstaw_gw
        argumenty = podstaw_gw(self, zapis=probki.pelny_zapis())
        r = gwbridge.format_disk("1440", "A", "GRY")
        self.assertEqual(r.operation, "format")
        self.assertEqual(r.diagnosis, "format_ok")
        with open(argumenty) as fh:
            wywolanie = fh.read().split("\n")
        self.assertEqual(wywolanie[0], "write")
        self.assertIn("ibm.1440", wywolanie)
        self.assertFalse(os.path.exists(wywolanie[-1]),
                         "tymczasowy obraz ma zostac usuniety")
        gwbridge.set_language("pl")
        self.assertIn("sformatowana i zweryfikowana", r.text())
        self.assertNotIn("Obraz:", r.text())



class StanySciezek(unittest.TestCase):
    """Stany, z ktorych rysowana jest mapa sciezek w oknie."""

    def test_szesc_stanow(self):
        r = gwbridge.parse_log(
            probki.pelny_odczyt({(1, 1)}, slabe={(40, 0)}), "1440")
        s = r.snapshot()
        self.assertEqual(s[(0, 0)][0], "ok")
        self.assertEqual(s[(1, 1)][0], "bad")
        self.assertEqual(s[(40, 0)][0], "retried",
                         "odczytana dopiero przy ponownej probie to nie 'ok'")

    def test_problem_napedu_to_nie_uszkodzenie(self):
        s = gwbridge.parse_log(probki.uszkodzony_naped(), "1440").snapshot()
        self.assertEqual(s[(19, 0)][0], "misplaced")
        self.assertEqual(s[(19, 0)][4], (1,), "obce sektory z cylindra 1")
        self.assertEqual(s[(19, 1)][0], "bad")

    def test_proby_w_toku(self):
        tekst = ("T5.0: IBM MFM (0/18 sectors) from Raw Flux "
                 "(152400 flux in 400.28ms)\n")
        s = gwbridge.parse_log(tekst, "1440").snapshot()
        self.assertEqual(s[(5, 0)][0], "active")

    def test_zapisane_sciezki(self):
        r = gwbridge.GwReport(operation="write", format_key="1440")
        p = gwbridge.GwParser(r)
        for linia in probki.pelny_zapis().splitlines():
            p.feed(linia)
        self.assertEqual({v[0] for v in r.snapshot().values()}, {"ok"})

    def test_kazda_proba_zglasza_zmiane(self):
        """
        Bez tego mapa nie pokazalaby na zywo, ze naped meczy sie z jedna
        sciezka - zmiana szlaby dopiero z nastepna sciezka.
        """
        r = gwbridge.GwReport(operation="read", format_key="1440")
        p = gwbridge.GwParser(r)
        zmiany = [p.feed(l) for l in probki.MARTWA_SCIEZKA_C1H1.splitlines()]
        self.assertEqual(zmiany, [True, True, True, True, True])

    def test_geometria(self):
        self.assertEqual(gwbridge.GwReport("read", "1440").cylinders, 80)
        self.assertEqual(gwbridge.GwReport("read", "360").cylinders, 40)



class MapaSektorowWRaporcie(unittest.TestCase):
    """Mapa w ukladzie gw: kolumna to cylinder, wiersz to strona i sektor."""

    def setUp(self):
        gwbridge.set_language("pl")
        self.wejscie = probki.pelny_odczyt({(1, 1)})
        self.r = gwbridge.parse_log(self.wejscie, "1440")

    def test_identyczna_z_mapa_z_gw(self):
        """Uklad ma byc ten sam co w gw - linia w linie."""
        linie = self.wejscie.splitlines()
        start = next(i for i, l in enumerate(linie) if l.startswith("Cyl->"))
        self.assertEqual(self.r.sector_map_lines(), linie[start:start + 38])

    def test_uszkodzone_sektory_na_swoim_miejscu(self):
        mapa = self.r.sector_map_lines()[2:]
        iksy = [(w[:4], w.index("X") - 6) for w in mapa if "X" in w]
        self.assertEqual(len(iksy), 18)
        self.assertTrue(all(wiersz.startswith("1.") and cyl == 1
                            for wiersz, cyl in iksy))

    def test_w_raporcie_przed_rozpoznaniem(self):
        tekst = self.r.text()
        self.assertIn("Mapa sektorow", tekst)
        self.assertLess(tekst.index("1.17: "), tekst.index("Rozpoznanie:"))
        self.assertGreater(tekst.index("nie da sie odkodowac"),
                           tekst.index("1.17: "),
                           "rozpoznanie zostaje na koncu, po mapie")

    def zapis(self, tekst=None, kod=0):
        r = gwbridge.GwReport(operation="write", format_key="1440")
        p = gwbridge.GwParser(r)
        for linia in (tekst or probki.pelny_zapis()).splitlines():
            p.feed(linia)
        r.returncode = kod
        return r

    def test_zapis_ma_mape_sciezek_zamiast_sektorow(self):
        """
        gw zapisuje cale sciezki naraz i nie wypisuje mapy sektorow. Mapa
        w raporcie musi to odzwierciedlac i nazywac sie inaczej, zeby nie
        sugerowala dokladnosci, ktorej nie ma.
        """
        tekst = self.zapis().text()
        self.assertNotIn("Mapa sektorow", tekst)
        self.assertIn("Mapa sciezek", tekst)
        wiersze = [w for w in tekst.splitlines() if w.startswith("H")]
        self.assertEqual(len(wiersze), 3, "naglowek i po wierszu na strone")
        self.assertEqual(wiersze[1], "H0:   " + "." * 80)
        self.assertEqual(wiersze[2], "H1:   " + "." * 80)

    def test_niezapisane_sciezki_oznaczone(self):
        pelny = probki.pelny_zapis()
        uciety = pelny[:pelny.index("T40.0:")]
        wiersze = [w for w in self.zapis(uciety, kod=1).text().splitlines()
                   if w.startswith("H0:")]
        self.assertEqual(wiersze[0], "H0:   " + "." * 40 + "X" * 40)

    def test_rozpoznanie_nie_przesadza_o_nosniku(self):
        """
        Sciezka rozmagnesowana wyglada jak uszkodzona powierzchnia, a daje
        sie odzyskac ponownym zapisem - sprawdzone na prawdziwej dyskietce.
        Rozpoznanie ma o tym mowic, a nie skazywac nosnika.
        """
        gwbridge.set_language("pl")
        tekst = gwbridge.parse_log(
            probki.pelny_odczyt({(1, 1)}), "1440").text()
        self.assertIn("sformatowanie i ponowny zapis", tekst)
        self.assertIn("formatowanie kasuje zawartosc", tekst)

    def test_linie_raportu_nie_sa_dluzsze_od_mapy(self):
        """W zapisanym pliku .txt nic nie ma wystawac poza mape."""
        for raport in (self.zapis(), gwbridge.parse_log(
                probki.pelny_odczyt({(1, 1)}), "1440")):
            for linia in raport.text().splitlines():
                with self.subTest(linia=linia[:40]):
                    self.assertLessEqual(len(linia), 88)

    def test_przerwany_odczyt_nie_ma_mapy(self):
        uciety = self.wejscie[:self.wejscie.index("T10.0:")]
        r = gwbridge.parse_log(uciety, "1440")
        self.assertEqual(r.sector_map_lines(), [])
        self.assertNotIn("Mapa sektorow", r.text())

    def test_czterdziesci_cylindrow(self):
        r = gwbridge.GwReport(operation="read", format_key="360")
        r.map_rows = {(0, 0): "." * 40, (1, 8): "." * 39 + "X"}
        mapa = r.sector_map_lines()
        self.assertEqual(mapa[0], "Cyl-> " + "".join(f"{c:<10}" for c in range(4)))
        self.assertEqual(mapa[1], "H. S: " + "0123456789" * 4)
        self.assertEqual(mapa[-1], "1. 8: " + "." * 39 + "X")



class WskazanaSciezkaDoGw(PrzypadekZKatalogiem):
    """
    Pod Windowsem narzedzia Greaseweazle rozpakowuje sie do dowolnego
    katalogu. Jesli nie trafi on do PATH, polecenie dziala tylko w tym
    folderze - a program uruchomiony z Eksploratora ma inny katalog roboczy
    i nie widzi go wcale. Zgloszone z prawdziwej instalacji.
    """

    def setUp(self):
        super().setUp()
        self.addCleanup(gwbridge.set_tool_path, None)

    def test_wskazana_ma_pierwszenstwo(self):
        atrapa = os.path.join(self.katalog, "gw-gdzie-indziej")
        with open(atrapa, "w") as fh:
            fh.write("#!/bin/sh\n")
        gwbridge.set_tool_path(atrapa)
        self.assertEqual(gwbridge.find_gw(), atrapa)
        self.assertEqual(gwbridge.tool_path(), atrapa)

    def test_nieistniejaca_wraca_do_szukania(self):
        """Zla sciezka nie moze odciac programu od dzialajacego gw."""
        podstaw_gw(self, odczyt=probki.pelny_odczyt())
        z_path = gwbridge.find_gw()
        gwbridge.set_tool_path(os.path.join(self.katalog, "nie-ma-mnie"))
        self.assertEqual(gwbridge.find_gw(), z_path)

    def test_odczyt_uzywa_wskazanego_pliku(self):
        argumenty = podstaw_gw(self, odczyt=probki.pelny_odczyt())
        wskazany = gwbridge.find_gw()
        stara = os.environ["PATH"]
        os.environ["PATH"] = "/nie-ma-takiego-katalogu"
        self.addCleanup(os.environ.__setitem__, "PATH", stara)
        self.assertIsNone(gwbridge.find_gw(), "bez PATH nie ma jak go znalezc")
        gwbridge.set_tool_path(wskazany)
        raport = gwbridge.read_to_image(self.sciezka("d.img"), "1440")
        self.assertEqual(raport.diagnosis, "ok")
        self.assertTrue(os.path.exists(argumenty))

    def test_wiersz_polecen_odrzuca_zla_sciezke(self):
        import contextlib
        import io as wejscie_wyjscie
        bledy = wejscie_wyjscie.StringIO()
        with contextlib.redirect_stderr(bledy):
            kod = gwbridge.main(["--gw", os.path.join(self.katalog, "brak"),
                                 "info"])
        self.assertEqual(kod, 1)
        self.assertIn("nie istnieje", bledy.getvalue())


if __name__ == "__main__":
    unittest.main()
