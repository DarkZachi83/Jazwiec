"""
Testy rozkladania programu na dyskietki i generowanego instalatora.

Najmocniejszym sprawdzeniem jest tu SymulacjaInstalatora: wykonuje
wygenerowany plik wsadowy tak, jak zrobilby to COMMAND.COM, razem ze
zmianami dyskietek i sklejaniem plikow podzielonych, a na koncu porownuje
odtworzone drzewo ze zrodlem bajt w bajt. Bez DOS-a pod reka to jedyny
sposob, zeby sprawdzic instalator naprawde, a nie tylko obejrzec go wzrokiem.
"""

import hashlib
import os
import unittest

from helpers import PrzypadekZKatalogiem, czy_jest, fsck_czysty

import fat12
import diskset


class Planowanie(PrzypadekZKatalogiem):

    def test_program_mieszczacy_sie_daje_jedna_dyskietke(self):
        zrodlo = self.zbuduj_drzewo({"GRA.EXE": b"x" * 10_000})
        plan = diskset.zaplanuj(zrodlo, "1440", "GRA")
        self.assertEqual(plan.liczba_dyskietek, 1)
        self.assertFalse(plan.podzielone)

    def test_plik_wiekszy_niz_nosnik_jest_dzielony(self):
        zrodlo = self.zbuduj_drzewo({"WIELKI.BIN": os.urandom(3_500_000)})
        plan = diskset.zaplanuj(zrodlo, "1440", "TEST")
        czesci = [c for d in plan.dyskietki for c in d.czesci]
        self.assertEqual(len(plan.podzielone), 1)
        self.assertGreaterEqual(len(czesci), 3)
        self.assertEqual(sum(c.rozmiar for c in czesci), 3_500_000,
                         "suma czesci musi sie zgadzac co do bajtu")

    def test_o_liczbie_moga_zadecydowac_wpisy_a_nie_miejsce(self):
        """
        Przy wielu drobnych plikach katalog glowny konczy sie pierwszy.
        Dyskietka 720 KB miesci 112 wpisow, a nie tysiac malych plikow.
        """
        opis = {f"P{numer:04d}.DAT": b"x" * 200 for numer in range(400)}
        zrodlo = self.zbuduj_drzewo(opis)
        plan = diskset.zaplanuj(zrodlo, "720", "DROBNE")
        limit = fat12.FLOPPY_FORMATS["720"].root_entries
        self.assertGreater(plan.liczba_dyskietek, 3)
        for dysk in plan.dyskietki:
            with self.subTest(dysk=dysk.numer):
                self.assertLess(dysk.wpisy, limit)

    def test_ostrzega_gdy_wskazano_poziom_za_wysoko(self):
        zrodlo = self.zbuduj_drzewo({"Gra 1988/PLIK.TXT": b"x"})
        plan = diskset.zaplanuj(zrodlo, "1440", "GRA")
        self.assertTrue(any("poziom za wysoko" in o
                            for o in plan.ostrzezenia))

    def test_katalogi_posrednie_i_puste_sa_uwzgledniane(self):
        """
        MD w DOS-ie nie tworzy sciezek wielopoziomowych, a katalog na zapisy
        stanu gry bywa w zrodle pusty.
        """
        zrodlo = self.zbuduj_drzewo({
            "GRA/DANE/PLIK.DAT": b"x",
            "GRA/SAVE": None,
        })
        plan = diskset.zaplanuj(zrodlo, "1440", "GRA")
        self.assertIn("GRA", plan.katalogi)
        self.assertIn("GRA\\SAVE", plan.katalogi)
        self.assertLess(plan.katalogi.index("GRA"),
                        plan.katalogi.index("GRA\\DANE"),
                        "katalog nadrzedny musi powstac wczesniej")


class NazwyDocelowe(PrzypadekZKatalogiem):

    def test_propozycja_z_nazwy_katalogu(self):
        self.assertEqual(
            diskset.popraw_nazwe("Pool of Radiance (1988)(SSI) [RPG]"),
            "POOLOFRA")

    def test_odrzuca_nazwy_niedozwolone(self):
        for zla in ("POOL.EXE", "ZBYTDLUGANAZWA", "PO OL", ""):
            with self.subTest(nazwa=zla):
                with self.assertRaises(diskset.PaczkaError):
                    diskset.sprawdz_nazwe(zla)

    def test_dysk_docelowy(self):
        self.assertEqual(diskset.sprawdz_dysk("d"), "D:")
        self.assertEqual(diskset.sprawdz_dysk("C:"), "C:")
        for zly in ("CD", "1", ""):
            with self.subTest(dysk=zly):
                with self.assertRaises(diskset.PaczkaError):
                    diskset.sprawdz_dysk(zly)


class NazwaInstalatora(PrzypadekZKatalogiem):
    """
    Wsad instalatora lezy w katalogu docelowym i jest stamtad wykonywany.
    Skopiowanie pliku programu o tej samej nazwie nadpisaloby go w trakcie
    dzialania, a COMMAND.COM czyta wsad przyrostowo.
    """

    def test_domyslna_gdy_brak_kolizji(self):
        zrodlo = self.zbuduj_drzewo({"GRA.EXE": b"x"})
        plan = diskset.zaplanuj(zrodlo, "720", "GRA")
        self.assertEqual(plan.wsad, diskset.NAZWA_WSADU)

    def test_zmieniana_przy_kolizji(self):
        zrodlo = self.zbuduj_drzewo({diskset.NAZWA_WSADU: b"@ECHO OFF\r\n"})
        plan = diskset.zaplanuj(zrodlo, "720", "GRA")
        self.assertNotEqual(plan.wsad, diskset.NAZWA_WSADU)
        self.assertTrue(any("instalator nazwano" in o
                            for o in plan.ostrzezenia))

    def test_setup_bat_programu_nie_nadpisuje_wsadu(self):
        """Wlasnie to przerywalo instalacje przy drugiej dyskietce."""
        zrodlo = self.zbuduj_drzewo({"SETUP.BAT": b"@ECHO OFF\r\n",
                                     "GRA.EXE": b"x" * 1000})
        plan = diskset.zaplanuj(zrodlo, "720", "GRA")
        wyjscie = self.sciezka("obrazy")
        diskset.zbuduj(plan, wyjscie, "GRA")
        obraz = fat12.Fat12Image(os.path.join(wyjscie, "DYSK01.img"),
                                 read_only=True)
        self.addCleanup(obraz.close)
        wsad = obraz.read_file("/" + plan.wsad).decode("cp437")
        for linia in wsad.split("\r\n"):
            if linia.startswith("COPY %2"):
                self.assertNotIn(f"\\{plan.wsad}", linia,
                                 "instalator kopiuje plik na samego siebie")


class Wsad(PrzypadekZKatalogiem):

    def zbuduj(self, opis, format_klucz="1440", dysk="C:"):
        zrodlo = self.zbuduj_drzewo(opis)
        plan = diskset.zaplanuj(zrodlo, format_klucz, "TEST",
                               dysk_docelowy=dysk)
        wyjscie = self.sciezka("obrazy")
        pliki = diskset.zbuduj(plan, wyjscie, "TEST")
        return zrodlo, plan, pliki

    def test_linie_miesza_sie_w_limicie_dos(self):
        """
        Wiersz polecen DOS-a przyjmuje okolo 127 znakow. Sklejanie pieciu
        czesci pelnymi sciezkami ten limit przekraczalo.
        """
        _, plan, pliki = self.zbuduj({"WIELKI.BIN": os.urandom(6_000_000)})
        obraz = fat12.Fat12Image(pliki[0], read_only=True)
        self.addCleanup(obraz.close)
        for nazwa in ("INSTALL.BAT", plan.wsad):
            tresc = obraz.read_file("/" + nazwa).decode("cp437")
            for linia in tresc.split("\r\n"):
                with self.subTest(plik=nazwa, linia=linia[:40]):
                    self.assertLessEqual(len(linia), diskset.MAX_LINIA_WSADU)

    def test_wsad_jest_czystym_ascii_z_koncami_dos(self):
        _, plan, pliki = self.zbuduj({"PLIK.TXT": b"x"})
        obraz = fat12.Fat12Image(pliki[0], read_only=True)
        self.addCleanup(obraz.close)
        for nazwa in ("INSTALL.BAT", plan.wsad):
            surowe = obraz.read_file("/" + nazwa)
            with self.subTest(plik=nazwa):
                self.assertTrue(all(b < 128 for b in surowe))
                self.assertNotIn(b"\n", surowe.replace(b"\r\n", b""))

    def test_bez_zmiennych_srodowiskowych(self):
        """
        Srodowisko DOS-a ma domyslnie 256 bajtow i SET potrafi sie w nim
        nie zmiescic. Nierozwiniete %ZMIENNA% laduje wsad na dyskietce.
        """
        _, plan, pliki = self.zbuduj({"PLIK.TXT": b"x"})
        obraz = fat12.Fat12Image(pliki[0], read_only=True)
        self.addCleanup(obraz.close)
        for nazwa in ("INSTALL.BAT", plan.wsad):
            tresc = obraz.read_file("/" + nazwa).decode("cp437")
            with self.subTest(plik=nazwa):
                self.assertNotIn("SET ", tresc)
                self.assertNotIn("%ZDYSK%", tresc)

    def test_dysk_docelowy_trafia_do_instalatora(self):
        _, _, pliki = self.zbuduj({"PLIK.TXT": b"x"}, dysk="D:")
        obraz = fat12.Fat12Image(pliki[0], read_only=True)
        self.addCleanup(obraz.close)
        tresc = obraz.read_file("/INSTALL.BAT").decode("cp437")
        self.assertIn("D:\\TEST", tresc)

    def test_instalator_wypisuje_dostepne_dyski(self):
        _, _, pliki = self.zbuduj({"PLIK.TXT": b"x"})
        obraz = fat12.Fat12Image(pliki[0], read_only=True)
        self.addCleanup(obraz.close)
        tresc = obraz.read_file("/INSTALL.BAT").decode("cp437")
        self.assertIn("IF EXIST D:\\NUL", tresc)
        self.assertIn("GOTO ZLYDYSK", tresc)

    @unittest.skipUnless(czy_jest("fsck.fat"), "brak fsck.fat")
    def test_obrazy_sa_poprawne(self):
        _, _, pliki = self.zbuduj({
            "GRA.EXE": os.urandom(50_000),
            "DANE/A.DAT": os.urandom(30_000),
        })
        for sciezka in pliki:
            with self.subTest(obraz=os.path.basename(sciezka)):
                self.assertTrue(fsck_czysty(sciezka))


class SymulacjaInstalatora(PrzypadekZKatalogiem):
    """
    Wykonuje wygenerowany wsad tak, jak zrobilby to COMMAND.COM.

    Katalogiem biezacym jest katalog docelowy - ustawia go INSTALL.BAT przed
    oddaniem sterowania i nic go pozniej nie zmienia. Sciezki wzgledne w
    poleceniach sklejajacych opieraja sie wlasnie na tym zalozeniu.
    """

    DYSK, ZRODLO = "C:", "A:"

    def wykonaj(self, plan, obrazy_sciezki, cel_host):
        obrazy = {os.path.basename(p): fat12.Fat12Image(p, read_only=True)
                  for p in obrazy_sciezki}
        for obraz in obrazy.values():
            self.addCleanup(obraz.close)

        def na_dyskietkach(nazwa):
            for obraz in obrazy.values():
                if obraz.exists("/" + nazwa):
                    return obraz
            return None

        przedrostek = f"{self.DYSK}\\{plan.katalog_docelowy}"

        def host(sciezka_dos: str) -> str:
            czysta = sciezka_dos.replace("%1", self.DYSK) \
                                .replace("%2", self.ZRODLO)
            czysta = czysta.replace(przedrostek, "").lstrip("\\")
            return os.path.join(cel_host, czysta.replace("\\", "/")) \
                if czysta else cel_host

        wsad = obrazy["DYSK01.img"].read_file("/" + plan.wsad).decode("cp437")
        licznik = {"md": 0, "copy": 0, "append": 0, "del": 0, "check": 0}

        for surowa in wsad.replace("\r\n", "\n").split("\n"):
            linia = surowa.strip()
            if linia.endswith(" >NUL"):
                linia = linia[:-5].rstrip()

            if linia.startswith("IF NOT EXIST") and "\\NUL MD " in linia:
                os.makedirs(host(linia.split("MD ")[1]), exist_ok=True)
                licznik["md"] += 1
            elif linia.startswith("COPY /B") and "+" in linia:
                cel, czesc = linia[8:].split("+")
                with open(host(czesc), "rb") as zr, \
                        open(host(cel), "ab") as fh:
                    fh.write(zr.read())
                licznik["append"] += 1
            elif linia.startswith("COPY /B"):
                zrodlo, cel = linia[8:].split()
                obraz = na_dyskietkach(zrodlo)
                self.assertIsNotNone(obraz, f"brak {zrodlo} na dyskietkach")
                os.makedirs(os.path.dirname(host(cel)), exist_ok=True)
                with open(host(cel), "wb") as fh:
                    fh.write(obraz.read_file("/" + zrodlo))
                licznik["copy"] += 1
            elif linia.startswith("COPY %2"):
                czesci = linia.split()
                nazwa = czesci[1].replace("%2\\", "")
                obraz = na_dyskietkach(nazwa)
                self.assertIsNotNone(obraz, f"brak {nazwa} na dyskietkach")
                cel = host(czesci[2])
                os.makedirs(os.path.dirname(cel), exist_ok=True)
                with open(cel, "wb") as fh:
                    fh.write(obraz.read_file("/" + nazwa))
                licznik["copy"] += 1
            elif linia.startswith("IF NOT EXIST") and "GOTO BLAD" in linia:
                sciezka = host(linia.split()[3])
                self.assertTrue(os.path.exists(sciezka),
                                f"instalator zglosilby blad: {linia}")
                licznik["check"] += 1
            elif linia.startswith("DEL "):
                sciezka = host(linia[4:])
                if os.path.exists(sciezka):
                    os.remove(sciezka)
                    licznik["del"] += 1
        return licznik

    def sumy(self, korzen: str) -> dict:
        wynik = {}
        for biezacy, _, nazwy in os.walk(korzen):
            for nazwa in nazwy:
                pelna = os.path.join(biezacy, nazwa)
                wzgledna = os.path.relpath(pelna, korzen)
                with open(pelna, "rb") as fh:
                    wynik[wzgledna] = hashlib.sha256(fh.read()).hexdigest()
        return wynik

    def sprawdz_odtworzenie(self, opis, format_klucz="1440"):
        zrodlo = self.zbuduj_drzewo(opis)
        plan = diskset.zaplanuj(zrodlo, format_klucz, "TEST")
        obrazy = diskset.zbuduj(plan, self.sciezka("obrazy"), "TEST")
        cel = self.sciezka("dysk_c", "TEST")
        os.makedirs(cel, exist_ok=True)
        self.wykonaj(plan, obrazy, cel)

        zrodlowe = self.sumy(zrodlo)
        odtworzone = self.sumy(cel)
        self.assertEqual(len(zrodlowe), len(odtworzone))
        self.assertEqual(set(zrodlowe.values()), set(odtworzone.values()),
                         "odtworzone pliki musza zgadzac sie co do bajtu")
        return plan, cel

    def test_program_na_jednej_dyskietce(self):
        self.sprawdz_odtworzenie({
            "GRA.EXE": os.urandom(30_000),
            "DANE/A.DAT": os.urandom(5_000),
        })

    def test_program_na_kilku_dyskietkach_z_plikiem_dzielonym(self):
        plan, _ = self.sprawdz_odtworzenie({
            "WIELKI.BIN": os.urandom(2_500_000),
            "GRA.EXE": os.urandom(400_000),
            "DANE/A.DAT": os.urandom(100_000),
            "DANE/B.DAT": os.urandom(80_000),
        })
        self.assertGreater(plan.liczba_dyskietek, 1)
        self.assertEqual(len(plan.podzielone), 1)

    def test_katalog_pusty_jest_odtwarzany(self):
        _, cel = self.sprawdz_odtworzenie({
            "GRA.EXE": b"x" * 100,
            "GRA/DANE/PLIK.DAT": b"y" * 100,
            "GRA/SAVE": None,
        })
        self.assertTrue(os.path.isdir(os.path.join(cel, "GRA", "SAVE")))

    def test_program_z_wlasnym_setup_bat(self):
        plan, cel = self.sprawdz_odtworzenie({
            "SETUP.BAT": b"@ECHO OFF\r\nECHO Konfiguracja\r\n",
            "GRA.EXE": os.urandom(20_000),
        })
        with open(os.path.join(cel, "SETUP.BAT"), "rb") as fh:
            self.assertIn(b"Konfiguracja", fh.read())


class ObrazStartowy(PrzypadekZKatalogiem):

    def test_pliki_systemowe_zostaja_nietkniete(self):
        podstawa = self.sciezka("boot.img")
        fmt = fat12.FLOPPY_FORMATS["1440"]
        fat12.format_image(podstawa, fmt, "DOS", overwrite=True)
        obraz = fat12.Fat12Image(podstawa)
        obraz.write_file("/IO.SYS", b"S" * 40_000)
        obraz.write_file("/COMMAND.COM", b"C" * 54_000)
        obraz.close()

        zrodlo = self.zbuduj_drzewo({"GRA.EXE": os.urandom(20_000)})
        plan = diskset.zaplanuj(zrodlo, "1440", "GRA",
                               obraz_bazowy=podstawa)
        pliki = diskset.zbuduj(plan, self.sciezka("obrazy"), "GRA",
                              obraz_bazowy=podstawa)
        pierwszy = fat12.Fat12Image(pliki[0], read_only=True)
        self.addCleanup(pierwszy.close)
        nazwy = {e.name for e in pierwszy.listdir("/")}
        self.assertIn("IO.SYS", nazwy)
        self.assertIn("COMMAND.COM", nazwy)
        self.assertIn("INSTALL.BAT", nazwy)

    def test_niezgodny_format_jest_odrzucany(self):
        podstawa = self.sciezka("mala.img")
        fat12.format_image(podstawa, fat12.FLOPPY_FORMATS["720"], "DOS",
                           overwrite=True)
        zrodlo = self.zbuduj_drzewo({"GRA.EXE": b"x"})
        with self.assertRaises(diskset.PaczkaError):
            diskset.zaplanuj(zrodlo, "1440", "GRA", obraz_bazowy=podstawa)


if __name__ == "__main__":
    unittest.main()
