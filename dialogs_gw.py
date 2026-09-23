"""
dialogs_gw.py - okno Greaseweazle.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Osobne okno, a nie kolejna pozycja w oknie napedow USB. Przeplyw pracy jest
inny: naped i format trzeba wskazac, bo gw nie rozpoznaje ich sam, a stacja
USB poznaje nosnik po rozmiarze. Raport z Greaseweazle jest tez znacznie
bogatszy - rozroznia uszkodzony nosnik od uszkodzonego napedu - wiec
wyswietlamy go od razu w oknie, a nie w osobnym.

Dlugie operacje - odczyt trwa okolo poltorej minuty - ida w watku w tle.
Watek niczego nie rysuje: tylko zapisuje biezacy raport, a okno co chwile
go odpytuje i przerysowuje postep. Tkinter nie znosi dotykania widzetow
spoza watku, w ktorym powstaly.

Wymaga modulu gwbridge.
"""

from __future__ import annotations

import os
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import TYPE_CHECKING

import gwbridge
from styles import (
    APP_NAME, SCREEN, PANEL, FRAME, TEXT, ACCENT, HINT, ALERT, GOOD,
    DIM, WARN, DRIVE, Panel,
)
from system import _real_home, _znajdz_ikone, hand_back

if TYPE_CHECKING:                  # tylko dla adnotacji - bez importu cyklicznego
    from gui_main import RetroZachar

ODPYTYWANIE_MS = 150


# Kolor kazdego stanu sciezki. Czerwony i purpurowy znacza co innego:
# pierwszy mowi "wyrzuc dyskietke", drugi "nie wkladaj nic do tego napedu".
KOLORY_STANOW = {
    "pending": DIM,
    "active": ACCENT,
    "ok": GOOD,
    "retried": WARN,
    "bad": ALERT,
    "misplaced": DRIVE,
}


class TrackMap(tk.Canvas):
    """
    Mapa sciezek dyskietki: rzad na kazda strone, kolumna na kazdy cylinder.

    Uklad odpowiada fizycznej geometrii - tak samo rysuje swoja mape gw
    i tak rysowal X-Copy na Amidze. Wzor uszkodzenia od razu mowi, co sie
    stalo: jeden czerwony kwadrat to uszkodzone miejsce na nosniku, caly
    czerwony rzad to martwa glowica, purpurowe to glowica, ktora nie
    dojezdza na wlasciwy cylinder.

    Rysuje sie od nowa przy zmianie rozmiaru, a przy zmianie stanow tylko
    przebarwia kwadraty, ktore sie zmienily.
    """

    LEWY = 30          # miejsce na etykiety stron
    GORA = 16          # miejsce na podzialke cylindrow
    RZAD = 16          # wysokosc rzedu
    ODSTEP = 2

    def __init__(self, parent: tk.Misc, font, cylinders: int = 80,
                 heads: int = 2):
        super().__init__(parent, bg=PANEL, bd=0, highlightthickness=0)
        self.font = font
        self.cylinders, self.heads = cylinders, heads
        self._stany: dict[tuple[int, int], str] = {}
        self._komorki: dict[tuple[int, int], int] = {}
        self._uklad = (0.0, 0.0)          # szerokosc kolumny, poczatek x
        self._dopasuj_wysokosc()
        self.bind("<Configure>", lambda e: self._narysuj(), add="+")

    def _dopasuj_wysokosc(self) -> None:
        self.configure(height=self.GORA + self.heads * self.RZAD + 2)

    def geometria(self, cylinders: int, heads: int) -> None:
        """Dyskietka 360 KB ma 40 cylindrow, pozostale 80."""
        if (cylinders, heads) != (self.cylinders, self.heads):
            self.cylinders, self.heads = cylinders, heads
            self._stany.clear()
            self._dopasuj_wysokosc()
            self._narysuj()

    def wyczysc(self) -> None:
        self._stany.clear()
        for klucz, element in self._komorki.items():
            self.itemconfigure(element, fill=KOLORY_STANOW["pending"])

    def pokaz(self, stany: dict[tuple[int, int], str]) -> None:
        """Przebarwia tylko kwadraty, ktorych stan sie zmienil."""
        for klucz in set(self._stany) | set(stany):
            nowy = stany.get(klucz, "pending")
            if self._stany.get(klucz, "pending") != nowy:
                element = self._komorki.get(klucz)
                if element is not None:
                    self.itemconfigure(element, fill=KOLORY_STANOW[nowy])
        self._stany = dict(stany)

    def komorka_pod(self, x: int, y: int) -> tuple[int, int] | None:
        szerokosc, poczatek = self._uklad
        if szerokosc <= 0 or x < poczatek or y < self.GORA:
            return None
        cyl = int((x - poczatek) // szerokosc)
        glowica = int((y - self.GORA) // self.RZAD)
        if 0 <= cyl < self.cylinders and 0 <= glowica < self.heads:
            return cyl, glowica
        return None

    def _narysuj(self) -> None:
        self.delete("all")
        self._komorki.clear()
        szer = self.winfo_width()
        if szer <= self.LEWY + self.cylinders:
            return
        kolumna = (szer - self.LEWY) / self.cylinders
        self._uklad = (kolumna, float(self.LEWY))

        for cyl in range(0, self.cylinders, 10):
            self.create_text(self.LEWY + cyl * kolumna, 1, text=str(cyl),
                             anchor="nw", fill=HINT, font=self.font,
                             tags="podzialka")
        # Cylindry liczy sie od zera: 80 cylindrow to numery 0-79. Numer
        # ostatniego na koncu podzialki pokazuje, ze siatka konczy sie tam
        # z zalozenia - bez niego podzialka urwana na 70 wygladala na niepelna.
        ostatni = self.cylinders - 1
        if ostatni % 10:
            # wyrownany do prawej krawedzi ostatniego kwadratu, ktora lezy
            # przed krawedzia plotna - przy samej krawedzi cyfra wystawala
            # o piksel i mogla byc przycieta
            self.create_text(
                self.LEWY + self.cylinders * kolumna - self.ODSTEP, 1,
                text=str(ostatni), anchor="ne", fill=HINT, font=self.font,
                tags="podzialka")
        for glowica in range(self.heads):
            gora = self.GORA + glowica * self.RZAD
            self.create_text(2, gora + (self.RZAD - self.ODSTEP) / 2,
                             text=f"H{glowica}", anchor="w", fill=TEXT,
                             font=self.font)
            for cyl in range(self.cylinders):
                x0 = self.LEWY + cyl * kolumna
                stan = self._stany.get((cyl, glowica), "pending")
                self._komorki[(cyl, glowica)] = self.create_rectangle(
                    x0, gora, x0 + max(1.0, kolumna - self.ODSTEP),
                    gora + self.RZAD - self.ODSTEP,
                    fill=KOLORY_STANOW[stan], width=0)


# Wiersz mapy sektorow ("1.17: ....") albo mapy sciezek ("H1:   ....").
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


class GwDialog(tk.Toplevel):
    """Odczyt, zapis i formatowanie dyskietek przez Greaseweazle."""

    def __init__(self, master: "RetroZachar"):
        super().__init__(master, bg=SCREEN)
        self.app = master
        app = master

        self.worker: threading.Thread | None = None
        self._aktywny: tk.Button | None = None
        self._przerwij = False
        self._zamknij_po = False
        self._biezacy: gwbridge.GwReport | None = None
        self._migawka: dict = {}
        self._wynik: tuple | None = None
        self._po_zakonczeniu = None
        self._stan: gwbridge.GwStatus | None = None
        self.raport: gwbridge.GwReport | None = None

        self.title(app.t("gw_title"))
        self.configure(padx=12, pady=12)
        self.transient(master)

        naped = app.config_data.get("gwdrive", gwbridge.DEFAULT_DRIVE)
        if naped not in gwbridge.DRIVES:
            naped = gwbridge.DEFAULT_DRIVE
        format_ = app.config_data.get("gwformat", "1440")
        if format_ not in gwbridge.GW_FORMATS:
            format_ = "1440"
        # Sciezka do gw wskazana wczesniej recznie. Pod Windowsem to czesto
        # jedyna droga: narzedzia rozpakowane poza PATH dzialaja tylko
        # w swoim katalogu, a okno uruchomione z Eksploratora go nie ma.
        gwbridge.set_tool_path(app.config_data.get("gwpath") or None)
        self.var_drive = tk.StringVar(value=naped)
        self.var_format = tk.StringVar(value=format_)

        panel = Panel(self, app.t("gw_title"), app.f_title)
        panel.pack(fill="both", expand=True)
        body = panel.body

        tk.Label(body, text=app.t("gw_intro"), bg=PANEL, fg=HINT,
                 font=app.f_small, justify="left", anchor="w",
                 ).pack(fill="x", pady=(0, 8))

        # -- stan urzadzenia ------------------------------------------------
        wiersz = tk.Frame(body, bg=PANEL)
        wiersz.pack(fill="x")
        self.lbl_device = tk.Label(wiersz, text=app.t("gw_checking"),
                                   bg=PANEL, fg=ACCENT, font=app.f_body,
                                   anchor="w", justify="left")
        self.lbl_device.pack(side="left", fill="x", expand=True)
        self.btn_recheck = app._button(wiersz, app.t("gw_recheck"),
                                       self.sprawdz_urzadzenie)
        self.btn_recheck.configure(font=app.f_small, padx=6)
        self.btn_recheck.pack(side="right")
        self.btn_tool = app._button(wiersz, app.t("gw_pick_tool"),
                                    self.wskaz_narzedzie)
        self.btn_tool.configure(font=app.f_small, padx=6)
        self.btn_tool.pack(side="right", padx=(0, 6))

        self.lbl_tool = tk.Label(body, text="", bg=PANEL, fg=HINT,
                                 font=app.f_small, anchor="w", justify="left")
        self.lbl_tool.pack(fill="x", pady=(2, 0))

        tk.Frame(body, bg=FRAME, height=1).pack(fill="x", pady=10)

        # -- naped i format -------------------------------------------------
        wiersz = tk.Frame(body, bg=PANEL)
        wiersz.pack(fill="x")
        tk.Label(wiersz, text=app.t("gw_drive"), bg=PANEL, fg=TEXT,
                 font=app.f_body, width=9, anchor="w").pack(side="left")
        self.drive_buttons = app.radio_group(
            wiersz, self.var_drive, [(d, d) for d in gwbridge.DRIVES],
            side="left", padx=(0, 10))
        tk.Label(body, text=app.t("gw_drive_hint"), bg=PANEL, fg=HINT,
                 font=app.f_small, anchor="w").pack(fill="x", pady=(2, 8))

        # Zakladka na kazda rodzine nosnikow. Bez podzialu lista formatow
        # rozrosla by sie do kilkunastu pozycji i przestala byc czytelna,
        # a beda dochodzic kolejne systemy.
        self.rodziny = list(gwbridge.RODZINY)
        zakladki = Panel(body, [gwbridge.RODZINY[r] for r in self.rodziny],
                         app.f_small, on_select=self._wybrano_rodzine)
        zakladki.pack(fill="x")
        self.zakladki = zakladki
        self.strony: list[tk.Frame] = []
        self.format_buttons: dict[str, tk.Radiobutton] = {}
        najwiecej = max(len(gwbridge.nosniki_rodziny(r))
                        for r in self.rodziny)
        for rodzina in self.rodziny:
            strona = tk.Frame(zakladki.body, bg=PANEL,
                              height=najwiecej * 22)
            strona.pack_propagate(False)
            self.strony.append(strona)
            self.format_buttons.update(app.radio_group(
                strona, self.var_format,
                [(n.klucz, n.etykieta)
                 for n in gwbridge.nosniki_rodziny(rodzina)],
                font=app.f_small, fill="x"))
        zakladki.select(self.rodziny.index(
            gwbridge.rodzina_nosnika(self.var_format.get())))

        tk.Frame(body, bg=FRAME, height=1).pack(fill="x", pady=10)

        # -- operacje -------------------------------------------------------
        operacje = tk.Frame(body, bg=PANEL)
        operacje.pack(fill="x")
        # Zaden przycisk nie jest wyrozniony na stale - trzy operacje sa
        # rownorzedne. Na zolto swieci sie ten, ktory uruchomil trwajaca
        # operacje. Stale wyrozniony "Zgraj" zostawal zolty takze wtedy, gdy
        # trwal zapis albo formatowanie, i wygladal, jakby trwal odczyt.
        self.btn_read = app._button(
            operacje,
            app.t("gw_read",
                  ext=gwbridge.NOSNIKI[self.var_format.get()].rozszerzenie),
            self.odczyt)
        self.btn_read.pack(side="left")
        self.btn_write = app._button(operacje, app.t("gw_write"), self.zapis)
        self.btn_write.pack(side="left", padx=(8, 0))
        self.btn_format = app._button(operacje, app.t("gw_format_disk"),
                                      self.formatowanie)
        self.btn_format.pack(side="left", padx=(8, 0))

        # Mapa sciezek zamiast paska postepu - pokazuje nie tylko ile, ale
        # tez gdzie i jak. Pod nia legenda i szczegoly wskazanej sciezki.
        nosnik = gwbridge.NOSNIKI[self.var_format.get()]
        self.mapa = TrackMap(body, app.f_small, nosnik.cylindry,
                             nosnik.glowice)
        self.mapa.pack(fill="x", pady=(10, 2))
        self.mapa.bind("<Motion>", self._najechanie, add="+")
        self.mapa.bind("<Leave>", lambda e: self._pokaz_szczegoly(None),
                       add="+")

        legenda = tk.Frame(body, bg=PANEL)
        legenda.pack(fill="x", pady=(2, 4))
        for stan in KOLORY_STANOW:
            tk.Frame(legenda, bg=KOLORY_STANOW[stan], width=10,
                     height=10).pack(side="left", padx=(0, 4))
            tk.Label(legenda, text=app.t("gw_legend_" + stan), bg=PANEL,
                     fg=HINT, font=app.f_small).pack(side="left",
                                                     padx=(0, 12))

        self.lbl_info = tk.Label(body, text=app.t("gw_hover_hint"),
                                 bg=PANEL, fg=HINT, font=app.f_small,
                                 anchor="w")
        self.lbl_info.pack(fill="x")
        self.lbl_progress = tk.Label(body, text="", bg=PANEL, fg=TEXT,
                                     font=app.f_small, anchor="w",
                                     justify="left")
        self.lbl_progress.pack(fill="x")
        self.mapa.bind(
            "<Configure>",
            lambda e: self.lbl_progress.configure(
                wraplength=max(100, e.width)), add="+")
        self.var_format.trace_add("write", lambda *_: self._format_zmieniony())

        # -- raport ---------------------------------------------------------
        pole = tk.Frame(body, bg=PANEL)
        pole.pack(fill="both", expand=True, pady=(8, 0))
        self.widok = ReportView(pole, app.f_small,
                                _znajdz_ikone("jazwiec-gw.png"))
        przewijak = ttk.Scrollbar(pole, orient="vertical",
                                  command=self.widok.yview,
                                  style="RZ.Vertical.TScrollbar")
        self.widok.configure(yscrollcommand=przewijak.set)
        przewijak.pack(side="right", fill="y")
        self.widok.pack(side="left", fill="both", expand=True)

        dol = tk.Frame(body, bg=PANEL)
        dol.pack(fill="x", pady=(10, 0))
        self.btn_save = app._button(dol, app.t("gw_save_report"),
                                    self.zapisz_raport)
        self.btn_save.configure(font=app.f_small, state="disabled")
        self.btn_save.pack(side="left")
        app._button(dol, app.t("drive_close"), self.zamknij).pack(
            side="right")
        self.btn_cancel = app._button(dol, app.t("gw_cancel"),
                                      self.przerwij)
        self.btn_cancel.configure(state="disabled")
        self.btn_cancel.pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.zamknij)
        self.bind("<Escape>", lambda e: self.zamknij())
        self._odswiez_przyciski()
        # Okno nie moze byc wezsze niz mapa sektorow w raporcie - po
        # zwezeniu mapa zawinelaby sie i stracila uklad kolumn.
        self.update_idletasks()
        self.minsize(self.winfo_reqwidth(), 1)
        self.sprawdz_urzadzenie()

    # -- urzadzenie --------------------------------------------------------

    def sprawdz_urzadzenie(self) -> None:
        """gw info w tle - wywolanie bywa wolne, a okno ma nie zamarzac."""
        if self.worker is not None:
            return
        self.lbl_device.configure(text=self.app.t("gw_checking"), fg=ACCENT)
        self._stan = None
        self._odswiez_przyciski()

        def praca():
            self._stan = gwbridge.probe()

        watek = threading.Thread(target=praca, daemon=True)
        watek.start()

        def czekaj():
            if watek.is_alive():
                self.after(ODPYTYWANIE_MS, czekaj)
            else:
                self._pokaz_stan()

        self.after(ODPYTYWANIE_MS, czekaj)

    def wskaz_narzedzie(self) -> None:
        """
        Reczne wskazanie pliku gw.

        Pod Windowsem narzedzia rozpakowuje sie do dowolnego katalogu.
        Jesli nie trafi on do PATH, polecenie dziala tylko w tym folderze,
        a program uruchomiony z Eksploratora ma inny katalog roboczy.
        """
        app = self.app
        poczatek = gwbridge.tool_path() or str(_real_home())
        wybor = filedialog.askopenfilename(
            parent=self, title=app.t("gw_pick_tool_title"),
            initialdir=os.path.dirname(poczatek) if os.path.isfile(poczatek)
            else poczatek)
        if not wybor:
            return
        gwbridge.set_tool_path(wybor)
        if app.config_data.get("gwpath") != wybor:
            app.config_data["gwpath"] = wybor
            app._save_config()
        self.sprawdz_urzadzenie()

    def _pokaz_stan(self) -> None:
        if not self.winfo_exists():
            return
        stan = self._stan
        app = self.app
        gwbridge.set_language(app.lang)
        wskazane = gwbridge.tool_path()
        self.lbl_tool.configure(
            text=wskazane if wskazane else app.t("gw_tool_hint"),
            fg=TEXT if wskazane else HINT)
        problem = stan.problem() if stan else None
        if problem:
            self.lbl_device.configure(text=problem, fg=ALERT)
        else:
            self.lbl_device.configure(
                text=app.t("gw_ready", model=stan.model,
                            firmware=stan.firmware, port=stan.port,
                            tool=stan.tool_version),
                fg=GOOD)
        self._odswiez_przyciski()

    def _wybrano_rodzine(self, indeks: int) -> None:
        """Pokazuje formaty jednej rodziny. Wybor pozostaje bez zmian."""
        for strona in self.strony:
            strona.pack_forget()
        self.strony[indeks].pack(fill="both", expand=True)

    def _odswiez_przyciski(self) -> None:
        zajety = self.worker is not None
        gotowy = self._stan is not None and self._stan.ready and not zajety
        app = self.app
        # Formatowanie polega na zapisaniu pustego obrazu, a takiego nie
        # zbudujemy dla AmigaDOS - nie mamy jego silnika.
        umiemy_formatowac = gwbridge.NOSNIKI[
            self.var_format.get()].nasz_system_plikow
        for przycisk in (self.btn_read, self.btn_write, self.btn_format):
            trwa = zajety and przycisk is self._aktywny
            wlaczony = gotowy and (przycisk is not self.btn_format
                                   or umiemy_formatowac)
            przycisk.configure(
                state="normal" if wlaczony else "disabled",
                bg=ACCENT if trwa else FRAME,
                font=app.f_bold if trwa else app.f_body,
                # zablokowany, ale czytelny: ciemny napis na zoltym tle
                disabledforeground=SCREEN if trwa else "#6B6B6B")
        for przycisk in (self.btn_recheck, self.btn_tool):
            przycisk.configure(state="disabled" if zajety else "normal")
        self.btn_cancel.configure(state="normal" if zajety else "disabled")
        self.btn_save.configure(
            state="normal" if self.raport is not None and not zajety
            else "disabled")
        for grupa in (self.drive_buttons, self.format_buttons):
            for przycisk in grupa.values():
                przycisk.configure(state="disabled" if zajety else "normal")

    # -- operacje ----------------------------------------------------------

    def _zapamietaj_wybor(self) -> tuple[str, str]:
        naped, format_ = self.var_drive.get(), self.var_format.get()
        dane = self.app.config_data
        if (dane.get("gwdrive"), dane.get("gwformat")) != (naped, format_):
            dane["gwdrive"], dane["gwformat"] = naped, format_
            self.app._save_config()
        return naped, format_

    def odczyt(self) -> None:
        app = self.app
        naped, format_ = self._zapamietaj_wybor()
        # gw wybiera przeksztalcenie po rozszerzeniu: .adf dla Amigi,
        # .st dla Atari, .img dla peceta. Zle rozszerzenie konczy sie
        # obrazem, ktorego zaden emulator nie otworzy.
        koncowka = gwbridge.NOSNIKI[format_].rozszerzenie
        cel = filedialog.asksaveasfilename(
            parent=self, title=app.t("gw_pick_save"),
            defaultextension=koncowka, initialfile="dyskietka" + koncowka,
            initialdir=app.config_data.get("outdir", str(_real_home())),
            filetypes=[(app.t("dlg_filter_images"), "*" + koncowka),
                       (app.t("dlg_filter_all"), "*.*")])
        if not cel:
            return

        def po(raport):
            # O otwarcie obrazu pytamy tylko wtedy, gdy naprawde powstal.
            # Po przerwanej pracy gw - na przyklad po wyjeciu przewodu USB -
            # pliku nie ma wcale, a pytanie konczylo sie bledem "nie ma
            # takiego pliku".
            if raport is None or raport.cancelled or raport.fatal:
                return
            if not os.path.isfile(cel) or os.path.getsize(cel) == 0:
                return
            if not gwbridge.NOSNIKI[format_].nasz_system_plikow:
                return          # obrazu Amigi ani Atari nasz silnik nie czyta
            hand_back(cel)
            if messagebox.askyesno(APP_NAME, app.t("gw_open_read"),
                                   parent=self):
                app._open_path(Path(cel))

        self._uruchom(
            app.t("gw_reading"),
            lambda postep: gwbridge.read_to_image(cel, format_, naped,
                                                  progress=postep),
            po, przycisk=self.btn_read)

    def zapis(self) -> None:
        app = self.app
        naped, format_ = self._zapamietaj_wybor()
        # Najczestszy przypadek: obraz przygotowany przed chwila w oknie
        # glownym. Okno wyboru startuje wiec od niego.
        otwarty = getattr(app, "image_path", None)
        zrodlo = filedialog.askopenfilename(
            parent=self, title=app.t("gw_pick_open"),
            initialdir=str(otwarty.parent) if otwarty
            else app.config_data.get("outdir", str(_real_home())),
            initialfile=otwarty.name if otwarty else "",
            filetypes=[(app.t("dlg_filter_images"),
                        "*" + gwbridge.NOSNIKI[format_].rozszerzenie),
                       (app.t("dlg_filter_all"), "*.*")])
        if not zrodlo:
            return

        # Obrazy dyskietek maja jednoznaczne rozmiary, wiec zamiast odrzucac
        # obraz innego formatu surowymi liczbami, rozpoznajemy go i pytamy.
        try:
            rozmiar = os.path.getsize(zrodlo)
        except OSError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        if rozmiar != gwbridge.NOSNIKI[format_].rozmiar:
            pasujace = [k for k, n in gwbridge.NOSNIKI.items()
                        if n.rozmiar == rozmiar]
            if not pasujace:
                messagebox.showerror(
                    APP_NAME, app.t("gw_size_unknown", size=rozmiar),
                    parent=self)
                return
            if not messagebox.askyesno(
                    APP_NAME,
                    app.t("gw_size_switch",
                          image=gwbridge.NOSNIKI[pasujace[0]].etykieta,
                          chosen=gwbridge.NOSNIKI[format_].etykieta),
                    parent=self):
                return
            self.var_format.set(pasujace[0])
            naped, format_ = self._zapamietaj_wybor()

        if not messagebox.askyesno(
                APP_NAME, app.t("gw_confirm_write", drive=naped, path=zrodlo),
                icon="warning", default="no", parent=self):
            return
        self._uruchom(
            app.t("gw_writing"),
            lambda postep: gwbridge.write_image(zrodlo, format_, naped,
                                                progress=postep),
            przycisk=self.btn_write)

    def formatowanie(self) -> None:
        app = self.app
        naped, format_ = self._zapamietaj_wybor()
        if not messagebox.askyesno(
                APP_NAME,
                app.t("gw_confirm_format", drive=naped,
                      format=gwbridge.NOSNIKI[format_].etykieta),
                icon="warning", default="no", parent=self):
            return
        etykieta = simpledialog.askstring(APP_NAME, app.t("gw_label"),
                                          parent=self)
        if etykieta is None:
            return
        self._uruchom(
            app.t("gw_formatting"),
            lambda postep: gwbridge.format_disk(format_, naped,
                                                etykieta.strip()[:11],
                                                progress=postep),
            przycisk=self.btn_format)

    # -- praca w tle -------------------------------------------------------

    def _uruchom(self, opis: str, zadanie, po_zakonczeniu=None,
                 przycisk: tk.Button | None = None) -> None:
        gwbridge.set_language(self.app.lang)
        self._aktywny = przycisk
        self._przerwij = False
        self._biezacy = None
        self._wynik = None
        self._po_zakonczeniu = po_zakonczeniu
        self.raport = None
        self._migawka = {}
        self._geometria_z_formatu()
        self.mapa.wyczysc()
        self._pokaz("")
        self.lbl_progress.configure(text=opis, fg=ACCENT)

        def praca():
            try:
                self._wynik = (zadanie(self._postep), None)
            except (gwbridge.GwError, OSError) as exc:
                self._wynik = (None, exc)

        self.worker = threading.Thread(target=praca, daemon=True)
        self.worker.start()
        self._odswiez_przyciski()
        self.after(ODPYTYWANIE_MS, self._odpytuj)

    def _postep(self, raport: gwbridge.GwReport) -> bool:
        """
        Wywolywane z watku w tle - niczego nie rysuje, tylko zapamietuje.

        Migawke stanow robi ten watek, bo to on zmienia raport. Okno dostaje
        gotowy, niezmienny slownik zamiast czytac taki, do ktorego w tej
        chwili ktos dopisuje.
        """
        self._migawka = raport.snapshot()
        self._biezacy = raport
        return not self._przerwij

    def _odpytuj(self) -> None:
        if not self.winfo_exists():
            return
        raport = self._biezacy
        self.mapa.pokaz(self._stany_do_pokazania(trwa=True))
        if raport is not None and not self._przerwij:
            self.lbl_progress.configure(
                text=self.app.t("gw_progress", done=raport.done_tracks,
                                total=raport.total_tracks), fg=TEXT)
        if self.worker is not None and self.worker.is_alive():
            self.after(ODPYTYWANIE_MS, self._odpytuj)
            return
        self._zakoncz()

    def _zakoncz(self) -> None:
        self.worker = None
        self._aktywny = None
        raport, blad = self._wynik or (None, None)
        if blad is not None:
            self.lbl_progress.configure(text=str(blad), fg=ALERT)
            self._pokaz(str(blad))
        elif raport is not None:
            self.raport = raport
            dobrze = raport.diagnosis in ("ok", "write_ok", "format_ok")
            self._migawka = raport.snapshot()
            self.mapa.pokaz(self._stany_do_pokazania(trwa=False))
            self.lbl_progress.configure(
                text=self.app.t("gw_done"), fg=GOOD if dobrze else ALERT)
            self._pokaz(raport.text())
        self._odswiez_przyciski()

        if self._zamknij_po:
            self.destroy()
            return
        if self._po_zakonczeniu is not None:
            self._po_zakonczeniu(raport)

    # -- mapa sciezek ------------------------------------------------------

    def _format_zmieniony(self) -> None:
        # Napis na przycisku pokazuje rozszerzenie, ktore naprawde powstanie:
        # .adf dla Amigi, .st dla Atari, .img dla peceta.
        self.btn_read.configure(text=self.app.t(
            "gw_read",
            ext=gwbridge.NOSNIKI[self.var_format.get()].rozszerzenie))
        self._geometria_z_formatu()
        self._odswiez_przyciski()

    def _geometria_z_formatu(self) -> None:
        nosnik = gwbridge.NOSNIKI[self.var_format.get()]
        self.mapa.geometria(nosnik.cylindry, nosnik.glowice)

    def _stany_do_pokazania(self, trwa: bool) -> dict:
        """
        Stany sciezek z migawki, z wyroznieniem sciezki w pracy.

        gw wypisuje linie po skonczeniu sciezki, nie na jej poczatku. Zolta
        jest wiec sciezka, ktora jeszcze sie meczy ponownymi probami, a gdy
        takiej nie ma - nastepna w kolejnosci. Po zakonczeniu zolta nie
        ma byc zadna: przerwana w polowie sciezka wraca do oczekujacych.
        """
        stany = {k: v[0] for k, v in self._migawka.items()}
        if not trwa:
            return {k: ("pending" if s == "active" else s)
                    for k, s in stany.items()}
        if "active" in stany.values():
            return stany
        glowice = self.mapa.heads
        wszystkie = self.mapa.cylinders * glowice
        indeksy = [c * glowice + h for c, h in stany]
        nastepna = max(indeksy) + 1 if indeksy else 0
        if nastepna < wszystkie:
            stany[divmod(nastepna, glowice)] = "active"
        return stany

    def _najechanie(self, zdarzenie) -> None:
        self._pokaz_szczegoly(self.mapa.komorka_pod(zdarzenie.x,
                                                    zdarzenie.y))

    def _pokaz_szczegoly(self, klucz) -> None:
        app = self.app
        if klucz is None:
            self.lbl_info.configure(text=app.t("gw_hover_hint"), fg=HINT)
            return
        cyl, glowica = klucz
        stan = self.mapa._stany.get(klucz, "pending")
        czesci = [app.t("gw_track_head", cyl=cyl, head=glowica,
                        state=app.t("gw_legend_" + stan))]
        szczegoly = self._migawka.get(klucz)
        if szczegoly is not None:
            _, znalezione, wszystkie, proby, obce = szczegoly
            if wszystkie:
                czesci.append(app.t("gw_track_sectors", found=znalezione,
                                    total=wszystkie))
            if proby > 1:
                czesci.append(app.t("gw_track_attempts", count=proby))
            if obce:
                czesci.append(app.t("gw_track_foreign",
                                    cyls=", ".join(map(str, obce))))
        self.lbl_info.configure(text="   ".join(czesci),
                                fg=KOLORY_STANOW.get(stan, TEXT))

    def przerwij(self) -> None:
        if self.worker is not None:
            self._przerwij = True
            self.lbl_progress.configure(text=self.app.t("gw_cancelling"),
                                        fg=ALERT)

    def zamknij(self) -> None:
        """Nie zostawiamy dzialajacego gw bez nadzoru - najpierw przerwanie."""
        if self.worker is None:
            self.destroy()
            return
        if messagebox.askyesno(APP_NAME, self.app.t("gw_busy_close"),
                               icon="warning", parent=self):
            self._zamknij_po = True
            self.przerwij()

    # -- raport ------------------------------------------------------------

    def _pokaz(self, tekst: str) -> None:
        self.widok.pokaz(tekst)

    def zapisz_raport(self) -> None:
        if self.raport is None:
            return
        app = self.app
        cel = filedialog.asksaveasfilename(
            parent=self, title=app.t("dlg_save_report"),
            defaultextension=".txt", initialfile="raport_gw.txt",
            initialdir=app.config_data.get("outdir", str(_real_home())),
            filetypes=[(app.t("filter_text"), "*.txt"),
                       (app.t("dlg_filter_all"), "*.*")])
        if not cel:
            return
        try:
            with open(cel, "w", encoding="utf-8") as fh:
                fh.write(self.raport.text() + "\n")
            hand_back(cel)
        except OSError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        self.lbl_progress.configure(text=app.t("report_saved", path=cel),
                                    fg=GOOD)
