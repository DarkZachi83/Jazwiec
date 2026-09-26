"""
styles.py - wyglad programu.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Jedno miejsce na wszystko, co decyduje o tym, jak program sie prezentuje:
nazwa i wersja, paleta barw, dobor czcionki i ramka panelu. Zmiana koloru
albo wersji nie wymaga szukania po calym interfejsie.
"""

from __future__ import annotations

import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from system import _znajdz_ikone

APP_NAME = "RetroZachar - FFD Disk Maker - Jazwiec"
APP_VERSION = "1.13.1"


# --------------------------------------------------------------------------
#  Paleta - barwy karty EGA, tak jak w menedzerach plikow z epoki DOS
# --------------------------------------------------------------------------

SCREEN = "#000000"     # tlo ekranu
PANEL = "#0000A8"      # wnetrze paneli
FRAME = "#00A8A8"      # ramki i naglowki
TEXT = "#C6C6C6"       # tekst zwykly
BRIGHT = "#FFFFFF"     # tekst wyrozniony
ACCENT = "#FFFF55"     # tytuly, klawisze funkcyjne
HINT = "#5454FC"       # podpisy pomocnicze
ALERT = "#FF5555"      # bledy
GOOD = "#54FC54"       # potwierdzenia
FIELD = "#000080"      # tlo pol edycji
DIM = "#545454"        # elementy nieaktywne, sciezki oczekujace
WARN = "#A85400"       # ostrzezenia - "braz" z palety CGA, jej pomaranczowy
DRIVE = "#FC54FC"      # problemy napedu, odrozniane od uszkodzen nosnika


def _pick_font(root: tk.Misc, candidates: list[str]) -> str:
    families = set(tkfont.families(root))
    for name in candidates:
        if name in families:
            return name
    return tkfont.nametofont("TkFixedFont").actual("family")


# --------------------------------------------------------------------------
#  Panel z cyanowa ramka, opcjonalnie z zakladkami
# --------------------------------------------------------------------------

class Panel(tk.Frame):
    """
    Ramka w stylu tekstowego menedzera plikow: obwodka i tytul wpisany
    w gorna krawedz. Jako tytul mozna podac liste nazw - wtedy panel dostaje
    klikalne zakladki, a wybor trafia do funkcji on_select.
    """

    def __init__(self, parent: tk.Misc, title: str | list[str], font: tuple,
                 on_select=None, **kwargs):
        super().__init__(
            parent, bg=PANEL, highlightbackground=FRAME,
            highlightcolor=FRAME, highlightthickness=1, bd=0, **kwargs
        )
        self.font = font
        self.on_select = on_select
        self.active = 0
        self.tabs: list[tk.Label] = []

        header = tk.Frame(self, bg=PANEL)
        header.place(x=14, y=-1, anchor="nw")

        if isinstance(title, str):
            self.title_var = tk.StringVar(value=title)
            tk.Label(
                header, textvariable=self.title_var, bg=PANEL, fg=ACCENT,
                font=font, padx=6,
            ).pack(side="left")
        else:
            self.title_var = None
            for index, text in enumerate(title):
                tab = tk.Label(
                    header, text=f" {text} ", bg=PANEL, font=font,
                    padx=6, cursor="hand2",
                )
                tab.pack(side="left")
                tab.bind("<Button-1>", lambda e, i=index: self.select(i))
                self.tabs.append(tab)
            self._paint_tabs()

        self.body = tk.Frame(self, bg=PANEL, bd=0)
        self.body.pack(fill="both", expand=True, padx=10, pady=(20, 10))

    def _paint_tabs(self) -> None:
        for index, tab in enumerate(self.tabs):
            chosen = index == self.active
            tab.configure(
                fg=ACCENT if chosen else TEXT,
                font=(self.font[0], self.font[1],
                      "bold" if chosen else "normal"),
            )

    def select(self, index: int) -> None:
        self.active = index
        self._paint_tabs()
        if self.on_select:
            self.on_select(index)

    def set_title(self, text: str) -> None:
        if self.title_var is not None:
            self.title_var.set(text)


# --------------------------------------------------------------------------
#  Aplikacja
# --------------------------------------------------------------------------



class ProgressBar(tk.Canvas):
    """
    Pasek postepu, ktory przerysowuje sie przy kazdej zmianie rozmiaru.

    Pamieta ulamek, a nie narysowana szerokosc. Wczesniejsze paski rysowaly
    prostokat raz, przy biezacej szerokosci plotna - gdy na koniec operacji
    pojawial sie dlugi napis ze sciezka, okno sie rozszerzalo, plotno razem
    z nim, a prostokat zostawal krotszy. Pasek wygladal wtedy, jakby nie
    doszedl do konca, choc operacja sie zakonczyla.
    """

    def __init__(self, parent: tk.Misc, height: int = 12, **kwargs):
        super().__init__(
            parent, height=height, bg=FIELD, bd=0, highlightthickness=1,
            highlightbackground=FRAME, **kwargs,
        )
        self._ulamek = 0.0
        self._kolor = FRAME
        self.bind("<Configure>", lambda e: self._rysuj(), add="+")

    def show(self, done: int, total: int, colour: str = FRAME) -> None:
        """Ustawia postep jako czesc calosci i od razu go rysuje."""
        self._ulamek = min(1.0, done / total) if total else 0.0
        self._kolor = colour
        self._rysuj()

    def clear(self) -> None:
        self._ulamek = 0.0
        self._rysuj()

    def _rysuj(self) -> None:
        self.delete("all")
        szerokosc, wysokosc = self.winfo_width(), self.winfo_height()
        if szerokosc <= 1 or self._ulamek <= 0:
            return
        self.create_rectangle(
            0, 0, max(2, int(szerokosc * self._ulamek)), wysokosc,
            fill=self._kolor, width=0,
        )

_WIERSZ_MAPY = re.compile(r"^(?:\d\.\s?\d+|H\d): +")


def _podziel_na_bloki(linie: list[str]) -> list[tuple[list[str], bool]]:
    """
    Dzieli raport na bloki: tekst przed mapa, mapa sektorow, tekst po niej.

    Mapa zaczyna sie od podzialki "Cyl->" i konczy na ostatnim wierszu
    postaci "1.17: ....". Raport bez mapy to jeden blok.
    """
    if not any(l.startswith("Cyl-> ") for l in linie):
        return [(list(linie), False)]
    poczatek = next(i for i, l in enumerate(linie) if l.startswith("Cyl-> "))
    koniec = poczatek + 2
    while koniec < len(linie) and _WIERSZ_MAPY.match(linie[koniec]):
        koniec += 1
    return [(linie[:poczatek], False), (linie[poczatek:koniec], True),
            (linie[koniec:], False)]


class ReportView(tk.Canvas):
    """
    Raport na tle obrazu.

    Widzet tekstowy Tk nie potrafi miec obrazu w tle, wiec raport rysujemy
    na plotnie: obraz na spodzie, tekst na wierzchu. Obraz jest juz
    przyciemniony i ma wygaszone brzegi - Tk nie umie mieszac przezroczystosci
    w locie, a nie chcemy zaleznosci od biblioteki graficznej.

    Tlo stoi w miejscu, przewija sie tylko tekst. Kazda linijka ma pod soba
    czarny cien przesuniety o piksel - na jasnych fragmentach obrazu sam
    jasny tekst tracil kontrast.

    Zaznaczania tekstu mysza tu nie ma; raport zapisuje sie do pliku.
    """

    MARGINES = 8
    # Obraz ma u dolu wtopiony tytul. Pod tekstem zostawiamy tyle wolnego
    # miejsca do przewijania, zeby przy przewinieciu do konca ostatnia
    # linia raportu - rozpoznanie, najwazniejsza w calosci - zatrzymala sie
    # nad tytulem, a nie na nim.
    ZAPAS_POD_TYTULEM = 44

    # Najszersza linia raportu to mapa sektorow: szesc znakow opisu i po
    # jednym znaku na kazdy z 80 cylindrow. Pole musi ja miescic w calosci,
    # bo zawinieta mapa traci uklad kolumn.
    ZNAKOW_W_LINII = 88

    def __init__(self, parent: tk.Misc, font, obraz: str | None,
                 height: int = 270):
        super().__init__(parent, bg=SCREEN, height=height, bd=0,
                         highlightthickness=1, highlightbackground=FRAME)
        self.font = font
        self.configure(width=self.szerokosc_linii() + 2 * self.MARGINES)
        self._tekst = ""
        self._elementy: list[int] = []
        self._tlo = None
        self._tlo_id = None
        if obraz:
            try:
                self._tlo = tk.PhotoImage(file=obraz, master=self)
            except tk.TclError:
                self._tlo = None
        if self._tlo is not None:
            self._tlo_id = self.create_image(0, 0, image=self._tlo,
                                             anchor="center")
        self.bind("<Configure>", lambda e: self._przelicz(), add="+")
        # kolko myszy: Linux zglasza przyciski 4 i 5, Windows zdarzenie z delta
        self.bind("<Button-4>", lambda e: self.yview_scroll(-3, "units"))
        self.bind("<Button-5>", lambda e: self.yview_scroll(3, "units"))
        self.bind("<MouseWheel>", lambda e: self.yview_scroll(
            -1 if e.delta > 0 else 1, "units"))

    def szerokosc_linii(self, znakow: int | None = None) -> int:
        """Szerokosc w pikselach linii o danej liczbie znakow tej czcionki."""
        import tkinter.font as tkfont
        return tkfont.Font(root=self, font=self.font).measure(
            "0" * (znakow or self.ZNAKOW_W_LINII))

    # -- przewijanie z nieruchomym tlem ------------------------------------

    def yview(self, *argumenty):
        wynik = super().yview(*argumenty)
        self._tlo_na_miejsce()
        return wynik

    def yview_scroll(self, ile, co):
        super().yview_scroll(ile, co)
        self._tlo_na_miejsce()

    def yview_moveto(self, ulamek):
        super().yview_moveto(ulamek)
        self._tlo_na_miejsce()

    def _tlo_na_miejsce(self) -> None:
        if self._tlo_id is not None:
            self.coords(self._tlo_id, self.winfo_width() / 2,
                        self.canvasy(0) + self.winfo_height() / 2)
            self.tag_lower(self._tlo_id)

    # -- tresc -------------------------------------------------------------

    def tekst(self) -> str:
        return self._tekst

    def pokaz(self, tekst: str) -> None:
        """
        Rysuje raport: tekst z cieniem, a mape sektorow jako osobny blok.

        Mapa nie moze sie zawijac i musi miec znaki dokladnie w kolumnach,
        bo na jej nieczytelne sektory nakladamy czerwone X. Gdyby byla
        czescia jednego duzego napisu, zawinieta wyzej dluga sciezka do
        obrazu przesunelaby ja o linie i czerwone znaki trafilyby obok.
        """
        for element in self._elementy:
            self.delete(element)
        self._elementy.clear()
        self._bloki: list[tuple[int, bool]] = []    # (element, czy mapa)
        self._tekst = tekst
        if tekst:
            import tkinter.font as tkfont
            czcionka = tkfont.Font(root=self, font=self.font)
            wiersz = czcionka.metrics("linespace")
            znak = czcionka.measure("0")
            szer = max(100, self.winfo_width() - 2 * self.MARGINES)
            y = self.MARGINES
            for linie, mapa in _podziel_na_bloki(tekst.splitlines()):
                puste = 0
                while linie and not linie[0].strip():
                    linie.pop(0)
                    puste += 1
                if not linie:
                    continue
                y += puste * wiersz
                tresc = "\n".join(linie)
                for dx, kolor in ((1, SCREEN), (0, TEXT)):
                    element = self.create_text(
                        self.MARGINES + dx, y + dx, text=tresc, anchor="nw",
                        fill=kolor, font=self.font,
                        width=0 if mapa else szer)
                    self._elementy.append(element)
                    self._bloki.append((element, mapa))
                if mapa:
                    for nr, linia in enumerate(linie):
                        for kolumna, litera in enumerate(linia):
                            if litera == "X" and _WIERSZ_MAPY.match(linia):
                                self._elementy.append(self.create_text(
                                    self.MARGINES + kolumna * znak,
                                    y + nr * wiersz, text="X", anchor="nw",
                                    fill=ALERT, font=self.font))
                y = self.bbox(self._elementy[-1])[3]
                # ostatni element bloku mapy to czerwony X - granice bloku
                # wyznacza jednak caly tekst mapy
                y = max(y, self.bbox(self._bloki[-1][0])[3])
        super().yview_moveto(0)
        self._przelicz()

    def _przelicz(self) -> None:
        szer = max(100, self.winfo_width() - 2 * self.MARGINES)
        for element, mapa in getattr(self, "_bloki", []):
            if not mapa:
                self.itemconfigure(element, width=szer)
        wysokosc = self.winfo_height()
        if self._elementy:
            ramka = self.bbox(*self._elementy)
            zapas = self.ZAPAS_POD_TYTULEM if self._tlo is not None \
                else self.MARGINES
            wysokosc = max(wysokosc, ramka[3] + zapas)
        self.configure(scrollregion=(0, 0, self.winfo_width(), wysokosc))
        self._tlo_na_miejsce()


class StyleMixin:
    """
    Wyglad okna glownego i fabryki widzetow w stylu programu.

    Domieszka dla okna glownego: tworzy czcionki i style, ustawia ikone
    i udostepnia pomocnikow w rodzaju _button czy radio_group. Siegaja po
    nich takze okna dialogowe - przez odwolanie do okna glownego - wiec
    wyglad calego programu bierze sie z tego jednego miejsca.
    """

    def _ustaw_ikone(self) -> None:
        """
        Ustawia ikone okna. Podajemy dwa rozmiary: duzy do przelacznika
        okien, maly do paska zadan - pomniejszony sam z siebie wychodzi
        gorzej niz osobno przygotowany kadr glowy.
        """
        obrazy = []
        for nazwa in ("jazwiec.png", "jazwiec-32.png"):
            sciezka = _znajdz_ikone(nazwa)
            if sciezka:
                try:
                    obrazy.append(tk.PhotoImage(file=sciezka, master=self))
                except tk.TclError:
                    pass
        if obrazy:
            # Referencje musza przezyc, inaczej Tk zwolni obrazy.
            self._ikony = obrazy
            try:
                self.iconphoto(True, *obrazy)
            except tk.TclError:
                pass

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "RZ.Treeview",
            background=PANEL, fieldbackground=PANEL, foreground=TEXT,
            font=self.f_body, rowheight=22, borderwidth=0,
        )
        style.map(
            "RZ.Treeview",
            background=[("selected", FRAME)],
            foreground=[("selected", SCREEN)],
        )
        style.configure(
            "RZ.Treeview.Heading",
            background=FRAME, foreground=SCREEN, font=self.f_bold,
            relief="flat", borderwidth=0, padding=(6, 4),
        )
        style.map("RZ.Treeview.Heading", background=[("active", ACCENT)])
        style.configure(
            "RZ.Vertical.TScrollbar",
            background=FRAME, troughcolor=PANEL, bordercolor=PANEL,
            arrowcolor=SCREEN, relief="flat",
        )

    def _button(self, parent: tk.Misc, text: str, command,
                width: int | None = None, accent: bool = False) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, width=width,
            font=self.f_bold if accent else self.f_body,
            bg=ACCENT if accent else FRAME,
            fg=SCREEN, activebackground=BRIGHT, activeforeground=SCREEN,
            relief="flat", bd=0, padx=10, pady=5,
            highlightthickness=0, cursor="hand2",
            disabledforeground="#6B6B6B",
        )

    def _entry(self, parent: tk.Misc, textvariable: tk.StringVar,
               **kwargs) -> tk.Entry:
        return tk.Entry(
            parent, textvariable=textvariable, font=self.f_body,
            bg=FIELD, fg=BRIGHT, insertbackground=ACCENT,
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=FRAME, highlightcolor=ACCENT, **kwargs
        )

    def paint_radios(self, buttons: dict, variable: tk.Variable) -> None:
        """
        Wyroznia zaznaczona pozycje kolorem i gruboscia napisu.

        Sama kropka wskaznika w tym motywie nie odrozniala sie od pozostalych,
        wiec bez tego nie widac, co jest wybrane.
        """
        chosen = variable.get()
        for value, button in buttons.items():
            try:
                active = value == chosen
                button.configure(
                    fg=ACCENT if active else TEXT,
                    font=self.f_bold if active else self.f_body,
                )
            except tk.TclError:
                pass          # widget z zamknietego juz okna

    def radio_group(self, parent: tk.Misc, variable: tk.Variable,
                    items, command=None, font=None, **pack) -> dict:
        """
        Buduje grupe przyciskow wyboru wraz z podswietlaniem.

        Powstalo po tym, jak to samo niedopatrzenie - przyciski bez
        wyroznienia wybranej pozycji - powtorzylo sie w czterech oknach
        z rzedu. Nowe okna maja uzywac tej metody zamiast skladac
        Radiobutton samodzielnie.

        items to pary (wartosc, napis).
        """
        buttons: dict = {}
        for value, text in items:
            button = tk.Radiobutton(
                parent, text=text, value=value, variable=variable,
                bg=PANEL, fg=TEXT, selectcolor=ACCENT,
                activebackground=PANEL, activeforeground=ACCENT,
                font=font or self.f_body, anchor="w", bd=0,
                highlightthickness=0, cursor="hand2", command=command,
            )
            button.pack(**(pack or {"fill": "x", "pady": 1}))
            buttons[value] = button

        variable.trace_add(
            "write", lambda *_: self.paint_radios(buttons, variable))
        self.paint_radios(buttons, variable)
        return buttons

    def _caption(self, parent: tk.Misc, text: str, **kwargs) -> tk.Label:
        return tk.Label(
            parent, text=text, bg=PANEL, fg=TEXT,
            font=self.f_body, anchor="w", **kwargs
        )
