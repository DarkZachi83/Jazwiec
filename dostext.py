"""
dostext.py - tlumaczenie plikow tekstowych miedzy swiatem DOS a wspolczesnym.

Czesc projektu "RetroZachar FFD Disk Maker".

Po co to jest
    Plik autoexec.bat z ramkami rysowanymi znakami polgraficznymi to w DOS
    ciag bajtow w stronie kodowej 437. Wspolczesny edytor zapisuje tekst
    w UTF-8, wiec bez tlumaczenia w obie strony ramka rozsypuje sie przy
    pierwszym zapisie. Ten modul zdejmuje ten problem: bajty DOS-owe zamienia
    na znaki Unicode do edycji i z powrotem przy zapisie na dyskietke.

Dlaczego to bezpieczne
    Strony kodowe 437, 850 i 852 przypisuja kazdemu z 256 bajtow inny znak
    Unicode. Zamiana jest wiec wzajemnie jednoznaczna: bajty odczytane
    z dyskietki, zamienione na tekst i z powrotem, daja dokladnie ten sam
    ciag. Sprawdzane w testach dla calego zakresu.

Co jeszcze rozni te swiaty
    Konce wierszy - DOS uzywa pary CR LF, systemy uniksowe samego LF.
    Znacznik konca pliku - starsze programy DOS koncza plik tekstowy bajtem
    0x1A (Ctrl+Z). Modul zapamietuje, czy byl, i odtwarza go przy zapisie.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "CODEPAGES",
    "DEFAULT_CODEPAGE",
    "DosText",
    "load",
    "save",
    "unmappable",
    "looks_binary",
    "graphics_map",
    "IBM_GRAPHICS",
    "char_for_code",
]

# Strony kodowe DOS wraz z opisem. Wszystkie sa wzajemnie jednoznaczne
# na calym zakresie 0-255, wiec konwersja tam i z powrotem niczego nie gubi.
CODEPAGES: dict[str, str] = {
    "cp437": "CP437 - DOS US, pelny zestaw znakow polgraficznych",
    "cp852": "CP852 - Europa Srodkowa, polskie znaki diakrytyczne",
    "cp850": "CP850 - Europa Zachodnia",
}

DEFAULT_CODEPAGE = "cp437"

EOF_MARKER = 0x1A          # Ctrl+Z, historyczny znacznik konca pliku

# Dosowe symbole ozdobne z zakresu 1-31. Karta graficzna PC wyswietlala te
# bajty jako usmiechy, karciane kolory i strzalki - stad znane wpisywanie
# ich przez Alt+1, Alt+3 i tak dalej. Pythonowe kodeki odwzorowuja je na
# znaki sterujace, wiec bez tej tablicy bylyby w edytorze niewidoczne.
IBM_GRAPHICS: dict[int, str] = {
    1: "\u263A", 2: "\u263B", 3: "\u2665", 4: "\u2666", 5: "\u2663",
    6: "\u2660", 7: "\u2022", 8: "\u25D8", 11: "\u2642", 12: "\u2640",
    14: "\u266B", 15: "\u263C", 16: "\u25BA", 17: "\u25C4", 18: "\u2195",
    19: "\u203C", 20: "\u00B6", 21: "\u00A7", 22: "\u25AC", 23: "\u21A8",
    24: "\u2191", 25: "\u2193", 26: "\u2192", 27: "\u2190", 28: "\u221F",
    29: "\u2194", 30: "\u25B2", 31: "\u25BC",
}

# Tabulacja oraz konce wierszy zostaja soba - maja w pliku tekstowym
# znaczenie sterujace, nie ozdobne.
_KEEP_CONTROL = {0x00, 0x09, 0x0A, 0x0D}

_graphics_cache: dict[str, dict[int, str]] = {}


def graphics_map(codepage: str) -> dict[int, str]:
    """
    Symbole ozdobne dostepne w danej stronie kodowej.

    Pomijamy te, ktorych znak wystepuje takze w zakresie 32-255 tej samej
    strony - inaczej zapis przestalby byc jednoznaczny. W CP850 dotyczy to
    akapitu i paragrafu, w CP852 samego paragrafu.
    """
    if codepage in _graphics_cache:
        return _graphics_cache[codepage]
    gorne = {bytes([b]).decode(codepage) for b in range(32, 256)}
    mapa = {
        code: glyph for code, glyph in IBM_GRAPHICS.items()
        if code not in _KEEP_CONTROL and glyph not in gorne
    }
    _graphics_cache[codepage] = mapa
    return mapa


@dataclass
class DosText:
    """Zawartosc pliku tekstowego przygotowana do edycji."""

    text: str                       # z pojedynczym LF, bez znacznika konca
    codepage: str = DEFAULT_CODEPAGE
    crlf: bool = True               # czy oryginal mial konce wierszy DOS
    eof_marker: bool = False        # czy oryginal konczyl sie bajtem 0x1A


def load(data: bytes, codepage: str = DEFAULT_CODEPAGE) -> DosText:
    """
    Zamienia bajty z dyskietki na tekst gotowy do edycji.

    Konce wierszy sprowadza do samego LF, zeby pole edycji i zewnetrzne
    edytory zachowywaly sie normalnie. Informacja o tym, jak bylo
    w oryginale, wraca przy zapisie.
    """
    if codepage not in CODEPAGES:
        codepage = DEFAULT_CODEPAGE

    payload = bytes(data)
    eof_marker = payload.endswith(bytes([EOF_MARKER]))
    if eof_marker:
        payload = payload[:-1]

    # Gdy w pliku nie ma ani jednego konca wiersza - bo jest pusty albo
    # zawiera jedna linie - nie ma czego wykrywac. Przyjmujemy wtedy
    # konwencje DOS, bo tam trafi wynik.
    if b"\n" in payload:
        crlf = b"\r\n" in payload
    else:
        crlf = True
    text = payload.decode(codepage)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Symbole ozdobne zamiast niewidocznych znakow sterujacych.
    for code, glyph in graphics_map(codepage).items():
        text = text.replace(chr(code), glyph)
    return DosText(text=text, codepage=codepage, crlf=crlf,
                   eof_marker=eof_marker)


def save(document: DosText) -> bytes:
    """
    Zamienia tekst z powrotem na bajty do zapisania na dyskietce.

    Znaki, ktorych wybrana strona kodowa nie zna, zastepuje pytajnikiem -
    warto wczesniej wywolac unmappable() i pokazac uzytkownikowi, co
    przepadnie.
    """
    text = document.text.replace("\r\n", "\n").replace("\r", "\n")
    if document.crlf:
        text = text.replace("\n", "\r\n")
    # Symbole ozdobne wracaja na swoje bajty, zanim reszta pojdzie
    # przez zwykly kodek.
    for code, glyph in graphics_map(document.codepage).items():
        text = text.replace(glyph, chr(code))
    payload = text.encode(document.codepage, errors="replace")
    if document.eof_marker:
        payload += bytes([EOF_MARKER])
    return payload


def unmappable(text: str, codepage: str) -> list[str]:
    """
    Zwraca znaki, ktorych wybrana strona kodowa nie potrafi zapisac.

    Typowy przypadek: ktos wklei do pliku polskie znaki, majac wybrane
    CP437, ktory ich nie ma. Lepiej powiedziec o tym przed zapisem niz
    zostawic na dyskietce pytajniki.
    """
    ozdobne = set(graphics_map(codepage).values())
    braki: list[str] = []
    seen: set[str] = set()
    for char in text:
        if char in seen or char in "\r\n" or char in ozdobne:
            continue
        seen.add(char)
        try:
            char.encode(codepage)
        except UnicodeEncodeError:
            braki.append(char)
    return braki


def looks_binary(data: bytes, sample: int = 4096) -> bool:
    """
    Zgrubna ocena, czy plik jest tekstowy.

    Bajt zerowy w tresci praktycznie nie zdarza sie w plikach tekstowych
    DOS, a jest normalny w programach. Drugim sygnalem jest duzy udzial
    bajtow sterujacych innych niz tabulacja i konce wierszy.
    """
    chunk = bytes(data[:sample])
    if not chunk:
        return False
    if b"\x00" in chunk:
        return True
    dozwolone = {0x09, 0x0A, 0x0D, EOF_MARKER}
    sterujace = sum(1 for b in chunk if b < 0x20 and b not in dozwolone)
    return sterujace > len(chunk) // 50


def char_for_code(code: int, codepage: str = DEFAULT_CODEPAGE) -> str | None:
    """
    Znak odpowiadajacy dosowemu kodowi, jak przy wpisywaniu Alt+186.

    Zwraca None dla kodow, ktorych nie da sie wstawic do tekstu: zera,
    tabulacji i koncow wierszy oraz tych symboli ozdobnych, ktore w danej
    stronie kodowej nie sa jednoznaczne.
    """
    if not 0 <= code <= 255:
        return None
    if code in _KEEP_CONTROL:
        return None
    if code < 32:
        return graphics_map(codepage).get(code)
    return bytes([code]).decode(codepage)
