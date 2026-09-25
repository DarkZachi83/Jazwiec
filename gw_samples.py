"""
Probki wyjscia polecenia gw z prawdziwego urzadzenia.

Greaseweazle V4.1, firmware 1.6, narzedzia 1.23, naped Panasonic
JU-257A606P oraz naped uszkodzony z zablokowana glowica.

Fragmenty nietrywialne - martwa sciezka, sektory z obcego cylindra, blad
krytyczny, gw info - sa przepisane doslownie. Powtarzalne linie poprawnie
odczytanych sciezek sa generowane w identycznym formacie; liczby przejsc
strumienia nie maja dla rozbioru znaczenia.
"""

GW_INFO_URZADZENIE = """\
Host Tools: 1.23
Device:
  Port:     /dev/ttyACM0
  Model:    Greaseweazle V4.1
  MCU:      AT32F403A, 216MHz, 224kB SRAM
  Firmware: 1.6
  Serial:   GW053C0C51284700000754A413
  USB:      Full Speed (12 Mbit/s), 128kB Buffer
"""

GW_INFO_BRAK = """\
Host Tools: 1.23
Device:
  Not found
"""

GW_BLAD_KRYTYCZNY = """\
** FATAL ERROR:
Cannot find the Greaseweazle device
"""

# Dyskietka windowsowa na napedzie Panasonic - doslownie
MARTWA_SCIEZKA_C1H1 = """\
T1.1: IBM MFM (0/18 sectors) from Raw Flux (135692 flux in 400.30ms)
T1.1: IBM MFM (0/18 sectors) from Raw Flux (203248 flux in 600.20ms) (Retry #1.1)
T1.1: IBM MFM (0/18 sectors) from Raw Flux (203727 flux in 600.20ms) (Retry #1.2)
T1.1: IBM MFM (0/18 sectors) from Raw Flux (204316 flux in 600.19ms) (Retry #1.3)
T1.1: Giving up: 18 sectors missing
"""

# Uszkodzony naped, glowica zablokowana na cylindrze 1 - doslownie, lacznie
# z powtorzeniami: gw wypisuje te same obce sektory przy kazdej probie
# odczytu. Skrocenie ich usuwaloby wlasnie to, co ma sprawdzic test.
OBCY_CYLINDER = """\
T19.0: IBM MFM (0/18 sectors) from Raw Flux (234503 flux in 597.45ms) (Retry #1.2)
T19.0: Ignoring unexpected sector C:1 H:0 R:1 N:2
T19.0: Ignoring unexpected sector C:1 H:0 R:4 N:2
T19.0: Ignoring unexpected sector C:1 H:0 R:9 N:2
T19.0: Ignoring unexpected sector C:1 H:0 R:2 N:2
T19.0: Ignoring unexpected sector C:1 H:0 R:1 N:2
T19.0: Ignoring unexpected sector C:1 H:0 R:4 N:2
T19.0: Ignoring unexpected sector C:1 H:0 R:9 N:2
T19.0: Ignoring unexpected sector C:1 H:0 R:2 N:2
T19.0: IBM MFM (0/18 sectors) from Raw Flux (234509 flux in 597.46ms) (Retry #1.3)
T19.0: Giving up: 18 sectors missing
T19.1: IBM MFM (0/18 sectors) from Raw Flux (112433 flux in 398.49ms)
T19.1: IBM MFM (0/18 sectors) from Raw Flux (168075 flux in 597.44ms) (Retry #1.1)
T19.1: IBM MFM (0/18 sectors) from Raw Flux (168337 flux in 597.52ms) (Retry #1.2)
T19.1: IBM MFM (0/18 sectors) from Raw Flux (167789 flux in 597.52ms) (Retry #1.3)
T19.1: Giving up: 18 sectors missing
T20.0: Ignoring unexpected sector C:1 H:0 R:1 N:2
T20.0: Ignoring unexpected sector C:1 H:0 R:4 N:2
T20.0: IBM MFM (0/18 sectors) from Raw Flux (156399 flux in 398.52ms)
"""


def _linia(cyl, head, znalezione=18, ms="400.28", flux=152400):
    return (f"T{cyl}.{head}: IBM MFM ({znalezione}/18 sectors) from Raw Flux "
            f"({flux} flux in {ms}ms)")


def _mapa(martwe: set) -> str:
    """Mapa sektorow w ukladzie gw; martwe to zbior (cylinder, glowica)."""
    wiersze = [
        "Cyl-> 0         1         2         3         4         5         "
        "6         7         ",
        "H. S: " + "0123456789" * 8,
    ]
    for glowica in (0, 1):
        for sektor in range(18):
            znaki = "".join("X" if (c, glowica) in martwe else "."
                            for c in range(80))
            wiersze.append(f"{glowica}.{sektor:>2}: {znaki}")
    return "\n".join(wiersze)


def pelny_odczyt(martwe: set = frozenset(), ms: str = "400.28",
                 slabe: set = frozenset()) -> str:
    """
    Kompletne wyjscie gw read dla dyskietki 1,44 MB.

    Sciezki z martwe dostaja blok doslownie przepisany z prawdziwego odczytu.
    Sciezki ze slabe czytaja sie niepelnie za pierwszym razem, a w calosci
    przy ponownej probie - w formacie linii ponownych prob z prawdziwego gw.
    """
    wiersze = ["Reading c=0-79:h=0-1 revs=2", "Format ibm.1440"]
    for cyl in range(80):
        for glowica in (0, 1):
            if (cyl, glowica) in slabe:
                wiersze.append(_linia(cyl, glowica, znalezione=11, ms=ms))
                wiersze.append(
                    f"T{cyl}.{glowica}: IBM MFM (18/18 sectors) from Raw Flux "
                    f"(228600 flux in 600.20ms) (Retry #1.1)")
            elif (cyl, glowica) in martwe:
                wiersze += MARTWA_SCIEZKA_C1H1.replace(
                    "T1.1", f"T{cyl}.{glowica}").strip().splitlines()
            else:
                wiersze.append(_linia(cyl, glowica, ms=ms))
    wiersze.append(_mapa(martwe))
    znalezione = 2880 - 18 * len(martwe)
    wiersze.append(f"Found {znalezione} sectors of 2880 "
                   f"({znalezione * 100 // 2880}%)")
    return "\n".join(wiersze) + "\n"


def uszkodzony_naped() -> str:
    """
    Odczyt z uszkodzonego napedu: do cylindra 18 wszystko dobrze, potem
    doslownie przepisany fragment z sektorami z obcego cylindra.
    """
    wiersze = ["Reading c=0-79:h=0-1 revs=2", "Format ibm.1440"]
    for cyl in range(19):
        for glowica in (0, 1):
            wiersze.append(_linia(cyl, glowica, ms="398.50"))
    wiersze += OBCY_CYLINDER.strip().splitlines()
    return "\n".join(wiersze) + "\n"


def glowica_milczy() -> str:
    """Strona 1 nie czyta niczego na zadnej sciezce, strona 0 czyta."""
    wiersze = ["Reading c=0-79:h=0-1 revs=2", "Format ibm.1440"]
    martwe = set()
    for cyl in range(10):
        wiersze.append(_linia(cyl, 0))
        wiersze.append(_linia(cyl, 1, znalezione=0))
        wiersze.append(f"T{cyl}.1: Giving up: 18 sectors missing")
        martwe.add((cyl, 1))
    return "\n".join(wiersze) + "\n"


# Zapis obrazu z Jazwca na naped Panasonic - format linii doslownie.
# gw nie wypisuje weryfikacji sciezka po sciezce; potwierdza calosc
# jednym zdaniem na koncu.
_LINIA_ZAPISU = ("T{c}.{h}: Writing Track (Flux: 200.0ms period, "
                 "220.0 ms total, Terminate at index)")


def pelny_zapis(potwierdzenie: bool = True) -> str:
    wiersze = ["Format ibm.1440", "Writing c=0-79:h=0-1"]
    wiersze += [_LINIA_ZAPISU.format(c=c, h=h)
                for c in range(80) for h in (0, 1)]
    if potwierdzenie:
        wiersze.append("All tracks verified")
    return "\n".join(wiersze) + "\n"


def obcy_format(sciezek: int = 12) -> str:
    """
    Dyskietka zapisana w innym formacie niz wybrany - na przyklad amigowa
    czytana jako pecetowa. Kontroler nie znajduje zadnego sektora, choc
    glowica stoi wlasciwie i strumien jest czytany normalnie.
    """
    wiersze = ["Reading c=0-79:h=0-1 revs=2", "Format ibm.1440"]
    for numer in range(sciezek):
        cyl, glowica = divmod(numer, 2)
        wiersze.append(_linia(cyl, glowica, znalezione=0))
        wiersze.append(f"T{cyl}.{glowica}: Giving up: 18 sectors missing")
    return "\n".join(wiersze) + "\n"


def naped_stoi(sciezek: int = 10) -> str:
    """
    Glowica stoi nieruchomo na cylindrze 40 od poczatku odczytu.

    Zadna sciezka nie daje sektorow - tak samo jak przy obcym formacie -
    ale naglowki zdradzaja, ze sektory pochodza z cylindra 40. Rozpoznanie
    musi wskazac naped, a nie format dyskietki.

    Cylinder zablokowania celowo lezy poza czytanymi sciezkami: gdyby
    glowica stala na cylindrze 1, sciezka cylindra 1 znalazlaby swoje
    wlasne sektory i odczytala sie poprawnie.
    """
    wiersze = ["Reading c=0-79:h=0-1 revs=2", "Format ibm.1440"]
    for numer in range(sciezek):
        cyl, glowica = divmod(numer, 2)
        wiersze.append(_linia(cyl, glowica, znalezione=0))
        for sektor in (1, 4, 9):
            wiersze.append(f"T{cyl}.{glowica}: Ignoring unexpected sector "
                           f"C:40 H:{glowica} R:{sektor} N:2")
        wiersze.append(f"T{cyl}.{glowica}: Giving up: 18 sectors missing")
    return "\n".join(wiersze) + "\n"


# Odczyt dyskietki amigowej na napedzie Panasonic - naglowek i linie sciezek
# doslownie. AmigaDOS ma 11 sektorow na sciezke i gw czyta go z liczba
# obrotow 1.1 zamiast 2, wiec czas odczytu jest zupelnie inny niz przy IBM.
def odczyt_amigi(sciezek: int = 20) -> str:
    wiersze = ["Reading c=0-79:h=0-1 revs=1.1", "Format amiga.amigados"]
    for numer in range(sciezek):
        cyl, glowica = divmod(numer, 2)
        wiersze.append(
            f"T{cyl}.{glowica}: AmigaDOS (11/11 sectors) from Raw Flux "
            f"(4{4000 + numer * 37} flux in 219.93ms)")
    return "\n".join(wiersze) + "\n"
