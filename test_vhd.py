"""
Testy czytania obrazow dyskow VHD.

Obrazy do testow budujemy tutaj, bajt po bajcie, wedlug opisu formatu.
Prawdziwy plik z 86Boxa sluzyl do sprawdzenia rozbioru podczas pisania
modulu - tu go nie ma, bo to cudze dane i kilkaset megabajtow.
"""

import os
import struct
import unittest

from helpers import PrzypadekZKatalogiem

import vhd

SEKTOR = 512


def stopka(rozmiar: int, odmiana: int = vhd.STALA,
           dane_od: int = 0xFFFFFFFFFFFFFFFF, zla_suma: bool = False) -> bytes:
    """Stopka VHD: 512 bajtow z geometria, rozmiarem i suma kontrolna."""
    sektorow = rozmiar // SEKTOR
    cylindrow = max(1, sektorow // (4 * 62))
    pola = bytearray(512)
    pola[0:8] = vhd.KOSMYK_STOPKI
    pola[8:12] = struct.pack(">I", 2)              # cechy
    pola[12:16] = struct.pack(">I", 0x00010000)    # wersja formatu
    pola[16:24] = struct.pack(">Q", dane_od)
    pola[28:32] = b"test"
    pola[36:40] = b"Wi2k"
    pola[40:48] = struct.pack(">Q", rozmiar)
    pola[48:56] = struct.pack(">Q", rozmiar)
    pola[56:60] = struct.pack(">HBB", cylindrow, 4, 62)
    pola[60:64] = struct.pack(">I", odmiana)
    suma = (~sum(pola)) & 0xFFFFFFFF
    pola[64:68] = struct.pack(">I", suma + (1 if zla_suma else 0))
    return bytes(pola)


class ObrazStaly(PrzypadekZKatalogiem):
    """
    Odmiana stala: dane po kolei, stopka na koncu.

    Sprawdzona wylacznie wedlug opisu formatu - 86Box zapisuje domyslnie
    obrazy rozszerzalne i prawdziwego pliku tej odmiany nie mielismy.
    """

    def zbuduj(self, sektorow: int = 8) -> str:
        sciezka = self.sciezka("staly.vhd")
        dane = bytearray()
        for numer in range(sektorow):
            dane += bytes([numer]) * SEKTOR
        with open(sciezka, "wb") as fh:
            fh.write(bytes(dane) + stopka(sektorow * SEKTOR))
        return sciezka

    def test_rozpoznaje_odmiane_i_geometrie(self):
        with vhd.open_image(self.zbuduj()) as obraz:
            self.assertEqual(obraz.footer.kind, vhd.STALA)
            self.assertEqual(obraz.kind_name, "stala")
            self.assertEqual(obraz.size, 8 * SEKTOR)
            self.assertEqual(obraz.sector_count, 8)
            self.assertTrue(obraz.footer.checksum_ok)

    def test_czyta_sektory(self):
        with vhd.open_image(self.zbuduj()) as obraz:
            self.assertEqual(obraz.read_sector(0), bytes([0]) * SEKTOR)
            self.assertEqual(obraz.read_sector(5), bytes([5]) * SEKTOR)
            self.assertEqual(obraz.read(2, 2),
                             bytes([2]) * SEKTOR + bytes([3]) * SEKTOR)

    def test_stopka_nie_jest_trescia_dysku(self):
        """Ostatni sektor dysku to dane, a nie stopka doklejona za nimi."""
        with vhd.open_image(self.zbuduj()) as obraz:
            self.assertEqual(obraz.read_sector(7), bytes([7]) * SEKTOR)
            with self.assertRaises(vhd.VhdError):
                obraz.read_sector(8)


class ObrazRozszerzalny(PrzypadekZKatalogiem):
    """
    Odmiana rozszerzalna: dane w blokach, kolejnosc opisuje tablica.

    Tak zapisuje 86Box. Blok, do ktorego nigdy nic nie zapisano, w pliku
    nie istnieje - stad obraz dysku 245 MB miesci sie w ulamku tego
    rozmiaru.
    """

    BLOK = 4096           # 8 sektorow na blok, zeby test byl czytelny

    def zbuduj(self, bloki: dict, blokow: int = 4) -> str:
        """bloki: numer bloku -> bajt wypelniajacy. Reszta niezajeta."""
        sciezka = self.sciezka("rozszerzalny.vhd")
        rozmiar = blokow * self.BLOK
        bitmapa = SEKTOR                      # 8 sektorow = 1 bajt, dopelnione
        kopia = stopka(rozmiar, vhd.ROZSZERZALNA, dane_od=SEKTOR)

        naglowek = bytearray(1024)
        naglowek[0:8] = vhd.KOSMYK_NAGLOWKA
        naglowek[8:16] = struct.pack(">Q", 0xFFFFFFFFFFFFFFFF)
        naglowek[16:24] = struct.pack(">Q", 1536)      # tablica zaraz za nim
        naglowek[24:28] = struct.pack(">I", 0x00010000)
        naglowek[28:32] = struct.pack(">I", blokow)
        naglowek[32:36] = struct.pack(">I", self.BLOK)
        naglowek[36:40] = struct.pack(">I", (~sum(naglowek)) & 0xFFFFFFFF)

        tablica_sektorow = (4 * blokow + SEKTOR - 1) // SEKTOR
        pierwszy = (1536 + tablica_sektorow * SEKTOR) // SEKTOR
        wpisy, tresc, kolejny = [], bytearray(), pierwszy
        for numer in range(blokow):
            if numer not in bloki:
                wpisy.append(vhd.NIEZAJETY)
                continue
            wpisy.append(kolejny)
            tresc += b"\xff" * bitmapa                 # bitmapa: same jedynki
            tresc += bytes([bloki[numer]]) * self.BLOK
            kolejny += (bitmapa + self.BLOK) // SEKTOR

        tablica = struct.pack(f">{blokow}I", *wpisy)
        tablica += bytes(tablica_sektorow * SEKTOR - len(tablica))
        with open(sciezka, "wb") as fh:
            fh.write(kopia + bytes(naglowek) + tablica + bytes(tresc)
                     + stopka(rozmiar, vhd.ROZSZERZALNA, dane_od=SEKTOR))
        return sciezka

    def test_czyta_z_blokow(self):
        with vhd.open_image(self.zbuduj({0: 0xAA, 2: 0xBB})) as obraz:
            self.assertEqual(obraz.kind_name, "rozszerzalna")
            self.assertEqual(obraz.read_sector(0), b"\xaa" * SEKTOR)
            self.assertEqual(obraz.read_sector(7), b"\xaa" * SEKTOR)
            self.assertEqual(obraz.read_sector(16), b"\xbb" * SEKTOR)

    def test_blok_niezajety_to_zera(self):
        """
        Obszar dysku, do ktorego nigdy nic nie zapisano, nie istnieje
        w pliku. Czyta sie jako zera, a nie jako blad.
        """
        with vhd.open_image(self.zbuduj({0: 0xAA, 2: 0xBB})) as obraz:
            self.assertEqual(obraz.read_sector(8), bytes(SEKTOR))
            self.assertEqual(obraz.read_sector(31), bytes(SEKTOR))

    def test_blok_niezajety_nie_siega_do_pliku(self):
        """
        Bez sprawdzenia tablicy program szukalby pod przesunieciem z samych
        jedynek, dostal pustke i uzupelnil ja zerami - wynik ten sam, ale
        przy dysku pelnym dziur to tysiace jalowych odczytow.
        """
        with vhd.open_image(self.zbuduj({0: 0xAA})) as obraz:
            siegniecia = []
            prawdziwy = obraz._plik.seek
            obraz._plik.seek = lambda *a, **k: (siegniecia.append(a)
                                                or prawdziwy(*a, **k))
            self.assertEqual(obraz.read_sector(8), bytes(SEKTOR))
            self.assertEqual(siegniecia, [],
                             "pusty blok czyta sie bez dotykania pliku")
            obraz.read_sector(0)
            self.assertTrue(siegniecia, "zajety blok juz tak")

    def test_kolejnosc_w_pliku_nie_musi_odpowiadac_dyskowi(self):
        """Blok o wyzszym numerze moze lezec w pliku wczesniej."""
        sciezka = self.zbuduj({1: 0x11, 3: 0x33})
        with vhd.open_image(sciezka) as obraz:
            self.assertEqual(obraz.read_sector(8), b"\x11" * SEKTOR)
            self.assertEqual(obraz.read_sector(24), b"\x33" * SEKTOR)
            self.assertEqual(obraz.read_sector(0), bytes(SEKTOR))

    def test_plik_jest_mniejszy_niz_dysk(self):
        sciezka = self.zbuduj({0: 0xAA})
        with vhd.open_image(sciezka) as obraz:
            self.assertLess(os.path.getsize(sciezka), obraz.size)


class OdmianyOdrzucane(PrzypadekZKatalogiem):

    def test_roznicowy_mowi_wprost(self):
        """
        Obraz roznicowy trzyma tylko roznice wobec innego pliku. Czytanie go
        w pojedynke daloby nieprawdziwa zawartosc, wiec lepiej odmowic.
        """
        sciezka = self.sciezka("roznicowy.vhd")
        with open(sciezka, "wb") as fh:
            fh.write(bytes(4096) + stopka(4096, vhd.ROZNICOWA))
        with self.assertRaises(vhd.VhdError) as blad:
            vhd.open_image(sciezka)
        self.assertIn("roznicow", str(blad.exception))

    def test_nie_vhd(self):
        sciezka = self.sciezka("zwykly.img")
        with open(sciezka, "wb") as fh:
            fh.write(bytes(4096))
        self.assertFalse(vhd.looks_like_vhd(sciezka))
        with self.assertRaises(vhd.VhdError):
            vhd.open_image(sciezka)

    def test_rozpoznanie_po_zawartosci_a_nie_nazwie(self):
        sciezka = self.sciezka("bez_rozszerzenia")
        with open(sciezka, "wb") as fh:
            fh.write(bytes(4096) + stopka(4096))
        self.assertTrue(vhd.looks_like_vhd(sciezka))

    def test_zla_suma_kontrolna_jest_zglaszana(self):
        """Obraz sie otworzy, ale program ma wiedziec, ze stopka nie gra."""
        sciezka = self.sciezka("uszkodzona.vhd")
        with open(sciezka, "wb") as fh:
            fh.write(bytes(4096) + stopka(4096, zla_suma=True))
        with vhd.open_image(sciezka) as obraz:
            self.assertFalse(obraz.footer.checksum_ok)

    def test_sektor_poza_dyskiem(self):
        sciezka = self.sciezka("maly.vhd")
        with open(sciezka, "wb") as fh:
            fh.write(bytes(4096) + stopka(4096))
        with vhd.open_image(sciezka) as obraz:
            with self.assertRaises(vhd.VhdError):
                obraz.read_sector(8)

    def test_uciety_plik(self):
        sciezka = self.sciezka("uciety.vhd")
        with open(sciezka, "wb") as fh:
            fh.write(bytes(100))
        with self.assertRaises(vhd.VhdError):
            vhd.open_image(sciezka)


class WierszPolecen(PrzypadekZKatalogiem):

    def uruchom(self, *argumenty):
        import contextlib
        import io
        wyjscie, bledy = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(wyjscie), \
                contextlib.redirect_stderr(bledy):
            kod = vhd.main(list(argumenty))
        return kod, wyjscie.getvalue(), bledy.getvalue()

    def test_info(self):
        sciezka = self.sciezka("dysk.vhd")
        with open(sciezka, "wb") as fh:
            fh.write(bytes(8192) + stopka(8192))
        kod, wyjscie, _ = self.uruchom("info", sciezka)
        self.assertEqual(kod, 0)
        self.assertIn("stala", wyjscie)
        self.assertIn("zgodna", wyjscie)

    def test_blad_zamiast_sladu_wyjatku(self):
        kod, _, bledy = self.uruchom("info", self.sciezka("nie_ma.vhd"))
        self.assertEqual(kod, 1)
        self.assertNotIn("Traceback", bledy)



class ZapisDoObrazu(PrzypadekZKatalogiem):
    """
    Zapis sektorow. Przy odmianie rozszerzalnej najciekawszy jest przypadek,
    gdy trafia on w obszar, ktorego w pliku jeszcze nie ma - trzeba wtedy
    dolozyc caly blok i przesunac stopke.
    """

    BLOK = 4096

    def rozszerzalny(self, bloki: dict, blokow: int = 4) -> str:
        pomocnik = ObrazRozszerzalny(methodName="test_czyta_z_blokow")
        pomocnik.katalog = self.katalog
        pomocnik.BLOK = self.BLOK
        return pomocnik.zbuduj(bloki, blokow)

    def staly(self, sektorow: int = 8) -> str:
        sciezka = self.sciezka("staly.vhd")
        with open(sciezka, "wb") as fh:
            fh.write(bytes(sektorow * SEKTOR) + stopka(sektorow * SEKTOR))
        return sciezka

    def test_tylko_do_odczytu_nie_pozwala_pisac(self):
        with vhd.open_image(self.staly()) as obraz:
            with self.assertRaises(vhd.VhdError):
                obraz.write_sector(0, b"x" * SEKTOR)

    def test_zapis_do_stalego(self):
        sciezka = self.staly()
        with vhd.open_image(sciezka, read_only=False) as obraz:
            obraz.write_sector(3, b"A" * SEKTOR)
        with vhd.open_image(sciezka) as obraz:
            self.assertEqual(obraz.read_sector(3), b"A" * SEKTOR)
            self.assertEqual(obraz.read_sector(2), bytes(SEKTOR))

    def test_stopka_zostaje_na_koncu(self):
        """Stopka doklejona w zlym miejscu psuje caly obraz."""
        sciezka = self.staly()
        with vhd.open_image(sciezka, read_only=False) as obraz:
            obraz.write_sector(7, b"Z" * SEKTOR)
        with vhd.open_image(sciezka) as obraz:
            self.assertTrue(obraz.footer.checksum_ok)
            self.assertEqual(obraz.sector_count, 8)

    def test_zapis_w_istniejacy_blok(self):
        sciezka = self.rozszerzalny({0: 0xAA})
        przed = os.path.getsize(sciezka)
        with vhd.open_image(sciezka, read_only=False) as obraz:
            obraz.write_sector(2, b"N" * SEKTOR)
        self.assertEqual(os.path.getsize(sciezka), przed,
                         "istniejacy blok nie powieksza pliku")
        with vhd.open_image(sciezka) as obraz:
            self.assertEqual(obraz.read_sector(2), b"N" * SEKTOR)
            self.assertEqual(obraz.read_sector(1), b"\xaa" * SEKTOR)

    def test_zapis_w_blok_ktorego_nie_bylo(self):
        sciezka = self.rozszerzalny({0: 0xAA})
        przed = os.path.getsize(sciezka)
        with vhd.open_image(sciezka, read_only=False) as obraz:
            obraz.write_sector(16, b"N" * SEKTOR)       # blok 2, niezajety
        self.assertEqual(os.path.getsize(sciezka),
                         przed + SEKTOR + self.BLOK,
                         "plik rosnie o bitmape i caly blok")
        with vhd.open_image(sciezka) as obraz:
            self.assertEqual(obraz.read_sector(16), b"N" * SEKTOR)
            self.assertEqual(obraz.read_sector(17), bytes(SEKTOR),
                             "reszta nowego bloku to zera")
            self.assertEqual(obraz.read_sector(0), b"\xaa" * SEKTOR,
                             "stary blok nietkniety")
            self.assertTrue(obraz.footer.checksum_ok)

    def test_kolejne_nowe_bloki(self):
        sciezka = self.rozszerzalny({})
        with vhd.open_image(sciezka, read_only=False) as obraz:
            for lba, bajt in ((0, b"A"), (8, b"B"), (24, b"C")):
                obraz.write_sector(lba, bajt * SEKTOR)
        with vhd.open_image(sciezka) as obraz:
            self.assertEqual(obraz.read_sector(0), b"A" * SEKTOR)
            self.assertEqual(obraz.read_sector(8), b"B" * SEKTOR)
            self.assertEqual(obraz.read_sector(24), b"C" * SEKTOR)

    def test_zapis_kilku_sektorow(self):
        sciezka = self.rozszerzalny({0: 0x00})
        with vhd.open_image(sciezka, read_only=False) as obraz:
            obraz.write(1, b"X" * SEKTOR + b"Y" * SEKTOR)
        with vhd.open_image(sciezka) as obraz:
            self.assertEqual(obraz.read_sector(1), b"X" * SEKTOR)
            self.assertEqual(obraz.read_sector(2), b"Y" * SEKTOR)

    def test_zly_rozmiar_sektora_odrzucony(self):
        with vhd.open_image(self.staly(), read_only=False) as obraz:
            with self.assertRaises(vhd.VhdError):
                obraz.write_sector(0, b"za krotkie")

    def test_sektor_poza_dyskiem_odrzucony(self):
        with vhd.open_image(self.staly(), read_only=False) as obraz:
            with self.assertRaises(vhd.VhdError):
                obraz.write_sector(99, b"x" * SEKTOR)



class ObrazNiepelny(PrzypadekZKatalogiem):
    """
    Obraz uciety - na przyklad niedokonczone pobieranie - ma tablice
    wskazujaca poza koniec pliku. Odczyt znosimy, zapis odmawiamy: trafilby
    za koniec pliku, rozdmuchal go i zostawil stopke w srodku, zamieniajac
    obraz niepelny w calkiem zepsuty.
    """

    def uciety(self) -> str:
        pomocnik = ObrazRozszerzalny(methodName="test_czyta_z_blokow")
        pomocnik.katalog = self.katalog
        pelny = pomocnik.zbuduj({0: 0xAA, 2: 0xBB})
        with open(pelny, "rb") as fh:
            tresc = fh.read()
        stopka_pliku = tresc[-SEKTOR:]
        sciezka = self.sciezka("uciety.vhd")
        with open(sciezka, "wb") as fh:
            fh.write(tresc[:len(tresc) // 2] + stopka_pliku)
        return sciezka

    def test_odczyt_dziala_i_zglasza_niepelnosc(self):
        with vhd.open_image(self.uciety()) as obraz:
            self.assertTrue(obraz.truncated)
            self.assertEqual(obraz.read_sector(0), b"\xaa" * SEKTOR)

    def test_zapis_odmowiony(self):
        with self.assertRaises(vhd.VhdError) as blad:
            vhd.open_image(self.uciety(), read_only=False)
        self.assertIn("niepelny", str(blad.exception))

    def test_pelny_obraz_nie_jest_uznany_za_uciety(self):
        pomocnik = ObrazRozszerzalny(methodName="test_czyta_z_blokow")
        pomocnik.katalog = self.katalog
        with vhd.open_image(pomocnik.zbuduj({0: 0xAA}),
                            read_only=False) as obraz:
            self.assertFalse(obraz.truncated)


if __name__ == "__main__":
    unittest.main()
