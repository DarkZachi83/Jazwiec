"""
Testy konwersji tekstu miedzy swiatem DOS a Unicode.

Najwazniejsza wlasnosc to odwracalnosc: plik otwarty w edytorze i zapisany
bez zmian musi wrocic na dyskietke bajt w bajt. Bez tego kazde zajrzenie do
pliku bylo by ryzykiem.
"""

import unittest

from helpers import KORZEN  # noqa: F401  - dopisuje korzen projektu do sciezki

import dostext


ZAKRES_BEZ_STEROWANIA = bytes(
    b for b in range(256) if b not in (0x0D, dostext.EOF_MARKER))


class Odwracalnosc(unittest.TestCase):

    def test_kazdy_bajt_wraca_taki_sam(self):
        for strona in dostext.CODEPAGES:
            with self.subTest(strona=strona):
                dokument = dostext.load(ZAKRES_BEZ_STEROWANIA, strona)
                self.assertEqual(dostext.save(dokument),
                                 ZAKRES_BEZ_STEROWANIA)

    def test_strony_kodowe_sa_wzajemnie_jednoznaczne(self):
        """Na tym opiera sie cala odwracalnosc - warto sprawdzic wprost."""
        for strona in dostext.CODEPAGES:
            with self.subTest(strona=strona):
                znaki = bytes(range(256)).decode(strona)
                self.assertEqual(len(set(znaki)), 256)


class KonceWierszy(unittest.TestCase):

    def test_rozpoznanie(self):
        przypadki = [
            (b"a\r\nb\r\n", True, "konce DOS"),
            (b"a\nb\n", False, "konce uniksowe"),
            (b"", True, "pusty - przyjmujemy konwencje DOS"),
            (b"jedna linia", True, "bez konca wiersza"),
        ]
        for dane, oczekiwane, opis in przypadki:
            with self.subTest(opis=opis):
                self.assertEqual(dostext.load(dane, "cp437").crlf, oczekiwane)

    def test_nowy_plik_zapisuje_sie_po_dosowemu(self):
        """
        Dla pustej tresci nie ma czego wykrywac, a plik trafi na dyskietke -
        wiec konce wierszy musza byc DOS-owe.
        """
        dokument = dostext.load(b"", "cp437")
        dokument.text = "FILES=30\nBUFFERS=20\n"
        self.assertEqual(dostext.save(dokument),
                         b"FILES=30\r\nBUFFERS=20\r\n")


class ZnacznikKoncaPliku(unittest.TestCase):

    def test_zachowany_gdy_byl(self):
        dane = b"tresc\r\n\x1a"
        dokument = dostext.load(dane, "cp437")
        self.assertTrue(dokument.eof_marker)
        self.assertEqual(dostext.save(dokument), dane)

    def test_niedodawany_gdy_go_nie_bylo(self):
        dokument = dostext.load(b"tresc\r\n", "cp437")
        self.assertFalse(dokument.eof_marker)
        self.assertFalse(dostext.save(dokument).endswith(b"\x1a"))


class SymboleOzdobne(unittest.TestCase):
    """
    Bajty 1-31 wyswietlane byly przez karte graficzna PC jako usmiechy
    i strzalki. Pythonowe kodeki odwzorowuja je na znaki sterujace, wiec
    bez wlasnej tablicy bylyby w edytorze niewidoczne.
    """

    def test_dostepne_w_cp437(self):
        mapa = dostext.graphics_map("cp437")
        self.assertEqual(mapa[1], "\u263a")
        self.assertEqual(mapa[3], "\u2665")
        self.assertEqual(len(mapa), 28)

    def test_kolizje_sa_wykluczane(self):
        """
        W CP852 paragraf ma juz kod 245, wiec udostepnienie go takze pod 21
        odebraloby zapisowi jednoznacznosc.
        """
        self.assertNotIn(21, dostext.graphics_map("cp852"))
        self.assertEqual(dostext.char_for_code(245, "cp852"), "\u00a7")
        self.assertIsNone(dostext.char_for_code(21, "cp852"))

    def test_tabulacja_i_konce_wierszy_zostaja_sterujace(self):
        for kod in (0x00, 0x09, 0x0A, 0x0D):
            with self.subTest(kod=kod):
                self.assertIsNone(dostext.char_for_code(kod, "cp437"))

    def test_plik_z_usmiechem_wraca_bez_zmian(self):
        dane = bytes([0x01, 0x20, 0xC9, 0xCD, 0xBB, 0x0D, 0x0A, 0x03])
        dokument = dostext.load(dane, "cp437")
        self.assertIn("\u263a", dokument.text)
        self.assertEqual(dostext.save(dokument), dane)


class WpisywaniePoKodzie(unittest.TestCase):
    """Odpowiednik dosowego Alt+kod."""

    def test_ramki(self):
        przypadki = {186: "\u2551", 201: "\u2554", 205: "\u2550",
                     219: "\u2588"}
        for kod, znak in przypadki.items():
            with self.subTest(kod=kod):
                self.assertEqual(dostext.char_for_code(kod, "cp437"), znak)

    def test_ten_sam_kod_daje_inny_znak_w_innej_stronie(self):
        self.assertEqual(dostext.char_for_code(164, "cp437"), "\u00f1")
        self.assertEqual(dostext.char_for_code(164, "cp852"), "\u0104")

    def test_kody_poza_zakresem(self):
        for kod in (-1, 256, 1000):
            with self.subTest(kod=kod):
                self.assertIsNone(dostext.char_for_code(kod, "cp437"))


class ZnakiNieDoZapisania(unittest.TestCase):

    def test_polskie_litery_w_cp437(self):
        braki = dostext.unmappable("Zazolc gesla jazn: Zażółć", "cp437")
        self.assertTrue(braki)
        self.assertIn("ż", braki)

    def test_cp852_przyjmuje_polskie_litery(self):
        self.assertEqual(
            dostext.unmappable("Zażółć gęślą jaźń", "cp852"), [])

    def test_symbole_ozdobne_nie_sa_zglaszane(self):
        """Maja swoje bajty, wiec nie sa brakiem."""
        self.assertEqual(dostext.unmappable("\u263a\u2665", "cp437"), [])


class RozpoznanieBinariow(unittest.TestCase):

    def test_tekst_nie_jest_binarny(self):
        self.assertFalse(dostext.looks_binary(b"@ECHO OFF\r\nPATH=C:\\DOS\r\n"))

    def test_program_jest_binarny(self):
        self.assertTrue(
            dostext.looks_binary(bytes([0x4D, 0x5A, 0x90, 0x00]) * 50))

    def test_pusty_plik_nie_jest_binarny(self):
        self.assertFalse(dostext.looks_binary(b""))


if __name__ == "__main__":
    unittest.main()
