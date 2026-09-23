"""
ui_panels.py - uklad okna glownego.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Budowa wszystkich stalych czesci okna: menu, baner, lewy panel tworzenia
obrazow, prawy panel z zawartoscia nosnika, pasek stanu i klawisze
funkcyjne. Takze blokowanie przyciskow zaleznie od stanu oraz pasek
zajetosci nosnika.

To domieszka: metody zakladaja, ze dzialaja w oknie glownym i korzystaja
z jego atrybutow przez self. Przeniesione tu bez zmian, zeby gui_main.py
dalo sie czytac - a nie przebudowane w samodzielne klasy.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from fat12 import FLOPPY_FORMATS
from features import DRIVES_AVAILABLE, GW_AVAILABLE, PACZKA_AVAILABLE
from languages import LANGUAGE_NAMES
from styles import (
    APP_NAME, APP_VERSION, SCREEN, PANEL, FRAME, TEXT, BRIGHT, ACCENT,
    HINT, ALERT, FIELD, Panel,
)
from system import _human, _znajdz_ikone


class PanelsMixin:
    """Budowa i odswiezanie stalych czesci okna glownego."""

    def _build_ui(self) -> None:
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.var_capacity.set(self.t("capacity_none"))
        self.var_filepath.set(self.t("filepath_none"))
        self._build_menu()
        self._build_banner()
        # Stopka przed obszarem glownym: pakowanie przydziela miejsce po
        # kolei, wiec obszar glowny z expand=True zabralby cala wysokosc
        # i przycial pasek klawiszy przy dolnej krawedzi okna.
        self._build_footer()
        self._build_main()
        self._bind_keys()
        self._refresh_controls()
        if self.image:
            self._update_capacity()

    def _build_menu(self) -> None:
        opts = dict(
            bg=PANEL, fg=TEXT, activebackground=FRAME,
            activeforeground=SCREEN, font=self.f_body, bd=0,
        )
        bar = tk.Menu(self, **opts)

        def item(menu, key, command, accel):
            menu.add_command(
                label=f"{self.t(key):<24}{accel}", command=command)

        disk = tk.Menu(bar, tearoff=0, **opts)
        item(disk, "menu_open", self.open_image, "F3")
        disk.add_command(label=self.t("menu_close"), command=self.close_image)
        disk.add_separator()
        if PACZKA_AVAILABLE:
            disk.add_command(label=self.t("menu_komplet"),
                             command=self.open_komplet)
            disk.add_separator()
        item(disk, "menu_label", self.change_label, "Ctrl+L")
        disk.add_separator()
        item(disk, "menu_quit", self.quit_app, "F10")
        bar.add_cascade(label=self.t("menu_disk"), menu=disk)

        files = tk.Menu(bar, tearoff=0, **opts)
        item(files, "menu_add", self.add_files, "F5")
        files.add_command(label=self.t("menu_add_folder"),
                          command=self.add_folder)
        files.add_separator()
        files.add_command(label=self.t("menu_edit"),
                          command=self.edit_selected)
        files.add_command(label=self.t("menu_new_text"),
                          command=self.new_text_file)
        files.add_separator()
        item(files, "menu_extract", self.extract_selected, "F9")
        files.add_separator()
        item(files, "menu_new_folder", self.new_folder, "F7")
        item(files, "menu_rename", self.rename_selected, "F6")
        item(files, "menu_delete", self.delete_selected, "F8")
        files.add_separator()
        item(files, "menu_refresh", self.refresh_listing, "F2")
        bar.add_cascade(label=self.t("menu_files"), menu=files)

        # Menu napedow pojawia sie, gdy dostepna jest ktorakolwiek droga do
        # fizycznej dyskietki - stacja USB albo Greaseweazle.
        if DRIVES_AVAILABLE or GW_AVAILABLE:
            drive = tk.Menu(bar, tearoff=0, **opts)
            if DRIVES_AVAILABLE:
                drive.add_command(label=self.t("menu_drive_panel"),
                                  command=self.open_drive_panel)
            if GW_AVAILABLE:
                drive.add_command(label=self.t("menu_gw"),
                                  command=self.open_gw_panel)
            bar.add_cascade(label=self.t("menu_drive"), menu=drive)

        langs = tk.Menu(bar, tearoff=0, **opts)
        for code, name in LANGUAGE_NAMES.items():
            langs.add_radiobutton(
                label=name, value=code, variable=self.var_lang,
                selectcolor=ACCENT,
                command=lambda c=code: self.set_language(c),
            )
        bar.add_cascade(label=self.t("menu_language"), menu=langs)

        helpm = tk.Menu(bar, tearoff=0, **opts)
        helpm.add_command(label=self.t("menu_shortcuts"), command=self.show_help)
        helpm.add_command(label=self.t("menu_about"), command=self.show_about)
        bar.add_cascade(label=self.t("menu_help"), menu=helpm)

        self.configure(menu=bar)

    def _build_banner(self) -> None:
        bar = tk.Frame(self, bg=FRAME)
        bar.pack(fill="x", side="top")
        tk.Label(
            bar, text="RetroZachar", bg=FRAME, fg=SCREEN,
            font=self.f_banner, padx=14, pady=6,
        ).pack(side="left")
        tk.Label(
            bar, text="FFD Disk Maker", bg=FRAME, fg=PANEL,
            font=(self.f_banner[0], 16),
        ).pack(side="left")
        tk.Label(
            bar, text="  Jazwiec", bg=FRAME, fg=SCREEN,
            font=self.f_banner,
        ).pack(side="left")
        tk.Label(
            bar, text=self.t("app_subtitle"),
            bg=FRAME, fg=SCREEN, font=self.f_small, padx=14,
        ).pack(side="right")

    def _build_main(self) -> None:
        main = tk.Frame(self, bg=SCREEN)
        main.pack(fill="both", expand=True, padx=10, pady=10)
        main.columnconfigure(0, minsize=340)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_creator(main)
        self._build_browser(main)

    def _build_creator(self, parent: tk.Misc) -> None:
        self.creator_panel = Panel(
            parent, [self.t("tab_popular"), self.t("tab_other")],
            self.f_title, on_select=self._switch_format_tab,
        )
        self.creator_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        body = self.creator_panel.body

        # Obie listy formatow leza jedna na drugiej w kontenerze o stalej
        # wysokosci, zeby pola ponizej nie przeskakiwaly przy zmianie zakladki.
        groups = ["popular", "other"]
        rows = max(
            sum(1 for f in FLOPPY_FORMATS.values() if f.group == g)
            for g in groups
        )
        stack = tk.Frame(body, bg=PANEL, height=rows * 24 + 4)
        stack.pack(fill="x")
        stack.pack_propagate(False)

        self.radios: dict[str, tk.Radiobutton] = {}
        self.format_pages: list[tk.Frame] = []
        for group in groups:
            page = tk.Frame(stack, bg=PANEL)
            for key, fmt in FLOPPY_FORMATS.items():
                if fmt.group != group:
                    continue
                button = tk.Radiobutton(
                    page, text=fmt.label, value=key, variable=self.var_format,
                    bg=PANEL, fg=TEXT, selectcolor=ACCENT,
                    activebackground=PANEL, activeforeground=ACCENT,
                    font=self.f_body, anchor="w", bd=0, highlightthickness=0,
                    cursor="hand2",
                )
                button.pack(fill="x", pady=1)
                self.radios[key] = button
            self.format_pages.append(page)

        self.creator_panel.active = self.format_tab
        self.creator_panel._paint_tabs()
        self.format_pages[self.format_tab].pack(fill="both", expand=True)

        self.lbl_chosen = tk.Label(
            body, text="", bg=PANEL, fg=BRIGHT, font=self.f_bold, anchor="w",
        )
        self.lbl_chosen.pack(fill="x", pady=(10, 0))
        self.lbl_hint = tk.Label(
            body, text="", bg=PANEL, fg=HINT, font=self.f_small, anchor="w",
        )
        self.lbl_hint.pack(fill="x", pady=(2, 12))

        tk.Frame(body, bg=FRAME, height=1).pack(fill="x", pady=(0, 12))

        self._caption(body, self.t("field_filename")).pack(fill="x")
        self._caption(
            body, self.t("field_filename_note")
        ).configure(fg=HINT, font=self.f_small)
        entry = self._entry(body, self.var_filename)
        entry.pack(fill="x", ipady=4, pady=(2, 10))
        entry.bind("<Return>", lambda e: self.create_image())

        self._caption(body, self.t("field_volume")).pack(fill="x")
        self._entry(body, self.var_label).pack(fill="x", ipady=4, pady=(2, 10))

        self._caption(body, self.t("field_outdir")).pack(fill="x")
        picker = tk.Frame(body, bg=PANEL)
        picker.pack(fill="x", pady=(2, 14))
        self._entry(picker, self.var_outdir).pack(
            side="left", fill="x", expand=True, ipady=4)
        self._button(picker, "...", self.pick_outdir, width=3).pack(
            side="left", padx=(6, 0))

        self._button(
            body, self.t("button_create"), self.create_image, accent=True,
        ).pack(fill="x", ipady=4)

        # Grafika pod przyciskiem. Tkinter nie skaluje obrazow z zachowaniem
        # proporcji - potrafi tylko dzielic rozmiar przez liczby calkowite -
        # wiec plik jest przygotowany z gory w docelowej szerokosci panelu.
        self._grafika = None
        sciezka = _znajdz_ikone("jazwiec-panel.png")
        if sciezka:
            try:
                self._grafika = tk.PhotoImage(file=sciezka, master=self)
            except tk.TclError:
                self._grafika = None
        if self._grafika is not None:
            ramka = tk.Frame(body, bg=PANEL)
            ramka.pack(fill="x", side="bottom", pady=(12, 0))
            tk.Label(ramka, image=self._grafika, bg=PANEL, bd=0,
                     highlightthickness=0).pack()

        self._update_hint()

    def _build_browser(self, parent: tk.Misc) -> None:
        panel = Panel(parent, self.t("panel_contents"), self.f_title)
        panel.grid(row=0, column=1, sticky="nsew")
        self.browser_panel = panel
        body = panel.body
        body.rowconfigure(3, weight=1)
        body.columnconfigure(0, weight=1)

        tk.Label(
            body, textvariable=self.var_location, bg=FIELD, fg=ACCENT,
            font=self.f_bold, anchor="w", padx=8, pady=4,
        ).grid(row=0, column=0, columnspan=2, sticky="ew")

        # Pelna sciezka pliku obrazu. Bez niej nie widac, gdzie na dysku
        # wyladowal swiezo utworzony obraz ani co sie wlasnie edytuje.
        tk.Label(
            body, textvariable=self.var_filepath, bg=PANEL, fg=HINT,
            font=self.f_small, anchor="w", padx=2,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 0))

        toolbar = tk.Frame(body, bg=PANEL)
        toolbar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
        actions = (
            ("button_open", self.open_image),
            ("button_add", self.add_files),
            ("button_add_folder", self.add_folder),
            ("button_extract", self.extract_selected),
            ("button_new_folder", self.new_folder),
            ("button_delete", self.delete_selected),
        )
        for col, (key, cmd) in enumerate(actions):
            # Bez uniform - rowne kolumny wymuszalyby szerokosc
            # najdluzszego przycisku na wszystkich i napisy sie ucinaly.
            toolbar.columnconfigure(col, weight=1)
            btn = self._button(toolbar, self.t(key), cmd)
            btn.configure(padx=2, font=self.f_small)
            btn.grid(row=0, column=col, sticky="ew", padx=(0, 4))
            if key != "button_open":
                self._needs_image(btn)
            if key in ("button_add", "button_add_folder",
                       "button_new_folder", "button_delete"):
                self._needs_writable(btn)

        columns = ("size", "date", "attr")
        tree = ttk.Treeview(
            body, columns=columns, style="RZ.Treeview",
            selectmode="extended", show="tree headings",
        )
        tree.heading("#0", text=self.t("column_name"), anchor="w")
        tree.heading("size", text=self.t("column_size"), anchor="e")
        tree.heading("date", text=self.t("column_date"), anchor="w")
        tree.heading("attr", text=self.t("column_attr"), anchor="w")
        tree.column("#0", width=150, minwidth=110, anchor="w")
        tree.column("size", width=92, anchor="e", stretch=False)
        tree.column("date", width=152, anchor="w", stretch=False)
        tree.column("attr", width=92, anchor="w", stretch=False)
        tree.grid(row=3, column=0, sticky="nsew")
        tree.tag_configure("dir", foreground=BRIGHT)
        tree.tag_configure("up", foreground=ACCENT)
        tree.tag_configure("hidden", foreground=HINT)
        tree.bind("<Double-1>", self._on_activate)
        tree.bind("<Return>", self._on_activate)
        self.tree = tree

        scroll = ttk.Scrollbar(
            body, orient="vertical", command=tree.yview,
            style="RZ.Vertical.TScrollbar",
        )
        scroll.grid(row=3, column=1, sticky="ns")
        tree.configure(yscrollcommand=scroll.set)

        gauge = tk.Frame(body, bg=PANEL)
        gauge.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.canvas = tk.Canvas(
            gauge, height=14, bg=FIELD, bd=0, highlightthickness=1,
            highlightbackground=FRAME,
        )
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", lambda e: self._draw_gauge())
        tk.Label(
            gauge, textvariable=self.var_capacity, bg=PANEL, fg=TEXT,
            font=self.f_small, anchor="w",
        ).pack(fill="x", pady=(4, 0))

    def _build_footer(self) -> None:
        # Pasek stanu na czarnym tle gubil sie na dole okna. Wlasne tlo
        # i pionowy znacznik po lewej robia z niego czytelna wstege.
        bar = tk.Frame(self, bg=SCREEN)
        bar.pack(fill="x", side="bottom")
        keys = [
            ("F1", "key_help", self.show_help),
            ("F2", "key_refresh", self.refresh_listing),
            ("F3", "key_open", self.open_image),
            ("F4", "key_add_folder", self.add_folder),
            ("F5", "key_add", self.add_files),
            ("F6", "key_rename", self.rename_selected),
            ("F7", "key_folder", self.new_folder),
            ("F8", "key_delete", self.delete_selected),
            ("F9", "key_extract", self.extract_selected),
            ("F10", "key_quit", self.quit_app),
        ]
        for i, (key, label_key, cmd) in enumerate(keys):
            bar.columnconfigure(i, weight=1)
            cell = tk.Frame(bar, bg=SCREEN, cursor="hand2")
            cell.grid(row=0, column=i, sticky="ew", padx=1)
            tk.Label(
                cell, text=key, bg=SCREEN, fg=TEXT, font=self.f_small,
            ).pack(side="left", padx=(4, 2))
            tk.Label(
                cell, text=self.t(label_key), bg=FRAME, fg=SCREEN,
                font=self.f_small, anchor="w",
            ).pack(side="left", fill="x", expand=True, ipady=3, padx=(0, 2))
            for widget in (cell, *cell.winfo_children()):
                widget.bind("<Button-1>", lambda e, c=cmd: c())

        # Przypiete do dolu. Obszar glowny jest pakowany po stopce, wiec bez
        # tego pasek stanu wyladowalby tuz pod banerem, u gory okna.
        band = tk.Frame(self, bg=FIELD)
        band.pack(fill="x", side="bottom", padx=10, pady=(0, 6))
        self.status_mark = tk.Frame(band, bg=ACCENT, width=4)
        self.status_mark.pack(side="left", fill="y")
        self.lbl_status = tk.Label(
            band, textvariable=self.var_status, bg=FIELD, fg=ACCENT,
            font=self.f_body, anchor="w", padx=10, pady=6,
        )
        self.lbl_status.pack(side="left", fill="x", expand=True)

    def _bind_keys(self) -> None:
        for key, cmd in (
            ("<F1>", self.show_help),
            ("<F2>", self.refresh_listing),
            ("<F3>", self.open_image),
            ("<F4>", self.add_folder),
            ("<F5>", self.add_files),
            ("<F6>", self.rename_selected),
            ("<F7>", self.new_folder),
            ("<F8>", self.delete_selected),
            ("<F9>", self.extract_selected),
            ("<F10>", self.quit_app),
            ("<Control-l>", self.change_label),
        ):
            self.bind(key, lambda e, c=cmd: (c(), "break")[1])

        # Te dwa dzialaja tylko na liscie plikow, zeby nie przeszkadzaly
        # podczas wpisywania nazw w polach tekstowych.
        for key, cmd in (
            ("<Delete>", self.delete_selected),
            ("<BackSpace>", self.go_up),
        ):
            self.tree.bind(key, lambda e, c=cmd: (c(), "break")[1])

    def _needs_image(self, widget: tk.Widget) -> None:
        """Rejestruje przycisk, ktory dziala tylko przy otwartym obrazie."""
        if not hasattr(self, "_guarded_list"):
            self._guarded_list = []
        self._guarded_list.append(widget)

    def _needs_writable(self, widget: tk.Widget) -> None:
        """Przycisk zmieniajacy zawartosc - bezuzyteczny przy podgladzie."""
        if not hasattr(self, "_writable_list"):
            self._writable_list = []
        self._writable_list.append(widget)

    def _refresh_controls(self) -> None:
        writable = ("normal" if self.image and not self.image_readonly
                    else "disabled")
        for widgets, state in (
            (getattr(self, "_guarded_list", []),
             "normal" if self.image else "disabled"),
            (getattr(self, "_writable_list", []), writable),
        ):
            for widget in widgets:
                try:
                    widget.configure(state=state)
                except tk.TclError:
                    pass          # widget z poprzedniej wersji okna

    def _switch_format_tab(self, index: int) -> None:
        """Pokazuje jedna z dwoch list formatow. Wybor pozostaje bez zmian."""
        self.format_tab = index
        for page in self.format_pages:
            page.pack_forget()
        self.format_pages[index].pack(fill="both", expand=True)

    def _update_hint(self) -> None:
        chosen = self.var_format.get()
        for key, button in getattr(self, "radios", {}).items():
            active = key == chosen
            button.configure(
                fg=ACCENT if active else TEXT,
                font=self.f_bold if active else self.f_body,
            )
        if not hasattr(self, "lbl_hint"):
            return
        fmt = FLOPPY_FORMATS[chosen]
        # Nazwa wybranego formatu jest widoczna takze wtedy, gdy pochodzi
        # z drugiej zakladki - inaczej nie wiadomo, co sie wlasnie utworzy.
        self.lbl_chosen.configure(
            text=self.t("chosen", label=fmt.label.strip()))
        note = (
            self.t("geometry_sector", bytes=fmt.bytes_per_sector)
            if fmt.bytes_per_sector != 512 else ""
        )
        self.lbl_hint.configure(text=self.t(
            "geometry", size=_human(fmt.size_bytes),
            sectors=fmt.total_sectors, root=fmt.root_entries) + note)

    def _update_capacity(self) -> None:
        if not self.image:
            return
        free = self.image.free_bytes
        total = self.image.total_bytes
        self.var_capacity.set(self.t(
            "capacity", used=_human(total - free),
            free=_human(free), total=_human(total),
        ))
        self._draw_gauge()

    def _draw_gauge(self) -> None:
        self.canvas.delete("all")
        if not self.image:
            return
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 1:
            return
        used = self.image.total_bytes - self.image.free_bytes
        ratio = used / self.image.total_bytes if self.image.total_bytes else 0
        fill = ALERT if ratio > 0.92 else (ACCENT if ratio > 0.75 else FRAME)
        self.canvas.create_rectangle(
            0, 0, max(2, int(width * ratio)), height, fill=fill, width=0,
        )
