"""
dialogs_diskset.py - kreator kompletu dyskietek.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Rozklada program wiekszy niz dyskietka na kolejne nosniki wraz
z instalatorem. Wymaga modulu diskset.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import diskset
import engines
from engines import ImageError
from fat12 import FLOPPY_FORMATS
from styles import (
    APP_NAME, SCREEN, PANEL, FRAME, TEXT, ACCENT, HINT, ALERT,
    GOOD, FIELD, Panel, ProgressBar,
)
from system import _real_home, hand_back, wzorce_plikow

if TYPE_CHECKING:                  # tylko dla adnotacji - bez importu cyklicznego
    from gui_main import RetroZachar


class KompletDialog(tk.Toplevel):
    """
    Rozklada program wiekszy niz dyskietka na komplet nosnikow.

    Plan powstaje osobno od nagrywania i pokazujemy go w calosci, bo pomylka
    kosztuje tu nagranie kilku dyskietek. Dopiero po obejrzeniu planu
    odblokowuje sie przycisk nagrywania.
    """

    def __init__(self, master: "RetroZachar"):
        super().__init__(master, bg=SCREEN)
        self.app = master
        self.plan = None
        app = master

        self.title(app.t("kpl_title"))
        self.configure(padx=12, pady=12)
        self.transient(master)

        # Ostatni katalog z programem, tak jak ostatni katalog na obrazy.
        # Programy lezy zwykle obok siebie, wiec okno wyboru ma startowac
        # tam, gdzie skonczylo sie poprzednio.
        self.var_source = tk.StringVar(
            value=app.config_data.get("disksetsrc", ""))
        self.var_format = tk.StringVar(value="1440")
        self.var_target = tk.StringVar(value=diskset.DOMYSLNY_KATALOG)
        self.var_drive = tk.StringVar(value=diskset.DOMYSLNY_DYSK)
        if self.var_source.get():
            self.var_target.set(
                diskset.popraw_nazwe(Path(self.var_source.get()).name))
        self.var_output = tk.StringVar(
            value=app.config_data.get("outdir", str(_real_home())))
        self.var_boot_on = tk.BooleanVar(value=False)
        self.var_boot = tk.StringVar()

        panel = Panel(self, app.t("kpl_title"), app.f_title)
        panel.pack(fill="both", expand=True)
        body = panel.body

        tk.Label(body, text=app.t("kpl_intro"), bg=PANEL, fg=HINT,
                 font=app.f_small, justify="left", anchor="w",
                 ).pack(fill="x", pady=(0, 10))

        self._pole(body, "kpl_source", self.var_source, self._pick_source)
        self._pole(body, "kpl_output", self.var_output, self._pick_output)

        tk.Label(body, text=app.t("kpl_target_drive"), bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x")
        wiersz = tk.Frame(body, bg=PANEL)
        wiersz.pack(fill="x", pady=(2, 4))
        app._entry(wiersz, self.var_drive, width=3).pack(
            side="left", ipady=3)
        tk.Label(wiersz, text="\\", bg=PANEL, fg=TEXT,
                 font=app.f_bold).pack(side="left", padx=4)
        app._entry(wiersz, self.var_target, width=12).pack(
            side="left", ipady=3)
        tk.Label(body, text=app.t("kpl_target_hint2"), bg=PANEL, fg=HINT,
                 font=app.f_small, justify="left", anchor="w",
                 ).pack(fill="x", pady=(2, 6))
        tk.Label(body, text=app.t("kpl_target_hint"), bg=PANEL, fg=HINT,
                 font=app.f_small, justify="left", anchor="w",
                 ).pack(fill="x", pady=(2, 6))

        tk.Label(body, text=app.t("kpl_format"), bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x", pady=(6, 0))
        formaty = tk.Frame(body, bg=PANEL)
        formaty.pack(fill="x")
        self.radia = app.radio_group(
            formaty, self.var_format,
            [(key, fmt.label.strip())
             for key, fmt in FLOPPY_FORMATS.items()
             if fmt.group == "popular"],
            font=app.f_small, fill="x")

        tk.Checkbutton(
            body, text=app.t("kpl_boot"), variable=self.var_boot_on,
            bg=PANEL, fg=TEXT, selectcolor=SCREEN, activebackground=PANEL,
            activeforeground=ACCENT, font=app.f_body, bd=0,
            highlightthickness=0, cursor="hand2", anchor="w",
            command=self._boot_toggled,
        ).pack(fill="x", pady=(10, 0))
        self.boot_row = tk.Frame(body, bg=PANEL)
        app._entry(self.boot_row, self.var_boot).pack(
            side="left", fill="x", expand=True, ipady=3)
        wybor = app._button(self.boot_row, "...", self._pick_boot, width=3)
        wybor.pack(side="left", padx=(6, 0))
        tk.Label(body, text=app.t("kpl_boot_hint"), bg=PANEL, fg=HINT,
                 font=app.f_small, justify="left", anchor="w",
                 ).pack(fill="x", pady=(2, 10))

        tk.Frame(body, bg=FRAME, height=1).pack(fill="x", pady=(0, 10))

        self.widok = tk.Text(
            body, width=74, height=16, bg=FIELD, fg=TEXT, font=app.f_small,
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=FRAME, wrap="none",
        )
        self.widok.configure(state="disabled")
        self.widok.pack(fill="both", expand=True)

        self.canvas = ProgressBar(body)
        self.canvas.pack(fill="x", pady=(8, 4))
        self.lbl_stan = tk.Label(body, text="", bg=PANEL, fg=ACCENT,
                                 font=app.f_small, anchor="w",
                                 justify="left")
        # Napis zawija sie do szerokosci paska zamiast rozpychac okno.
        # Dluga sciezka w komunikacie konczacym nagrywanie poszerzala okno
        # tak, ze pasek pozornie nie dochodzil do konca.
        self.canvas.bind(
            "<Configure>",
            lambda e: self.lbl_stan.configure(wraplength=max(100, e.width)),
            add="+")
        self.lbl_stan.pack(fill="x")

        przyciski = tk.Frame(body, bg=PANEL)
        przyciski.pack(fill="x", pady=(10, 0))
        app._button(przyciski, app.t("kpl_plan"), self.zaplanuj,
                    accent=True).pack(side="left")
        self.btn_build = app._button(przyciski, app.t("kpl_build"),
                                     self.nagraj)
        self.btn_build.configure(state="disabled")
        self.btn_build.pack(side="left", padx=(8, 0))
        self.btn_save = app._button(przyciski, app.t("kpl_save_plan"),
                                    self.zapisz_plan)
        self.btn_save.configure(state="disabled", font=app.f_small)
        self.btn_save.pack(side="left", padx=(8, 0))
        app._button(przyciski, app.t("drive_close"), self.destroy).pack(
            side="right")

        self.bind("<Escape>", lambda e: self.destroy())

    # -- pola z przyciskiem wyboru -----------------------------------------

    def _pole(self, parent, klucz: str, zmienna: tk.StringVar, komenda):
        app = self.app
        tk.Label(parent, text=app.t(klucz), bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x")
        wiersz = tk.Frame(parent, bg=PANEL)
        wiersz.pack(fill="x", pady=(2, 8))
        app._entry(wiersz, zmienna).pack(side="left", fill="x",
                                         expand=True, ipady=3)
        app._button(wiersz, "...", komenda, width=3).pack(
            side="left", padx=(6, 0))

    def _pick_source(self) -> None:
        wybor = filedialog.askdirectory(
            parent=self, title=self.app.t("kpl_pick_source"),
            initialdir=self.var_source.get() or str(_real_home()))
        if wybor:
            self.var_source.set(wybor)
            self._zapamietaj_zrodlo(wybor)
            # Nazwa katalogow z dyskow bywa opisowa i po mechanicznym
            # skroceniu daje bezsens, wiec to tylko propozycja do poprawienia.
            self.var_target.set(diskset.popraw_nazwe(Path(wybor).name))

    def _pick_output(self) -> None:
        wybor = filedialog.askdirectory(
            parent=self, title=self.app.t("kpl_pick_output"),
            initialdir=self.var_output.get() or str(_real_home()))
        if wybor:
            self.var_output.set(wybor)

    def _pick_boot(self) -> None:
        wybor = filedialog.askopenfilename(
            parent=self, title=self.app.t("kpl_pick_boot"),
            initialdir=self.var_output.get() or str(_real_home()),
            filetypes=[(self.app.t("dlg_filter_images"),
                        wzorce_plikow(engines.all_extensions())),
                       (self.app.t("dlg_filter_all"), "*.*")])
        if wybor:
            self.var_boot.set(wybor)
            self.var_boot_on.set(True)
            self._boot_toggled()

    def _boot_toggled(self) -> None:
        if self.var_boot_on.get():
            self.boot_row.pack(fill="x", pady=(4, 0),
                               after=self.boot_row.master.winfo_children()[
                                   self.boot_row.master.winfo_children()
                                   .index(self.boot_row) - 1])
        else:
            self.boot_row.pack_forget()

    # -- plan --------------------------------------------------------------

    def _pokaz(self, tekst: str) -> None:
        self.widok.configure(state="normal")
        self.widok.delete("1.0", "end")
        self.widok.insert("1.0", tekst)
        self.widok.configure(state="disabled")

    def zaplanuj(self) -> None:
        app = self.app
        zrodlo = self.var_source.get().strip()
        if not zrodlo:
            self.lbl_stan.configure(text=app.t("kpl_need_source"), fg=ALERT)
            return
        obraz = (self.var_boot.get().strip()
                 if self.var_boot_on.get() else None)
        try:
            self.plan = diskset.zaplanuj(
                zrodlo, self.var_format.get(),
                self.var_target.get().strip() or diskset.DOMYSLNY_KATALOG,
                obraz_bazowy=obraz or None,
                dysk_docelowy=self.var_drive.get().strip()
                or diskset.DOMYSLNY_DYSK)
        except (diskset.PaczkaError, ImageError, OSError) as exc:
            self.plan = None
            self._pokaz(str(exc))
            self.lbl_stan.configure(text=str(exc).splitlines()[0], fg=ALERT)
            self.btn_build.configure(state="disabled")
            self.btn_save.configure(state="disabled")
            return

        self._zapamietaj_zrodlo(zrodlo)
        self._pokaz(diskset.opis_planu(self.plan))
        self.lbl_stan.configure(
            text=app.t("kpl_planned", count=self.plan.liczba_dyskietek),
            fg=GOOD)
        self.btn_build.configure(state="normal")
        self.btn_save.configure(state="normal")

    def zapisz_plan(self) -> None:
        if self.plan is None:
            return
        app = self.app
        cel = filedialog.asksaveasfilename(
            parent=self, title=app.t("dlg_save_report"),
            defaultextension=".txt", initialfile="plan.txt",
            initialdir=self.var_output.get() or str(_real_home()),
            filetypes=[(app.t("filter_text"), "*.txt"),
                       (app.t("dlg_filter_all"), "*.*")])
        if not cel:
            return
        try:
            with open(cel, "w", encoding="utf-8") as fh:
                fh.write(diskset.opis_planu(self.plan) + "\n")
            hand_back(cel)
        except OSError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        self.lbl_stan.configure(text=app.t("report_saved", path=cel), fg=GOOD)

    # -- nagrywanie --------------------------------------------------------

    def nagraj(self) -> None:
        app = self.app
        if self.plan is None:
            self.lbl_stan.configure(text=app.t("kpl_need_plan"), fg=ALERT)
            return
        katalog = self.var_output.get().strip() or str(_real_home())
        if not messagebox.askyesno(
            APP_NAME,
            app.t("kpl_confirm", count=self.plan.liczba_dyskietek,
                  path=katalog),
            icon="warning", default="no", parent=self,
        ):
            return

        def postep(numer, ile, nazwa):
            self.lbl_stan.configure(text=app.t(
                "kpl_building", name=nazwa, numer=numer, ile=ile), fg=ACCENT)
            self._pasek(numer - 1, ile)
            self.update()
            return True

        obraz = (self.var_boot.get().strip()
                 if self.var_boot_on.get() else None)
        try:
            pliki = diskset.zbuduj(
                self.plan, katalog,
                etykieta=self.var_target.get().strip(),
                obraz_bazowy=obraz or None, postep=postep)
        except (diskset.PaczkaError, ImageError, OSError) as exc:
            self.lbl_stan.configure(text=str(exc), fg=ALERT)
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        for sciezka in pliki:
            hand_back(sciezka)
        self._pasek(len(pliki), len(pliki))
        self.lbl_stan.configure(
            text=app.t("kpl_done", count=len(pliki), path=katalog), fg=GOOD)
        app.config_data["outdir"] = katalog
        app._save_config()
        app.status(app.t("kpl_done", count=len(pliki), path=katalog), "ok")

    def _pasek(self, zrobione: int, ile: int) -> None:
        self.canvas.show(zrobione, ile)

    def _zapamietaj_zrodlo(self, sciezka: str) -> None:
        if self.app.config_data.get("disksetsrc") != sciezka:
            self.app.config_data["disksetsrc"] = sciezka
            self.app._save_config()
