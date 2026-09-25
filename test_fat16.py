"""
Testy odczytu partycji FAT16 i FAT12 z obrazow dyskow twardych.

Obrazy budujemy tutaj, bajt po bajcie: blok BPB, dwie tablice FAT, katalog
glowny i obszar danych. Dzieki temu wiemy dokladnie, co powinno wyjsc -
i mozemy sprawdzic rzeczy, ktorych na cudzym obrazie nie da sie wymusic,
jak plik zajmujacy kilka klastrow albo uszkodzony lancuch.

Prawdziwy obraz z 86Boxa sluzyl do sprawdzenia modulu podczas pisania.
"""

import datetime
import os
import struct
import subprocess
import unittest

from helpers import PrzypadekZKatalogiem

import fat16
import partitions

SEKTOR = 512


class BudowniczyFat:
    """
    Sklada obraz partycji FAT - tyle, ile potrzeba do odczytu.

    Liczba klastrow decyduje o tym, czy wyjdzie FAT12 czy FAT16: tak samo
    liczyl DOS i tak samo rozpoznaje to nasz silnik.
    """

    def __init__(self, klastrow: int = 4200, sektorow_na_klaster: int = 4,
                 etykieta: str = "TESTOWY"):
        self.spc = sektorow_na_klaster
        self.klastrow = klastrow
        self.etykieta = etykieta
        self.bits = 12 if klastrow < fat16.GRANICA_FAT12 else 16
        self.wpisy_glowne = 512
        self.zarezerwowane = 1
        self.fatow = 2
        bajtow_fat = (klastrow + 2) * (2 if self.bits == 16 else 1.5)
        self.sektorow_fat = int((bajtow_fat + SEKTOR - 1) // SEKTOR) + 1
        self.sektorow_glownych = self.wpisy_glowne * 32 // SEKTOR
        self.pierwszy_danych = (self.zarezerwowane
                                + self.fatow * self.sektorow_fat
                                + self.sektorow_glownych)
        self.sektorow = self.pierwszy_danych + klastrow * self.spc
        self._fat = [0] * (klastrow + 2)
        # Dwa pierwsze wpisy to znacznik nosnika i znacznik konca - w FAT16
        # pelne szesnascie bitow. Wpisanie tu wartosci dwunastobitowych
        # daje obraz, ktory fsck.fat uznaje za uszkodzony.
        self._fat[0] = 0xFFF8 if self.bits == 16 else 0xFF8
        self._fat[1] = 0xFFFF if self.bits == 16 else 0xFFF
        self._dane: dict[int, bytes] = {}
        self._glowny: list[bytes] = []
        self._wolny = 2

    # -- budowanie ---------------------------------------------------------

    def _zajmij(self, dane: bytes) -> int:
        """Rozklada dane na klastry i wiaze je w lancuch."""
        rozmiar = self.spc * SEKTOR
        kawalki = [dane[i:i + rozmiar] for i in range(0, len(dane), rozmiar)]
        pierwszy = self._wolny
        for numer, kawalek in enumerate(kawalki):
            klaster = self._wolny
            self._dane[klaster] = kawalek.ljust(rozmiar, b"\x00")
            self._wolny += 1
            koniec = 0xFFFF if self.bits == 16 else 0xFFF
            self._fat[klaster] = (koniec if numer == len(kawalki) - 1
                                  else klaster + 1)
        return pierwszy

    def _wpis(self, nazwa: str, atrybuty: int, klaster: int,
              rozmiar: int) -> bytes:
        wpis = bytearray(32)
        if atrybuty == 0x08:
            wpis = bytearray(32)
            wpis[0:11] = nazwa.upper().ljust(11)[:11].encode("latin1")
            wpis[0x0B] = atrybuty
            return bytes(wpis)
        if nazwa in (".", ".."):
            # Wpisy kropkowe leza w polu nazwy jako takie, bez kropki
            # oddzielajacej rozszerzenie.
            wpis[0:8] = nazwa.ljust(8).encode("latin1")
            wpis[8:11] = b"   "
        else:
            rdzen, _, rozszerzenie = nazwa.partition(".")
            wpis[0:8] = rdzen.upper().ljust(8)[:8].encode("latin1")
            wpis[8:11] = rozszerzenie.upper().ljust(3)[:3].encode("latin1")
        wpis[0x0B] = atrybuty
        # 2 stycznia 1992, 03:04:10 - data wpisana wprost, zeby test mogl
        # sprawdzic przeliczanie lat liczonych od 1980.
        wpis[0x16:0x18] = struct.pack("<H", (3 << 11) | (4 << 5) | 5)
        wpis[0x18:0x1A] = struct.pack("<H", ((1992 - 1980) << 9) | (1 << 5) | 2)
        wpis[0x1A:0x1C] = struct.pack("<H", klaster)
        wpis[0x1C:0x20] = struct.pack("<I", rozmiar)
        return bytes(wpis)

    def plik(self, nazwa: str, dane: bytes) -> "BudowniczyFat":
        self._glowny.append(self._wpis(nazwa, 0x20, self._zajmij(dane),
                                       len(dane)))
        return self

    def katalog(self, nazwa: str, pliki: dict) -> "BudowniczyFat":
        """Podkatalog z wpisami kropkowymi, jak w prawdziwym systemie."""
        klaster = self._wolny
        self._wolny += 1
        wpisy = [self._wpis(".", 0x10, klaster, 0),
                 self._wpis("..", 0x10, 0, 0)]
        for nazwa_pliku, dane in pliki.items():
            wpisy.append(self._wpis(nazwa_pliku, 0x20,
                                    self._zajmij(dane), len(dane)))
        self._dane[klaster] = b"".join(wpisy).ljust(self.spc * SEKTOR, b"\x00")
        self._fat[klaster] = 0xFFFF if self.bits == 16 else 0xFFF
        self._glowny.append(self._wpis(nazwa, 0x10, klaster, 0))
        return self

    def skasowany(self, nazwa: str) -> "BudowniczyFat":
        wpis = bytearray(self._wpis(nazwa, 0x20, 0, 10))
        wpis[0] = fat16.SKASOWANY
        self._glowny.append(bytes(wpis))
        return self

    def etykieta_wolumenu(self, nazwa: str) -> "BudowniczyFat":
        self._glowny.append(self._wpis(nazwa, 0x08, 0, 0))
        return self

    def uszkodz_lancuch(self, klaster: int) -> "BudowniczyFat":
        """Klaster wskazujacy sam na siebie - lancuch bez konca."""
        self._fat[klaster] = klaster
        return self

    # -- zlozenie ----------------------------------------------------------

    def _bpb(self) -> bytes:
        s = bytearray(SEKTOR)
        s[0:3] = b"\xeb\x3c\x90"
        s[3:11] = b"MSDOS5.0"
        s[0x0B:0x0D] = struct.pack("<H", SEKTOR)
        s[0x0D] = self.spc
        s[0x0E:0x10] = struct.pack("<H", self.zarezerwowane)
        s[0x10] = self.fatow
        s[0x11:0x13] = struct.pack("<H", self.wpisy_glowne)
        s[0x15] = 0xF8
        s[0x16:0x18] = struct.pack("<H", self.sektorow_fat)
        s[0x18:0x1A] = struct.pack("<H", 63)
        s[0x1A:0x1C] = struct.pack("<H", 16)
        s[0x20:0x24] = struct.pack("<I", self.sektorow)
        s[0x26] = 0x29
        s[0x2B:0x36] = self.etykieta.ljust(11)[:11].encode("latin1")
        s[0x36:0x3E] = (b"FAT16   " if self.bits == 16 else b"FAT12   ")
        s[510:512] = b"\x55\xaa"
        return bytes(s)

    def _tablica_fat(self) -> bytes:
        dane = bytearray(self.sektorow_fat * SEKTOR)
        if self.bits == 16:
            for numer, wartosc in enumerate(self._fat):
                dane[numer * 2:numer * 2 + 2] = struct.pack("<H",
                                                            wartosc & 0xFFFF)
        else:
            for numer, wartosc in enumerate(self._fat):
                miejsce = numer + numer // 2
                para = int.from_bytes(dane[miejsce:miejsce + 2], "little")
                if numer & 1:
                    para = (para & 0x000F) | ((wartosc & 0xFFF) << 4)
                else:
                    para = (para & 0xF000) | (wartosc & 0xFFF)
                dane[miejsce:miejsce + 2] = struct.pack("<H", para)
        return bytes(dane)

    def zbuduj(self) -> bytes:
        # Etykieta zyje w dwoch miejscach: w sektorze rozruchowym i jako
        # wpis w katalogu glownym. DOS zapisuje oba, a fsck.fat zglasza
        # brak drugiego - obraz testowy musi byc pod tym wzgledem taki sam
        # jak prawdziwy, inaczej nie da sie odroznic naszych bledow od
        # jego wlasnych.
        if self.etykieta and not any(
                w[0x0B] == 0x08 for w in self._glowny):
            self._glowny.insert(0, self._wpis(self.etykieta, 0x08, 0, 0))
        obraz = bytearray(self.sektorow * SEKTOR)
        obraz[0:SEKTOR] = self._bpb()
        fat = self._tablica_fat()
        for numer in range(self.fatow):
            od = (self.zarezerwowane + numer * self.sektorow_fat) * SEKTOR
            obraz[od:od + len(fat)] = fat
        glowny = b"".join(self._glowny)
        od = (self.zarezerwowane + self.fatow * self.sektorow_fat) * SEKTOR
        obraz[od:od + len(glowny)] = glowny
        for klaster, dane in self._dane.items():
            od = (self.pierwszy_danych
                  + (klaster - 2) * self.spc) * SEKTOR
            obraz[od:od + len(dane)] = dane
        return bytes(obraz)


def wpis_partycji(typ: int, start: int, dlugosc: int) -> bytes:
    return (b"\x80\x00\x00\x00" + bytes([typ]) + b"\x00\x00\x00"
            + struct.pack("<I", start) + struct.pack("<I", dlugosc))


class OdczytPartycji(PrzypadekZKatalogiem):

    def dysk(self, budowniczy: BudowniczyFat, start: int = 63) -> str:
        """Obraz dysku z tablica partycji i partycja od podanego sektora."""
        partycja = budowniczy.zbuduj()
        sciezka = self.sciezka("dysk.img")
        mbr = bytearray(SEKTOR)
        mbr[446:462] = wpis_partycji(
            0x06 if budowniczy.bits == 16 else 0x01,
            start, budowniczy.sektorow)
        mbr[510:512] = b"\x55\xaa"
        with open(sciezka, "wb") as fh:
            fh.write(bytes(mbr) + bytes((start - 1) * SEKTOR) + partycja)
        return sciezka

    def test_katalog_glowny(self):
        b = (BudowniczyFat()
             .plik("CONFIG.SYS", b"FILES=30\r\n")
             .plik("AUTOEXEC.BAT", b"@ECHO OFF\r\n")
             .katalog("DOS", {"EDIT.COM": b"x" * 100}))
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            nazwy = [w.name for w in obraz.listdir("/")]
        self.assertEqual(nazwy, ["CONFIG.SYS", "AUTOEXEC.BAT", "DOS"])

    def test_rozpoznaje_fat16(self):
        with fat16.HardDiskImage(self.dysk(BudowniczyFat())) as obraz:
            self.assertEqual(obraz.volume.bpb.bits, 16)
            self.assertIn("FAT16", obraz.format_name)
            self.assertEqual(obraz.get_label(), "TESTOWY")

    def test_rozpoznaje_fat12_po_liczbie_klastrow(self):
        """
        O rodzaju decyduje liczba klastrow, nie napis w sektorze
        rozruchowym - ten bywa mylacy.
        """
        b = BudowniczyFat(klastrow=1000).plik("A.TXT", b"x")
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            self.assertEqual(obraz.volume.bpb.bits, 12)
            self.assertIn("FAT12", obraz.format_name)

    def test_fat12_lancuch_przez_wpisy_parzyste_i_nieparzyste(self):
        """
        Przy dwunastu bitach dwa wpisy dziela trzy bajty, wiec parzyste
        i nieparzyste rozpakowuje sie inaczej. Plik z jednego klastra
        uzywa tylko jednej z tych drog i nie sprawdza niczego.
        """
        tresc = bytes(range(200)) * 60           # kilka klastrow
        b = BudowniczyFat(klastrow=1000).plik("DUZY.BIN", tresc)
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            self.assertEqual(obraz.volume.bpb.bits, 12)
            self.assertEqual(obraz.read_file("/DUZY.BIN"), tresc)
            self.assertGreater(len(obraz.volume.chain(2)), 3,
                               "lancuch ma przejsc przez oba rodzaje wpisow")

    def test_zawartosc_pliku(self):
        tresc = b"DEVICE=HIMEM.SYS\r\nFILES=30\r\n"
        b = BudowniczyFat().plik("CONFIG.SYS", tresc)
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            self.assertEqual(obraz.read_file("/CONFIG.SYS"), tresc)

    def test_plik_z_kilku_klastrow(self):
        """Lancuch klastrow, a nie jeden kawalek - i dokladna dlugosc."""
        tresc = bytes(range(256)) * 40           # ponad 2 klastry po 2 kB
        b = BudowniczyFat().plik("DUZY.BIN", tresc)
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            odczytane = obraz.read_file("/DUZY.BIN")
        self.assertEqual(len(odczytane), len(tresc))
        self.assertEqual(odczytane, tresc)

    def test_podkatalog(self):
        b = BudowniczyFat().katalog("DOS", {"EDIT.COM": b"abc",
                                            "FORMAT.COM": b"defg"})
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            wpisy = obraz.listdir("/DOS")
            self.assertEqual([w.name for w in wpisy],
                             ["EDIT.COM", "FORMAT.COM"])
            self.assertEqual(obraz.read_file("/DOS/FORMAT.COM"), b"defg")

    def test_wpisy_kropkowe_nie_sa_pokazywane(self):
        b = BudowniczyFat().katalog("DOS", {"A.TXT": b"x"})
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            nazwy = [w.name for w in obraz.listdir("/DOS")]
        self.assertNotIn(".", nazwy)
        self.assertNotIn("..", nazwy)

    def test_skasowane_i_etykieta_pomijane(self):
        b = (BudowniczyFat()
             .plik("A.TXT", b"x")
             .skasowany("STARY.TXT")
             .etykieta_wolumenu("ETYKIETA"))
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            nazwy = [w.name for w in obraz.listdir("/")]
        self.assertEqual(nazwy, ["A.TXT"])

    def test_data_liczona_od_1980(self):
        b = BudowniczyFat().plik("A.TXT", b"x")
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            wpis = obraz.stat("/A.TXT")
        self.assertEqual(wpis.modified,
                         datetime.datetime(1992, 1, 2, 3, 4, 10))

    def test_miejsce_na_partycji(self):
        b = BudowniczyFat(klastrow=4200).plik("A.TXT", b"x" * 5000)
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            self.assertEqual(obraz.total_bytes, 4200 * 2048)
            self.assertLess(obraz.free_bytes, obraz.total_bytes)
            self.assertGreater(obraz.free_bytes, 4000 * 2048)

    def test_partycja_nie_od_zera(self):
        """
        Partycja zaczyna sie od sektora 63, wiec wszystkie numery wewnatrz
        trzeba przeliczac. Pomylka tutaj daje smieci zamiast katalogu.
        """
        b = BudowniczyFat().plik("A.TXT", b"tresc")
        with fat16.HardDiskImage(self.dysk(b, start=2048)) as obraz:
            self.assertEqual(obraz.read_file("/A.TXT"), b"tresc")

    def test_brak_pliku(self):
        b = BudowniczyFat().plik("A.TXT", b"x")
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            self.assertFalse(obraz.exists("/NIE_MA.TXT"))
            with self.assertRaises(fat16.Fat16Error):
                obraz.read_file("/NIE_MA.TXT")

    def test_uszkodzony_lancuch_nie_zapetla(self):
        b = BudowniczyFat().plik("A.TXT", b"x" * 5000).uszkodz_lancuch(2)
        with fat16.HardDiskImage(self.dysk(b)) as obraz:
            dane = obraz.read_file("/A.TXT")
            self.assertEqual(obraz.volume.chain(2), [2],
                             "klaster wskazujacy sam na siebie konczy lancuch")
        self.assertLessEqual(len(dane), 5000)


class TylkoDoOdczytu(PrzypadekZKatalogiem):

    def obraz(self):
        b = BudowniczyFat().plik("A.TXT", b"x")
        sciezka = self.sciezka("dysk.img")
        mbr = bytearray(SEKTOR)
        mbr[446:462] = wpis_partycji(0x06, 63, b.sektorow)
        mbr[510:512] = b"\x55\xaa"
        with open(sciezka, "wb") as fh:
            fh.write(bytes(mbr) + bytes(62 * SEKTOR) + b.zbuduj())
        return fat16.HardDiskImage(sciezka)

    def test_zglasza_sie_jako_tylko_do_odczytu(self):
        with self.obraz() as obraz:
            self.assertTrue(obraz.read_only)

    def test_kazda_proba_zapisu_konczy_sie_bledem(self):
        """
        Nadpisanie obrazu dysku w trakcie pracy maszyny niszczy caly system
        plikow, a nie jedna dyskietke - milczace przepuszczenie zapisu
        byloby tu najgorsza mozliwoscia.
        """
        with self.obraz() as obraz:
            for operacja, argumenty in (
                    ("write_file", ("/A.TXT", b"x")),
                    ("import_file", ("/tmp/x", "/")),
                    ("mkdir", ("/NOWY",)),
                    ("remove", ("/A.TXT",)),
                    ("rename", ("/A.TXT", "B.TXT")),
                    ("set_label", ("INNA",))):
                with self.subTest(operacja=operacja):
                    with self.assertRaises(fat16.Fat16Error):
                        getattr(obraz, operacja)(*argumenty)


class Rozpoznawanie(PrzypadekZKatalogiem):

    def test_vhd_po_sygnaturze(self):
        self.assertTrue(fat16.looks_like_disk(b"conectix" + bytes(1016),
                                              1048576))

    def test_surowy_obraz_po_tablicy_partycji(self):
        naglowek = bytearray(1024)
        naglowek[446:462] = wpis_partycji(0x06, 63, 20000)
        naglowek[510:512] = b"\x55\xaa"
        self.assertTrue(fat16.looks_like_disk(bytes(naglowek),
                                              21000 * SEKTOR))

    def test_dyskietka_to_nie_dysk(self):
        """Sektor rozruchowy dyskietki tez ma sygnature 55AA."""
        naglowek = bytearray(1024)
        naglowek[510:512] = b"\x55\xaa"
        self.assertFalse(fat16.looks_like_disk(bytes(naglowek), 1474560))

    def test_partycja_wieksza_niz_plik_odrzucona(self):
        naglowek = bytearray(1024)
        naglowek[446:462] = wpis_partycji(0x06, 63, 10_000_000)
        naglowek[510:512] = b"\x55\xaa"
        self.assertFalse(fat16.looks_like_disk(bytes(naglowek), 1048576))


class WyborPartycji(PrzypadekZKatalogiem):

    def dysk_z_dwiema(self) -> str:
        pierwsza = BudowniczyFat(etykieta="PIERWSZA").plik("A.TXT", b"aaa")
        druga = BudowniczyFat(etykieta="DRUGA").plik("B.TXT", b"bbb")
        start1, start2 = 63, 63 + pierwsza.sektorow + 63
        sciezka = self.sciezka("dwie.img")
        mbr = bytearray(SEKTOR)
        mbr[446:462] = wpis_partycji(0x06, start1, pierwsza.sektorow)
        mbr[462:478] = wpis_partycji(0x06, start2, druga.sektorow)
        mbr[510:512] = b"\x55\xaa"
        with open(sciezka, "wb") as fh:
            fh.write(bytes(mbr) + bytes((start1 - 1) * SEKTOR)
                     + pierwsza.zbuduj() + bytes(63 * SEKTOR)
                     + druga.zbuduj())
        return sciezka

    def test_domyslnie_pierwsza_czytelna(self):
        with fat16.HardDiskImage(self.dysk_z_dwiema()) as obraz:
            self.assertEqual(obraz.get_label(), "PIERWSZA")
            self.assertEqual(obraz.partition_index, 1)
            self.assertEqual(len(obraz.partitions), 2)

    def test_mozna_wskazac_druga(self):
        with fat16.HardDiskImage(self.dysk_z_dwiema(), partition=2) as obraz:
            self.assertEqual(obraz.get_label(), "DRUGA")
            self.assertEqual([w.name for w in obraz.listdir("/")], ["B.TXT"])

    def test_nieistniejaca_partycja(self):
        with self.assertRaises(fat16.Fat16Error):
            fat16.HardDiskImage(self.dysk_z_dwiema(), partition=7)

    def test_dysk_bez_czytelnych_partycji(self):
        sciezka = self.sciezka("ntfs.img")
        mbr = bytearray(SEKTOR)
        mbr[446:462] = wpis_partycji(0x07, 63, 1000)
        mbr[510:512] = b"\x55\xaa"
        with open(sciezka, "wb") as fh:
            fh.write(bytes(mbr) + bytes(2000 * SEKTOR))
        with self.assertRaises(fat16.Fat16Error) as blad:
            fat16.HardDiskImage(sciezka)
        self.assertIn("FAT", str(blad.exception))


class BezTablicyPartycji(PrzypadekZKatalogiem):

    def test_caly_obraz_jako_jeden_system_plikow(self):
        """
        Zdarzaja sie obrazy bez tablicy partycji - na przyklad dyski
        przygotowane przez narzedzia, ktore pomijaly ten krok.
        """
        b = BudowniczyFat().plik("A.TXT", b"tresc")
        sciezka = self.sciezka("bez_mbr.img")
        with open(sciezka, "wb") as fh:
            fh.write(b.zbuduj())
        with fat16.HardDiskImage(sciezka) as obraz:
            self.assertIsNone(obraz.partition)
            self.assertEqual(obraz.read_file("/A.TXT"), b"tresc")


class BledneObrazy(PrzypadekZKatalogiem):

    def test_partycja_bez_sensownego_bpb(self):
        sciezka = self.sciezka("smieci.img")
        mbr = bytearray(SEKTOR)
        mbr[446:462] = wpis_partycji(0x06, 63, 1000)
        mbr[510:512] = b"\x55\xaa"
        with open(sciezka, "wb") as fh:
            fh.write(bytes(mbr) + bytes(2000 * SEKTOR))
        with self.assertRaises(fat16.Fat16Error):
            fat16.HardDiskImage(sciezka)

    def test_brak_pliku(self):
        with self.assertRaises(fat16.Fat16Error):
            fat16.HardDiskImage(self.sciezka("nie_ma.vhd"))

    def test_blad_dziedziczy_po_wspolnym_przodku(self):
        """Okno lapie jeden typ bledu dla wszystkich silnikow."""
        import engines
        self.assertTrue(issubclass(fat16.Fat16Error, engines.ImageError))


class WarstwaSilnikow(PrzypadekZKatalogiem):
    """
    Obraz dysku ma sie otwierac ta sama droga co dyskietka - ale zawsze
    tylko do odczytu. Zapis wymaga siegniecia po silnik wprost.
    """

    def test_dysk_rozpoznany_przez_warstwe(self):
        import engines
        b = BudowniczyFat().plik("A.TXT", b"tresc")
        sciezka = self.sciezka("dysk.img")
        mbr = bytearray(SEKTOR)
        mbr[446:462] = wpis_partycji(0x06, 63, b.sektorow)
        mbr[510:512] = b"\x55\xaa"
        with open(sciezka, "wb") as fh:
            fh.write(bytes(mbr) + bytes(62 * SEKTOR) + b.zbuduj())
        silnik = engines.detect(sciezka)
        self.assertIsNotNone(silnik)
        self.assertEqual(silnik.key, "harddisk")
        obraz = engines.open_image(sciezka)
        self.addCleanup(obraz.close)
        self.assertTrue(obraz.read_only,
                        "z menu obraz dysku otwiera sie tylko do odczytu")
        self.assertEqual(obraz.read_file("/A.TXT"), b"tresc")

    def test_dyskietka_nadal_trafia_do_fat12(self):
        """
        Obrazy nie moga sie mylic: dyskietka ma sensowny blok BPB w
        pierwszym sektorze, a dysk tablice partycji.
        """
        import engines
        import fat12
        sciezka = self.sciezka("dyskietka.img")
        fat12.format_image(sciezka, fat12.FLOPPY_FORMATS["1440"], "TEST",
                           overwrite=True)
        silnik = engines.detect(sciezka)
        self.assertEqual(silnik.key, "fat12")


class LenistwoOdczytu(PrzypadekZKatalogiem):
    """
    Dysk 240 MB nie moze byc wczytywany w calosci, zeby pokazac katalog.
    Liczymy, ile sektorow program naprawde przeczytal.
    """

    class Liczacy:
        def __init__(self, dysk):
            self._dysk = dysk
            self.odczytow = 0

        def read_sector(self, lba):
            self.odczytow += 1
            return self._dysk.read_sector(lba)

        @property
        def sector_count(self):
            return self._dysk.sector_count

        @property
        def kind_name(self):
            return self._dysk.kind_name

        def close(self):
            self._dysk.close()

    def test_katalog_glowny_nie_czyta_calego_dysku(self):
        b = BudowniczyFat(klastrow=20000)
        for numer in range(20):
            b.plik(f"PLIK{numer:02d}.TXT", b"x" * 100)
        sciezka = self.sciezka("duzy.img")
        with open(sciezka, "wb") as fh:
            fh.write(b.zbuduj())
        liczacy = self.Liczacy(partitions.open_disk(sciezka))
        wolumin = fat16.FatVolume(liczacy, 0, b.sektorow)
        przed = liczacy.odczytow
        wolumin.listdir("/")
        liczacy.close()
        self.assertLess(liczacy.odczytow - przed, b.sektorow // 10,
                        "katalog glowny to ulamek dysku")



def _fsck_dostepny() -> bool:
    import shutil
    return shutil.which("fsck.fat") is not None


@unittest.skipUnless(_fsck_dostepny(), "brak fsck.fat (pakiet dosfstools)")
class ZapisOcenionyPrzezFsck(PrzypadekZKatalogiem):
    """
    Niezalezne potwierdzenie poprawnosci zapisu.

    Wlasny silnik nie moze byc sedzia we wlasnej sprawie: czyta tak, jak
    zapisal, wiec zgodny blad po obu stronach zostalby niezauwazony. Tak
    wlasnie wyszlo z dwoma pierwszymi wpisami tablicy FAT.
    """

    def sprawdz(self, sciezka: str) -> subprocess.CompletedProcess:
        return subprocess.run(["fsck.fat", "-n", "-v", sciezka],
                              capture_output=True, text=True)

    def obraz(self, klastrow: int = 4200) -> str:
        sciezka = self.sciezka("partycja.img")
        b = BudowniczyFat(klastrow=klastrow,
                          etykieta="DOS").plik("CONFIG.SYS", b"FILES=30")
        with open(sciezka, "wb") as fh:
            fh.write(b.zbuduj())
        return sciezka

    def test_obraz_testowy_jest_poprawny(self):
        """Punkt wyjscia musi byc czysty, inaczej nic nie udowodnimy."""
        wynik = self.sprawdz(self.obraz())
        self.assertEqual(wynik.returncode, 0, wynik.stdout[-400:])

    def test_po_zapisie_nadal_poprawny(self):
        sciezka = self.obraz()
        with fat16.HardDiskImage(sciezka, read_only=False) as obraz:
            obraz.write_file("/AUTOEXEC.BAT", b"@ECHO OFF\r\n")
            obraz.mkdir("/GRY")
            obraz.mkdir("/GRY/POOL")
            obraz.write_file("/GRY/POOL/POOL.EXE", bytes(range(256)) * 300)
            obraz.write_file("/TYMCZASOWY.TXT", b"x" * 9000)
            obraz.remove("/TYMCZASOWY.TXT")
            obraz.rename("/CONFIG.SYS", "CONFIG.OLD")
            obraz.set_label("TESTOWY")
        wynik = self.sprawdz(sciezka)
        self.assertEqual(wynik.returncode, 0, wynik.stdout[-600:])
        with fat16.HardDiskImage(sciezka) as obraz:
            self.assertEqual(obraz.get_label(), "TESTOWY")

    def test_fat12_po_zapisie(self):
        sciezka = self.obraz(klastrow=1000)
        with fat16.HardDiskImage(sciezka, read_only=False) as obraz:
            obraz.write_file("/DUZY.BIN", bytes(range(256)) * 200)
            obraz.mkdir("/PODKATALOG")
            obraz.write_file("/PODKATALOG/A.TXT", b"tresc")
        wynik = self.sprawdz(sciezka)
        self.assertEqual(wynik.returncode, 0, wynik.stdout[-600:])

    def test_kasowanie_zwalnia_klastry(self):
        sciezka = self.obraz()
        with fat16.HardDiskImage(sciezka, read_only=False) as obraz:
            przed = obraz.free_bytes
            obraz.write_file("/DUZY.BIN", b"x" * 100000)
            self.assertLess(obraz.free_bytes, przed)
            obraz.remove("/DUZY.BIN")
            self.assertEqual(obraz.free_bytes, przed)
        wynik = self.sprawdz(sciezka)
        self.assertEqual(wynik.returncode, 0, wynik.stdout[-400:])



class KopiowanieDrzewa(PrzypadekZKatalogiem):
    """
    Kopiowanie katalogu na dysk. Kontrakt musi byc ten sam co przy
    dyskietce - okno wola obie drogi tak samo i nie odroznia ich.
    """

    def dysk(self) -> str:
        sciezka = self.sciezka("dysk.img")
        b = BudowniczyFat(klastrow=6000,
                          etykieta="DOS").plik("CONFIG.SYS", b"x")
        mbr = bytearray(SEKTOR)
        mbr[446:462] = wpis_partycji(0x06, 63, b.sektorow)
        mbr[510:512] = b"\x55\xaa"
        with open(sciezka, "wb") as fh:
            fh.write(bytes(mbr) + bytes(62 * SEKTOR) + b.zbuduj())
        return sciezka

    def drzewo(self) -> str:
        korzen = self.sciezka("Sid Meiers Civilization")
        os.makedirs(os.path.join(korzen, "SAVE"))
        for numer in range(4):
            with open(os.path.join(korzen, f"CIV{numer}.DAT"), "wb") as fh:
                fh.write(bytes(3000))
        with open(os.path.join(korzen, "SAVE", "GRA1.SVE"), "wb") as fh:
            fh.write(b"zapis")
        return korzen

    def test_ten_sam_kontrakt_co_przy_dyskietce(self):
        import inspect
        import fat12
        dysk = inspect.signature(fat16.HardDiskImage.import_tree)
        dyskietka = inspect.signature(fat12.Fat12Image.import_tree)
        self.assertEqual(list(dysk.parameters), list(dyskietka.parameters))

    def test_struktura_i_zawartosc(self):
        with fat16.HardDiskImage(self.dysk(), read_only=False) as obraz:
            raport = obraz.import_tree(self.drzewo(), "/")
            self.assertEqual(raport["files"], 5)
            self.assertEqual(raport["dirs"], 2)
            self.assertEqual([w.name for w in obraz.listdir("/SIDMEIER")],
                             ["CIV0.DAT", "CIV1.DAT", "CIV2.DAT", "CIV3.DAT",
                              "SAVE"])
            self.assertEqual(obraz.read_file("/SIDMEIER/SAVE/GRA1.SVE"),
                             b"zapis")

    def test_raport_podaje_nazwe_z_dysku(self):
        """
        Wczesniej raport pokazywal "SID MEIERS C" - nazwe ze spacjami,
        ktora nigdzie nie istniala, bo wpis i tak przechodzi przez 8.3.
        """
        with fat16.HardDiskImage(self.dysk(), read_only=False) as obraz:
            raport = obraz.import_tree(self.drzewo(), "/")
        self.assertIn("Sid Meiers Civilization -> SIDMEIER",
                      raport["renamed"])

    def test_bez_katalogu_nadrzednego(self):
        with fat16.HardDiskImage(self.dysk(), read_only=False) as obraz:
            obraz.import_tree(self.drzewo(), "/", include_root=False)
            nazwy = [w.name for w in obraz.listdir("/")]
        self.assertIn("CIV0.DAT", nazwy)
        self.assertNotIn("SIDMEIER", nazwy)

    def test_przerwanie_zatrzymuje_kopiowanie(self):
        """on_item zwracajace False ma zatrzymac prace, a nie tylko zglaszac."""
        widziane = []

        def obserwator(sciezka):
            widziane.append(sciezka)
            return len(widziane) < 3

        with fat16.HardDiskImage(self.dysk(), read_only=False) as obraz:
            raport = obraz.import_tree(self.drzewo(), "/",
                                       on_item=obserwator)
        self.assertEqual(len(widziane), 3)
        self.assertLess(raport["files"], 5)

    def test_skracanie_nazw(self):
        for nazwa, oczekiwana in (
                ("Sid Meiers Civilization", "SIDMEIER"),
                ("Leisure Suit Larry.exe", "LEISURES.EXE"),
                ("a.b.c.txt", "ABC.TXT"),
                ("config.sys", "CONFIG.SYS")):
            with self.subTest(nazwa=nazwa):
                self.assertEqual(fat16.HardDiskImage.short_name(nazwa),
                                 oczekiwana)


if __name__ == "__main__":
    unittest.main()
