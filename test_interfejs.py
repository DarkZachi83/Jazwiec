"""
Testy spojnosci tlumaczen oraz obecnosci i zachowania elementow okna.

Tu mieszcza sie sprawdzenia, ktore wylapalyby dwie regresje, jakie w tym
projekcie faktycznie wystapily: zniknieta klase edytora tekstu oraz grupy
przyciskow wyboru bez wyroznienia zaznaczonej pozycji.

Testy okna wymagaja serwera graficznego. Bez niego caly zestaw jest
pomijany, zamiast zglaszac blad.
"""

import os
import re
import unittest

from helpers import CzystyStart, PrzypadekZKatalogiem, podstaw_gw

import languages


def _pola(tekst: str) -> set:
    """Nazwy pol formatujacych w napisie, na przyklad {name} albo {count}."""
    return set(re.findall(r"\{(\w+)\}", tekst))


class Tlumaczenia(unittest.TestCase):

    def test_oba_jezyki_maja_ten_sam_zestaw_kluczy(self):
        polski = set(languages.TRANSLATIONS["pl"])
        angielski = set(languages.TRANSLATIONS["en"])
        self.assertEqual(polski - angielski, set(), "brakuje po angielsku")
        self.assertEqual(angielski - polski, set(), "brakuje po polsku")

    def test_pola_formatujace_sie_zgadzaja(self):
        """
        Rozjazd pol konczy sie wyjatkiem dopiero przy wyswietlaniu napisu,
        czyli zwykle u uzytkownika.
        """
        for klucz, polski in languages.TRANSLATIONS["pl"].items():
            with self.subTest(klucz=klucz):
                self.assertEqual(_pola(polski),
                                 _pola(languages.TRANSLATIONS["en"][klucz]))

    def test_nieznany_jezyk_cofa_sie_do_polskiego(self):
        self.assertEqual(languages.translate("de", "button_create"),
                         languages.TRANSLATIONS["pl"]["button_create"])

    def test_brakujacy_klucz_nie_wywraca_programu(self):
        self.assertEqual(languages.translate("pl", "klucz-ktorego-nie-ma"),
                         "klucz-ktorego-nie-ma")

    def test_nazwy_jezykow_podane_we_wlasnym_jezyku(self):
        """Zeby dalo sie wrocic po przypadkowym przelaczeniu."""
        self.assertEqual(languages.LANGUAGE_NAMES["pl"], "Polski")
        self.assertEqual(languages.LANGUAGE_NAMES["en"], "English")


def _okno_dostepne() -> bool:
    try:
        import tkinter
        korzen = tkinter.Tk()
        korzen.destroy()
        return True
    except Exception:       # noqa: BLE001 - brak wyswietlacza albo tkintera
        return False


@unittest.skipUnless(_okno_dostepne(), "brak serwera graficznego")
class SkladnikiOkna(CzystyStart):
    """
    Klasa edytora tekstu raz zniknela z pliku przy nieuwaznej przebudowie
    i nikt tego nie zauwazyl przez tydzien. Ten test kosztuje sekunde.
    """

    OCZEKIWANE = {
        "styles": ["Panel", "StyleMixin"],
        "ui_panels": ["PanelsMixin"],
        "gui_main": ["RetroZachar"],
        "dialogs_drive": ["DriveDialog", "FormatDialog", "ReportDialog"],
        "dialogs_files": ["FolderDialog", "TextEditor"],
        "dialogs_diskset": ["KompletDialog"],
        "dialogs_gw": ["GwDialog"],
    }

    def test_wszystkie_klasy_istnieja(self):
        import importlib
        for modul, klasy in self.OCZEKIWANE.items():
            zaladowany = importlib.import_module(modul)
            for nazwa in klasy:
                with self.subTest(klasa=f"{modul}.{nazwa}"):
                    self.assertTrue(hasattr(zaladowany, nazwa))

    def test_okno_wstaje_i_zamyka_sie(self):
        import gui_main
        app = gui_main.RetroZachar()
        try:
            app.update()
            self.assertGreater(app.winfo_width(), 100)
        finally:
            app.quit_app()


@unittest.skipUnless(_okno_dostepne(), "brak serwera graficznego")
class GrupyWyboru(CzystyStart):
    """
    Sama kropka wskaznika w tym motywie nie odroznia sie od pozostalych,
    wiec zaznaczona pozycje wyroznia kolor i grubosc napisu. To samo
    niedopatrzenie powtorzylo sie kolejno w czterech oknach.
    """

    def setUp(self):
        super().setUp()
        import gui_main
        import usbfloppy
        import dialogs_drive
        import dialogs_files
        import dialogs_diskset
        import styles
        self.rz = gui_main
        self.styl = styles
        self.napedy = dialogs_drive
        self.pliki = dialogs_files
        self.komplet = dialogs_diskset
        usbfloppy.low_level_tool = lambda: "/usr/bin/ufiformat"
        self.naped = usbfloppy.FloppyDrive("/dev/sdb", "ATRAPA", 1_474_560,
                                           512, "usb", "1440")
        usbfloppy.list_drives = lambda: [self.naped]
        self.app = gui_main.RetroZachar()
        self.app.update()
        self.addCleanup(self.app.quit_app)

    def sprawdz(self, grupa: dict, zmienna):
        for wartosc in grupa:
            with self.subTest(wybrano=wartosc):
                zmienna.set(wartosc)
                self.app.update()
                kolory = {k: b.cget("fg") for k, b in grupa.items()}
                self.assertEqual(kolory[wartosc], self.styl.ACCENT,
                                 "zaznaczona pozycja ma byc wyrozniona")
                self.assertEqual(
                    list(kolory.values()).count(self.styl.ACCENT), 1,
                    "wyrozniona ma byc dokladnie jedna pozycja")

    def test_format_w_oknie_glownym(self):
        self.sprawdz(self.app.radios, self.app.var_format)

    def test_nosnik_w_kreatorze_kompletu(self):
        okno = self.komplet.KompletDialog(self.app)
        self.addCleanup(okno.destroy)
        okno.update()
        self.sprawdz(okno.radia, okno.var_format)

    def test_strona_kodowa_w_edytorze(self):
        edytor = self.pliki.TextEditor(self.app, "/A.TXT", "A.TXT", b"tresc")
        self.addCleanup(edytor.destroy)
        edytor.update()
        self.sprawdz(edytor.codepage_buttons, edytor.var_codepage)

    def test_naped_i_format_w_oknie_greaseweazle(self):
        import dialogs_gw
        okno = dialogs_gw.GwDialog(self.app)
        self.addCleanup(okno.destroy)
        okno.update()
        self.sprawdz(okno.drive_buttons, okno.var_drive)
        self.sprawdz(okno.format_buttons, okno.var_format)

    def test_grupy_w_oknie_formatowania(self):
        okno_napedu = self.napedy.DriveDialog(self.app)
        self.addCleanup(okno_napedu.close)
        okno_napedu.update()
        okno_napedu.listbox.selection_set(0)

        class BezCzekania(self.napedy.FormatDialog):
            def wait_window(self, *a):
                pass

            def grab_set(self):
                pass

        okno = BezCzekania(okno_napedu, self.naped)
        self.addCleanup(okno.destroy)
        okno.update()
        self.sprawdz(okno.format_buttons, okno.var_format)
        self.sprawdz(okno.mode_buttons, okno.var_mode)


@unittest.skipUnless(_okno_dostepne(), "brak serwera graficznego")
class ZmianaJezyka(CzystyStart):
    """
    Zmiana jezyka przebudowuje okno od nowa. Listy zarejestrowanych
    przyciskow musza zostac wtedy wyczyszczone - inaczej kolejne
    odswiezenie siega po zniszczone widgety.
    """

    def test_przelaczanie_tam_i_z_powrotem(self):
        import gui_main
        app = gui_main.RetroZachar()
        self.addCleanup(app.quit_app)
        app.update()
        for jezyk in ("en", "pl", "en", "pl"):
            with self.subTest(jezyk=jezyk):
                app.set_language(jezyk)
                app.update()
                app._refresh_controls()
                self.assertEqual(app.lang, jezyk)


@unittest.skipUnless(_okno_dostepne(), "brak serwera graficznego")
class PasekPostepu(CzystyStart):
    """
    Pasek rysowal prostokat raz, przy biezacej szerokosci. Gdy okno sie
    potem rozszerzalo - na przyklad przez dlugi napis ze sciezka - pasek
    wygladal, jakby operacja nie doszla do konca.
    """

    def test_pelny_pasek_zostaje_pelny_po_poszerzeniu(self):
        import tkinter as tk
        import styles
        okno = tk.Tk()
        self.addCleanup(okno.destroy)
        pasek = styles.ProgressBar(okno)
        pasek.pack(fill="x")
        okno.geometry("300x40")
        okno.update()
        pasek.show(10, 10)
        for szerokosc in (300, 600, 200):
            with self.subTest(szerokosc=szerokosc):
                okno.geometry(f"{szerokosc}x40")
                okno.update()
                koniec = pasek.coords(pasek.find_all()[0])[2]
                self.assertGreaterEqual(koniec, pasek.winfo_width() - 1)


@unittest.skipUnless(_okno_dostepne(), "brak serwera graficznego")
class KreatorKompletu(CzystyStart):

    def test_pamieta_ostatni_katalog_z_programem(self):
        import gui_main
        import dialogs_diskset
        app = gui_main.RetroZachar()
        self.addCleanup(app.quit_app)
        app.config_data["disksetsrc"] = "/sciezka/do/gry"
        okno = dialogs_diskset.KompletDialog(app)
        self.addCleanup(okno.destroy)
        self.assertEqual(okno.var_source.get(), "/sciezka/do/gry")
        self.assertEqual(okno.var_target.get(), "GRY")

    def test_dluga_sciezka_nie_rozpycha_okna(self):
        import gui_main
        import dialogs_diskset
        app = gui_main.RetroZachar()
        self.addCleanup(app.quit_app)
        okno = dialogs_diskset.KompletDialog(app)
        self.addCleanup(okno.destroy)
        okno.update()
        przed = okno.winfo_width()
        okno.lbl_stan.configure(text="Nagrano 4 obrazow w " + "/bardzo/dluga" * 20)
        okno.update_idletasks()
        okno.update()
        self.assertEqual(okno.winfo_width(), przed)



@unittest.skipUnless(_okno_dostepne(), "brak serwera graficznego")
@unittest.skipIf(os.name == "nt", "atrapa gw jest skryptem uniksowym")
class OknoGreaseweazle(PrzypadekZKatalogiem):
    """
    Odczyt trwa okolo poltorej minuty, wiec idzie w watku w tle, a okno
    odpytuje jego stan. Test przechodzi cala droge: sprawdzenie urzadzenia,
    odczyt z postepem, raport w oknie. Osobno zamkniecie okna w trakcie
    pracy - gw nie moze zostac bez nadzoru.
    """

    def setUp(self):
        super().setUp()
        import gui_main
        import gw_samples
        self.probki = gw_samples
        self.app = gui_main.RetroZachar()
        self.addCleanup(self.app.quit_app)

    def czekaj(self, warunek, sekundy=20.0):
        import time
        koniec = time.time() + sekundy
        while time.time() < koniec:
            self.app.update()
            if warunek():
                return True
            time.sleep(0.02)
        return False

    def otworz(self):
        self.app.open_gw_panel()
        okno = self.app._gw_window
        self.assertTrue(self.czekaj(
            lambda: okno.btn_read.cget("state") == "normal"),
            "urzadzenie nie zostalo rozpoznane")
        return okno

    def test_odczyt_przez_okno(self):
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        podstaw_gw(self, odczyt=self.probki.pelny_odczyt({(1, 1)}))
        cel = self.sciezka("odczyt.img")
        stare = fd.asksaveasfilename, mb.askyesno
        fd.asksaveasfilename = lambda **k: cel
        mb.askyesno = lambda *a, **k: False
        self.addCleanup(lambda: setattr(fd, "asksaveasfilename", stare[0]))
        self.addCleanup(lambda: setattr(mb, "askyesno", stare[1]))

        okno = self.otworz()
        self.assertIn("Greaseweazle V4.1", okno.lbl_device.cget("text"))
        okno.odczyt()
        self.assertEqual(okno.btn_read.cget("state"), "disabled",
                         "w trakcie pracy przyciski maja byc zablokowane")
        self.assertTrue(self.czekaj(lambda: okno.worker is None))

        self.assertEqual(os.path.getsize(cel), 1474560)
        raport = okno.widok.tekst()
        self.assertIn("C1 H1", raport)
        self.assertEqual(okno.raport.bad_sectors, list(range(54, 72)))
        self.assertEqual(okno.btn_save.cget("state"), "normal")
        self.assertEqual(okno.btn_read.cget("state"), "normal")

    def test_wyrozniony_jest_przycisk_trwajacej_operacji(self):
        """
        Zgloszenie z uzytkowania: przy formatowaniu i przy zapisie na zolto
        swiecil sie "Zgraj do pliku .img", jakby trwal odczyt. Wyrozniony ma
        byc przycisk operacji, ktora naprawde trwa - i tylko w jej trakcie.
        """
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        import tkinter.simpledialog as sd
        import styles

        obraz = self.sciezka("zrodlo.img")
        with open(obraz, "wb") as fh:
            fh.write(bytes(1474560))
        podstaw_gw(self, odczyt=self.probki.pelny_odczyt(),
                   zapis=self.probki.pelny_zapis(), opoznienie=0.01)
        stare = (fd.asksaveasfilename, fd.askopenfilename, mb.askyesno,
                 sd.askstring)
        fd.asksaveasfilename = lambda **k: self.sciezka("odczyt.img")
        fd.askopenfilename = lambda **k: obraz
        mb.askyesno = lambda *a, **k: True
        sd.askstring = lambda *a, **k: ""

        def przywroc():
            (fd.asksaveasfilename, fd.askopenfilename, mb.askyesno,
             sd.askstring) = stare
        self.addCleanup(przywroc)

        okno = self.otworz()
        przyciski = {"odczyt": okno.btn_read, "zapis": okno.btn_write,
                     "formatowanie": okno.btn_format}

        def zolte():
            return {n for n, p in przyciski.items()
                    if p.cget("bg") == styles.ACCENT}

        self.assertEqual(zolte(), set(), "przed operacja nic nie swieci")
        for nazwa, metoda in (("formatowanie", okno.formatowanie),
                              ("zapis", okno.zapis),
                              ("odczyt", okno.odczyt)):
            with self.subTest(operacja=nazwa):
                mb.askyesno = lambda *a, **k: nazwa != "odczyt"
                metoda()
                self.assertTrue(self.czekaj(
                    lambda: okno._biezacy is not None
                    and okno._biezacy.done_tracks > 3))
                self.assertEqual(zolte(), {nazwa})
                self.assertTrue(self.czekaj(lambda: okno.worker is None))
                self.assertEqual(zolte(), set(),
                                 "po zakonczeniu nic nie swieci")

    def test_zapis_obrazu_innego_formatu(self):
        """
        Wybrany 720 KB, a obraz ma 1,44 MB. Zamiast surowego bledu z liczbami
        okno rozpoznaje format po rozmiarze i pyta, czy zapisac jako 1,44 MB.
        """
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        obraz = self.sciezka("duzy.img")
        with open(obraz, "wb") as fh:
            fh.write(bytes(1474560))
        argumenty = podstaw_gw(self, zapis=self.probki.pelny_zapis())
        pytania = []
        stare = fd.askopenfilename, mb.askyesno
        fd.askopenfilename = lambda **k: obraz
        mb.askyesno = lambda tytul, tresc, **k: pytania.append(tresc) or True
        self.addCleanup(lambda: setattr(fd, "askopenfilename", stare[0]))
        self.addCleanup(lambda: setattr(mb, "askyesno", stare[1]))

        okno = self.otworz()
        okno.var_format.set("720")
        okno.zapis()
        self.assertIn("1,44 MB", pytania[0])
        self.assertIn("720 KB", pytania[0])
        self.assertEqual(okno.var_format.get(), "1440")
        self.assertTrue(self.czekaj(lambda: okno.worker is None))
        self.assertEqual(okno.raport.diagnosis, "write_ok")
        with open(argumenty) as fh:
            self.assertIn("ibm.1440", fh.read())

    def odczytaj(self, zapis, opoznienie=0.0, obserwator=None):
        """Odczyt przez okno; obserwator dostaje okno przy kazdym kroku."""
        import time
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        podstaw_gw(self, odczyt=zapis, opoznienie=opoznienie)
        stare = fd.asksaveasfilename, mb.askyesno
        fd.asksaveasfilename = lambda **k: self.sciezka("odczyt.img")
        mb.askyesno = lambda *a, **k: False
        self.addCleanup(lambda: setattr(fd, "asksaveasfilename", stare[0]))
        self.addCleanup(lambda: setattr(mb, "askyesno", stare[1]))
        okno = self.otworz()
        okno.odczyt()
        koniec = time.time() + 30
        while okno.worker is not None and time.time() < koniec:
            self.app.update()
            if obserwator:
                obserwator(okno)
            time.sleep(0.01)
        self.app.update()
        return okno

    def test_mapa_po_odczycie(self):
        okno = self.odczytaj(self.probki.pelny_odczyt(
            {(1, 1)}, slabe={(40, 0), (41, 1)}))
        stany = okno.mapa._stany
        self.assertEqual(len(okno.mapa._komorki), 160)
        self.assertEqual(stany[(1, 1)], "bad")
        self.assertEqual(stany[(40, 0)], "retried")
        self.assertEqual(stany[(10, 0)], "ok")
        import dialogs_gw
        self.assertEqual(
            okno.mapa.itemcget(okno.mapa._komorki[(1, 1)], "fill"),
            dialogs_gw.KOLORY_STANOW["bad"])

    def test_w_trakcie_najwyzej_jedna_zolta(self):
        widziane = set()
        okno = self.odczytaj(
            self.probki.pelny_odczyt(), opoznienie=0.003,
            obserwator=lambda o: widziane.add(
                sum(1 for s in o.mapa._stany.values() if s == "active")))
        self.assertIn(1, widziane, "w trakcie ma byc widac sciezke w pracy")
        self.assertLessEqual(max(widziane), 1)
        self.assertNotIn("active", okno.mapa._stany.values(),
                         "po zakonczeniu zadna sciezka nie jest w pracy")

    def test_po_przerwaniu_nie_zostaje_zolta(self):
        """
        Po pelnym odczycie nie ma nastepnej sciezki, wiec zolty i tak nie
        mialby gdzie zostac. Znaczenie ma przerwanie: bez zabezpieczenia
        zolta zostalaby na sciezce, ktorej nikt juz nie czyta.
        """
        def przerwij_w_polowie(okno):
            r = okno._biezacy
            if r is not None and r.done_tracks > 40 and not okno._przerwij:
                okno.przerwij()

        okno = self.odczytaj(self.probki.pelny_odczyt(), opoznienie=0.003,
                             obserwator=przerwij_w_polowie)
        self.assertTrue(okno.raport.cancelled)
        self.assertLess(okno.raport.done_tracks, 160)
        self.assertNotIn("active", okno.mapa._stany.values())

    def test_problem_napedu_na_mapie(self):
        okno = self.odczytaj(self.probki.uszkodzony_naped())
        self.assertEqual(okno.mapa._stany[(19, 0)], "misplaced")
        okno._pokaz_szczegoly((19, 0))
        self.assertIn("cylindra 1", okno.lbl_info.cget("text"))

    def test_szczegoly_po_najechaniu(self):
        okno = self.odczytaj(self.probki.pelny_odczyt({(1, 1)}))
        okno._pokaz_szczegoly((1, 1))
        tekst = okno.lbl_info.cget("text")
        self.assertIn("C1 H1", tekst)
        self.assertIn("0 z 18", tekst)
        self.assertIn("prob: 4", tekst)
        okno._pokaz_szczegoly(None)
        self.assertIn("Najedz", okno.lbl_info.cget("text"))

    def test_podzialka_konczy_sie_na_ostatnim_cylindrze(self):
        """
        Cylindry liczy sie od zera, wiec 80 cylindrow to numery 0-79.
        Podzialka ma pokazac 79 na koncu, a nie urywac sie na 70.
        """
        podstaw_gw(self)
        okno = self.otworz()
        mapa = okno.mapa

        def etykiety():
            return [mapa.itemcget(e, "text")
                    for e in mapa.find_withtag("podzialka")]

        self.assertEqual(etykiety(), ["0", "10", "20", "30", "40", "50",
                                      "60", "70", "79"])
        okno.var_format.set("360")
        self.app.update()
        self.assertEqual(etykiety(), ["0", "10", "20", "30", "39"])
        ostatni = mapa.find_withtag("podzialka")[-1]
        self.assertLessEqual(mapa.bbox(ostatni)[2], mapa.winfo_width(),
                             "numer ostatniego cylindra miesci sie w mapie")

    def test_reczne_wskazanie_pliku_gw(self):
        """
        Program uruchomiony z Eksploratora nie widzi gw spoza PATH. Wskazanie
        pliku ma dzialac od razu i zostac zapamietane na nastepny raz.
        """
        import tkinter.filedialog as fd
        import gwbridge
        podstaw_gw(self, odczyt=self.probki.pelny_odczyt())
        narzedzie = gwbridge.find_gw()
        stara = os.environ["PATH"]
        os.environ["PATH"] = "/nie-ma-takiego-katalogu"
        self.addCleanup(os.environ.__setitem__, "PATH", stara)
        self.addCleanup(gwbridge.set_tool_path, None)

        self.app.open_gw_panel()
        okno = self.app._gw_window
        self.addCleanup(okno.destroy)
        # Czekamy na sam komunikat, a nie na wynik sprawdzenia: napis
        # odswieza sie chwile pozniej, w osobnym wywolaniu okna.
        self.assertTrue(self.czekaj(
            lambda: "Nie znaleziono" in okno.lbl_device.cget("text")),
            "okno ma powiedziec, ze nie znalazlo polecenia gw")
        self.assertEqual(okno.btn_read.cget("state"), "disabled")

        stary_wybor = fd.askopenfilename
        fd.askopenfilename = lambda **k: narzedzie
        self.addCleanup(lambda: setattr(fd, "askopenfilename", stary_wybor))
        okno.wskaz_narzedzie()
        self.assertTrue(self.czekaj(
            lambda: okno.btn_read.cget("state") == "normal"),
            "po wskazaniu pliku urzadzenie ma sie znalezc")
        self.assertIn("Greaseweazle V4.1", okno.lbl_device.cget("text"))
        self.assertEqual(self.app.config_data["gwpath"], narzedzie)
        self.assertEqual(okno.lbl_tool.cget("text"), narzedzie)

        okno.destroy()
        # Udajemy swiezy start programu: sama pamiec modulu nie wystarczy,
        # bo ta przetrwa zamkniecie okna i test przechodzilby nawet wtedy,
        # gdyby okno w ogole nie zagladalo do ustawien.
        gwbridge.set_tool_path(None)
        self.assertIsNone(gwbridge.find_gw())
        self.app.open_gw_panel()
        nowe_okno = self.app._gw_window
        self.addCleanup(nowe_okno.destroy)
        self.assertTrue(self.czekaj(
            lambda: nowe_okno.btn_read.cget("state") == "normal"),
            "sciezka ma byc wczytana z ustawien przy otwarciu okna")

    def test_zakladki_rodzin_nosnikow(self):
        """
        Kazda rodzina ma wlasna zakladke. Bez podzialu lista formatow
        rozrosla by sie do kilkunastu pozycji.
        """
        import gwbridge
        podstaw_gw(self)
        okno = self.otworz()
        self.assertEqual(len(okno.zakladki.tabs), len(gwbridge.RODZINY))
        for indeks, rodzina in enumerate(okno.rodziny):
            with self.subTest(rodzina=rodzina):
                okno.zakladki.select(indeks)
                self.app.update()
                widoczne = {k for k, b in okno.format_buttons.items()
                            if b.winfo_ismapped()}
                self.assertEqual(
                    widoczne,
                    {n.klucz for n in gwbridge.nosniki_rodziny(rodzina)})

    def test_rozszerzenie_pliku_zalezy_od_nosnika(self):
        """
        gw wybiera przeksztalcenie po rozszerzeniu. Zapisanie dyskietki
        Amigi jako .img dalo by obraz, ktorego zaden emulator nie otworzy.
        """
        import tkinter.filedialog as fd
        podstaw_gw(self)
        okno = self.otworz()
        zapisano = {}
        stare = fd.asksaveasfilename
        fd.asksaveasfilename = lambda **k: zapisano.update(k) or ""
        self.addCleanup(lambda: setattr(fd, "asksaveasfilename", stare))
        for klucz, koncowka in (("1440", ".img"), ("amiga880", ".adf"),
                                ("atarist720", ".st")):
            with self.subTest(nosnik=klucz):
                okno.var_format.set(klucz)
                self.app.update()
                okno.odczyt()
                self.assertEqual(zapisano["defaultextension"], koncowka)
                self.assertTrue(
                    zapisano["initialfile"].endswith(koncowka))
                self.assertIn(koncowka, okno.btn_read.cget("text"))

    def test_formatowanie_tylko_dla_pecetowych(self):
        """
        Pusty obraz umiemy zbudowac tylko silnikiem FAT12, wiec przy Amidze
        i Atari przycisk formatowania musi byc wylaczony.
        """
        podstaw_gw(self)
        okno = self.otworz()
        for klucz, oczekiwane in (("1440", "normal"),
                                  ("amiga880", "disabled"),
                                  ("atarist720", "disabled"),
                                  ("720", "normal")):
            with self.subTest(nosnik=klucz):
                okno.var_format.set(klucz)
                self.app.update()
                self.assertEqual(okno.btn_format.cget("state"), oczekiwane)
                self.assertEqual(okno.btn_read.cget("state"), "normal",
                                 "zgrywanie dziala dla kazdego nosnika")

    def test_mapa_dopasowuje_sie_do_formatu(self):
        podstaw_gw(self)
        okno = self.otworz()
        self.assertEqual(len(okno.mapa._komorki), 160)
        okno.var_format.set("360")
        self.app.update()
        self.assertEqual(len(okno.mapa._komorki), 80,
                         "dyskietka 360 KB ma 40 cylindrow")

    def test_raport_na_tle_obrazu(self):
        okno = self.odczytaj(self.probki.pelny_odczyt({(1, 1)}))
        widok = okno.widok
        self.assertIsNotNone(widok._tlo, "obraz tla ma byc wczytany")
        self.assertEqual(widok.tekst(), okno.raport.text())
        bloki = [e for e, _ in widok._bloki]
        self.assertEqual(len(bloki) % 2, 0, "kazdy blok ma tekst i cien")
        for cien, tekst in zip(bloki[::2], bloki[1::2]):
            self.assertEqual(widok.coords(cien)[0] - widok.coords(tekst)[0], 1)

    def test_tlo_stoi_a_tekst_sie_przewija(self):
        """
        Tlo da sie przewinac trzema drogami, a kazda przechodzi przez inna
        metode plotna: pasek przewijania (yview), kolko myszy (yview_scroll)
        i skok na koniec (yview_moveto). Tlo ma stac przy kazdej z nich.
        """
        okno = self.odczytaj(self.probki.pelny_odczyt({(1, 1)}))
        widok = okno.widok
        drogi = {
            "pasek przewijania": lambda: widok.yview("scroll", 4, "units"),
            "kolko myszy": lambda: widok.yview_scroll(3, "units"),
            "skok na koniec": lambda: widok.yview_moveto(1.0),
        }
        for nazwa, przewin in drogi.items():
            with self.subTest(droga=nazwa):
                widok.yview_moveto(0)
                self.app.update()
                przewin()
                self.app.update()
                self.assertGreater(widok.canvasy(0), 0,
                                   "tekst ma sie przesunac")
                _, y = widok.coords(widok._tlo_id)
                self.assertAlmostEqual(
                    y, widok.canvasy(0) + widok.winfo_height() / 2, delta=1)

    def test_rozpoznanie_zatrzymuje_sie_nad_tytulem(self):
        """
        Przy przewinieciu do konca ostatnia linia raportu ma lezec nad
        wtopionym w obraz tytulem, a nie na nim.
        """
        okno = self.odczytaj(self.probki.pelny_odczyt({(1, 1)}))
        widok = okno.widok
        widok.yview_moveto(1.0)
        self.app.update()
        dol_tekstu = widok.bbox(widok._elementy[-1])[3]
        dol_pola = widok.canvasy(0) + widok.winfo_height()
        self.assertGreaterEqual(dol_pola - dol_tekstu,
                                widok.ZAPAS_POD_TYTULEM - 2)

    def test_czerwone_x_na_uszkodzonych_sektorach(self):
        """
        Kazdy nieczytelny sektor ma czerwony X dokladnie w swojej kolumnie -
        takze wtedy, gdy wyzej w raporcie zawinela sie dluga sciezka.
        """
        import tkinter.font as tkfont
        import styles
        dlugi = self.sciezka("bardzo " * 12 + "dluga sciezka")
        os.makedirs(dlugi)
        okno = self.odczytaj(self.probki.pelny_odczyt({(1, 1)}))
        widok = okno.widok
        widok.pokaz(okno.raport.text().replace(
            okno.raport.image_path, os.path.join(dlugi, "obraz.img")))
        self.app.update()

        czcionka = tkfont.Font(root=widok, font=widok.font)
        wiersz = czcionka.metrics("linespace")
        znak = czcionka.measure("0")
        mapa = [e for e, m in widok._bloki if m][1]
        mx, my = widok.coords(mapa)
        linie = widok.itemcget(mapa, "text").splitlines()
        czerwone = [e for e in widok._elementy
                    if widok.itemcget(e, "fill") == styles.ALERT]
        self.assertEqual(len(czerwone), len(okno.raport.bad_sectors))
        for element in czerwone:
            x, y = widok.coords(element)
            linia = linie[round((y - my) / wiersz)]
            self.assertEqual(linia[round((x - widok.MARGINES) / znak)], "X")

    def test_po_bledzie_gw_nie_pyta_o_otwarcie_obrazu(self):
        """
        Po wyjeciu przewodu USB gw przerywa prace w polowie. Plik moze juz
        istniec, ale nie jest gotowym obrazem - pytanie o jego otwarcie
        konczylo sie bledem. Dwa przypadki, bo dwa rozne zabezpieczenia:
        plik powstal mimo bledu i plik nie powstal wcale.
        """
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        urwany = (self.probki.pelny_odczyt()[:1000]
                  + "\n" + self.probki.GW_BLAD_KRYTYCZNY)
        # Atrapa odpowiada "Nie" i przejmuje okna bledu. Gdy odpowiadala
        # "Tak", zepsuty program probowal otworzyc niepelny obraz i stawal
        # na niezamknietym oknie bledu - test zamiast upasc, wisial.
        stare = fd.asksaveasfilename, mb.askyesno, mb.showerror
        mb.showerror = lambda *a, **k: None
        self.addCleanup(lambda: setattr(fd, "asksaveasfilename", stare[0]))
        self.addCleanup(lambda: setattr(mb, "askyesno", stare[1]))
        self.addCleanup(lambda: setattr(mb, "showerror", stare[2]))

        przypadki = (
            # opis, czy plik powstal, wyjscie gw, kod wyjscia, rozpoznanie
            ("plik powstal mimo bledu", True, urwany, 1, "fatal"),
            ("pliku nie ma wcale", False, urwany, 1, "fatal"),
            ("gw konczy bez bledu, a pliku nie ma", False,
             self.probki.pelny_odczyt(), 0, "ok"),
        )
        for opis, powstal, wyjscie, kod, rozpoznanie in przypadki:
            with self.subTest(przypadek=opis):
                podstaw_gw(self, odczyt=wyjscie, tworzy_obraz=powstal,
                           kod_wyjscia=kod)
                cel = self.sciezka(f"urwany-{opis[:6]}-{powstal}.img")
                pytania = []
                fd.asksaveasfilename = lambda **k: cel
                mb.askyesno = lambda *a, **k: bool(pytania.append(a))

                self.app.open_gw_panel()
                okno = self.app._gw_window
                self.assertTrue(self.czekaj(
                    lambda: okno.btn_read.cget("state") == "normal"))
                okno.odczyt()
                self.assertTrue(self.czekaj(lambda: okno.worker is None))
                self.assertEqual(okno.raport.diagnosis, rozpoznanie)
                self.assertEqual(os.path.exists(cel), powstal)
                self.assertEqual(pytania, [],
                                 "nie ma o co pytac - gotowego obrazu brak")
                okno.destroy()
                self.app.update()

    def test_mapa_sciezek_po_zapisie(self):
        """
        Przy zapisie i formatowaniu raport pokazuje mape sciezek. Jej wiersze
        maja inny ksztalt niz wiersze mapy sektorow ("H0:" zamiast "0. 0:"),
        wiec okno musi je rozpoznac jako mape - inaczej by sie zawijaly.
        """
        import tkinter.messagebox as mb
        import tkinter.simpledialog as sd
        podstaw_gw(self, zapis=self.probki.pelny_zapis())
        stare = mb.askyesno, sd.askstring
        mb.askyesno = lambda *a, **k: True
        sd.askstring = lambda *a, **k: ""
        self.addCleanup(lambda: setattr(mb, "askyesno", stare[0]))
        self.addCleanup(lambda: setattr(sd, "askstring", stare[1]))

        okno = self.otworz()
        okno.formatowanie()
        self.assertTrue(self.czekaj(lambda: okno.worker is None))
        self.assertEqual(okno.raport.diagnosis, "format_ok")

        widok = okno.widok
        mapa = [e for e, m in widok._bloki if m]
        self.assertTrue(mapa, "mapa sciezek ma byc osobnym blokiem")
        self.assertEqual(int(widok.itemcget(mapa[1], "width")), 0)
        self.assertIn("H0:   ", widok.itemcget(mapa[1], "text"))

    def test_mapa_sektorow_sie_nie_zawija(self):
        okno = self.odczytaj(self.probki.pelny_odczyt({(1, 1)}))
        widok = okno.widok
        mapa = [e for e, m in widok._bloki if m]
        self.assertTrue(mapa, "raport z odczytu ma zawierac mape")
        self.assertEqual(int(widok.itemcget(mapa[1], "width")), 0)
        najdluzsza = max(len(l) for l in
                         widok.itemcget(mapa[1], "text").splitlines())
        potrzeba = widok.szerokosc_linii(najdluzsza)
        self.assertGreaterEqual(widok.winfo_width() - 2 * widok.MARGINES,
                                potrzeba)
        # Sprawdzamy zachowanie, a nie liczbe: po zwezeniu okna do jego
        # minimum mapa nadal musi miescic sie w jednej linii. Wczesniej
        # test porownywal minimum z biezaca szerokoscia okna, a ta rosnie
        # po wykryciu urzadzenia - dlugi napis o modelu i firmware poszerza
        # okno ponad minimum, wiec test padal na cudzym komputerze.
        okno.geometry(f"{okno.minsize()[0]}x{okno.winfo_height()}")
        self.app.update()
        self.assertGreaterEqual(widok.winfo_width() - 2 * widok.MARGINES,
                                potrzeba,
                                "po zwezeniu do minimum mapa by sie zawinela")

    def test_zamkniecie_w_trakcie_przerywa_gw(self):
        import tkinter.filedialog as fd
        import tkinter.messagebox as mb
        podstaw_gw(self, odczyt=self.probki.pelny_odczyt(), opoznienie=0.02)
        stare = fd.asksaveasfilename, mb.askyesno
        fd.asksaveasfilename = lambda **k: self.sciezka("d.img")
        mb.askyesno = lambda *a, **k: True
        self.addCleanup(lambda: setattr(fd, "asksaveasfilename", stare[0]))
        self.addCleanup(lambda: setattr(mb, "askyesno", stare[1]))

        okno = self.otworz()
        okno.odczyt()
        self.assertTrue(self.czekaj(
            lambda: okno._biezacy is not None
            and okno._biezacy.done_tracks > 5))
        okno.zamknij()
        self.assertTrue(self.czekaj(lambda: not okno.winfo_exists()),
                        "okno ma sie zamknac po przerwaniu pracy")
        self.assertTrue(okno._wynik[0].cancelled)
        self.assertLess(okno._wynik[0].done_tracks, 160)

    def test_wybor_napedu_i_formatu_zapamietany(self):
        import tkinter.filedialog as fd
        argumenty = podstaw_gw(self, odczyt=self.probki.pelny_odczyt())
        stare = fd.asksaveasfilename
        fd.asksaveasfilename = lambda **k: ""       # anulowanie wyboru pliku
        self.addCleanup(lambda: setattr(fd, "asksaveasfilename", stare))
        okno = self.otworz()
        okno.var_drive.set("B")
        okno.var_format.set("720")
        okno.odczyt()
        okno.destroy()
        self.assertEqual(self.app.config_data["gwdrive"], "B")
        self.assertEqual(self.app.config_data["gwformat"], "720")
        drugie = self.app
        drugie.open_gw_panel()
        nowe = drugie._gw_window
        self.addCleanup(nowe.destroy)
        self.assertEqual((nowe.var_drive.get(), nowe.var_format.get()),
                         ("B", "720"))
        self.assertFalse(os.path.exists(argumenty) and
                         "read" in open(argumenty).read(),
                         "po anulowaniu wyboru pliku gw nie ma ruszac")



class IzolacjaUstawien(unittest.TestCase):
    """
    Zestaw testow zapisywal do prawdziwego pliku ustawien uzytkownika:
    katalogi, jezyk, naped Greaseweazle. Wykryte, bo test odczytu padal przy
    drugim uruchomieniu - czytal format zapisany przez inny test.
    """

    def test_ustawienia_ida_do_katalogu_testow(self):
        import system
        from helpers import PLIK_USTAWIEN_TESTOW
        self.assertEqual(str(system.CONFIG_FILE), PLIK_USTAWIEN_TESTOW)

    @unittest.skipUnless(_okno_dostepne(), "brak serwera graficznego")
    def test_okno_glowne_zapisuje_w_katalogu_testow(self):
        import gui_main
        from helpers import PLIK_USTAWIEN_TESTOW
        self.assertEqual(str(gui_main.CONFIG_FILE), PLIK_USTAWIEN_TESTOW)



@unittest.skipUnless(_okno_dostepne(), "brak serwera graficznego")
class RaportBezObrazu(CzystyStart):
    """Brak pliku z obrazem tla nie moze popsuc raportu."""

    def test_raport_bez_tla(self):
        import tkinter as tk
        import dialogs_gw
        okno = tk.Tk()
        self.addCleanup(okno.destroy)
        widok = dialogs_gw.ReportView(okno, ("TkFixedFont", 9), None)
        widok.pack(fill="both", expand=True)
        okno.update()
        widok.pokaz("linia 1\nlinia 2")
        okno.update()
        self.assertIsNone(widok._tlo)
        self.assertEqual(widok.tekst(), "linia 1\nlinia 2")
        widok.yview_moveto(1.0)



class PodzialRaportuNaBloki(unittest.TestCase):

    def test_raport_z_mapa(self):
        import dialogs_gw
        linie = ["A", "", "Cyl-> 0", "H. S: 0", "0. 0: .", "1. 0: X",
                 "", "Rozpoznanie:"]
        bloki = dialogs_gw._podziel_na_bloki(linie)
        self.assertEqual([m for _, m in bloki], [False, True, False])
        self.assertEqual(bloki[1][0], ["Cyl-> 0", "H. S: 0", "0. 0: .",
                                       "1. 0: X"])

    def test_raport_bez_mapy(self):
        import dialogs_gw
        bloki = dialogs_gw._podziel_na_bloki(["A", "B"])
        self.assertEqual(bloki, [(["A", "B"], False)])


if __name__ == "__main__":
    unittest.main()
