"""
Testy zgrywania plyt CD i DVD.

Plyty budujemy tutaj jako pliki: opis wolumenu ISO 9660 w sektorze 16
i dane w pozostalych. Napedu optycznego w zestawie testow nie ma, wiec
uszkodzone sektory i sciezki audio udajemy - a to wlasnie te przypadki
decyduja, czy program zachowa sie sensownie na prawdziwej, porysowanej
plycie.
"""

import os
import unittest

from helpers import PrzypadekZKatalogiem

import optical

SEKTOR = optical.SEKTOR


def opis_wolumenu(sektorow: int, etykieta: str = "TESTOWA",
                  system: str = "RETROZACHAR",
                  rozmiar_bloku: int = SEKTOR) -> bytes:
    """Opis wolumenu ISO 9660 - to, co lezy w sektorze 16 plyty."""
    pvd = bytearray(SEKTOR)
    pvd[0] = 1                                   # podstawowy opis wolumenu
    pvd[1:6] = optical.SYGNATURA_ISO
    pvd[6] = 1
    pvd[8:40] = system.ljust(32).encode("latin1")
    pvd[40:72] = etykieta.ljust(32).encode("latin1")
    pvd[80:84] = sektorow.to_bytes(4, "little")
    pvd[84:88] = sektorow.to_bytes(4, "big")
    pvd[128:130] = rozmiar_bloku.to_bytes(2, "little")
    return bytes(pvd)


class PlytaTestowa(PrzypadekZKatalogiem):

    def plyta(self, sektorow: int = 100, iso: bool = True,
              etykieta: str = "TESTOWA", blokow_w_opisie: int | None = None,
              nazwa: str = "plyta.iso") -> str:
        # Opis wolumenu lezy w sektorze 16, wiec plyta z ISO 9660 musi miec
        # ich przynajmniej siedemnascie. Krotsza rosla o jeden sektor, bo
        # przypisanie poza koniec dokleja zamiast wstawiac.
        if iso:
            assert sektorow > optical.OPIS_WOLUMENU, \
                "plyta z ISO 9660 musi miec wiecej niz 17 sektorow"
        sciezka = self.sciezka(nazwa)
        obraz = bytearray()
        for numer in range(sektorow):
            obraz += bytes([numer % 251]) * SEKTOR
        if iso:
            obraz[16 * SEKTOR:17 * SEKTOR] = opis_wolumenu(
                blokow_w_opisie if blokow_w_opisie is not None else sektorow,
                etykieta)
        with open(sciezka, "wb") as fh:
            fh.write(bytes(obraz))
        return sciezka


class Rozpoznanie(PlytaTestowa):

    def test_opis_wolumenu(self):
        info = optical.probe(self.plyta(etykieta="POLICE QUEST II"))
        self.assertTrue(info.iso)
        self.assertTrue(info.present)
        self.assertEqual(info.label, "POLICE QUEST II")
        self.assertEqual(info.system_id, "RETROZACHAR")
        self.assertEqual(info.sectors, 100)
        self.assertTrue(info.readable)

    def test_plyta_bez_iso_daje_uwage(self):
        """
        Obraz powstanie, ale warto powiedziec, ze system plikow moze byc
        inny niz spodziewany - plyty Amigi czy konsol nie maja ISO 9660.
        """
        info = optical.probe(self.plyta(iso=False))
        self.assertFalse(info.iso)
        self.assertTrue(info.readable)
        self.assertTrue(any("ISO 9660" in u for u in info.notes))

    def test_opis_wiekszy_niz_nosnik_jest_przycinany(self):
        """
        Uszkodzony opis wolumenu potrafi podac wiecej blokow, niz plyta ma
        naprawde. Czytanie poza nosnik konczylo by sie bledem napedu.
        """
        info = optical.probe(self.plyta(sektorow=50, blokow_w_opisie=5000))
        self.assertEqual(info.sectors, 50)
        self.assertTrue(any("wiecej blokow" in u for u in info.notes))

    def test_brak_pliku(self):
        with self.assertRaises(optical.OpticalError):
            optical.probe(self.sciezka("nie_ma.iso"))

    def test_opis_dla_czlowieka(self):
        opis = optical.opis_plyty(optical.probe(self.plyta(etykieta="GRA")))
        self.assertIn("GRA", opis)
        self.assertIn("sektorow", opis)

    def test_sciezki_audio_sa_zapowiadane(self):
        """
        Sciezki CD-Audio leza poza systemem plikow i do .iso nie wchodza.
        Program ma to powiedziec przed zgrywaniem, a nie zapisac po cichu
        obraz bez muzyki - to najczestsza pulapka przy grach z lat 90.
        """
        prawdziwy = optical._sciezki_plyty

        def spis(uchwyt, info):
            info.data_tracks, info.audio_tracks = 1, 12

        optical._sciezki_plyty = spis
        self.addCleanup(setattr, optical, "_sciezki_plyty", prawdziwy)
        info = optical.probe(self.plyta())
        self.assertTrue(info.has_audio)
        self.assertTrue(any("audio" in u for u in info.notes),
                        "uwaga o sciezkach audio ma sie pojawic")
        self.assertIn("12 audio", optical.opis_plyty(info))

    def test_plyta_z_samymi_danymi_bez_uwagi_o_audio(self):
        info = optical.probe(self.plyta())
        self.assertFalse(info.has_audio)
        self.assertFalse(any("audio" in u for u in info.notes))

    def test_brak_plyty_opisany_wprost(self):
        self.assertEqual(optical.opis_plyty(optical.DiscInfo()),
                         "brak plyty w napedzie")
        self.assertEqual(
            optical.opis_plyty(optical.DiscInfo(tray_open=True)),
            "szuflada otwarta")


class SpisTresci(unittest.TestCase):
    """
    Rodzaj sciezki poznaje sie po jednym bajcie spisu tresci: mlodsze
    cztery bity to sposob adresowania, starsze to pole kontrolne, a w nim
    bit 2 oznacza dane. Pomylenie kolejnosci tych pol sprawia, ze plyta
    z muzyka wyglada jak plyta z danymi i ostrzezenie nigdy nie pada.
    """

    @staticmethod
    def bajt(pole_kontrolne: int, adresowanie: int = 1) -> int:
        return (pole_kontrolne << 4) | adresowanie

    def test_sciezka_z_danymi(self):
        self.assertTrue(optical.sciezka_z_danymi(self.bajt(0x4)))
        self.assertTrue(optical.sciezka_z_danymi(self.bajt(0x6)),
                        "dane z zastrzezonym kopiowaniem to nadal dane")

    def test_sciezka_audio(self):
        for opis, ctrl in (("zwykla", 0x0), ("z korekcja", 0x2),
                           ("czterokanalowa", 0x8)):
            with self.subTest(sciezka=opis):
                self.assertFalse(optical.sciezka_z_danymi(self.bajt(ctrl)))

    def test_adresowanie_nie_ma_znaczenia(self):
        for adr in (0, 1, 2, 3):
            with self.subTest(adresowanie=adr):
                self.assertTrue(optical.sciezka_z_danymi(self.bajt(0x4, adr)))
                self.assertFalse(optical.sciezka_z_danymi(self.bajt(0x0, adr)))

    def test_zapytanie_o_sciezke(self):
        """
        Czego wysylamy do sterownika: numer sciezki i znacznik formatu
        adresu pod wlasciwym indeksem. Samego wywolania bez napedu
        sprawdzic sie nie da, ale jego tresc juz tak.
        """
        wpis = optical.wpis_toc(3)
        self.assertEqual(len(wpis), optical.ROZMIAR_WPISU_TOC)
        self.assertEqual(wpis[0], 3, "numer sciezki na poczatku")
        self.assertEqual(wpis[2], optical.CDROM_LBA,
                         "znacznik formatu w trzecim bajcie")
        self.assertEqual(wpis[1], 0, "pole odpowiedzi zostaje puste")

    def test_rozmiar_wpisu_z_wyrownaniem(self):
        """
        Struktura sterownika ma dwanascie bajtow przez wyrownanie adresu.
        Krotszy bufor sprawia, ze wywolanie zawodzi i spis tresci nie
        wczytuje sie wcale - plyta wyglada wtedy jak plyta bez sciezek.
        """
        self.assertEqual(optical.ROZMIAR_WPISU_TOC, 12)


class Porcje(PlytaTestowa):

    def test_rozmiar_porcji_nie_zmienia_wyniku(self):
        zrodlo = self.plyta(sektorow=300)
        wyniki = []
        for porcja in (1, 7, 256, 4096):
            cel = self.sciezka(f"kopia{porcja}.iso")
            optical.read_to_iso(zrodlo, cel, chunk=porcja)
            with open(cel, "rb") as fh:
                wyniki.append(fh.read())
        with open(zrodlo, "rb") as fh:
            oryginal = fh.read()
        for numer, dane in enumerate(wyniki):
            with self.subTest(wariant=numer):
                self.assertEqual(dane, oryginal)

    def test_porcja_wieksza_niz_plyta(self):
        cel = self.sciezka("k.iso")
        raport = optical.read_to_iso(self.plyta(sektorow=40), cel,
                                     chunk=9999)
        self.assertEqual(raport.done, 40)
        self.assertEqual(os.path.getsize(cel), 40 * SEKTOR)



class Zgrywanie(PlytaTestowa):

    def test_kopia_jest_identyczna(self):
        zrodlo = self.plyta(sektorow=80)
        cel = self.sciezka("kopia.iso")
        raport = optical.read_to_iso(zrodlo, cel)
        self.assertTrue(raport.complete)
        self.assertEqual(raport.done, 80)
        with open(zrodlo, "rb") as a, open(cel, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_postep_rosnie_i_konczy_sie_na_calosci(self):
        widziane = []
        optical.read_to_iso(
            self.plyta(sektorow=200), self.sciezka("k.iso"),
            progress=lambda r: widziane.append(r.done) or True)
        self.assertEqual(widziane, sorted(widziane))
        self.assertEqual(widziane[-1], 200)

    def test_przerwanie(self):
        raport = optical.read_to_iso(
            self.plyta(sektorow=500), self.sciezka("k.iso"),
            progress=lambda r: r.done < 128)
        self.assertTrue(raport.cancelled)
        self.assertFalse(raport.complete)
        self.assertLess(raport.done, 500)

    def test_plyta_bez_danych_odrzucona(self):
        pusty = self.sciezka("pusty.iso")
        with open(pusty, "wb") as fh:
            fh.write(b"")
        with self.assertRaises(optical.OpticalError):
            optical.read_to_iso(pusty, self.sciezka("k.iso"))


class UszkodzonePlyty(PlytaTestowa):
    """
    Porysowana plyta to najczestszy przypadek przy starych nosnikach.
    Napedu w zestawie testow nie ma, wiec odmowe odczytu udajemy - liczy
    sie to, co program z nia zrobi.
    """

    def podstaw_uszkodzenia(self, nieczytelne: set):
        prawdziwy = optical._czytaj

        def czytaj(uchwyt, od, ile):
            if any(numer in nieczytelne for numer in range(od, od + ile)):
                if ile > 1:
                    return None              # cala porcja zawodzi
                return None
            return prawdziwy(uchwyt, od, ile)

        optical._czytaj = czytaj
        self.addCleanup(setattr, optical, "_czytaj", prawdziwy)

    def test_uszkodzone_sektory_nie_przerywaja_zgrywania(self):
        self.podstaw_uszkodzenia({70, 71, 300})
        zrodlo = self.plyta(sektorow=400)
        cel = self.sciezka("kopia.iso")
        raport = optical.read_to_iso(zrodlo, cel, retries=2)
        self.assertEqual(raport.done, 400, "reszta plyty ma byc odzyskana")
        self.assertEqual(raport.bad, [70, 71, 300])
        self.assertFalse(raport.complete)

    def test_nieczytelne_wypelniane_zerami(self):
        self.podstaw_uszkodzenia({5})
        cel = self.sciezka("kopia.iso")
        optical.read_to_iso(self.plyta(sektorow=40), cel)
        with open(cel, "rb") as fh:
            fh.seek(5 * SEKTOR)
            self.assertEqual(fh.read(SEKTOR), bytes(SEKTOR))

    def test_dobre_sektory_z_uszkodzonej_porcji_zostaja(self):
        """
        Porcja zawodzi w calosci, ale schodzimy do pojedynczych sektorow -
        z porysowanej plyty odzyskujemy wszystko poza samymi rysami.
        """
        self.podstaw_uszkodzenia({10})
        zrodlo = self.plyta(sektorow=64)
        cel = self.sciezka("kopia.iso")
        optical.read_to_iso(zrodlo, cel)
        with open(zrodlo, "rb") as a, open(cel, "rb") as b:
            oryginal, kopia = a.read(), b.read()
        for numer in (0, 9, 11, 63):
            with self.subTest(sektor=numer):
                self.assertEqual(kopia[numer * SEKTOR:(numer + 1) * SEKTOR],
                                 oryginal[numer * SEKTOR:(numer + 1) * SEKTOR])

    def test_liczba_prob_jest_respektowana(self):
        proby = []
        prawdziwy = optical._czytaj

        def czytaj(uchwyt, od, ile):
            if ile == 1 and od == 3:
                proby.append(od)
                return None
            if ile > 1 and od <= 3 < od + ile:
                return None
            return prawdziwy(uchwyt, od, ile)

        optical._czytaj = czytaj
        self.addCleanup(setattr, optical, "_czytaj", prawdziwy)
        optical.read_to_iso(self.plyta(sektorow=20), self.sciezka("k.iso"),
                            retries=5)
        self.assertEqual(len(proby), 5)


class PlytaAudio(PlytaTestowa):
    """
    Plyty z sama muzyka nie da sie zgrac do .iso i nie jest to kwestia
    jakosci nosnika: muzyka nie lezy w sektorach po 2048 bajtow. Program
    probowal mimo to - schodzil do pojedynczych sektorow, mielil z piecioma
    probami na kazdy i po trzech minutach byl na dziewieciu procentach.
    Zgloszone z prawdziwego napedu.
    """

    def podstaw_sciezki(self, dane: int, audio: int):
        prawdziwy = optical._sciezki_plyty

        def spis(uchwyt, info):
            info.data_tracks, info.audio_tracks = dane, audio

        optical._sciezki_plyty = spis
        self.addCleanup(setattr, optical, "_sciezki_plyty", prawdziwy)

    def test_rozpoznana_i_odrzucona(self):
        self.podstaw_sciezki(dane=0, audio=14)
        info = optical.probe(self.plyta())
        self.assertTrue(info.audio_only)
        self.assertFalse(info.readable)
        self.assertTrue(any("sama muzyka" in u for u in info.notes))
        self.assertTrue(any("WAV" in u for u in info.notes),
                        "warto powiedziec, czym taka plyte zgrac")

    def test_zgrywanie_odmawia_od_razu(self):
        self.podstaw_sciezki(dane=0, audio=14)
        with self.assertRaises(optical.OpticalError) as blad:
            optical.read_to_iso(self.plyta(), self.sciezka("k.iso"))
        self.assertIn("audio", str(blad.exception))

    def test_gra_z_muzyka_na_plycie_da_sie_zgrac(self):
        """
        Plyta mieszana ma dane i muzyke - dane zgrywamy, o muzyce tylko
        uprzedzamy. To co innego niz plyta z sama muzyka.
        """
        self.podstaw_sciezki(dane=1, audio=12)
        info = optical.probe(self.plyta())
        self.assertFalse(info.audio_only)
        self.assertTrue(info.readable)
        self.assertTrue(any("bez muzyki" in u for u in info.notes))


class PlytaKtoraNicNieOddaje(PlytaTestowa):

    def test_zgrywanie_konczy_sie_zamiast_mielic(self):
        """
        Gdy nie udaje sie nic od samego poczatku, dalsze proby nie maja
        sensu - a przy piatce prob na sektor trwaja godzinami.
        """
        prawdziwy = optical._czytaj
        optical._czytaj = lambda *a: None
        self.addCleanup(setattr, optical, "_czytaj", prawdziwy)
        with self.assertRaises(optical.OpticalError) as blad:
            optical.read_to_iso(self.plyta(sektorow=5000),
                                self.sciezka("k.iso"), retries=1, chunk=32)
        self.assertIn("ani jednego", str(blad.exception))

    def test_kilka_bledow_na_poczatku_nie_przerywa(self):
        """Uszkodzony poczatek plyty to jeszcze nie plyta nie do odczytu."""
        prawdziwy = optical._czytaj

        def czytaj(uchwyt, od, ile):
            if od < 3:
                return None
            return prawdziwy(uchwyt, od, ile)

        optical._czytaj = czytaj
        self.addCleanup(setattr, optical, "_czytaj", prawdziwy)
        raport = optical.read_to_iso(self.plyta(sektorow=300),
                                     self.sciezka("k.iso"), chunk=1)
        self.assertEqual(raport.done, 300)
        self.assertEqual(raport.bad, [0, 1, 2])



class KrotkiOdczyt(PlytaTestowa):
    """
    Naped potrafi oddac mniej danych, niz poproszono. Wczesniej program
    dopelnial reszte zerami i uznawal porcje za udana - czyli po cichu
    wstawial puste miejsca w obraz, nie mowiac o tym ani slowa.
    """

    def podstaw_krotki_odczyt(self, od_sektora: int):
        prawdziwy_odczyt = os.read

        def krotki(uchwyt, ile):
            dane = prawdziwy_odczyt(uchwyt, ile)
            polozenie = os.lseek(uchwyt, 0, os.SEEK_CUR) - len(dane)
            if polozenie // SEKTOR == od_sektora and len(dane) > SEKTOR:
                return dane[:SEKTOR]           # oddaje tylko jeden sektor
            return dane

        os.read = krotki
        self.addCleanup(setattr, os, "read", prawdziwy_odczyt)

    def test_krotki_odczyt_nie_wstawia_cichych_zer(self):
        zrodlo = self.plyta(sektorow=100)
        cel = self.sciezka("kopia.iso")
        self.podstaw_krotki_odczyt(32)
        optical.read_to_iso(zrodlo, cel, chunk=32)
        with open(zrodlo, "rb") as a, open(cel, "rb") as b:
            self.assertEqual(a.read(), b.read(),
                             "obraz ma byc wierny mimo krotkiego odczytu")


class PrzerwanieKlawiszem(PlytaTestowa):

    def test_ctrl_c_konczy_sie_komunikatem(self):
        """
        Przerwanie zgrywania to normalna droga wyjscia, a nie awaria -
        slad wyjatku tylko zaciemnia to, co juz zgrane.
        """
        import contextlib
        import io as we_wy
        prawdziwe = optical.read_to_iso

        def przerwij(*a, **k):
            raise KeyboardInterrupt

        optical.read_to_iso = przerwij
        self.addCleanup(setattr, optical, "read_to_iso", prawdziwe)
        wyjscie, bledy = we_wy.StringIO(), we_wy.StringIO()
        with contextlib.redirect_stdout(wyjscie), \
                contextlib.redirect_stderr(bledy):
            try:
                kod = optical.main(["read", self.plyta(),
                                    self.sciezka("k.iso")])
            except KeyboardInterrupt:
                # Przechwytujemy tutaj, bo przerwanie, ktore wyjdzie poza
                # test, zatrzymuje caly przebieg zestawu - i nie dowiemy
                # sie, ze cokolwiek bylo nie tak.
                self.fail("program nie przechwycil przerwania klawiszem")
        self.assertEqual(kod, 1)
        self.assertIn("przerwano", bledy.getvalue())
        self.assertNotIn("Traceback", bledy.getvalue())



class WierszPolecen(PlytaTestowa):

    def uruchom(self, *argumenty):
        import contextlib
        import io
        wyjscie, bledy = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(wyjscie), \
                contextlib.redirect_stderr(bledy):
            kod = optical.main(list(argumenty))
        return kod, wyjscie.getvalue(), bledy.getvalue()

    def test_probe(self):
        kod, wyjscie, _ = self.uruchom("probe", self.plyta(etykieta="GRA"))
        self.assertEqual(kod, 0)
        self.assertIn("GRA", wyjscie)

    def test_read(self):
        cel = self.sciezka("kopia.iso")
        kod, wyjscie, _ = self.uruchom("read", self.plyta(sektorow=40), cel)
        self.assertEqual(kod, 0)
        # Wiersz polecen wypisuje ten sam raport co okno - od wersji 1.13
        # zamiast wlasnego, krotszego podsumowania.
        self.assertIn("Plyta zgrana w calosci", wyjscie)
        self.assertIn(cel, wyjscie)
        self.assertEqual(os.path.getsize(cel), 40 * SEKTOR)

    def test_blad_bez_sladu_wyjatku(self):
        kod, _, bledy = self.uruchom("probe", self.sciezka("nie_ma.iso"))
        self.assertEqual(kod, 1)
        self.assertNotIn("Traceback", bledy)


class WykrywanieNapedow(unittest.TestCase):

    def test_lista_nie_wywraca_sie_bez_napedu(self):
        """Na maszynie bez napedu optycznego ma wyjsc pusta lista."""
        self.assertIsInstance(optical.list_drives(), list)


if __name__ == "__main__":
    unittest.main()
