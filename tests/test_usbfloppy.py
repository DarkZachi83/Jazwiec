"""
Testy obslugi fizycznych napedow.

Sprzetu nie ma, wiec urzadzenie udaje AtrapaNapedu z pomocy. Pozwala zadac,
ktore sektory sa martwe, a ktore slabe - czyli wracaja dopiero przy kolejnej
probie. Na tej roznicy opiera sie rozroznienie miedzy testem powierzchni
a weryfikacja po zapisie.

Wykrywanie napedow sprawdzamy na sztucznym drzewie /sys, bo najwazniejsza
jest tu wlasnosc negatywna: pendrive ani dysk zewnetrzny nie moga trafic na
liste urzadzen, na ktore program potrafi pisac.
"""

import gc
import os
import unittest

from helpers import PrzypadekZKatalogiem, podstaw_naped

import fat12
import usbfloppy


class IzolacjaUszkodzonychSektorow(PrzypadekZKatalogiem):

    def przygotuj(self, format_klucz="1440"):
        sciezka = self.sciezka("nosnik.bin")
        fat12.format_image(sciezka, fat12.FLOPPY_FORMATS[format_klucz],
                           "TEST", overwrite=True)
        fmt = fat12.FLOPPY_FORMATS[format_klucz]
        return sciezka, usbfloppy.FloppyDrive(
            sciezka, "ATRAPA", fmt.size_bytes, fmt.bytes_per_sector,
            "usb", format_klucz)

    def test_wskazuje_dokladnie_uszkodzone_sektory(self):
        """
        Odczyt idzie porcjami; dopiero gdy porcja zawiedzie, program schodzi
        do pojedynczych sektorow. Bez tego zglaszalby cala porcje.
        """
        sciezka, naped = self.przygotuj()
        martwe = {100, 101, 102, 500, 2879}
        podstaw_naped(usbfloppy, martwe=martwe)
        cel = self.sciezka("kopia.img")
        raport = usbfloppy.read_to_image(naped, cel)
        self.assertEqual(set(raport.bad_sectors), martwe)
        self.assertEqual(raport.done_sectors, 2880)

    def test_dobre_sektory_zostaja_nietkniete(self):
        sciezka, naped = self.przygotuj()
        martwe = {300}
        podstaw_naped(usbfloppy, martwe=martwe)
        cel = self.sciezka("kopia.img")
        usbfloppy.read_to_image(naped, cel)
        with open(sciezka, "rb") as fh:
            oryginal = fh.read()
        with open(cel, "rb") as fh:
            kopia = fh.read()
        for numer in (0, 1, 299, 301, 2879):
            with self.subTest(sektor=numer):
                self.assertEqual(kopia[numer * 512:(numer + 1) * 512],
                                 oryginal[numer * 512:(numer + 1) * 512])

    def test_nieodczytane_wypelniane_bajtem_dos(self):
        _, naped = self.przygotuj()
        podstaw_naped(usbfloppy, martwe={700})
        cel = self.sciezka("kopia.img")
        usbfloppy.read_to_image(naped, cel)
        with open(cel, "rb") as fh:
            fh.seek(700 * 512)
            self.assertEqual(set(fh.read(512)), {usbfloppy.FILL_BYTE})

    def test_przerwanie_konczy_odczyt(self):
        _, naped = self.przygotuj()
        podstaw_naped(usbfloppy)
        raport = usbfloppy.read_to_image(
            naped, self.sciezka("kopia.img"),
            progress=lambda r: r.done_sectors < 640)
        self.assertTrue(raport.cancelled)
        self.assertLessEqual(raport.done_sectors, 672)


class ProgiUszkodzen(PrzypadekZKatalogiem):
    """
    Test powierzchni i weryfikacja odpowiadaja na rozne pytania, wiec maja
    rozne progi. Pierwszy pyta "czy moge tu bezpiecznie zlozyc dane", drugi
    "czy zapis sie udal".
    """

    def przygotuj(self):
        sciezka = self.sciezka("nosnik.bin")
        fmt = fat12.FLOPPY_FORMATS["1440"]
        fat12.format_image(sciezka, fmt, "TEST", overwrite=True)
        # Obszar danych musi byc niezerowy - inaczej sektor "gubiony",
        # zapisujacy zera, nie roznilby sie od oczekiwanej tresci.
        wypelniacz = fat12.Fat12Image(sciezka)
        wypelniacz.write_file("/WYPELN.BIN", os.urandom(400_000))
        wypelniacz.close()
        obraz = self.sciezka("obraz.img")
        with open(sciezka, "rb") as zr, open(obraz, "wb") as ce:
            ce.write(zr.read())
        return sciezka, obraz, usbfloppy.FloppyDrive(
            sciezka, "ATRAPA", fmt.size_bytes, 512, "usb", "1440")

    def test_weryfikacja_toleruje_sektory_slabe(self):
        _, obraz, naped = self.przygotuj()
        podstaw_naped(usbfloppy, slabe={100, 500, 1200},
                      niepowodzenia=2)
        raport = usbfloppy.write_from_image(naped, obraz, verify=True)
        self.assertTrue(raport.verified)
        self.assertEqual(raport.bad_sectors, [])

    def test_weryfikacja_wylapuje_sektory_martwe(self):
        _, obraz, naped = self.przygotuj()
        podstaw_naped(usbfloppy, martwe={300, 301, 302})
        raport = usbfloppy.write_from_image(naped, obraz, verify=True)
        self.assertFalse(raport.verified)
        self.assertEqual(len(raport.bad_sectors), 3)

    def test_weryfikacja_wylapuje_rozjazd_tresci(self):
        """Sektor przyjal zapis, ale zapisal co innego."""
        _, obraz, naped = self.przygotuj()
        podstaw_naped(usbfloppy, gubione={33, 34})
        raport = usbfloppy.write_from_image(naped, obraz, verify=True)
        self.assertFalse(raport.verified)

    def test_test_powierzchni_oznacza_sektory_slabe(self):
        """
        Test powierzchni daje jedna probe na sektor, weryfikacja trzy.
        Sektor wymagajacy dwoch podejsc jest wiec oznaczany przy
        formatowaniu, a tolerowany przy sprawdzaniu zapisu.
        """
        _, _, naped = self.przygotuj()
        podstaw_naped(usbfloppy, slabe={800}, niepowodzenia=2)
        raport = usbfloppy.format_media(naped, "1440", "full", "TEST")
        self.assertIn(800, raport.bad_sectors,
                      "sektor z pogranicza ma byc oznaczony")

    def test_format_szybki_nie_bada_powierzchni(self):
        _, _, naped = self.przygotuj()
        podstaw_naped(usbfloppy)
        raport = usbfloppy.format_media(naped, "1440", "quick", "TEST")
        self.assertEqual(raport.bad_sectors, [])
        self.assertTrue(raport.verified)


class ZaporyPrzedZapisem(unittest.TestCase):
    """
    Zapis na urzadzenie fizyczne jest nieodwracalny. Kazda z zapor ma
    samodzielnie zatrzymac operacje.
    """

    def test_brak_nosnika(self):
        naped = usbfloppy.FloppyDrive("/dev/sdb", size_bytes=0)
        with self.assertRaises(usbfloppy.DriveError):
            usbfloppy.check_writable(naped)

    def test_rozmiar_nie_odpowiada_dyskietce(self):
        naped = usbfloppy.FloppyDrive("/dev/sdb", size_bytes=1_000_000,
                                      format_key=None)
        with self.assertRaises(usbfloppy.DriveError):
            usbfloppy.check_writable(naped)

    def test_urzadzenie_ponad_limit(self):
        naped = usbfloppy.FloppyDrive(
            "/dev/sdc", size_bytes=usbfloppy.MAX_MEDIA_BYTES * 2,
            format_key=None)
        with self.assertRaises(usbfloppy.DriveError):
            usbfloppy.check_writable(naped)

    def test_prawidlowa_dyskietka_przechodzi(self):
        naped = usbfloppy.FloppyDrive("/dev/sdb", size_bytes=1_474_560,
                                      format_key="1440")
        usbfloppy.check_writable(naped)          # nie moze zglosic bledu

    def test_obraz_o_zlym_rozmiarze_jest_odrzucany(self):
        naped = usbfloppy.FloppyDrive("/dev/sdb", size_bytes=1_474_560,
                                      format_key="1440")
        podstaw_naped(usbfloppy)
        with self.assertRaises(usbfloppy.DriveError):
            usbfloppy.write_from_image(naped, __file__)


class WykrywanieNapedow(PrzypadekZKatalogiem):
    """
    Sprawdzane na sztucznym drzewie /sys. Najwazniejsza jest tu wlasnosc
    negatywna: pendrive nie moze trafic na liste urzadzen do zapisu.
    """

    def zbuduj_sys(self, urzadzenia):
        korzen = self.sciezka("sys")
        os.makedirs(os.path.join(korzen, "sys", "block"))
        for nazwa, (wymienny, sektory, magistrala) in urzadzenia.items():
            rzeczywisty = os.path.join(korzen, "devices", magistrala, nazwa)
            os.makedirs(os.path.join(rzeczywisty, "device"))
            os.makedirs(os.path.join(rzeczywisty, "queue"))
            for plik, tresc in (("removable", str(wymienny)),
                                ("size", str(sektory)),
                                ("queue/hw_sector_size", "512"),
                                ("device/vendor", "ATRAPA"),
                                ("device/model", nazwa.upper())):
                with open(os.path.join(rzeczywisty, plik), "w") as fh:
                    fh.write(tresc)
            os.symlink(rzeczywisty,
                       os.path.join(korzen, "sys", "block", nazwa))
        return os.path.join(korzen, "sys")

    def test_pendrive_i_dysk_nie_trafiaja_na_liste(self):
        sys_korzen = self.zbuduj_sys({
            "sdb": (1, 2880, "usb1"),            # stacja z dyskietka 1,44
            "sde": (1, 1440, "usb1"),            # stacja z dyskietka 720
            "sdd": (1, 0, "usb1"),               # stacja pusta
            "sdc": (1, 15_728_640, "usb1"),      # pendrive 8 GB
            "sda": (0, 976_773_168, "ata1"),     # dysk systemowy
            "sdf": (1, 3_907_029_168, "usb1"),   # dysk zewnetrzny USB
        })
        znalezione = {os.path.basename(n.path)
                      for n in usbfloppy._linux_drives(sysfs=sys_korzen)}
        self.assertEqual(znalezione, {"sdb", "sde", "sdd"})

    def test_rozpoznaje_format_po_rozmiarze(self):
        sys_korzen = self.zbuduj_sys({"sdb": (1, 2880, "usb1")})
        naped = usbfloppy._linux_drives(sysfs=sys_korzen)[0]
        self.assertEqual(naped.format_key, "1440")
        self.assertEqual(naped.bus, "usb")


class PodgladDyskietki(PrzypadekZKatalogiem):
    """
    Podglad czyta leniwie: obszar systemowy przy otwarciu, klastry pliku
    dopiero przy wypakowaniu. Przy nosniku w kiepskim stanie ma to
    znaczenie, bo nie przechodzi calej powierzchni.
    """

    def przygotuj(self):
        sciezka = self.sciezka("nosnik.bin")
        fmt = fat12.FLOPPY_FORMATS["1440"]
        fat12.format_image(sciezka, fmt, "PODGLAD", overwrite=True)
        obraz = fat12.Fat12Image(sciezka)
        obraz.write_file("/README.TXT", b"tresc" * 100)
        obraz.mkdir("/UTILS")
        self.dane = os.urandom(12_000)
        obraz.write_file("/UTILS/EDIT.COM", self.dane)
        obraz.close()
        return sciezka, usbfloppy.FloppyDrive(
            sciezka, "ATRAPA", fmt.size_bytes, 512, "usb", "1440")

    def test_otwarcie_czyta_tylko_obszar_systemowy(self):
        sciezka, naped = self.przygotuj()
        licznik = {"sektory": 0}

        from helpers import AtrapaNapedu

        class Liczaca(AtrapaNapedu):
            def read(self, ile=-1):
                licznik["sektory"] += max(1, (ile if ile > 0 else 512) // 512)
                return super().read(ile)

        usbfloppy._open_device = lambda p, write: (Liczaca(p, write), None)
        podglad = usbfloppy.open_device_image(naped)
        self.assertLess(licznik["sektory"], 60,
                        "podglad nie moze czytac calego nosnika")
        self.assertEqual({e.name for e in podglad.listdir("/")},
                         {"README.TXT", "UTILS"})

    def test_wypakowanie_dociaga_klastry_pliku(self):
        _, naped = self.przygotuj()
        podstaw_naped(usbfloppy)
        podglad = usbfloppy.open_device_image(naped)
        self.assertEqual(podglad.read_file("/UTILS/EDIT.COM"), self.dane)

    def test_podglad_jest_tylko_do_odczytu(self):
        _, naped = self.przygotuj()
        podstaw_naped(usbfloppy)
        podglad = usbfloppy.open_device_image(naped)
        with self.assertRaises(fat12.Fat12Error):
            podglad.write_file("/NOWY.TXT", b"x")


class Deskryptory(PrzypadekZKatalogiem):
    """
    Urzadzenie musi zostac zwolnione takze po bledzie i po przerwaniu.
    Zapomniany uchwyt objawia sie potem jako "urzadzenie zajete".
    """

    def test_brak_wyciekow(self):
        if not os.path.isdir("/proc/self/fd"):
            self.skipTest("brak /proc")
        sciezka = self.sciezka("nosnik.bin")
        fmt = fat12.FLOPPY_FORMATS["720"]
        fat12.format_image(sciezka, fmt, "T", overwrite=True)
        obraz = self.sciezka("obraz.img")
        with open(sciezka, "rb") as zr, open(obraz, "wb") as ce:
            ce.write(zr.read())
        naped = usbfloppy.FloppyDrive(sciezka, "A", fmt.size_bytes, 512,
                                      "usb", "720")

        podstaw_naped(usbfloppy)
        gc.collect()
        przed = len(os.listdir("/proc/self/fd"))

        operacje = [
            lambda: usbfloppy.read_to_image(naped, self.sciezka("k.img")),
            lambda: usbfloppy.write_from_image(naped, obraz, verify=True),
            lambda: usbfloppy.format_media(naped, "720", "full", "T"),
            lambda: usbfloppy.read_to_image(
                naped, self.sciezka("k.img"),
                progress=lambda r: r.done_sectors < 100),
            lambda: usbfloppy.open_device_image(naped),
        ]
        for operacja in operacje:
            try:
                operacja()
            except Exception:       # noqa: BLE001 - interesuje nas tylko fd
                pass
        gc.collect()
        self.assertEqual(len(os.listdir("/proc/self/fd")), przed)


class Diagnostyka(PrzypadekZKatalogiem):

    def test_rozroznia_stany_nosnika(self):
        sciezka = self.sciezka("nosnik.bin")
        fmt = fat12.FLOPPY_FORMATS["720"]
        fat12.format_image(sciezka, fmt, "T", overwrite=True)
        naped = usbfloppy.FloppyDrive(sciezka, "A", fmt.size_bytes, 512,
                                      "usb", "720")

        podstaw_naped(usbfloppy)
        self.assertEqual(usbfloppy.probe_media(naped)["diagnosis"], "ok")

        pusty = self.sciezka("pusty.bin")
        with open(pusty, "wb") as fh:
            fh.write(b"\x00" * fmt.size_bytes)
        naped_pusty = usbfloppy.FloppyDrive(pusty, "A", fmt.size_bytes, 512,
                                            "usb", "720")
        self.assertEqual(
            usbfloppy.probe_media(naped_pusty)["diagnosis"], "no_filesystem")

        podstaw_naped(usbfloppy, martwe=set(range(32)))
        self.assertEqual(usbfloppy.probe_media(naped)["diagnosis"],
                         "unreadable")

    def test_brak_nosnika(self):
        naped = usbfloppy.FloppyDrive("/dev/sdb", size_bytes=0)
        self.assertEqual(usbfloppy.probe_media(naped)["diagnosis"],
                         "no_media")


if __name__ == "__main__":
    unittest.main()
