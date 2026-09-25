"""
dialogs_files.py - okna pracy z plikami na obrazie.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Podsumowanie przed skopiowaniem katalogu oraz edytor plikow
tekstowych ze swiadomoscia stron kodowych DOS.
"""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

import dostext
from fat12 import Fat12Error
from styles import (
    APP_NAME, SCREEN, PANEL, FRAME, TEXT, BRIGHT, ACCENT, HINT, ALERT,
    GOOD, FIELD, Panel, ProgressBar,
)
from system import _human, _measure_folder

if TYPE_CHECKING:                  # tylko dla adnotacji - bez importu cyklicznego
    from gui_main import RetroZachar


class FolderDialog(tk.Toplevel):
    """
    Podsumowanie przed skopiowaniem katalogu na dyskietke.

    Pokazuje, co dokladnie zostanie skopiowane. Ma to znaczenie, bo okno
    wyboru katalogu w Tk zwraca katalog *otwarty*, a nie podswietlony -
    latwo wiec wskazac o poziom za wysoko i zorientowac sie dopiero po
    fakcie. Podglad zawartosci sprawia, ze taka pomylka rzuca sie w oczy,
    a przycisk Zmien pozwala ja poprawic bez zaczynania od nowa.
    """

    def __init__(self, master: "RetroZachar", source: Path):
        super().__init__(master, bg=SCREEN)
        self.app = master
        self.source = source
        self.result: dict | None = None
        app = master

        self.title(app.t("tree_title"))
        self.configure(padx=12, pady=12)
        self.transient(master)
        self.resizable(False, False)

        panel = Panel(self, app.t("tree_title"), app.f_title)
        panel.pack(fill="both", expand=True)
        body = panel.body

        tk.Label(body, text=app.t("tree_source"), bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x")

        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x", pady=(0, 8))
        self.var_source = tk.StringVar()
        tk.Label(row, textvariable=self.var_source, bg=PANEL, fg=BRIGHT,
                 font=app.f_bold, anchor="w", justify="left",
                 wraplength=460).pack(side="left", fill="x", expand=True)
        change = app._button(row, app.t("tree_change"), self._change_source)
        change.configure(font=app.f_small, padx=6)
        change.pack(side="right", padx=(8, 0))

        self.var_content = tk.StringVar()
        self.var_free = tk.StringVar()
        tk.Label(body, textvariable=self.var_content, bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x")
        tk.Label(body, textvariable=self.var_free, bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x")
        self.lbl_fit = tk.Label(body, text="", bg=PANEL, fg=GOOD,
                                font=app.f_body, anchor="w", justify="left")
        self.lbl_fit.pack(fill="x")

        tk.Frame(body, bg=FRAME, height=1).pack(fill="x", pady=10)

        # Podglad zawartosci - najkrotsza droga do zauwazenia, ze wskazalo
        # sie katalog o poziom za wysoko.
        tk.Label(body, text=app.t("tree_preview"), bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x")
        self.lbl_preview = tk.Label(
            body, text="", bg=FIELD, fg=TEXT, font=app.f_small,
            anchor="nw", justify="left", padx=8, pady=6, height=9,
        )
        self.lbl_preview.pack(fill="x", pady=(2, 0))
        self.lbl_single = tk.Label(
            body, text="", bg=PANEL, fg=ACCENT, font=app.f_small,
            anchor="w", justify="left",
        )
        self.lbl_single.pack(fill="x", pady=(6, 0))

        tk.Frame(body, bg=FRAME, height=1).pack(fill="x", pady=10)

        self.var_root = tk.StringVar(value="with")
        tk.Label(body, text=app.t("tree_how"), bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x")
        self.choices: dict[str, tk.Radiobutton] = {}
        for value in ("with", "contents"):
            button = tk.Radiobutton(
                body, text="", value=value, variable=self.var_root,
                bg=PANEL, fg=TEXT, selectcolor=ACCENT,
                activebackground=PANEL, activeforeground=ACCENT,
                font=app.f_body, anchor="w", bd=0, highlightthickness=0,
                cursor="hand2",
            )
            button.pack(fill="x", pady=1)
            self.choices[value] = button

        tk.Label(body, text=app.t("tree_note"), bg=PANEL, fg=HINT,
                 font=app.f_small, anchor="w", justify="left",
                 ).pack(fill="x", pady=(8, 12))

        buttons = tk.Frame(body, bg=PANEL)
        buttons.pack(fill="x")
        app._button(buttons, app.t("tree_start"), self.accept,
                    accent=True).pack(side="left")
        app._button(buttons, app.t("drive_close"), self.destroy).pack(
            side="left", padx=(8, 0))

        self.var_root.trace_add("write", lambda *_: self._repaint())
        self._describe()
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_window()

    # -- opis wybranego katalogu -------------------------------------------

    def _describe(self) -> None:
        app = self.app
        files, dirs, total = _measure_folder(self.source)
        self.files, self.dirs, self.total = files, dirs, total

        self.var_source.set(str(self.source))
        self.var_content.set(app.t("tree_content", files=files, dirs=dirs,
                                   size=_human(total)))
        free = app.image.free_bytes if app.image else 0
        self.var_free.set(app.t("tree_free", free=_human(free)))
        if total <= free:
            self.lbl_fit.configure(text=app.t("tree_fits"), fg=GOOD)
        else:
            self.lbl_fit.configure(
                text=app.t("tree_too_big", missing=_human(total - free)),
                fg=ALERT)

        self.lbl_preview.configure(text=self._preview())
        # O pomylke chodzi wtedy, gdy w samym katalogu nie ma nic poza
        # jednym podkatalogiem - liczby powyzej sa zbiorcze z calego drzewa
        # i nic by tu nie powiedzialy.
        try:
            wprost = list(os.scandir(self.source))
        except OSError:
            wprost = []
        tylko_podkatalog = len(wprost) == 1 and wprost[0].is_dir()
        self.lbl_single.configure(
            text=app.t("tree_single") if tylko_podkatalog else "")
        self._repaint()

    def _preview(self) -> str:
        """Kilka pierwszych pozycji z katalogu, katalogi w nawiasach."""
        try:
            entries = sorted(os.scandir(self.source),
                             key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError as exc:
            return str(exc)
        lines = []
        for entry in entries[:8]:
            lines.append(f"  [{entry.name}]" if entry.is_dir()
                         else f"   {entry.name}")
        if len(entries) > 8:
            lines.append(self.app.t("tree_more", count=len(entries) - 8))
        return "\n".join(lines) or "  -"

    def _change_source(self) -> None:
        """Pozwala poprawic wybor bez zamykania okna."""
        chosen = filedialog.askdirectory(
            parent=self, title=self.app.t("dlg_add_folder"),
            initialdir=str(self.source),
        )
        if chosen:
            self.source = Path(chosen)
            self._describe()

    def _repaint(self) -> None:
        app = self.app
        chosen = self.var_root.get()
        labels = {
            "with": app.t("tree_with_root",
                          name=app.image.short_name(self.source.name)),
            "contents": app.t("tree_contents"),
        }
        for value, button in self.choices.items():
            active = value == chosen
            button.configure(
                text=labels[value],
                fg=ACCENT if active else TEXT,
                font=app.f_bold if active else app.f_body,
            )

    def accept(self) -> None:
        # Liczby z pomiaru ida dalej: pasek postepu przy kopiowaniu moze
        # dzieki nim pokazac prawdziwy postep, a nie samo tykanie licznika.
        self.result = {"with_root": self.var_root.get() == "with",
                       "source": self.source,
                       "files": self.files, "dirs": self.dirs}
        self.destroy()


class PostepKopiowania(tk.Toplevel):
    """
    Okno postepu dlugiego kopiowania, z mozliwoscia przerwania.

    Bez niego program przy trzech tysiacach plikow po prostu przestaje
    odpowiadac i wyglada na zawieszony - zgloszenie z uzytkowania.

    Nie ma tu watku w tle: kopiowanie idzie dalej w watku okna, a my co
    kilka pozycji oddajemy sterowanie Tkinterowi, zeby zdazyl sie
    przerysowac i przyjac klikniecie. Watek w tle wymagalby przenoszenia
    calego zapisu poza okno, a zapis do obrazu lepiej trzymac w jednym
    miejscu.
    """

    CO_ILE = 5          # co tyle pozycji odswiezamy okno

    def __init__(self, master, ile: int | None = None):
        super().__init__(master, bg=SCREEN)
        self.app = master
        app = master
        self.przerwane = False
        self.zrobione = 0
        self.ile = ile

        self.title(app.t("busy_title"))
        self.configure(padx=12, pady=12)
        self.transient(master)
        self.resizable(False, False)

        panel = Panel(self, app.t("busy_title"), app.f_title)
        panel.pack(fill="both", expand=True)
        body = panel.body

        self.lbl = tk.Label(body, text="", bg=PANEL, fg=TEXT,
                            font=app.f_body, anchor="w", width=46)
        self.lbl.pack(fill="x")
        self.lbl_plik = tk.Label(body, text="", bg=PANEL, fg=HINT,
                                 font=app.f_small, anchor="w", width=46)
        self.lbl_plik.pack(fill="x", pady=(2, 6))
        self.pasek = ProgressBar(body, height=14)
        self.pasek.pack(fill="x")
        app._button(body, app.t("busy_cancel"), self.przerwij).pack(
            pady=(10, 0))

        self.protocol("WM_DELETE_WINDOW", self.przerwij)
        self.bind("<Escape>", lambda e: self.przerwij())
        self.update()
        self.grab_set()

    def przerwij(self) -> None:
        self.przerwane = True

    def krok(self, opis: str = "") -> bool:
        """
        Zglasza kolejna pozycje. Zwraca False, gdy uzytkownik przerwal.

        Okno odswiezamy co kilka pozycji, a nie za kazdym razem: przy
        malych plikach samo rysowanie trwaloby dluzej niz kopiowanie.
        """
        self.zrobione += 1
        if self.przerwane:
            return False
        if self.zrobione % self.CO_ILE and self.zrobione != 1:
            return True
        app = self.app
        if self.ile:
            self.lbl.configure(text=app.t("busy_files", done=self.zrobione,
                                          total=self.ile))
            self.pasek.show(self.zrobione, self.ile)
        else:
            self.lbl.configure(text=app.t("busy_counting",
                                          done=self.zrobione))
        if opis:
            self.lbl_plik.configure(text=opis[-58:])
        try:
            self.update()
        except tk.TclError:
            return False          # okno zniknelo - traktujemy jak przerwanie
        return not self.przerwane

    def zamknij(self) -> None:
        try:
            self.grab_release()
            self.destroy()
        except tk.TclError:
            pass


class TextEditor(tk.Toplevel):
    """
    Edytor plikow tekstowych z dyskietki.

    Bajty DOS-owe sa pokazywane jako znaki Unicode, wiec ramki rysowane
    znakami polgraficznymi i litery diakrytyczne wygladaja tak, jak wygladaly
    na ekranie DOS - i da sie je poprawiac zwyklymi narzedziami. Przy zapisie
    wracaja do wybranej strony kodowej.

    Strony kodowe 437, 850 i 852 przypisuja kazdemu z 256 bajtow inny znak,
    wiec plik otwarty i zapisany bez zmian wraca na dyskietke identyczny.
    """

    def __init__(self, master: "RetroZachar", path: str, name: str,
                 data: bytes):
        super().__init__(master, bg=SCREEN)
        self.app = master
        self.path = path
        self.name = name
        self.original = bytes(data)
        app = master

        self.title(app.t("editor_title", name=name))
        self.configure(padx=12, pady=12)
        self.transient(master)

        codepage = app.config_data.get("codepage", dostext.DEFAULT_CODEPAGE)
        if codepage not in dostext.CODEPAGES:
            codepage = dostext.DEFAULT_CODEPAGE
        self.document = dostext.load(self.original, codepage)
        self.var_codepage = tk.StringVar(value=self.document.codepage)
        self.var_crlf = tk.BooleanVar(value=self.document.crlf)

        panel = Panel(self, app.t("editor_title", name=name), app.f_title)
        panel.pack(fill="both", expand=True)
        body = panel.body

        tk.Label(
            body, text=app.t("editor_intro"), bg=PANEL, fg=HINT,
            font=app.f_small, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 8))

        top = tk.Frame(body, bg=PANEL)
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text=app.t("editor_codepage"), bg=PANEL, fg=TEXT,
                 font=app.f_body).pack(side="left", padx=(0, 8))
        self.codepage_buttons = app.radio_group(
            top, self.var_codepage,
            [(key, key.upper()) for key in dostext.CODEPAGES],
            command=self._switch_codepage,
            side="left", padx=(0, 6))
        tk.Checkbutton(
            top, text=app.t("editor_crlf"), variable=self.var_crlf,
            bg=PANEL, fg=TEXT, selectcolor=SCREEN, activebackground=PANEL,
            activeforeground=ACCENT, font=app.f_small, bd=0,
            highlightthickness=0, cursor="hand2",
        ).pack(side="right")

        # Wpisywanie znaku po numerze, tak jak dosowe Alt+186. Tkinter nie
        # obsluguje kombinacji Alt z klawiatura numeryczna, wiec numer podaje
        # sie tutaj - a kto woli wybierac wzrokiem, ma tablice znakow.
        wpis = tk.Frame(body, bg=PANEL)
        wpis.pack(fill="x", pady=(0, 8))
        tk.Label(wpis, text=app.t("editor_code"), bg=PANEL, fg=TEXT,
                 font=app.f_body).pack(side="left")
        self.var_code = tk.StringVar()
        pole = app._entry(wpis, self.var_code, width=5)
        pole.pack(side="left", ipady=2)
        pole.bind("<Return>", lambda e: (self._insert_typed(), "break")[1])
        tk.Label(wpis, text=app.t("editor_code_hint"), bg=PANEL, fg=HINT,
                 font=app.f_small).pack(side="left", padx=(8, 0))
        self.btn_table = app._button(wpis, app.t("editor_table"),
                                     self._toggle_table)
        self.btn_table.configure(font=app.f_small, padx=6)
        self.btn_table.pack(side="right")
        self.lbl_hover = tk.Label(wpis, text="", bg=PANEL, fg=ACCENT,
                                  font=app.f_small)
        self.lbl_hover.pack(side="right", padx=(0, 10))

        self.table = tk.Frame(body, bg=PANEL)
        self._build_table()

        self.text = tk.Text(
            body, width=78, height=22, bg=FIELD, fg=TEXT, font=app.f_body,
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=FRAME, highlightcolor=ACCENT,
            insertbackground=ACCENT, selectbackground=FRAME,
            selectforeground=SCREEN, wrap="none", undo=True,
        )
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", self.document.text)
        self.text.edit_modified(False)

        scroll = ttk.Scrollbar(body, orient="horizontal",
                               command=self.text.xview,
                               style="RZ.Vertical.TScrollbar")
        scroll.pack(fill="x")
        self.text.configure(xscrollcommand=scroll.set)

        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x", pady=(10, 0))
        self.btn_save = app._button(row, app.t("editor_save"), self.save,
                                    accent=True)
        self.btn_save.pack(side="left")
        app._button(row, app.t("editor_close"), self.close).pack(
            side="left", padx=(8, 0))
        self.lbl_state = tk.Label(row, text="", bg=PANEL, fg=GOOD,
                                  font=app.f_small, anchor="e")
        self.lbl_state.pack(side="right")

        if master.image_readonly:
            self.btn_save.configure(state="disabled")
            self.lbl_state.configure(text=app.t("editor_readonly"), fg=ALERT)

        # Sama kropka wskaznika nie odroznia sie od pozostalych, wiec
        # wybrana strone kodowa wyroznia kolor i grubosc napisu.

        self.bind("<Control-s>", lambda e: (self.save(), "break")[1])
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.text.focus_set()

    # -- wstawianie znakow po kodzie ---------------------------------------

    def _insert(self, char: str) -> None:
        self.text.insert("insert", char)
        self.text.focus_set()

    def _insert_typed(self) -> None:
        """Wstawia znak o podanym numerze, jak dosowe Alt+kod."""
        raw = self.var_code.get().strip().lower()
        try:
            code = int(raw, 16) if raw.startswith("0x") else int(raw)
        except ValueError:
            return
        char = dostext.char_for_code(code, self.var_codepage.get())
        if char is None:
            self.lbl_hover.configure(
                text=self.app.t("editor_code_bad", code=code), fg=ALERT)
            return
        self._insert(char)
        self.var_code.set("")
        self.lbl_hover.configure(text="", fg=ACCENT)

    def _build_table(self) -> None:
        """Rysuje tablice 256 kodow biezacej strony kodowej."""
        for widget in self.table.winfo_children():
            widget.destroy()
        app = self.app
        codepage = self.var_codepage.get()
        for code in range(256):
            char = dostext.char_for_code(code, codepage)
            cell = tk.Label(
                self.table, text=char if char else "\u00b7",
                bg=FIELD, fg=BRIGHT if char else "#4A4A6A",
                font=app.f_body, width=2, padx=1, pady=0,
            )
            cell.grid(row=code // 16, column=code % 16, padx=1, pady=1)
            if char is None:
                continue
            cell.configure(cursor="hand2")
            cell.bind("<Button-1>", lambda e, c=char: self._insert(c))
            cell.bind("<Enter>", lambda e, n=code, c=char: self.lbl_hover
                      .configure(text=app.t("editor_hover", code=n,
                                            hex=f"{n:02X}", char=c),
                                 fg=ACCENT))
            cell.bind("<Leave>",
                      lambda e: self.lbl_hover.configure(text=""))

    def _toggle_table(self) -> None:
        if self.table.winfo_ismapped():
            self.table.pack_forget()
        else:
            self.table.pack(fill="x", pady=(0, 8), before=self.text)

    # -- strona kodowa -----------------------------------------------------

    def _switch_codepage(self) -> None:
        """
        Wczytuje plik od nowa w innej stronie kodowej.

        Przekodowanie tego, co jest w polu edycji, dawaloby smieci - te same
        znaki Unicode maja w roznych stronach inne bajty. Jedyne poprawne
        wyjscie to wrocic do oryginalnych bajtow i odczytac je inaczej.
        """
        if self.text.edit_modified() and not messagebox.askyesno(
            APP_NAME, self.app.t("editor_switch"),
            icon="warning", default="no", parent=self,
        ):
            self.var_codepage.set(self.document.codepage)
            return
        self.document = dostext.load(self.original, self.var_codepage.get())
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.document.text)
        self.text.edit_modified(False)
        self.var_crlf.set(self.document.crlf)
        self._build_table()      # inna strona kodowa to inne znaki

    # -- zapis -------------------------------------------------------------

    def save(self) -> None:
        app = self.app
        if app.image is None or app.image_readonly:
            return
        content = self.text.get("1.0", "end-1c")
        codepage = self.var_codepage.get()

        braki = dostext.unmappable(content, codepage)
        if braki and not messagebox.askyesno(
            APP_NAME,
            app.t("editor_unmappable", codepage=codepage.upper(),
                  chars=" ".join(braki[:30])),
            icon="warning", default="no", parent=self,
        ):
            return

        document = dostext.DosText(
            text=content, codepage=codepage, crlf=self.var_crlf.get(),
            eof_marker=self.document.eof_marker)
        payload = dostext.save(document)

        if not app._guard_write():
            return
        try:
            final = app.image.write_file(self.path, payload)
        except (Fat12Error, OSError) as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        app.config_data["codepage"] = codepage
        app._save_config()
        self.original = payload
        self.document = document
        self.text.edit_modified(False)
        self.lbl_state.configure(
            text=app.t("editor_saved", name=final, size=len(payload)),
            fg=GOOD)
        app._saved()
        app.status(app.t("status_edited", name=final, size=len(payload)), "ok")

    def close(self) -> None:
        if self.text.edit_modified() and not messagebox.askyesno(
            APP_NAME, self.app.t("editor_dirty"),
            icon="warning", default="no", parent=self,
        ):
            return
        self.destroy()
