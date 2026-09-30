"""Testy silnika FAT12: formatowanie, pliki, katalogi, nazwy 8.3."""

import os
import subprocess
import unittest

from helpers import PrzypadekZKatalogiem, czy_jest, fsck_czysty

import fat12
import engines


class Formaty(PrzypadekZKatalogiem):
    """Kazdy z dziewieciu formatow musi dac nosnik zgodny ze specyfikacja."""

    def test_geometria_zgadza_sie_z_deklaracja(self):
        for klucz, fmt in fat12.FLOPPY_FORMATS.items():
            with self.subTest(format=klucz):
                sciezka = self.sciezka(f"{klucz}.img")
                fat12.format_image(sciezka, fmt, "TEST", overwrite=True)
                self.assertEqual(os.path.getsize(sciezka), fmt.size_bytes)
                obraz = fat12.Fat12Image(sciezka)
                self.assertEqual(obraz.bytes_per_sector, fmt.bytes_per_sector)
                self.assertEqual(obraz.total_sectors, fmt.total_sectors)
                self.assertLess(obraz.cluster_count, 4085,
                                "powyzej tej liczby klastrow to juz FAT16")
                obraz.close()

    @unittest.skipUnless(czy_jest("fsck.fat"), "brak fsck.fat")
    def test_fsck_nie_ma_zastrzezen(self):
        """
        Niezalezne potwierdzenie poprawnosci. Wlasny silnik nie moze byc
        jedynym sedzia w swojej sprawie.
        """
        for klucz, fmt in fat12.FLOPPY_FORMATS.items():
            with self.subTest(format=klucz):
                sciezka = self.sciezka(f"{klucz}.img")
                fat12.format_image(sciezka, fmt, "TEST", overwrite=True)
                obraz = fat12.Fat12Image(sciezka)
                obraz.write_file("/DANE.BIN", os.urandom(5000))
                obraz.mkdir("/PODKAT")
                obraz.write_file("/PODKAT/PLIK.TXT", b"tresc")
                obraz.mkdir("/PODKAT/GLEBIEJ")
                obraz.close()
                self.assertTrue(fsck_czysty(sciezka))

    def test_etykieta_domyslna_nie_zalezy_od_jezyka(self):
        """Tresc zapisana na nosniku nie moze zmieniac sie z jezykiem okna."""
        etykiety = set()
        for jezyk in ("pl", "en"):
            fat12.set_language(jezyk)
            sciezka = self.sciezka(f"bez-{jezyk}.img")
            fat12.format_image(sciezka, fat12.FLOPPY_FORMATS["720"], "",
                               overwrite=True)
            obraz = fat12.Fat12Image(sciezka)
            etykiety.add(obraz.get_label())
            obraz.close()
        fat12.set_language("pl")
        self.assertEqual(etykiety, {"NO NAME"})


class OperacjeNaPlikach(PrzypadekZKatalogiem):

    def setUp(self):
        super().setUp()
        self.obraz_sciezka = self.sciezka("dysk.img")
        fat12.format_image(self.obraz_sciezka, fat12.FLOPPY_FORMATS["1440"],
                           "TESTY", overwrite=True)
        self.obraz = fat12.Fat12Image(self.obraz_sciezka)
        self.addCleanup(self.obraz.close)

    def test_odczyt_zwraca_dokladnie_to_co_zapisano(self):
        dane = os.urandom(200_000)
        self.obraz.write_file("/DUZY.BIN", dane)
        self.assertEqual(self.obraz.read_file("/DUZY.BIN"), dane)

    def test_nadpisanie_w_dol_skraca_plik(self):
        self.obraz.write_file("/PLIK.TXT", b"A" * 5000)
        self.obraz.write_file("/PLIK.TXT", b"B" * 10)
        self.assertEqual(self.obraz.read_file("/PLIK.TXT"), b"B" * 10)

    def test_usuniecie_zwalnia_miejsce(self):
        przed = self.obraz.free_bytes
        self.obraz.write_file("/DUZY.BIN", os.urandom(100_000))
        self.obraz.remove("/DUZY.BIN")
        self.assertEqual(self.obraz.free_bytes, przed)

    def test_podkatalog_rosnie_ponad_jeden_klaster(self):
        self.obraz.mkdir("/KAT")
        for numer in range(40):
            self.obraz.write_file(f"/KAT/P{numer:02d}.DAT", b"z" * 100)
        self.assertEqual(len(self.obraz.listdir("/KAT")), 40)

    def test_katalog_glowny_ma_twardy_limit(self):
        """Nie miejsce, tylko liczba wpisow konczy sie tu pierwsza."""
        maly = self.sciezka("maly.img")
        fat12.format_image(maly, fat12.FLOPPY_FORMATS["360"], "MALY",
                           overwrite=True)
        obraz = fat12.Fat12Image(maly)
        self.addCleanup(obraz.close)
        with self.assertRaises(fat12.Fat12Error):
            for numer in range(200):
                obraz.write_file(f"/P{numer:05d}.TXT", b"x")
        self.assertGreater(len(obraz.listdir("/")), 100)

    def test_brak_miejsca_nie_zostawia_sierot(self):
        wolne = self.obraz.free_bytes
        with self.assertRaises(fat12.Fat12Error):
            self.obraz.write_file("/OGROMNY.BIN", b"x" * (wolne * 2))
        self.assertEqual(self.obraz.free_bytes, wolne)


class Nazwy83(unittest.TestCase):

    def test_skracanie(self):
        przypadki = [
            ("plik.txt", "PLIK.TXT"),
            ("bardzo dluga nazwa.tekst", "BARDZODL.TEK"),
            ("bez rozszerzenia", "BEZROZSZ"),
        ]
        for wejscie, oczekiwane in przypadki:
            with self.subTest(nazwa=wejscie):
                self.assertEqual(fat12.to_short_name(wejscie), oczekiwane)

    def test_kolizje_rozwiazywane_tylda(self):
        zajete = {"PLIK.TXT"}
        druga = fat12.to_short_name("plik.txt", zajete)
        self.assertNotEqual(druga, "PLIK.TXT")
        self.assertIn("~", druga)


class WpisyKropkowe(PrzypadekZKatalogiem):
    """
    Wpisy "." i ".." zajmuja cale 11-bajtowe pole nazwy.

    Blad w tym miejscu przez dluzszy czas przechodzil niezauwazony, bo
    mtools go tolerowal, a fsck.fat zglaszal dopiero przy podkatalogach.
    """

    def test_pola_nazwy_sa_poprawne(self):
        sciezka = self.sciezka("kropki.img")
        fat12.format_image(sciezka, fat12.FLOPPY_FORMATS["720"], "K",
                           overwrite=True)
        obraz = fat12.Fat12Image(sciezka)
        obraz.mkdir("/PODKAT")
        wpisy = obraz._entries_in(obraz._resolve_dir("/PODKAT"),
                                  include_dots=True)
        obraz.close()
        self.assertEqual([w.name for w in wpisy[:2]], [".", ".."])

    @unittest.skipUnless(czy_jest("fsck.fat"), "brak fsck.fat")
    def test_fsck_akceptuje_podkatalogi(self):
        sciezka = self.sciezka("kropki.img")
        fat12.format_image(sciezka, fat12.FLOPPY_FORMATS["1440"], "K",
                           overwrite=True)
        obraz = fat12.Fat12Image(sciezka)
        obraz.mkdir("/A")
        obraz.mkdir("/A/B")
        obraz.write_file("/A/B/PLIK.TXT", b"x")
        obraz.close()
        self.assertTrue(fsck_czysty(sciezka))


class UszkodzoneKlastry(PrzypadekZKatalogiem):

    def test_oznaczenie_wylacza_klastry_z_uzycia(self):
        fmt = fat12.FLOPPY_FORMATS["1440"]
        obraz = fat12.build_image(fmt, "BAD")
        pierwszy = fat12.data_start_sector(fmt)
        klastry, krytyczne = fat12.mark_bad_clusters(
            obraz, fmt, [pierwszy, pierwszy + 1, pierwszy + 5])
        self.assertEqual(klastry, 3)
        self.assertEqual(krytyczne, 0)

        sciezka = self.sciezka("bad.img")
        with open(sciezka, "wb") as fh:
            fh.write(obraz)
        czysty = fat12.Fat12Image(sciezka)
        self.addCleanup(czysty.close)
        # trzy klastry mniej niz na nosniku bez oznaczen
        wzorzec = self.sciezka("wzorzec.img")
        fat12.format_image(wzorzec, fmt, "BAD", overwrite=True)
        odniesienie = fat12.Fat12Image(wzorzec)
        self.addCleanup(odniesienie.close)
        self.assertEqual(odniesienie.free_bytes - czysty.free_bytes,
                         3 * fmt.sectors_per_cluster * fmt.bytes_per_sector)

    def test_uszkodzenie_obszaru_systemowego_jest_zglaszane(self):
        fmt = fat12.FLOPPY_FORMATS["1440"]
        obraz = fat12.build_image(fmt, "BAD")
        _, krytyczne = fat12.mark_bad_clusters(obraz, fmt, [0, 1, 2])
        self.assertEqual(krytyczne, 3)


class KopiowanieDrzewa(PrzypadekZKatalogiem):

    def test_struktura_i_katalogi_puste(self):
        zrodlo = self.zbuduj_drzewo({
            "GRA.EXE": b"x" * 100,
            "DANE/PLANSZA.DAT": b"y" * 200,
            "DANE/POZIOMY/LVL01.MAP": b"z" * 50,
            "PUSTY": None,
            "Dokumentacja PL/instrukcja.txt": b"tresc",
        })
        sciezka = self.sciezka("drzewo.img")
        fat12.format_image(sciezka, fat12.FLOPPY_FORMATS["1440"], "D",
                           overwrite=True)
        obraz = fat12.Fat12Image(sciezka)
        self.addCleanup(obraz.close)
        raport = obraz.import_tree(zrodlo, "/", include_root=False)

        self.assertEqual(raport["files"], 4)
        self.assertFalse(raport["failed"])
        nazwy = {e.name for e in obraz.listdir("/")}
        self.assertIn("PUSTY", nazwy, "katalog pusty tez ma powstac")
        self.assertIn("DOKUMENT", nazwy, "nazwa skrocona do 8.3")
        self.assertEqual(
            {e.name for e in obraz.listdir("/DANE/POZIOMY")}, {"LVL01.MAP"})

    def test_ponowne_kopiowanie_nie_mnozy_katalogow(self):
        zrodlo = self.zbuduj_drzewo({"KAT/A.TXT": b"a", "KAT/B.TXT": b"b"})
        sciezka = self.sciezka("dwa.img")
        fat12.format_image(sciezka, fat12.FLOPPY_FORMATS["1440"], "D",
                           overwrite=True)
        obraz = fat12.Fat12Image(sciezka)
        self.addCleanup(obraz.close)
        obraz.import_tree(zrodlo, "/", include_root=False)
        katalogi = [e.name for e in obraz.listdir("/") if e.is_dir]
        self.assertEqual(katalogi, ["KAT"])


class WarstwaSilnikow(PrzypadekZKatalogiem):
    """Rozpoznanie idzie po zawartosci pliku, nie po rozszerzeniu."""

    def test_rozpoznaje_wszystkie_formaty_fat12(self):
        for klucz, fmt in fat12.FLOPPY_FORMATS.items():
            with self.subTest(format=klucz):
                sciezka = self.sciezka(f"{klucz}.dat")   # obce rozszerzenie
                fat12.format_image(sciezka, fmt, "T", overwrite=True)
                silnik = engines.detect(sciezka)
                self.assertIsNotNone(silnik)
                self.assertEqual(silnik.key, "fat12")

    def test_obcy_plik_daje_wlasny_typ_bledu(self):
        sciezka = self.sciezka("obcy.img")
        with open(sciezka, "wb") as fh:
            fh.write(b"\x11" * 737280)
        self.assertIsNone(engines.detect(sciezka))
        with self.assertRaises(engines.UnknownFormat):
            engines.open_image(sciezka)

    def test_blad_silnika_dziedziczy_po_wspolnym_przodku(self):
        self.assertTrue(issubclass(fat12.Fat12Error, engines.ImageError))

    def test_obraz_udostepnia_pomocnicze_operacje_na_sciezkach(self):
        sciezka = self.sciezka("api.img")
        fat12.format_image(sciezka, fat12.FLOPPY_FORMATS["720"], "T",
                           overwrite=True)
        obraz = engines.open_image(sciezka)
        self.addCleanup(obraz.close)
        self.assertEqual(obraz.join("/A", "B.TXT"), "/A/B.TXT")
        self.assertEqual(obraz.parent("/A/B.TXT"), "/A")
        self.assertEqual(obraz.short_name("dluga nazwa.tekst"),
                         "DLUGANAZ.TEK")



class AtariST(PrzypadekZKatalogiem):
    """
    Dyskietki Atari ST to odmiana FAT12: bez sygnatury 55 AA, z wlasna
    instrukcja skoku i - w formatach 800 i 880 KB - z dziesiecioma albo
    jedenastoma sektorami na sciezke zamiast dziewieciu.
    """

    def obraz_atari(self, klucz: str = "st800",
                    bez_sygnatury: bool = True) -> str:
        sciezka = self.sciezka(f"{klucz}.st")
        fat12.format_image(sciezka, fat12.FLOPPY_FORMATS[klucz], "ATARI",
                           overwrite=True)
        if bez_sygnatury:
            with open(sciezka, "r+b") as fh:
                fh.seek(0)
                fh.write(b"\x60\x1c\x00")     # skok jak w Atari
                fh.seek(510)
                fh.write(b"\x00\x00")          # brak sygnatury
        return sciezka

    def test_formaty_maja_wlasna_geometrie(self):
        st800 = fat12.FLOPPY_FORMATS["st800"]
        st880 = fat12.FLOPPY_FORMATS["st880"]
        self.assertEqual((st800.sectors_per_track, st800.heads), (10, 2))
        self.assertEqual((st880.sectors_per_track, st880.heads), (11, 2))
        self.assertEqual(st800.total_sectors * 512, 819200)
        self.assertEqual(st880.total_sectors * 512, 901120)

    def test_bez_powtorzen_z_formatami_pecetowymi(self):
        """
        Atarowskie 360 i 720 KB nie roznia sie od pecetowych, wiec nie maja
        osobnych pozycji - dwie nazwy na to samo tylko myla.
        """
        widziane = {}
        for klucz, f in fat12.FLOPPY_FORMATS.items():
            opis = (f.total_sectors * f.bytes_per_sector, f.sectors_per_track,
                    f.heads, f.sectors_per_cluster)
            self.assertNotIn(opis, widziane,
                             f"{klucz} powtarza geometrie {widziane.get(opis)}")
            widziane[opis] = klucz

    def test_rozpoznanie_bez_sygnatury(self):
        import engines
        for klucz in ("st800", "st880"):
            with self.subTest(format=klucz):
                sciezka = self.obraz_atari(klucz)
                silnik = engines.detect(sciezka)
                self.assertIsNotNone(silnik, "obraz Atari ma byc rozpoznany")
                self.assertEqual(silnik.key, "fat12")

    def test_otwarcie_i_zapis(self):
        import engines
        sciezka = self.obraz_atari("st880")
        obraz = engines.open_image(sciezka)
        self.addCleanup(obraz.close)
        obraz.mkdir("/AUTO")
        obraz.write_file("/AUTO/START.PRG", bytes(range(256)) * 20)
        self.assertEqual([w.name for w in obraz.listdir("/AUTO")],
                         ["START.PRG"])
        self.assertEqual(len(obraz.read_file("/AUTO/START.PRG")), 5120)

    def test_zapis_nie_dopisuje_sygnatury(self):
        """
        Obraz ma zostac taki, jaki byl - dopisanie sygnatury zmienialoby
        dyskietke Atari w cos posredniego.
        """
        import engines
        sciezka = self.obraz_atari("st800")
        obraz = engines.open_image(sciezka)
        obraz.write_file("/A.TXT", b"x")
        obraz.close()
        with open(sciezka, "rb") as fh:
            fh.seek(510)
            self.assertEqual(fh.read(2), b"\x00\x00")

    def test_fsck_nie_ma_zastrzezen(self):
        import shutil
        if not shutil.which("fsck.fat"):
            self.skipTest("brak fsck.fat")
        for klucz in ("st800", "st880"):
            with self.subTest(format=klucz):
                sciezka = self.obraz_atari(klucz, bez_sygnatury=False)
                wynik = subprocess.run(["fsck.fat", "-n", sciezka],
                                       capture_output=True, text=True)
                self.assertEqual(wynik.returncode, 0, wynik.stdout[-300:])

    def test_losowy_plik_nie_jest_dyskietka(self):
        """
        Rozluznienie rozpoznawania nie moze robic dyskietki z byle pliku.
        Wymagamy zgodnosci deklarowanej liczby sektorow z rozmiarem.
        """
        import engines
        import os
        sciezka = self.sciezka("smieci.bin")
        with open(sciezka, "wb") as fh:
            fh.write(os.urandom(819200))
        self.assertIsNone(engines.detect(sciezka))

    def test_niemozliwa_geometria_jest_odrzucana(self):
        """
        Blok parametrow moze sie zgadzac z rozmiarem, a i tak opisywac cos,
        co dyskietka nie jest. Granice geometrii odsiewaja takie przypadki -
        na dyskietce nie ma tysiaca sektorow na sciezce ani pieciu glowic.
        """
        rozmiar = 819200
        for opis, na_sciezke, glowic in (("tysiac sektorow", 1000, 2),
                                         ("piec glowic", 10, 5),
                                         ("zero sektorow", 0, 2)):
            with self.subTest(przypadek=opis):
                naglowek = bytearray(512)
                naglowek[0x0B:0x0D] = (512).to_bytes(2, "little")
                naglowek[0x0D] = 2
                naglowek[0x0E:0x10] = (1).to_bytes(2, "little")
                naglowek[0x10] = 2
                naglowek[0x11:0x13] = (112).to_bytes(2, "little")
                naglowek[0x13:0x15] = (rozmiar // 512).to_bytes(2, "little")
                naglowek[0x15] = 0xF9
                naglowek[0x16:0x18] = (5).to_bytes(2, "little")
                naglowek[0x18:0x1A] = na_sciezke.to_bytes(2, "little")
                naglowek[0x1A:0x1C] = glowic.to_bytes(2, "little")
                self.assertFalse(
                    fat12.rozpoznaj_naglowek(bytes(naglowek), rozmiar))

    def test_prawdziwa_geometria_przechodzi(self):
        """Ta sama droga musi przepuscic obraz, ktory jest poprawny."""
        with open(self.obraz_atari("st880"), "rb") as fh:
            naglowek = fh.read(512)
        self.assertTrue(fat12.rozpoznaj_naglowek(naglowek, 901120))

    def test_blok_parametrow_niezgodny_z_rozmiarem(self):
        """Obciety obraz Atari nie moze udawac calego."""
        import engines
        sciezka = self.obraz_atari("st880")
        with open(sciezka, "rb") as fh:
            dane = fh.read()
        obciety = self.sciezka("obciety.st")
        with open(obciety, "wb") as fh:
            fh.write(dane[:len(dane) // 2])
        self.assertIsNone(engines.detect(obciety))


if __name__ == "__main__":
    unittest.main()
