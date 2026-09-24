"""
dialogs_disk.py - wybor partycji obrazu dysku twardego.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Dyskietka jest jednym systemem plikow, a dysk twardy pojemnikiem na kilka.
Gdy na obrazie jest wiecej niz jedna czytelna partycja, program pyta, ktora
pokazac - zamiast milczaco wybierac pierwsza i zostawiac uzytkownika
z wrazeniem, ze reszty dysku nie ma.

Wymaga modulu fat16.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from styles import APP_NAME, SCREEN, PANEL, FRAME, HINT, Panel

if TYPE_CHECKING:                  # tylko dla adnotacji - bez importu cyklicznego
    from gui_main import RetroZachar


class PartitionDialog(tk.Toplevel):
    """Lista partycji obrazu; wybrana zostaje w polu wynik."""

    def __init__(self, master: "RetroZachar", partycje, biezaca: int | None = None):
        super().__init__(master, bg=SCREEN)
        self.app = master
        app = master
        self.wynik: int | None = None

        self.title(app.t("part_title"))
        self.configure(padx=12, pady=12)
        self.transient(master)
        self.resizable(False, False)

        panel = Panel(self, app.t("part_title"), app.f_title)
        panel.pack(fill="both", expand=True)
        body = panel.body

        tk.Label(body, text=app.t("part_intro"), bg=PANEL, fg=HINT,
                 font=app.f_small, anchor="w", justify="left").pack(
                     fill="x", pady=(0, 8))

        czytelne = [p for p in partycje if p.readable]
        self.var = tk.StringVar(
            value=str(biezaca if biezaca is not None else czytelne[0].index))
        self.buttons = app.radio_group(
            body, self.var,
            [(str(p.index), self._opis(p)) for p in czytelne],
            font=app.f_body, fill="x")

        nieczytelne = [p for p in partycje if not p.readable]
        if nieczytelne:
            # Partycji, ktorych nie umiemy czytac, nie ukrywamy - inaczej
            # uzytkownik zobaczylby dysk mniejszy, niz jest naprawde.
            tk.Frame(body, bg=FRAME, height=1).pack(fill="x", pady=8)
            tk.Label(body, text=app.t("part_others"), bg=PANEL, fg=HINT,
                     font=app.f_small, anchor="w").pack(fill="x")
            for p in nieczytelne:
                tk.Label(body, text="   " + self._opis(p), bg=PANEL, fg=HINT,
                         font=app.f_small, anchor="w").pack(fill="x")

        dol = tk.Frame(body, bg=PANEL)
        dol.pack(fill="x", pady=(12, 0))
        app._button(dol, app.t("btn_cancel"), self.destroy).pack(side="right")
        app._button(dol, app.t("part_open"), self.zatwierdz,
                    accent=True).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self.zatwierdz())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_window(self)

    @staticmethod
    def _opis(partycja) -> str:
        mega = partycja.size / 1048576
        rozmiar = f"{mega:.0f} MB" if mega >= 1 else f"{partycja.size} B"
        opis = f"{partycja.index}.  {partycja.type_name:<16} {rozmiar:>9}"
        if partycja.bootable:
            opis += "  [startowa]"
        if partycja.logical:
            opis += "  [logiczna]"
        return opis

    def zatwierdz(self) -> None:
        try:
            self.wynik = int(self.var.get())
        except ValueError:
            self.wynik = None
        self.destroy()


def wybierz_partycje(master: "RetroZachar", partycje,
                     biezaca: int | None = None) -> int | None:
    """
    Pyta o partycje i zwraca jej numer albo None, gdy zrezygnowano.

    Przy jednej czytelnej partycji nie ma o co pytac.
    """
    czytelne = [p for p in partycje if p.readable]
    if len(czytelne) < 2:
        return czytelne[0].index if czytelne else None
    return PartitionDialog(master, partycje, biezaca).wynik


__all__ = ["PartitionDialog", "wybierz_partycje", "APP_NAME"]
