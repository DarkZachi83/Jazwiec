"""
dialogs_optical.py - okno zgrywania plyt CD i DVD.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Zbudowane na tym samym wzorze co okno Greaseweazle: wybor urzadzenia, opis
nosnika z ostrzezeniami, pasek postepu i raport na dole. Zgrywanie plyty
trwa kilka minut, wiec idzie w watku w tle, a okno co chwile odpytuje jego
stan. Watek niczego nie rysuje - Tkinter nie znosi dotykania widzetow spoza
watku, w ktorym powstaly.

Wymaga modulu optical.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

import optical
from styles import (
    APP_NAME, SCREEN, PANEL, FRAME, TEXT, BRIGHT, ACCENT, HINT, ALERT, GOOD,
    FIELD, Panel, ProgressBar, ReportView,
)
from system import _real_home, _znajdz_ikone, hand_back, wzorzec_pliku

if TYPE_CHECKING:                  # tylko dla adnotacji - bez importu cyklicznego
    from gui_main import RetroZachar

ODPYTYWANIE_MS = 150


class OpticalDialog(tk.Toplevel):
    """Zgrywanie plyty z danymi do pliku .iso."""

    def __init__(self, master: "RetroZachar"):
        super().__init__(master, bg=SCREEN)
        self.app = master
        app = master

        self.worker: threading.Thread | None = None
        self._przerwij = False
        self._zamknij_po = False
        self._biezacy: optical.ReadReport | None = None
        self._wynik: tuple | None = None
        self.info: optical.DiscInfo | None = None
        self.raport: optical.ReadReport | None = None

        self.title(app.t("cd_title"))
        self.configure(padx=12, pady=12)
        self.transient(master)

        panel = Panel(self, app.t("cd_title"), app.f_title)
        panel.pack(fill="both", expand=True)
        body = panel.body

        tk.Label(body, text=app.t("cd_intro"), bg=PANEL, fg=HINT,
                 font=app.f_small, justify="left", anchor="w").pack(
                     fill="x", pady=(0, 8))

        # -- naped ----------------------------------------------------------
        wiersz = tk.Frame(body, bg=PANEL)
        wiersz.pack(fill="x")
        tk.Label(wiersz, text=app.t("cd_drive"), bg=PANEL, fg=TEXT,
                 font=app.f_body).pack(side="left")
        self.var_drive = tk.StringVar(
            value=app.config_data.get("cddrive", ""))
        self.drive_buttons: dict[str, tk.Radiobutton] = {}
        self.ramka_napedow = tk.Frame(wiersz, bg=PANEL)
        self.ramka_napedow.pack(side="left", padx=(8, 0))
        self.btn_refresh = app._button(wiersz, app.t("cd_refresh"),
                                       self.odswiez_napedy)
        self.btn_refresh.configure(font=app.f_small, padx=6)
        self.btn_refresh.pack(side="right")

        # -- liczba prob ----------------------------------------------------
        wiersz = tk.Frame(body, bg=PANEL)
        wiersz.pack(fill="x", pady=(8, 0))
        tk.Label(wiersz, text=app.t("cd_retries"), bg=PANEL, fg=TEXT,
                 font=app.f_body).pack(side="left")
        self.var_retries = tk.StringVar(
            value=str(app.config_data.get("cdretries",
                                          optical.DOMYSLNE_PROBY)))
        self.spin_retries = tk.Spinbox(
            wiersz, from_=1, to=20, width=4, textvariable=self.var_retries,
            font=app.f_body, bg=FIELD, fg=BRIGHT, buttonbackground=FRAME,
            relief="flat", insertbackground=BRIGHT, justify="right",
            highlightthickness=1, highlightbackground=FRAME)
        self.spin_retries.pack(side="left", padx=(8, 0))
        tk.Label(wiersz, text=app.t("cd_retries_hint"), bg=PANEL, fg=HINT,
                 font=app.f_small).pack(side="left", padx=(10, 0))

        tk.Frame(body, bg=FRAME, height=1).pack(fill="x", pady=10)

        # -- opis plyty -----------------------------------------------------
        self.lbl_disc = tk.Label(body, text=app.t("cd_no_disc"), bg=PANEL,
                                 fg=HINT, font=app.f_body, anchor="w",
                                 justify="left")
        self.lbl_disc.pack(fill="x")
        self.lbl_notes = tk.Label(body, text="", bg=PANEL, fg=ALERT,
                                  font=app.f_small, anchor="w",
                                  justify="left")
        self.lbl_notes.pack(fill="x", pady=(2, 8))

        # -- operacje -------------------------------------------------------
        operacje = tk.Frame(body, bg=PANEL)
        operacje.pack(fill="x")
        self.btn_check = app._button(operacje, app.t("cd_check"),
                                     self.sprawdz_plyte)
        self.btn_check.pack(side="left")
        self.btn_read = app._button(operacje, app.t("cd_read"), self.zgraj)
        self.btn_read.pack(side="left", padx=(8, 0))

        self.pasek = ProgressBar(body, height=14)
        self.pasek.pack(fill="x", pady=(10, 4))
        self.lbl_progress = tk.Label(body, text="", bg=PANEL, fg=TEXT,
                                     font=app.f_small, anchor="w",
                                     justify="left")
        self.lbl_progress.pack(fill="x")
        self.pasek.bind(
            "<Configure>",
            lambda e: self.lbl_progress.configure(
                wraplength=max(100, e.width)), add="+")

        # -- raport ---------------------------------------------------------
        pole = tk.Frame(body, bg=PANEL)
        pole.pack(fill="both", expand=True, pady=(8, 0))
        self.widok = ReportView(pole, app.f_small,
                                _znajdz_ikone("jazwiec-cd.png"))
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
        self.btn_cancel = app._button(dol, app.t("gw_cancel"), self.przerwij)
        self.btn_cancel.configure(state="disabled")
        self.btn_cancel.pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.zamknij)
        self.bind("<Escape>", lambda e: self.zamknij())
        self.odswiez_napedy()

    # -- napedy ------------------------------------------------------------

    def odswiez_napedy(self) -> None:
        """Lista napedow optycznych; pusta, gdy w komputerze zadnego nie ma."""
        for przycisk in self.drive_buttons.values():
            przycisk.destroy()
        self.drive_buttons.clear()
        napedy = optical.list_drives()
        if not napedy:
            self.lbl_disc.configure(text=self.app.t("cd_none"), fg=ALERT)
            self._odswiez_przyciski()
            return
        if self.var_drive.get() not in [n.path for n in napedy]:
            self.var_drive.set(napedy[0].path)
        self.drive_buttons = self.app.radio_group(
            self.ramka_napedow, self.var_drive,
            [(n.path, str(n)) for n in napedy],
            font=self.app.f_small, side="left", padx=(0, 10))
        self._odswiez_przyciski()

    def liczba_prob(self) -> int:
        try:
            ile = int(self.var_retries.get())
        except ValueError:
            ile = optical.DOMYSLNE_PROBY
        ile = max(1, min(20, ile))
        if str(ile) != self.var_retries.get():
            self.var_retries.set(str(ile))
        return ile

    def _zapamietaj(self) -> str:
        naped, proby = self.var_drive.get(), self.liczba_prob()
        dane = self.app.config_data
        if (dane.get("cddrive"), dane.get("cdretries")) != (naped, proby):
            dane["cddrive"], dane["cdretries"] = naped, proby
            self.app._save_config()
        return naped

    def _odswiez_przyciski(self) -> None:
        zajety = self.worker is not None
        jest_naped = bool(self.drive_buttons)
        self.btn_check.configure(
            state="normal" if jest_naped and not zajety else "disabled")
        gotowa = self.info is not None and self.info.readable
        self.btn_read.configure(
            state="normal" if gotowa and not zajety else "disabled")
        self.btn_refresh.configure(state="disabled" if zajety else "normal")
        self.btn_cancel.configure(state="normal" if zajety else "disabled")
        self.btn_save.configure(
            state="normal" if self.raport is not None and not zajety
            else "disabled")
        self.spin_retries.configure(state="disabled" if zajety else "normal")
        for przycisk in self.drive_buttons.values():
            przycisk.configure(state="disabled" if zajety else "normal")

    # -- sprawdzenie plyty --------------------------------------------------

    def sprawdz_plyte(self) -> None:
        """
        Odczytuje opis plyty. Idzie w tle, bo naped potrafi sie rozkrecac
        kilka sekund, a okno nie moze w tym czasie zamarzac.
        """
        if self.worker is not None:
            return
        naped = self._zapamietaj()
        self.info = None
        self.lbl_progress.configure(text=self.app.t("cd_checking"), fg=ACCENT)
        self.lbl_notes.configure(text="")

        def praca():
            try:
                self._wynik = (optical.probe(naped), None)
            except (optical.OpticalError, OSError) as exc:
                self._wynik = (None, exc)

        self._wynik = None
        watek = threading.Thread(target=praca, daemon=True)
        watek.start()

        def czekaj():
            if not self.winfo_exists():
                return
            if watek.is_alive():
                self.after(ODPYTYWANIE_MS, czekaj)
                return
            info, blad = self._wynik or (None, None)
            if blad is not None:
                self.lbl_disc.configure(text=str(blad), fg=ALERT)
                self.lbl_progress.configure(text="", fg=TEXT)
            else:
                self.info = info
                self._pokaz_plyte(info)
            self._odswiez_przyciski()

        self.after(ODPYTYWANIE_MS, czekaj)

    def _pokaz_plyte(self, info: optical.DiscInfo) -> None:
        self.lbl_disc.configure(
            text=optical.opis_plyty(info),
            fg=GOOD if info.readable else ALERT)
        # Uwagi na czerwono, bo to one decyduja, czy obraz bedzie wart
        # tego, co uzytkownik po nim oczekuje.
        self.lbl_notes.configure(text="\n".join(info.notes))
        self.lbl_progress.configure(text="", fg=TEXT)

    # -- zgrywanie ----------------------------------------------------------

    def zgraj(self) -> None:
        app = self.app
        naped = self._zapamietaj()
        if self.info is None or not self.info.readable:
            self.sprawdz_plyte()
            return
        nazwa = (self.info.label or "plyta").lower().replace(" ", "_")
        cel = filedialog.asksaveasfilename(
            parent=self, title=app.t("cd_pick_save"), defaultextension=".iso",
            initialfile=f"{nazwa}.iso",
            initialdir=app.config_data.get("cddir")
            or app.config_data.get("outdir", str(_real_home())),
            filetypes=[(app.t("dlg_filter_images"), wzorzec_pliku(".iso")),
                       (app.t("dlg_filter_all"), "*.*")])
        if not cel:
            return
        katalog = os.path.dirname(os.path.abspath(cel))
        if app.config_data.get("cddir") != katalog:
            app.config_data["cddir"] = katalog
            app._save_config()

        proby = self.liczba_prob()
        info = self.info
        self._przerwij = False
        self._biezacy = None
        self._wynik = None
        self.raport = None
        self.pasek.clear()
        self._pokaz("")
        self.lbl_progress.configure(text=app.t("cd_reading"), fg=ACCENT)

        def praca():
            try:
                self._wynik = (optical.read_to_iso(
                    naped, cel, progress=self._postep, retries=proby,
                    info=info), None)
            except (optical.OpticalError, OSError) as exc:
                self._wynik = (None, exc)

        self.worker = threading.Thread(target=praca, daemon=True)
        self.worker.start()
        self._odswiez_przyciski()
        self.after(ODPYTYWANIE_MS, self._odpytuj)

    def _postep(self, raport: optical.ReadReport) -> bool:
        """Wywolywane z watku w tle - tylko zapamietuje, niczego nie rysuje."""
        self._biezacy = raport
        return not self._przerwij

    def _odpytuj(self) -> None:
        if not self.winfo_exists():
            return
        raport = self._biezacy
        if raport is not None and not self._przerwij:
            self.pasek.show(raport.done, raport.sectors)
            klucz = "cd_progress_bad" if raport.bad else "cd_progress"
            self.lbl_progress.configure(
                text=self.app.t(klucz, done=raport.done,
                                total=raport.sectors, bad=len(raport.bad)),
                fg=ALERT if raport.bad else TEXT)
        if self.worker is not None and self.worker.is_alive():
            self.after(ODPYTYWANIE_MS, self._odpytuj)
            return
        self._zakoncz()

    def _zakoncz(self) -> None:
        self.worker = None
        raport, blad = self._wynik or (None, None)
        if blad is not None:
            self.lbl_progress.configure(text=str(blad), fg=ALERT)
            self._pokaz(str(blad))
        elif raport is not None:
            self.raport = raport
            self.pasek.show(raport.done, raport.sectors,
                            FRAME if raport.complete else ALERT)
            self.lbl_progress.configure(
                text=self.app.t("cd_done"),
                fg=GOOD if raport.complete else ALERT)
            self._pokaz(optical.opis_raportu(raport))
        self._odswiez_przyciski()
        if self._zamknij_po:
            self.destroy()

    def przerwij(self) -> None:
        if self.worker is not None:
            self._przerwij = True
            self.lbl_progress.configure(text=self.app.t("gw_cancelling"),
                                        fg=ALERT)

    def zamknij(self) -> None:
        if self.worker is None:
            self.destroy()
            return
        if messagebox.askyesno(APP_NAME, self.app.t("gw_busy_close"),
                               icon="warning", parent=self):
            self._zamknij_po = True
            self.przerwij()

    # -- raport -------------------------------------------------------------

    def _pokaz(self, tekst: str) -> None:
        self.widok.pokaz(tekst)

    def zapisz_raport(self) -> None:
        if self.raport is None:
            return
        app = self.app
        cel = filedialog.asksaveasfilename(
            parent=self, title=app.t("dlg_save_report"),
            defaultextension=".txt", initialfile="raport_plyta.txt",
            initialdir=app.config_data.get("cddir", str(_real_home())),
            filetypes=[(app.t("filter_text"), wzorzec_pliku(".txt")),
                       (app.t("dlg_filter_all"), "*.*")])
        if not cel:
            return
        try:
            with open(cel, "w", encoding="utf-8") as fh:
                fh.write(optical.opis_raportu(self.raport) + "\n")
            hand_back(cel)
        except OSError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        self.lbl_progress.configure(text=app.t("cd_report_saved", path=cel),
                                    fg=GOOD)
