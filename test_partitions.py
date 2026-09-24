"""
Testy tablicy partycji obrazow dyskow twardych.

Obrazy budujemy tutaj, bajt po bajcie. Najwiecej uwagi dostaja partycje
logiczne: ich przesuniecia liczy sie wzgledem dwoch roznych punktow i
pomylenie ich daje partycje w zupelnie zlym miejscu - a wygladajaca
sensownie.
"""

import struct
import unittest

from helpers import PrzypadekZKatalogiem

import partitions
import vhd

SEKTOR = 512


def wpis(typ: int, start: int, dlugosc: int, startowa: bool = False) -> bytes:
    """Jeden wpis tablicy partycji - 16 bajtow."""
    return (bytes([0x80 if startowa else 0x00]) + b"\x00\x00\x00"
            + bytes([typ]) + b"\x00\x00\x00"
            + struct.pack("<I", start) + struct.pack("<I", dlugosc))


def tablica(*wpisy: bytes) -> bytes:
    """Sektor z tablica partycji i sygnatura na koncu."""
    sektor = bytearray(SEKTOR)
    for numer, dane in enumerate(wpisy[:4]):
        sektor[446 + numer * 16:462 + numer * 16] = dane
    sektor[510:512] = partitions.SYGNATURA
    return bytes(sektor)


class TablicaPodstawowa(PrzypadekZKatalogiem):

    def dysk(self, pierwszy_sektor: bytes, sektorow: int = 2048) -> str:
        sciezka = self.sciezka("dysk.img")
        dane = bytearray(sektorow * SEKTOR)
        dane[0:SEKTOR] = pierwszy_sektor
        with open(sciezka, "wb") as fh:
            fh.write(bytes(dane))
        return sciezka

    def test_cztery_wpisy(self):
        sciezka = self.dysk(tablica(
            wpis(0x06, 63, 1000, startowa=True),
            wpis(0x01, 1063, 500),
            b"", wpis(0x83, 1563, 400)))
        with partitions.open_disk(sciezka) as dysk:
            lista = partitions.read_partitions(dysk)
        self.assertEqual([(p.type_id, p.start, p.sectors) for p in lista],
                         [(0x06, 63, 1000), (0x01, 1063, 500),
                          (0x83, 1563, 400)])
        self.assertTrue(lista[0].bootable)
        self.assertFalse(lista[1].bootable)
        self.assertEqual([p.index for p in lista], [1, 2, 3])

    def test_puste_wpisy_pomijane(self):
        sciezka = self.dysk(tablica(wpis(0x06, 63, 1000)))
        with partitions.open_disk(sciezka) as dysk:
            self.assertEqual(len(partitions.read_partitions(dysk)), 1)

    def test_brak_sygnatury_to_brak_tablicy(self):
        """
        Obraz bez tablicy partycji nie jest bledem - moze byc jednym
        systemem plikow na calym nosniku.
        """
        sciezka = self.dysk(bytes(SEKTOR))
        with partitions.open_disk(sciezka) as dysk:
            self.assertEqual(partitions.read_partitions(dysk), [])

    def test_typy_i_czytelnosc(self):
        sciezka = self.dysk(tablica(wpis(0x06, 63, 1000),
                                    wpis(0x07, 1063, 1000)))
        with partitions.open_disk(sciezka) as dysk:
            fat, ntfs = partitions.read_partitions(dysk)
        self.assertEqual(fat.type_name, "FAT16")
        self.assertTrue(fat.readable)
        self.assertEqual(ntfs.type_name, "HPFS / NTFS")
        self.assertFalse(ntfs.readable, "tego silnika nie mamy")

    def test_nieznany_typ_opisany_liczba(self):
        sciezka = self.dysk(tablica(wpis(0xA5, 63, 1000)))
        with partitions.open_disk(sciezka) as dysk:
            p = partitions.read_partitions(dysk)[0]
        self.assertIn("0xA5", p.type_name)
        self.assertFalse(p.readable)


class PartycjeLogiczne(PrzypadekZKatalogiem):
    """
    Dysk z epoki: C: podstawowy, D: i E: wewnatrz rozszerzonej.

    Przesuniecie w pierwszym wpisie ogniwa liczy sie od tego ogniwa,
    a w drugim - od poczatku calej partycji rozszerzonej.
    """

    ROZSZERZONA = 20063

    def dysk(self) -> str:
        sciezka = self.sciezka("dysk.img")
        dane = bytearray(60064 * SEKTOR)
        dane[0:SEKTOR] = tablica(wpis(0x06, 63, 20000, startowa=True),
                                 wpis(0x05, self.ROZSZERZONA, 40000))
        ogniwo1 = self.ROZSZERZONA
        dane[ogniwo1 * SEKTOR:(ogniwo1 + 1) * SEKTOR] = tablica(
            wpis(0x06, 63, 19000), wpis(0x05, 19063, 20000))
        ogniwo2 = self.ROZSZERZONA + 19063
        dane[ogniwo2 * SEKTOR:(ogniwo2 + 1) * SEKTOR] = tablica(
            wpis(0x01, 63, 15000), wpis(0x05, 34063, 6000))
        # Trzecie ogniwo jest tu nieprzypadkowo: przy dwoch oba sposoby
        # liczenia nastepnego skoku daja ten sam wynik i blad przechodzi
        # niezauwazony. Rozchodza sie dopiero przy trzecim.
        ogniwo3 = self.ROZSZERZONA + 34063
        dane[ogniwo3 * SEKTOR:(ogniwo3 + 1) * SEKTOR] = tablica(
            wpis(0x06, 63, 5000))
        with open(sciezka, "wb") as fh:
            fh.write(bytes(dane))
        return sciezka

    def test_wszystkie_widoczne_razem(self):
        with partitions.open_disk(self.dysk()) as dysk:
            lista = partitions.read_partitions(dysk)
        self.assertEqual(len(lista), 4)
        self.assertEqual([p.logical for p in lista],
                         [False, True, True, True])
        self.assertEqual([p.index for p in lista], [1, 2, 3, 4])

    def test_przesuniecia_liczone_z_wlasciwych_punktow(self):
        with partitions.open_disk(self.dysk()) as dysk:
            lista = partitions.read_partitions(dysk)
        self.assertEqual(lista[1].start, self.ROZSZERZONA + 63)
        self.assertEqual(lista[2].start, self.ROZSZERZONA + 19063 + 63,
                         "drugie ogniwo liczy sie od poczatku rozszerzonej")
        self.assertEqual(lista[3].start, self.ROZSZERZONA + 34063 + 63,
                         "trzecie tak samo - a nie od poprzedniego ogniwa")

    def test_sama_rozszerzona_nie_jest_partycja(self):
        """Jest pojemnikiem na inne, a nie miejscem na pliki."""
        with partitions.open_disk(self.dysk()) as dysk:
            lista = partitions.read_partitions(dysk)
        self.assertNotIn(0x05, [p.type_id for p in lista])

    def test_zapetlony_lancuch_sie_konczy(self):
        """Uszkodzony lancuch nie moze zawiesic programu."""
        # Prawdziwa petla: drugie ogniwo wskazuje na samo siebie. Wpis
        # z przesunieciem zero konczy przejscie zwyklym przerwaniem i
        # niczego by nie sprawdzil.
        sciezka = self.sciezka("zapetlony.img")
        dane = bytearray(2048 * SEKTOR)
        dane[0:SEKTOR] = tablica(wpis(0x05, 100, 1000))
        dane[100 * SEKTOR:101 * SEKTOR] = tablica(wpis(0x06, 63, 100),
                                                  wpis(0x05, 200, 500))
        dane[300 * SEKTOR:301 * SEKTOR] = tablica(wpis(0x06, 63, 100),
                                                  wpis(0x05, 200, 500))
        with open(sciezka, "wb") as fh:
            fh.write(bytes(dane))
        with partitions.open_disk(sciezka) as dysk:
            lista = partitions.read_partitions(dysk)
        self.assertEqual(len(lista), 2,
                         "ogniwo odwiedzone raz konczy przejscie lancucha")


class OtwieranieObrazow(PrzypadekZKatalogiem):

    def test_vhd_rozpoznany_po_zawartosci(self):
        """Nie po nazwie: obraz VHD poznaje sie po stopce."""
        from test_vhd import stopka
        sciezka = self.sciezka("dysk.obraz")
        with open(sciezka, "wb") as fh:
            fh.write(tablica(wpis(0x06, 63, 1000)) + bytes(2047 * SEKTOR)
                     + stopka(2048 * SEKTOR))
        with partitions.open_disk(sciezka) as dysk:
            self.assertIsInstance(dysk, vhd.VhdImage)
            self.assertEqual(len(partitions.read_partitions(dysk)), 1)

    def test_surowy_obraz(self):
        sciezka = self.sciezka("surowy.img")
        with open(sciezka, "wb") as fh:
            fh.write(tablica(wpis(0x06, 63, 1000)) + bytes(2047 * SEKTOR))
        with partitions.open_disk(sciezka) as dysk:
            self.assertIsInstance(dysk, partitions.RawDisk)
            self.assertEqual(dysk.sector_count, 2048)

    def test_brak_pliku(self):
        with self.assertRaises(partitions.DiskError):
            partitions.open_disk(self.sciezka("nie_ma.img"))

    def test_plik_za_krotki(self):
        sciezka = self.sciezka("krotki.img")
        with open(sciezka, "wb") as fh:
            fh.write(b"abc")
        with self.assertRaises(partitions.DiskError):
            partitions.open_disk(sciezka)

    def test_sektor_poza_dyskiem(self):
        sciezka = self.sciezka("maly.img")
        with open(sciezka, "wb") as fh:
            fh.write(bytes(4 * SEKTOR))
        with partitions.open_disk(sciezka) as dysk:
            with self.assertRaises(partitions.DiskError):
                dysk.read_sector(4)

    def test_opis_dla_czlowieka(self):
        sciezka = self.sciezka("opis.img")
        with open(sciezka, "wb") as fh:
            fh.write(tablica(wpis(0x06, 63, 1000, startowa=True))
                     + bytes(2047 * SEKTOR))
        opis = partitions.describe(sciezka)
        self.assertIn("FAT16", opis)
        self.assertIn("startowa", opis)

    def test_wiersz_polecen_bez_sladu_wyjatku(self):
        import contextlib
        import io
        bledy = io.StringIO()
        with contextlib.redirect_stderr(bledy):
            kod = partitions.main([self.sciezka("nie_ma.img")])
        self.assertEqual(kod, 1)
        self.assertNotIn("Traceback", bledy.getvalue())
        self.assertIn("nie ma takiego pliku", bledy.getvalue())


if __name__ == "__main__":
    unittest.main()
