"""
diskset.py - dzielenie programu na komplet dyskietek wraz z instalatorem.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Do czego to sluzy
    Program wiekszy niz dyskietka trzeba jakos przeniesc na maszyne z DOS-em.
    Modul rozklada drzewo katalogow na kolejne nosniki, dzieli pliki wieksze
    od dyskietki na czesci i dopisuje na pierwszym nosniku instalator, ktory
    sklada wszystko z powrotem na dysku twardym.

Dlaczego wsad, a nie program
    Na maszynie docelowej nie mozemy niczego zakladac. Instalator uzywa
    wylacznie polecen wbudowanych w COMMAND.COM: MD, COPY, DEL, ECHO,
    PAUSE, IF EXIST i GOTO. Dziala wiec na czystym DOS-ie 3.3, bez
    archiwizatorow i bez zadnych narzedzi zewnetrznych.

Pulapka, ktora wyznaczyla ksztalt instalatora
    COMMAND.COM czyta plik wsadowy przyrostowo: po kazdej linii wraca na
    nosnik po nastepna. Wsad lezacy na dyskietce, ktory prosi o jej zmiane,
    przy kolejnej linii czytalby juz z innego nosnika i sypalby sie w sposob
    trudny do zdiagnozowania. Dlatego na dyskietce pierwszej jest tylko maly
    INSTALL.BAT: zaklada katalog na dysku twardym, kopiuje tam wlasciwy
    SETUP.BAT i oddaje mu sterowanie bez CALL. Od tej chwili wykonywany wsad
    lezy na dysku twardym i zmiany dyskietek mu nie szkodza.

Ograniczenia DOS-a uwzglednione w planowaniu
    * katalog glowny dyskietki miesci 224 wpisy przy 1,44 MB i 112 przy
      720 KB - przy wielu drobnych plikach to one koncza sie pierwsze,
    * miejsce liczy sie w klastrach, wiec kazdy plik marnuje srednio pol
      klastra; przy 720 KB klaster ma 1024 bajty,
    * sciezka w DOS-ie ma najwyzej 64 znaki,
    * linia wsadu okolo 127 znakow.

Nazwy na dyskietkach
    Pliki trafiaja do katalogu glownego dyskietki pod wygenerowanymi nazwami
    F0001.000, F0002.000 i dalej. Dzieki temu nie ma kolizji nazw 8.3 miedzy
    plikami z roznych katalogow ani klopotu z dlugoscia sciezki na samej
    dyskietce. Przypisanie tych nazw do plikow docelowych jest w SPIS.TXT na
    kazdym nosniku - na wypadek, gdyby trzeba bylo cos odzyskac recznie.

Dyskietka startowa
    Modul nie potrafi utworzyc dyskietki startowej i nie probuje. Wymaga to
    plikow systemowych, ktorych nie mamy prawa rozprowadzac, oraz sektora
    rozruchowego DOS-a. Zamiast tego przyjmuje gotowy obraz startowy jako
    podstawe pierwszej dyskietki i dopisuje instalator w wolnym miejscu.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass, field

import fat12

__all__ = [
    "PaczkaError",
    "Plik",
    "Czesc",
    "Dyskietka",
    "Plan",
    "DOMYSLNY_KATALOG",
    "popraw_nazwe",
    "sprawdz_nazwe",
    "sprawdz_dysk",
    "zaplanuj",
    "zbuduj",
    "opis_planu",
]

DOMYSLNY_KATALOG = "ZGRYW"
DOMYSLNY_DYSK = "C:"

# Litery sprawdzane przy wypisywaniu dostepnych dyskow. W DOS-ie
# IF EXIST X:\NUL mowi, czy dysk o tej literze w ogole istnieje.
LITERY_DYSKOW = "CDEFGH"

# Wpisy i miejsce rezerwowane na pierwszej dyskietce na instalator:
# INSTALL.BAT, SETUP.BAT, SPIS.TXT oraz znacznik nosnika.
# Wpisy zajete na kazdej dyskietce niezaleznie od zawartosci: etykieta
# wolumenu, znacznik nosnika i SPIS.TXT.
WPISY_STALE = 3
# Dodatkowo na pierwszej: INSTALL.BAT i SETUP.BAT.
WPISY_INSTALATORA = WPISY_STALE + 2

# SPIS.TXT rosnie z liczba pozycji na dyskietce, a liczbe te znamy dopiero
# po ulozeniu planu. Rezerwujemy wiec z gory tyle, ile zajalby przy komplecie
# wpisow - okolo 48 bajtow na wiersz.
BAJTY_WIERSZA_SPISU = 48
NAGLOWEK_SPISU = 400

# SETUP.BAT to trzy wiersze na plik plus obsluga zmian dyskietek.
BAJTY_WSADU_NA_PLIK = 220
NAGLOWEK_WSADU = 8 * 1024

WZOR_ZNACZNIKA = "DYSK{numer:02d}.ID"

# Wsad instalatora laduje w katalogu docelowym, obok plikow programu, i jest
# stamtad wykonywany. Gdyby program mial plik o tej samej nazwie - a SETUP.BAT
# ma polowa gier z epoki - skopiowanie go nadpisaloby wsad w trakcie
# dzialania. COMMAND.COM czyta wsad przyrostowo, wiec od tej chwili czytalby
# cudzy plik. Dlatego nazwa jest nietypowa, a przy kolizji zmieniana.
NAZWA_WSADU = "JAZWIEC.BAT"

# Tymczasowe czesci plikow podzielonych tez trafiaja do katalogu docelowego.
PREFIKS_CZESCI = "F"

MAX_SCIEZKA_DOS = 64

# Nazwa katalogu na maszynie docelowej. DOS przyjmie najwyzej osiem znakow
# bez kropki - nazwy w rodzaju "Pool of Radiance (1988)(SSI) [RPG]" po
# mechanicznym skroceniu daja POOLOFRA.)_R, czyli bezsens z rozszerzeniem.
# Dlatego nazwe podaje uzytkownik, a my ja tylko sprawdzamy.
ZNAKI_NAZWY = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"


def popraw_nazwe(nazwa: str) -> str:
    """
    Sprowadza propozycje nazwy katalogu do postaci akceptowanej przez DOS.

    Sluzy do podpowiadania, nie do cichego naprawiania tego, co wpisal
    uzytkownik - sprawdzaniem zajmuje sie sprawdz_nazwe().
    """
    czyste = "".join(z for z in nazwa.upper() if z in ZNAKI_NAZWY)
    return czyste[:8] or DOMYSLNY_KATALOG


def sprawdz_nazwe(nazwa: str) -> str:
    """Zglasza blad, gdy nazwa nie nadaje sie na katalog w DOS-ie."""
    if not nazwa:
        raise PaczkaError("Podaj nazwe katalogu na maszynie docelowej.")
    if len(nazwa) > 8:
        raise PaczkaError(
            f"Nazwa katalogu moze miec najwyzej 8 znakow, a ma {len(nazwa)}.")
    zle = sorted({z for z in nazwa.upper() if z not in ZNAKI_NAZWY})
    if zle:
        raise PaczkaError(
            "W nazwie katalogu nie moga wystapic te znaki: "
            + " ".join(zle))
    return nazwa.upper()
MAX_LINIA_WSADU = 120


class PaczkaError(Exception):
    """Blad planowania albo budowy kompletu dyskietek."""


# --------------------------------------------------------------------------
#  Struktury planu
# --------------------------------------------------------------------------

@dataclass
class Plik:
    """Jeden plik zrodlowy wraz z jego miejscem na maszynie docelowej."""

    zrodlo: str                 # sciezka na komputerze
    katalog: str                # katalog docelowy, "" dla glownego
    nazwa: str                  # nazwa docelowa w postaci 8.3
    rozmiar: int
    numer: int = 0              # numer porzadkowy, daje nazwe na dyskietce
    prefiks: str = PREFIKS_CZESCI

    @property
    def cel(self) -> str:
        return f"{self.katalog}\\{self.nazwa}" if self.katalog else self.nazwa


@dataclass
class Czesc:
    """Fragment pliku lezacy na jednej dyskietce."""

    plik: Plik
    indeks: int                 # ktora to czesc, liczone od zera
    offset: int
    rozmiar: int

    @property
    def caly_plik(self) -> bool:
        return self.indeks == 0 and self.rozmiar == self.plik.rozmiar

    @property
    def nazwa_na_dyskietce(self) -> str:
        return f"{self.plik.prefiks}{self.plik.numer:04d}.{self.indeks:03d}"


@dataclass
class Dyskietka:
    """Zawartosc jednej dyskietki w planie."""

    numer: int
    czesci: list[Czesc] = field(default_factory=list)
    zajete: int = 0
    wpisy: int = 0

    @property
    def znacznik(self) -> str:
        return WZOR_ZNACZNIKA.format(numer=self.numer)


@dataclass
class Plan:
    """Kompletny plan rozlozenia programu na dyskietki."""

    dyskietki: list[Dyskietka]
    pliki: list[Plik]
    format_klucz: str
    katalog_docelowy: str
    katalogi: list[str] = field(default_factory=list)
    dysk_docelowy: str = DOMYSLNY_DYSK
    wsad: str = NAZWA_WSADU
    podzielone: list[Plik] = field(default_factory=list)
    ostrzezenia: list[str] = field(default_factory=list)
    rozmiar_zrodla: int = 0

    @property
    def liczba_dyskietek(self) -> int:
        return len(self.dyskietki)

    @property
    def format(self) -> fat12.FloppyFormat:
        return fat12.FLOPPY_FORMATS[self.format_klucz]


# --------------------------------------------------------------------------
#  Skanowanie zrodla
# --------------------------------------------------------------------------

def _zbierz(katalog: str) -> tuple[list[Plik], list[str], list[str]]:
    """
    Przechodzi drzewo i przypisuje kazdemu plikowi miejsce docelowe
    w postaci nazw 8.3, pilnujac unikalnosci w obrebie katalogu.

    Zwraca takze pelna liste katalogow - wszystkich napotkanych, a nie
    tylko tych, w ktorych lezy jakis plik. Ma to dwa powody. Po pierwsze
    MD w DOS-ie nie tworzy sciezek wielopoziomowych, wiec katalog posredni
    bez wlasnych plikow musialby powstac osobno. Po drugie katalogi puste
    w zrodle tez maja znaczenie - niejedna gra wymaga istnienia katalogu
    na zapisy stanu i bez niego przerywa dzialanie.
    """
    pliki: list[Plik] = []
    katalogi: list[str] = []
    ostrzezenia: list[str] = []
    mapa: dict[str, str] = {os.path.abspath(katalog): ""}

    for biezacy, podkatalogi, nazwy in os.walk(katalog, followlinks=False):
        podkatalogi.sort()
        nazwy.sort()
        cel_katalogu = mapa.get(os.path.abspath(biezacy))
        if cel_katalogu is None:
            continue

        zajete: set[str] = set()
        for nazwa in podkatalogi:
            krotka = fat12.to_short_name(nazwa, zajete)
            zajete.add(krotka.upper())
            sciezka = f"{cel_katalogu}\\{krotka}" if cel_katalogu else krotka
            mapa[os.path.abspath(os.path.join(biezacy, nazwa))] = sciezka
            katalogi.append(sciezka)
            if krotka.upper() != nazwa.upper():
                ostrzezenia.append(f"{nazwa} -> {krotka}")

        for nazwa in nazwy:
            pelna = os.path.join(biezacy, nazwa)
            if os.path.islink(pelna) or not os.path.isfile(pelna):
                continue
            krotka = fat12.to_short_name(nazwa, zajete)
            zajete.add(krotka.upper())
            if krotka.upper() != nazwa.upper():
                ostrzezenia.append(f"{nazwa} -> {krotka}")
            try:
                rozmiar = os.path.getsize(pelna)
            except OSError as exc:
                ostrzezenia.append(f"{nazwa}: {exc}")
                continue
            pliki.append(Plik(zrodlo=pelna, katalog=cel_katalogu,
                              nazwa=krotka, rozmiar=rozmiar))

    for numer, plik in enumerate(sorted(pliki, key=lambda p: p.cel), start=1):
        plik.numer = numer
    # Kolejnosc od najplytszych: MD w DOS-ie nie tworzy sciezek
    # wielopoziomowych, wiec katalog nadrzedny musi powstac wczesniej.
    katalogi.sort(key=lambda s: (s.count("\\"), s))
    return pliki, katalogi, ostrzezenia


def _sprawdz_sciezki(pliki: list[Plik], katalog_docelowy: str) -> list[str]:
    """Wylapuje sciezki, ktore po zlozeniu przekrocza limit DOS-a."""
    uwagi = []
    przedrostek = len(f"C:\\{katalog_docelowy}\\")
    for plik in pliki:
        if przedrostek + len(plik.cel) > MAX_SCIEZKA_DOS:
            uwagi.append(f"{plik.cel}: sciezka dluzsza niz "
                         f"{MAX_SCIEZKA_DOS} znakow")
    return uwagi


# --------------------------------------------------------------------------
#  Planowanie
# --------------------------------------------------------------------------

def _wolna_nazwa(proponowana: str, zajete: set[str]) -> str:
    """Zwraca nazwe niekolidujaca z plikami programu."""
    if proponowana.upper() not in zajete:
        return proponowana
    rdzen, _, rozszerzenie = proponowana.partition(".")
    for numer in range(1, 100):
        przyrostek = str(numer)
        kandydat = f"{rdzen[:8 - len(przyrostek)]}{przyrostek}.{rozszerzenie}"
        if kandydat.upper() not in zajete:
            return kandydat
    raise PaczkaError("Nie udalo sie dobrac nazwy dla instalatora.")


def _wolny_prefiks(zajete: set[str]) -> str:
    """
    Dobiera litere rozpoczynajaca nazwy czesci plikow podzielonych.

    Czesci maja postac F0001.000 i leza przejsciowo w katalogu docelowym.
    Kolizja jest malo prawdopodobna, ale kosztuje tyle samo co sprawdzenie.
    """
    import re
    for litera in PREFIKS_CZESCI + "GHJKLMNPQRSTUVWXYZ":
        wzor = re.compile(rf"^{litera}\d{{4}}\.\d{{3}}$")
        if not any(wzor.match(n) for n in zajete):
            return litera
    raise PaczkaError("Nie udalo sie dobrac przedrostka nazw czesci.")


def _zaokraglij(rozmiar: int, klaster: int) -> int:
    """Miejsce faktycznie zajete przez plik, z zaokragleniem do klastra."""
    return max(1, (rozmiar + klaster - 1) // klaster) * klaster


def _wolne_miejsce(fmt: fat12.FloppyFormat) -> int:
    """Ile bajtow miesci pusta dyskietka danego formatu."""
    pierwszy = fat12.data_start_sector(fmt)
    klastry = (fmt.total_sectors - pierwszy) // fmt.sectors_per_cluster
    return klastry * fmt.sectors_per_cluster * fmt.bytes_per_sector


def _zajete_w_obrazie(sciezka: str, fmt: fat12.FloppyFormat) -> int:
    """Ile miejsca zajmuje juz obraz bazowy pierwszej dyskietki."""
    obraz = fat12.Fat12Image(sciezka, read_only=True)
    try:
        if obraz.total_sectors * obraz.bytes_per_sector != fmt.size_bytes:
            raise PaczkaError(
                "Obraz bazowy ma inny format niz wybrany dla kompletu.")
        return obraz.total_bytes - obraz.free_bytes
    finally:
        obraz.close()


def sprawdz_dysk(litera: str) -> str:
    """Sprowadza podana litere dysku do postaci "C:" i odrzuca bezsensy."""
    czysta = litera.strip().upper().rstrip(":")
    if len(czysta) != 1 or not czysta.isalpha():
        raise PaczkaError(
            "Dysk docelowy to pojedyncza litera, na przyklad C albo D.")
    return czysta + ":"


def zaplanuj(katalog: str, format_klucz: str = "1440",
             katalog_docelowy: str = DOMYSLNY_KATALOG,
             obraz_bazowy: str | None = None,
             dysk_docelowy: str = DOMYSLNY_DYSK) -> Plan:
    """
    Uklada program na dyskietkach, nie zapisujac jeszcze niczego.

    Najpierw wlasne nosniki dostaja pliki wieksze od dyskietki, pociete na
    czesci. Reszta idzie metoda pierwszego pasujacego malejaco: najwieksze
    pliki dostaja miejsce najpierw, drobne dopelniaja luki. Daje to mniej
    dyskietek niz ukladanie po kolei, a pozostaje zrozumiale.
    """
    if format_klucz not in fat12.FLOPPY_FORMATS:
        raise PaczkaError(f"Nieznany format dyskietki: {format_klucz}")
    fmt = fat12.FLOPPY_FORMATS[format_klucz]
    if not os.path.isdir(katalog):
        raise PaczkaError(f"{katalog} nie jest katalogiem.")
    katalog_docelowy = sprawdz_nazwe(katalog_docelowy.strip())
    dysk_docelowy = sprawdz_dysk(dysk_docelowy)

    pliki, katalogi, ostrzezenia = _zbierz(katalog)
    if not pliki:
        raise PaczkaError("W tym katalogu nie ma plikow do nagrania.")
    ostrzezenia += _sprawdz_sciezki(pliki, katalog_docelowy)

    # Gdy wszystko lezy w jednym podkatalogu, uzytkownik prawdopodobnie
    # wskazal katalog o poziom za wysoko - i caly program wyladuje
    # w zagniezdzonym katalogu o skroconej, bezsensownej nazwie.
    pierwsze = {p.katalog.split("\\")[0] for p in pliki}
    if len(pierwsze) == 1 and pierwsze != {""}:
        jedyny = pierwsze.pop()
        ostrzezenia.insert(0, (
            f"Wszystkie pliki leza w podkatalogu {jedyny} - byc moze "
            f"wskazano katalog o poziom za wysoko."))

    # Nazwy, ktore instalator zaklada w katalogu docelowym, nie moga
    # pokrywac sie z niczym, co nalezy do samego programu.
    w_glownym = {p.nazwa.upper() for p in pliki if not p.katalog}
    wsad = _wolna_nazwa(NAZWA_WSADU, w_glownym)
    if wsad != NAZWA_WSADU:
        ostrzezenia.insert(0, (
            f"Program zawiera wlasny {NAZWA_WSADU} - instalator nazwano "
            f"{wsad}, zeby go nie nadpisac."))

    prefiks = _wolny_prefiks(w_glownym)
    if prefiks != PREFIKS_CZESCI:
        ostrzezenia.insert(0, (
            f"Nazwy plikow programu koliduja z nazwami czesci - "
            f"uzyto przedrostka {prefiks}."))
    for plik in pliki:
        plik.prefiks = prefiks

    klaster = fmt.sectors_per_cluster * fmt.bytes_per_sector
    pojemnosc = _wolne_miejsce(fmt)

    # Na kazdej dyskietce miejsce zabiera znacznik nosnika i SPIS.TXT.
    # Rozmiaru spisu nie znamy przed ulozeniem planu, wiec liczymy go dla
    # najgorszego przypadku - dyskietki wypelnionej wpisami po brzegi.
    limit_wpisow = fmt.root_entries - WPISY_STALE
    rezerwa_spisu = _zaokraglij(
        NAGLOWEK_SPISU + limit_wpisow * BAJTY_WIERSZA_SPISU, klaster)
    na_dyskietke = pojemnosc - klaster - rezerwa_spisu

    rezerwa = NAGLOWEK_WSADU + len(pliki) * BAJTY_WSADU_NA_PLIK
    if obraz_bazowy:
        rezerwa = max(rezerwa, _zajete_w_obrazie(obraz_bazowy, fmt) + rezerwa)

    dyskietki: list[Dyskietka] = []

    def nowa() -> Dyskietka:
        dysk = Dyskietka(numer=len(dyskietki) + 1)
        if dysk.numer == 1:
            dysk.zajete = _zaokraglij(rezerwa, klaster)
            dysk.wpisy = WPISY_INSTALATORA
        dyskietki.append(dysk)
        return dysk

    nowa()
    if dyskietki[0].zajete >= na_dyskietke:
        raise PaczkaError(
            "Obraz bazowy nie zostawia miejsca na instalator.")

    # --- pliki wieksze niz dyskietka: pelne czesci zajmuja wlasne nosniki --
    podzielone: list[Plik] = []
    reszty: list[tuple[Plik, int, int]] = []
    zwykle: list[Plik] = []

    for plik in sorted(pliki, key=lambda p: p.rozmiar, reverse=True):
        if plik.rozmiar <= na_dyskietke:
            zwykle.append(plik)
            continue
        podzielone.append(plik)
        offset, indeks = 0, 0
        while plik.rozmiar - offset > na_dyskietke:
            dysk = dyskietki[-1]
            wolne = na_dyskietke - dysk.zajete
            if wolne < klaster or dysk.wpisy >= limit_wpisow:
                dysk = nowa()
                wolne = na_dyskietke - dysk.zajete
            fragment = min(wolne, plik.rozmiar - offset)
            dysk.czesci.append(Czesc(plik, indeks, offset, fragment))
            dysk.zajete += _zaokraglij(fragment, klaster)
            dysk.wpisy += 1
            offset += fragment
            indeks += 1
        reszty.append((plik, indeks, offset))

    # --- reszta metoda pierwszego pasujacego malejaco ---------------------
    do_ulozenia = [(p, 0, 0, p.rozmiar) for p in zwykle]
    do_ulozenia += [(p, i, o, p.rozmiar - o) for p, i, o in reszty]
    do_ulozenia.sort(key=lambda t: t[3], reverse=True)

    for plik, indeks, offset, rozmiar in do_ulozenia:
        miejsce = _zaokraglij(rozmiar, klaster)
        cel = None
        for dysk in dyskietki:
            if (dysk.zajete + miejsce <= na_dyskietke
                    and dysk.wpisy < limit_wpisow):
                cel = dysk
                break
        if cel is None:
            cel = nowa()
            if cel.zajete + miejsce > na_dyskietke:
                raise PaczkaError(
                    f"Plik {plik.cel} ({rozmiar} B) nie miesci sie "
                    f"na pustej dyskietce tego formatu.")
        cel.czesci.append(Czesc(plik, indeks, offset, rozmiar))
        cel.zajete += miejsce
        cel.wpisy += 1

    for dysk in dyskietki:
        dysk.czesci.sort(key=lambda c: (c.plik.numer, c.indeks))

    return Plan(
        dyskietki=dyskietki,
        pliki=pliki,
        katalogi=katalogi,
        dysk_docelowy=dysk_docelowy,
        wsad=wsad,
        format_klucz=format_klucz,
        katalog_docelowy=katalog_docelowy,
        podzielone=podzielone,
        ostrzezenia=ostrzezenia,
        rozmiar_zrodla=sum(p.rozmiar for p in pliki),
    )


# --------------------------------------------------------------------------
#  Instalator
# --------------------------------------------------------------------------

def _wsad(linie: list[str]) -> bytes:
    """
    Sklada plik wsadowy: konce wierszy DOS, czysty ASCII.

    Strony kodowej maszyny docelowej nie znamy, wiec zadnych znakow
    diakrytycznych ani polgraficznych - tylko to, co wyglada tak samo
    wszedzie.
    """
    zbyt_dlugie = [l for l in linie if len(l) > MAX_LINIA_WSADU]
    if zbyt_dlugie:
        raise PaczkaError(
            "Linia wsadu przekracza limit DOS-a: " + zbyt_dlugie[0][:60])
    return ("\r\n".join(linie) + "\r\n").encode("ascii", errors="replace")


def _install_bat(plan: Plan) -> bytes:
    """
    Wsad startowy z pierwszej dyskietki.

    Nie uzywa zmiennych srodowiskowych. Srodowisko DOS-a ma domyslnie
    256 bajtow i SET potrafi sie w nim nie zmiescic. Nierozwiniete %ZMIENNA%
    zamienia sie wtedy w pusty ciag, przez co COPY laduje wsad na dyskietke
    zamiast na dysk twardy - a wtedy COMMAND.COM przy pierwszej zmianie
    nosnika traci plik wsadowy i prosi o wlozenie dyskietki z nim.

    Zamiast tego kazdy wariant wywolania ma wlasna galaz z literami dyskow
    wpisanymi na stale, a wartosci ida dalej jako parametry wsadu.

    Wybor dysku
        Wsad DOS-a nie potrafi wczytac tekstu od uzytkownika - SET /P pojawil
        sie dopiero w cmd z Windows 2000, a CHOICE.COM czyta pojedynczy
        klawisz i nie wolno nam go rozprowadzac. Dlatego dysk wskazuje sie
        przy nagrywaniu kompletu albo parametrem wywolania, a instalator
        pokazuje cel, wypisuje dostepne dyski i czeka na potwierdzenie.
    """
    katalog = plan.katalog_docelowy
    wsad = plan.wsad
    rdzen = wsad.partition(".")[0]
    domyslny = plan.dysk_docelowy

    linie = [
        "@ECHO OFF",
        "ECHO.",
        "ECHO   RetroZachar - Jazwiec",
        f"ECHO   Komplet {plan.liczba_dyskietek} dyskietek",
        "ECHO.",
        'IF "%1"=="" GOTO BEZ',
        'IF "%2"=="" GOTO TYLKO',
        "GOTO OBA",
    ]

    def galaz(etykieta: str, dysk: str, zrodlo: str,
              pytaj: bool) -> list[str]:
        krok = [f":{etykieta}"]
        if pytaj:
            # Tylko przy domyslnym wyborze warto pokazac, co jeszcze jest
            # pod reka. Kto podal dysk parametrem, juz zdecydowal.
            krok += [
                f"ECHO   Program zostanie zainstalowany w:  "
                f"{dysk}\\{katalog}",
                "ECHO.",
                "ECHO   Dostepne dyski:",
            ]
            for litera in LITERY_DYSKOW:
                krok.append(f"IF EXIST {litera}:\\NUL ECHO       {litera}:")
            krok += [
                "ECHO.",
                "ECHO   Aby wybrac inny dysk, nacisnij Ctrl+C i uruchom:",
                "ECHO       INSTALL D:",
                "ECHO.",
                f"ECHO   Aby instalowac w {dysk}\\{katalog}, "
                f"nacisnij dowolny klawisz.",
            ]
        else:
            krok += [
                f"ECHO   Cel: {dysk}\\{katalog}   Zrodlo: {zrodlo}",
                "ECHO   Nacisnij klawisz, aby rozpoczac, "
                "albo Ctrl+C aby przerwac.",
            ]
        krok += [
            "PAUSE >NUL",
            f"IF NOT EXIST {dysk}\\NUL GOTO ZLYDYSK",
            f"IF NOT EXIST {dysk}\\{katalog}\\NUL MD {dysk}\\{katalog}",
            f"COPY {zrodlo}\\{wsad} {dysk}\\{katalog} >NUL",
            f"IF NOT EXIST {dysk}\\{katalog}\\{wsad} GOTO BLAD",
            dysk,
            f"CD \\{katalog}",
            f"{rdzen} {dysk} {zrodlo}",
        ]
        return krok

    linie += galaz("BEZ", domyslny, "A:", pytaj=True)
    linie += galaz("TYLKO", "%1", "A:", pytaj=False)
    linie += galaz("OBA", "%1", "%2", pytaj=False)
    linie += [
        ":ZLYDYSK",
        "ECHO.",
        "ECHO   BLAD: wskazany dysk nie istnieje.",
        "ECHO   Uruchom INSTALL z litera istniejacego dysku, na przyklad:",
        "ECHO       INSTALL D:",
        "GOTO KONIEC",
        ":BLAD",
        "ECHO.",
        "ECHO   BLAD: nie udalo sie skopiowac instalatora na dysk.",
        "ECHO   Sprawdz, czy dysk ma wolne miejsce i nie jest zabezpieczony.",
        ":KONIEC",
    ]
    return _wsad(linie)


def _setup_bat(plan: Plan) -> bytes:
    """
    Wlasciwy instalator, wykonywany juz z dysku twardego.

    Dysk docelowy i naped zrodlowy dostaje jako parametry %1 i %2, nie przez
    srodowisko. Uruchomiony bez nich odmawia dzialania zamiast zgadywac -
    zgadywanie skonczyloby sie kopiowaniem w przypadkowe miejsce.
    """
    katalog = plan.katalog_docelowy
    baza = f"%1\\{katalog}"
    linie = [
        "@ECHO OFF",
        'IF NOT "%1"=="" GOTO START',
        "ECHO.",
        "ECHO   Ten plik uruchamia sie sam podczas instalacji.",
        "ECHO   Wloz dyskietke 1 i wydaj polecenie:  INSTALL",
        "ECHO.",
        "GOTO KONIEC",
        ":START",
        "ECHO.",
    ]

    for podkatalog in plan.katalogi:
        linie.append(f"IF NOT EXIST {baza}\\{podkatalog}\\NUL "
                     f"MD {baza}\\{podkatalog}")

    for dysk in plan.dyskietki:
        linie += [
            "ECHO.",
            f"ECHO   --- Dyskietka {dysk.numer} z {plan.liczba_dyskietek} ---",
            f":D{dysk.numer:02d}",
            f"IF EXIST %2\\{dysk.znacznik} GOTO K{dysk.numer:02d}",
            f"ECHO   Wloz dyskietke {dysk.numer} do napedu %2",
            "ECHO   i nacisnij dowolny klawisz.",
            "PAUSE >NUL",
            f"GOTO D{dysk.numer:02d}",
            f":K{dysk.numer:02d}",
        ]
        for czesc in dysk.czesci:
            zrodlo = f"%2\\{czesc.nazwa_na_dyskietce}"
            cel = (f"{baza}\\{czesc.plik.cel}" if czesc.caly_plik
                   else f"{baza}\\{czesc.nazwa_na_dyskietce}")
            linie += [
                f"ECHO   {czesc.plik.cel}",
                f"COPY {zrodlo} {cel} >NUL",
                f"IF NOT EXIST {cel} GOTO BLAD",
            ]

    if plan.podzielone:
        linie += ["ECHO.", "ECHO   Skladanie plikow podzielonych..."]
        for plik in plan.podzielone:
            czesci = sorted(
                (c for d in plan.dyskietki for c in d.czesci
                 if c.plik is plik),
                key=lambda c: c.indeks)

            # Sciezki wzgledne zamiast pelnych. Polecenie sklejajace piec
            # czesci pelnymi sciezkami przekraczalo 120 znakow, czyli wiecej,
            # niz przyjmuje wiersz polecen DOS-a. Katalogiem biezacym jest
            # tu katalog docelowy - ustawia go INSTALL.BAT przed oddaniem
            # sterowania i nic go pozniej nie zmienia.
            cel = plik.cel
            pierwsza = czesci[0].nazwa_na_dyskietce
            linie += [
                f"ECHO   {plik.cel}",
                f"COPY /B {pierwsza} {cel} >NUL",
                f"IF NOT EXIST {cel} GOTO BLAD",
                f"DEL {pierwsza}",
            ]

            # Kazda kolejna czesc doklejana osobno i od razu kasowana.
            # W szczycie potrzeba wtedy miejsca na gotowy plik i jedna
            # czesc, zamiast na plik i wszystkie czesci naraz.
            for czesc in czesci[1:]:
                linie.append(
                    f"COPY /B {cel}+{czesc.nazwa_na_dyskietce} >NUL")
                linie.append(f"DEL {czesc.nazwa_na_dyskietce}")
            linie.append(f"IF NOT EXIST {cel} GOTO BLAD")

    linie += [
        "ECHO.",
        f"ECHO   Gotowe. Program jest w {baza}",
        "ECHO.",
        "GOTO KONIEC",
        ":BLAD",
        "ECHO.",
        "ECHO   BLAD: nie udalo sie skopiowac pliku.",
        "ECHO   Sprawdz wolne miejsce i uruchom instalacje ponownie.",
        "ECHO.",
        ":KONIEC",
    ]
    return _wsad(linie)


def _spis(plan: Plan, dysk: Dyskietka) -> bytes:
    """Czytelne przypisanie nazw z dyskietki do plikow docelowych."""
    linie = [
        "RetroZachar - Jazwiec",
        f"Dyskietka {dysk.numer} z {plan.liczba_dyskietek}",
        f"Katalog docelowy: {plan.katalog_docelowy}",
        "",
        "Na dyskietce        Plik docelowy",
        "-" * 58,
    ]
    for czesc in dysk.czesci:
        opis = czesc.plik.cel
        if not czesc.caly_plik:
            opis += f"  (czesc {czesc.indeks + 1})"
        linie.append(f"{czesc.nazwa_na_dyskietce:<20}{opis}")
    return _wsad(linie)


# --------------------------------------------------------------------------
#  Budowa obrazow
# --------------------------------------------------------------------------

def zbuduj(plan: Plan, katalog_wyjsciowy: str, etykieta: str = "",
           obraz_bazowy: str | None = None, postep=None) -> list[str]:
    """
    Zapisuje komplet obrazow dyskietek i zwraca liste utworzonych plikow.

    postep dostaje (numer, ile, nazwa) i moze zwrocic False, zeby przerwac.
    Obrazy juz utworzone zostaja na dysku - kasowanie ich bez pytania byloby
    gorsze niz zostawienie.
    """
    os.makedirs(katalog_wyjsciowy, exist_ok=True)
    fmt = plan.format
    utworzone: list[str] = []

    setup = _setup_bat(plan)
    install = _install_bat(plan)

    for dysk in plan.dyskietki:
        sciezka = os.path.join(katalog_wyjsciowy, f"DYSK{dysk.numer:02d}.img")
        if postep and not postep(dysk.numer, plan.liczba_dyskietek,
                                 os.path.basename(sciezka)):
            return utworzone

        if dysk.numer == 1 and obraz_bazowy:
            with open(obraz_bazowy, "rb") as zrodlo, \
                    open(sciezka, "wb") as cel:
                cel.write(zrodlo.read())
        else:
            nazwa = (etykieta or plan.katalog_docelowy).strip()[:8]
            fat12.format_image(sciezka, fmt, f"{nazwa} {dysk.numer}",
                               overwrite=True)

        obraz = fat12.Fat12Image(sciezka)
        try:
            obraz.write_file("/" + dysk.znacznik,
                             _wsad([f"Dyskietka {dysk.numer}"]))
            if dysk.numer == 1:
                obraz.write_file("/INSTALL.BAT", install)
                obraz.write_file("/" + plan.wsad, setup)
            obraz.write_file("/SPIS.TXT", _spis(plan, dysk))

            for czesc in dysk.czesci:
                with open(czesc.plik.zrodlo, "rb") as fh:
                    fh.seek(czesc.offset)
                    dane = fh.read(czesc.rozmiar)
                obraz.write_file("/" + czesc.nazwa_na_dyskietce, dane)
        except fat12.Fat12Error as exc:
            raise PaczkaError(f"Dyskietka {dysk.numer}: {exc}") from exc
        finally:
            obraz.close()
        utworzone.append(sciezka)

    return utworzone


# --------------------------------------------------------------------------
#  Opis planu
# --------------------------------------------------------------------------

def opis_planu(plan: Plan) -> str:
    """Plan w postaci czytelnego tekstu, do pokazania przed nagraniem."""
    fmt = plan.format
    pojemnosc = _wolne_miejsce(fmt)
    linie = [
        "RetroZachar - Jazwiec - plan kompletu dyskietek",
        "=" * 62,
        "",
        f"{'Data:':<26}{datetime.datetime.now():%Y-%m-%d %H:%M}",
        f"{'Nosnik:':<26}{fmt.label.strip()}",
        f"{'Plikow:':<26}{len(plan.pliki)}",
        f"{'Razem:':<26}{plan.rozmiar_zrodla} B",
        f"{'Dyskietek:':<26}{plan.liczba_dyskietek}",
        f"{'Katalog docelowy:':<26}{plan.dysk_docelowy}\\{plan.katalog_docelowy}",
        "",
        "-" * 62,
    ]
    for dysk in plan.dyskietki:
        procent = dysk.zajete * 100 // pojemnosc if pojemnosc else 0
        linie.append(
            f"Dyskietka {dysk.numer:>2}: {len(dysk.czesci):>3} plikow, "
            f"{dysk.zajete:>9} B  ({procent}% zapelnienia)"
            + ("   + instalator" if dysk.numer == 1 else ""))
    linie.append("-" * 62)

    if plan.podzielone:
        linie += ["", "Pliki podzielone miedzy dyskietki:"]
        for plik in plan.podzielone:
            ile = sum(1 for d in plan.dyskietki for c in d.czesci
                      if c.plik is plik)
            linie.append(f"  {plik.cel}  ({plik.rozmiar} B, {ile} czesci)")
        najwiekszy = max(p.rozmiar for p in plan.podzielone)
        jedna_czesc = _wolne_miejsce(fmt)
        linie += [
            "",
            "Podczas skladania potrzeba na dysku docelowym okolo",
            f"{najwiekszy + jedna_czesc} B wolnego miejsca - tyle, ile zajmuje",
            "najwiekszy z tych plikow plus jedna czesc. Czesci sa kasowane",
            "na biezaco, zaraz po doklejeniu.",
        ]

    if plan.ostrzezenia:
        linie += ["", "Nazwy skrocone do 8.3 oraz uwagi:"]
        for uwaga in plan.ostrzezenia[:20]:
            linie.append(f"  {uwaga}")
        if len(plan.ostrzezenia) > 20:
            linie.append(f"  ... i {len(plan.ostrzezenia) - 20} wiecej")

    linie += [
        "",
        "Na maszynie docelowej:",
        "  A:",
        "  INSTALL",
        "",
        f"Program wyladuje w {plan.dysk_docelowy}\\{plan.katalog_docelowy}.",
        "Instalator pokaze cel i poczeka na potwierdzenie, a takze wypisze,",
        "ktore dyski sa dostepne. Inny dysk albo naped podaje sie wtedy",
        "jako parametry:",
        "  INSTALL D: B:",
    ]
    return "\n".join(linie)
