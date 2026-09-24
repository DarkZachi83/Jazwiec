"""
dialogs_drive.py - okna obslugi fizycznych napedow.

Czesc projektu "RetroZachar - FFD Disk Maker - Jazwiec".

Lista napedow z odczytem, zapisem i diagnostyka, okno formatowania
oraz raport z operacji. Wymaga modulu usbfloppy - bez niego okno
glowne po prostu nie pokazuje menu napedow.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import usbfloppy
from usbfloppy import DriveError
from fat12 import FLOPPY_FORMATS
from styles import (
    APP_NAME, SCREEN, PANEL, FRAME, TEXT, ACCENT, HINT, ALERT,
    GOOD, FIELD, Panel, ProgressBar,
)
from system import _real_home, hand_back, wzorce_plikow

if TYPE_CHECKING:                  # tylko dla adnotacji - bez importu cyklicznego
    from gui_main import RetroZachar


# --------------------------------------------------------------------------
#  Okno fizycznego napedu
# --------------------------------------------------------------------------

class DriveDialog(tk.Toplevel):
    """
    Wykrywanie stacji dyskietek, zgrywanie nosnika do pliku .img i zapis
    obrazu z powrotem na dyskietke.

    Sama operacja idzie w osobnym watku, bo zgranie dyskietki 1,44 MB trwa
    minute, a przy uszkodzonych sektorach znacznie dluzej. Watek nie dotyka
    widgetow - odklada tylko liczniki, ktore glowny watek odczytuje co
    100 ms. Inaczej Tkinter potrafi sie zablokowac.
    """

    def __init__(self, master: "RetroZachar"):
        super().__init__(master, bg=SCREEN)
        self.app = master
        self.title(master.t("drive_title"))
        self.configure(padx=12, pady=12)
        self.transient(master)
        self.resizable(False, False)

        self.drives: list = []
        self.worker: threading.Thread | None = None
        self.cancel_requested = False
        self.live_report = None
        self.outcome: tuple | None = None

        self._build()
        self.scan()
        self._centre_on_parent()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _centre_on_parent(self) -> None:
        self.update_idletasks()
        parent = self.app
        x = parent.winfo_rootx() + (parent.winfo_width()
                                    - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height()
                                    - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    # -- budowa okna -------------------------------------------------------

    def _build(self) -> None:
        app = self.app
        panel = Panel(self, app.t("drive_title"), app.f_title)
        panel.pack(fill="both", expand=True)
        body = panel.body

        tk.Label(
            body, text=app.t("drive_intro"), bg=PANEL, fg=HINT,
            font=app.f_small, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 10))

        self.listbox = tk.Listbox(
            body, height=6, width=74, bg=FIELD, fg=TEXT,
            font=app.f_body, relief="flat", bd=0, highlightthickness=1,
            highlightbackground=FRAME, selectbackground=FRAME,
            selectforeground=SCREEN, activestyle="none",
        )
        self.listbox.pack(fill="both", expand=True)

        self.lbl_note = tk.Label(
            body, text="", bg=PANEL, fg=ACCENT, font=app.f_small, anchor="w",
            justify="left", wraplength=560,
        )
        self.lbl_note.pack(fill="x", pady=(8, 0))

        self.canvas = ProgressBar(body, height=14)
        self.canvas.pack(fill="x", pady=(10, 4))
        self.lbl_progress = tk.Label(
            body, text="", bg=PANEL, fg=TEXT, font=app.f_small, anchor="w",
        )
        self.lbl_progress.pack(fill="x")

        buttons = tk.Frame(body, bg=PANEL)
        buttons.pack(fill="x", pady=(12, 0))
        self.btn_scan = app._button(buttons, app.t("drive_scan"), self.scan)
        self.btn_read = app._button(buttons, app.t("drive_read"), self.read_disk)
        self.btn_write = app._button(buttons, app.t("drive_write"),
                                     self.write_disk)
        self.btn_browse = app._button(buttons, app.t("drive_browse"),
                                      self.browse_disk)
        self.btn_format = app._button(buttons, app.t("drive_format"),
                                      self.format_disk)
        self.btn_cancel = app._button(buttons, app.t("drive_cancel"),
                                      self.request_cancel)
        self.btn_close = app._button(buttons, app.t("drive_close"), self.close)
        for widget in (self.btn_scan, self.btn_read, self.btn_write,
                       self.btn_browse, self.btn_format, self.btn_cancel,
                       self.btn_close):
            widget.configure(font=app.f_small, padx=6)
            widget.pack(side="left", padx=(0, 6))
        self.btn_cancel.configure(state="disabled")

    # -- wykrywanie --------------------------------------------------------

    def scan(self) -> None:
        if self.worker is not None:
            return
        app = self.app
        self.listbox.delete(0, "end")
        try:
            self.drives = usbfloppy.list_drives()
        except DriveError as exc:
            self.drives = []
            self.lbl_note.configure(text=str(exc), fg=ALERT)
            return

        for drive in self.drives:
            suffix = ("" if drive.has_media
                      else "  |  " + app.t("drive_no_media"))
            self.listbox.insert("end", drive.describe() + suffix)

        blocked = [d for d in self.drives if not d.accessible]
        if not self.drives:
            self.lbl_note.configure(text=app.t("drive_none"), fg=ALERT)
        elif blocked:
            # Sam brak roota nie jest problemem - liczy sie to, czy da sie
            # otworzyc konkretne urzadzenie. Z regula udev da sie bez niego.
            key = "drive_no_admin" if os.name == "nt" else "drive_no_root"
            self.lbl_note.configure(text=app.t(key), fg=ALERT)
            if os.name == "nt":
                self._offer_elevation()
        else:
            self.listbox.selection_set(0)
            self.lbl_note.configure(
                text=app.t("drive_found", count=len(self.drives)), fg=GOOD)

    def _offer_elevation(self) -> None:
        """
        Pod Windowsem surowego dostepu do woluminu nie da sie uzyskac inaczej
        niz przez UAC. Program startuje wiec normalnie i prosi o podniesienie
        uprawnien dopiero tutaj, gdy naprawde siega po naped.
        """
        if getattr(self, "_elevation_asked", False):
            return
        self._elevation_asked = True
        if not messagebox.askyesno(
            APP_NAME, self.app.t("drive_elevate_ask"),
            icon="question", default="no", parent=self,
        ):
            return
        if usbfloppy.relaunch_elevated():
            self.app.quit_app()
        else:
            messagebox.showerror(
                APP_NAME, self.app.t("drive_elevate_failed"), parent=self)

    def _selected(self):
        picked = self.listbox.curselection()
        if not picked:
            self.lbl_note.configure(text=self.app.t("drive_pick"), fg=ALERT)
            return None
        return self.drives[picked[0]]

    # -- zgrywanie ---------------------------------------------------------

    def read_disk(self) -> None:
        app = self.app
        drive = self._selected()
        if drive is None or self.worker is not None:
            return
        if not drive.has_media:
            self.lbl_note.configure(text=app.t("drive_needs_media"), fg=ALERT)
            return

        target = filedialog.asksaveasfilename(
            parent=self, title=app.t("dlg_save_image"),
            defaultextension=".img", initialfile="dyskietka.img",
            initialdir=app.config_data.get("outdir", str(_real_home())),
            filetypes=[
                (app.t("dlg_filter_images"),
                 wzorce_plikow((".img", ".ima", ".vfd", ".dsk", ".flp"))),
                (app.t("dlg_filter_all"), "*.*"),
            ],
        )
        if not target:
            return

        def job():
            return usbfloppy.read_to_image(drive, target, self._tick)

        self._start(job, app.t("drive_reading"), ("read", target))

    # -- zapis -------------------------------------------------------------

    def write_disk(self) -> None:
        app = self.app
        drive = self._selected()
        if drive is None or self.worker is not None:
            return
        try:
            usbfloppy.check_writable(drive)
        except DriveError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        source = filedialog.askopenfilename(
            parent=self, title=app.t("dlg_pick_image"),
            initialdir=app.config_data.get("outdir", str(_real_home())),
            filetypes=[
                (app.t("dlg_filter_images"),
                 wzorce_plikow((".img", ".ima", ".vfd", ".dsk", ".flp"))),
                (app.t("dlg_filter_all"), "*.*"),
            ],
        )
        if not source:
            return

        fmt = FLOPPY_FORMATS.get(drive.format_key or "")
        if not messagebox.askyesno(
            APP_NAME,
            app.t("drive_write_confirm", device=drive.path,
                  media=fmt.label.strip() if fmt else drive.size_bytes,
                  image=Path(source).name),
            icon="warning", default="no", parent=self,
        ):
            return

        def job():
            return usbfloppy.write_from_image(
                drive, source, self._tick, verify=True)

        self._start(job, app.t("drive_writing"), ("write", source))

    def browse_disk(self) -> None:
        """
        Otwiera system plikow dyskietki w glownym panelu.

        Odczyt jest leniwy - z napedu schodzi tylko obszar systemowy, a przy
        wypakowywaniu pliku jego wlasne klastry. Przy nosniku w kiepskim
        stanie ma to znaczenie: podglad nie przechodzi calej powierzchni.
        """
        app = self.app
        drive = self._selected()
        if drive is None or self.worker is not None:
            return
        if not drive.has_media:
            self.lbl_note.configure(text=app.t("drive_needs_media"), fg=ALERT)
            return
        # Naped, ktory nie rozpoznaje nosnika, odpowiada na kazdy odczyt
        # dopiero po kilkudziesieciu sekundach. Otwarcie podgladu idzie wiec
        # w watku roboczym, zeby okno pozostalo zywe.
        def job():
            return usbfloppy.open_device_image(drive)

        self._start(job, app.t("drive_working"), ("browse", drive))

    def format_disk(self) -> None:
        app = self.app
        drive = self._selected()
        if drive is None or self.worker is not None:
            return
        try:
            usbfloppy.check_writable(drive)
        except DriveError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return

        options = FormatDialog(self, drive).result
        if options is None:
            return
        key, mode, label, needs_density = options

        fmt = FLOPPY_FORMATS.get(key)

        if needs_density:
            # Zejscie z HD na DD daje nosnik, ktorego naped nie odczyta,
            # dopoki otwor gestosci pozostaje odsloniety. Bez tego
            # ostrzezenia dyskietka po prostu "przestaje dzialac".
            current = FLOPPY_FORMATS.get(drive.format_key or "")
            target_fmt = FLOPPY_FORMATS.get(key)
            if (current and target_fmt
                    and target_fmt.size_bytes < current.size_bytes
                    and current.size_kb >= 1200):
                if not messagebox.askyesno(
                    APP_NAME,
                    app.t("hd_hole_warn", size=target_fmt.size_kb,
                          device=drive.path),
                    icon="warning", default="no", parent=self,
                ):
                    return

            # FORMAT UNIT potrafi zawiesic tansza stacje. Zanim cokolwiek
            # wyslemy, pokazujemy uzytkownikowi, co naped sam o sobie mowi.
            try:
                inquiry = usbfloppy.low_level_inquire(drive)
            except DriveError as exc:
                messagebox.showerror(APP_NAME, str(exc), parent=self)
                return
            if not messagebox.askyesno(
                APP_NAME,
                app.t("ll_warning", inquiry=inquiry,
                      size=fmt.size_kb if fmt else key),
                icon="warning", default="no", parent=self,
            ):
                return

        if not messagebox.askyesno(
            APP_NAME,
            app.t("format_confirm", device=drive.path,
                  media=fmt.label.strip() if fmt else key,
                  mode=app.t("format_" + mode)),
            icon="warning", default="no", parent=self,
        ):
            return

        def job():
            target = drive
            if needs_density:
                # Po zmianie gestosci naped zglasza inny rozmiar nosnika,
                # wiec trzeba go wykryc na nowo, zanim zapiszemy system plikow.
                self.live_report = usbfloppy.TransferReport(stage="lowlevel")
                usbfloppy.low_level_format(drive, key)
                # Naped potrzebuje chwili, zanim rozpozna nosnik o nowej
                # gestosci - odczyt geometrii od razu zwraca stara wartosc.
                target = usbfloppy.redetect(
                    drive.path, FLOPPY_FORMATS[key].size_bytes)
                if target is None:
                    raise DriveError(app.t("redetect_failed")
                                     + "\n\n" + app.t("ll_recover"))
            return usbfloppy.format_media(
                target, key, mode, label, self._tick)

        caption = (app.t("format_ll_running") if needs_density
                   else app.t("format_title"))
        self._start(job, caption, ("format", mode))

    def show_report(self, report, action: str,
                    file_path: str = "", mode: str = "") -> None:
        drive = self._selected() or self.drives[0]
        ReportDialog(
            self, usbfloppy.report_text(report, drive, action,
                                        file_path, mode))

    # -- watek i postep ----------------------------------------------------

    def _tick(self, report) -> bool:
        """Wolane z watku roboczego. Tylko odklada dane, nic nie rysuje."""
        self.live_report = report
        return not self.cancel_requested

    def _start(self, job, caption: str, context: tuple) -> None:
        self.cancel_requested = False
        self.live_report = None
        self.outcome = None
        self.context = context
        self.lbl_note.configure(text=caption, fg=ACCENT)
        for widget in (self.btn_scan, self.btn_read, self.btn_write,
                       self.btn_browse, self.btn_format, self.btn_close):
            widget.configure(state="disabled")
        self.btn_cancel.configure(state="normal")

        def run():
            try:
                self.outcome = ("ok", job())
            except (DriveError, OSError) as exc:
                self.outcome = ("error", exc)
            except Exception as exc:        # noqa: BLE001
                # Nieprzewidziany blad tez musi wrocic do glownego watku.
                # Inaczej okno zostaje z zablokowanymi przyciskami i jedynym
                # wyjsciem jest zamkniecie programu.
                self.outcome = ("error", exc)

        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()
        self.after(100, self._poll)

    def _poll(self) -> None:
        report = self.live_report
        if report is not None:
            self._draw(report.done_sectors, report.total_sectors,
                       len(report.bad_sectors), report.stage)

        if self.worker is not None and self.worker.is_alive():
            self.after(100, self._poll)
            return

        self.worker = None
        for widget in (self.btn_scan, self.btn_read, self.btn_write,
                       self.btn_browse, self.btn_format, self.btn_close):
            widget.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self._finish()

    def _draw(self, done: int, total: int, bad: int,
              stage: str = "") -> None:
        app = self.app
        if stage and not total:
            # Zmiana gestosci idzie przez zewnetrzne narzedzie i nie raportuje
            # postepu - pokazujemy sama nazwe etapu.
            self.lbl_progress.configure(text=app.t("stage_" + stage))
        elif stage:
            # Zapis i format skladaja sie z kilku przebiegow po nosniku.
            # Bez nazwy etapu pasek dobiega do konca i pozornie zamiera.
            self.lbl_progress.configure(text=app.t(
                "drive_progress_stage", stage=app.t("stage_" + stage),
                done=done, total=total, bad=bad))
        else:
            self.lbl_progress.configure(
                text=app.t("drive_progress", done=done, total=total, bad=bad))
        self.canvas.show(done, total, ALERT if bad else FRAME)

    # -- podsumowanie ------------------------------------------------------

    def _finish(self) -> None:
        app = self.app
        if self.outcome is None:
            return
        kind, payload = self.outcome
        self.outcome = None
        action, target = self.context

        if kind == "error":
            text = str(payload)
            if action == "format" and app.t("ll_recover") not in text:
                text += "\n\n" + app.t("ll_recover")
            self.lbl_note.configure(text=str(payload), fg=ALERT)
            messagebox.showerror(APP_NAME, text, parent=self)
            return

        if action == "browse":
            image = payload
            app.open_floppy_preview(image, target)
            damaged = len(image.damaged_sectors)
            if damaged:
                self.lbl_note.configure(
                    text=app.t("browse_damaged", count=damaged), fg=ALERT)
            else:
                self.lbl_note.configure(text=app.t(
                    "browse_opened", device=target.path,
                    count=len(app.tree.get_children())), fg=GOOD)
            app.status(app.t("browse_hint"))
            return

        report = payload

        if report.cancelled:
            self.lbl_note.configure(text=app.t("drive_cancelled"), fg=ALERT)
            return

        if action == "format":
            seconds = f"{report.elapsed:.0f}"
            # Najpierw odswiezenie listy, bo scan() nadpisuje pole komunikatu.
            self.scan()
            if report.bad_sectors:
                self.lbl_note.configure(text=app.t(
                    "format_done_bad", time=seconds,
                    count=report.bad_clusters), fg=ALERT)
            else:
                self.lbl_note.configure(
                    text=app.t("format_done", time=seconds), fg=GOOD)
            self.show_report(report, "format", mode=target)
            return

        if action == "read":
            hand_back(target)
            seconds = f"{report.elapsed:.0f}"
            if report.bad_sectors:
                self.lbl_note.configure(text=app.t(
                    "drive_read_bad", name=Path(target).name,
                    sectors=report.done_sectors,
                    bad=len(report.bad_sectors)), fg=ALERT)
                messagebox.showwarning(
                    APP_NAME,
                    app.t("drive_bad_report", count=len(report.bad_sectors),
                          ranges=usbfloppy._format_ranges(report.bad_sectors)),
                    parent=self)
            else:
                self.lbl_note.configure(text=app.t(
                    "drive_read_ok", name=Path(target).name,
                    sectors=report.done_sectors, time=seconds), fg=GOOD)
            self.show_report(report, "read", file_path=target)
            app._open_path(Path(target))
            return

        seconds = f"{report.elapsed:.0f}"
        if report.verified is False:
            text = app.t("drive_verify_failed",
                         count=len(report.bad_sectors))
            self.lbl_note.configure(text=text, fg=ALERT)
            messagebox.showerror(APP_NAME, text, parent=self)
        elif report.bad_sectors:
            text = app.t("drive_write_bad", count=len(report.bad_sectors))
            self.lbl_note.configure(text=text, fg=ALERT)
            messagebox.showwarning(APP_NAME, text, parent=self)
        else:
            self.lbl_note.configure(
                text=app.t("drive_write_ok", time=seconds), fg=GOOD)
        self.show_report(report, "write", file_path=str(target))

    # -- zamkniecie --------------------------------------------------------

    def request_cancel(self) -> None:
        self.cancel_requested = True
        self.btn_cancel.configure(state="disabled")

    def close(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            self.request_cancel()
            self.after(200, self.close)
            return
        self.destroy()


class FormatDialog(tk.Toplevel):
    """
    Wybor formatu, trybu i etykiety przed sformatowaniem dyskietki.

    Formaty niezgodne z obecnym nosnikiem tez sa na liscie - wybranie
    takiego uruchamia najpierw zmiane gestosci zapisu. Dzieki temu dyskietke
    1,44 MB da sie tu przerobic na 720 KB, o ile w systemie jest ufiformat.
    """

    def __init__(self, master: "DriveDialog", drive):
        super().__init__(master, bg=SCREEN)
        self.app = master.app
        self.drive = drive
        self.result: tuple | None = None
        app = self.app

        self.title(app.t("format_title"))
        self.configure(padx=12, pady=12)
        self.transient(master)
        self.resizable(False, False)

        panel = Panel(self, app.t("format_title"), app.f_title)
        panel.pack(fill="both", expand=True)
        body = panel.body

        tk.Label(
            body, text=app.t("format_intro"), bg=PANEL, fg=HINT,
            font=app.f_small, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 10))

        # Na liscie sa formaty pasujace do nosnika oraz te, ktore ufiformat
        # potrafi uzyskac przez zmiane gestosci.
        self.native = {
            key for key, fmt in FLOPPY_FORMATS.items()
            if fmt.size_bytes == drive.size_bytes
        }
        offered = list(self.native) + [
            key for key in ("720", "1440") if key not in self.native
        ]
        order = [key for key in FLOPPY_FORMATS if key in offered]

        self.var_format = tk.StringVar(
            value=drive.format_key or (order[0] if order else "1440"))
        tk.Label(body, text=app.t("format_which"), bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x")

        self.format_buttons: dict[str, tk.Radiobutton] = {}
        for key in order:
            fmt = FLOPPY_FORMATS[key]
            suffix = ("" if key in self.native
                      else "   - " + app.t("format_needs_ll"))
            button = tk.Radiobutton(
                body, text=fmt.label + suffix, value=key,
                variable=self.var_format, bg=PANEL, fg=TEXT,
                selectcolor=ACCENT, activebackground=PANEL,
                activeforeground=ACCENT, font=app.f_body, anchor="w",
                bd=0, highlightthickness=0, cursor="hand2",
            )
            button.pack(fill="x", pady=1)
            self.format_buttons[key] = button

        self.lbl_density = tk.Label(
            body, text="", bg=PANEL, fg=HINT, font=app.f_small,
            justify="left", anchor="w",
        )
        self.lbl_density.pack(fill="x", pady=(8, 0))

        tk.Frame(body, bg=FRAME, height=1).pack(fill="x", pady=10)

        self.var_mode = tk.StringVar(value="full")
        tk.Label(body, text=app.t("format_mode"), bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x")
        self.mode_buttons: dict[str, tk.Radiobutton] = {}
        for value in ("quick", "full"):
            button = tk.Radiobutton(
                body, text=app.t("format_" + value), value=value,
                variable=self.var_mode, bg=PANEL, fg=TEXT,
                selectcolor=ACCENT, activebackground=PANEL,
                activeforeground=ACCENT, font=app.f_body, anchor="w",
                bd=0, highlightthickness=0, cursor="hand2",
            )
            button.pack(fill="x", pady=1)
            self.mode_buttons[value] = button

        tk.Label(
            body, text=app.t("format_full_note"), bg=PANEL, fg=HINT,
            font=app.f_small, justify="left", anchor="w",
        ).pack(fill="x", pady=(6, 10))

        tk.Label(body, text=app.t("format_label"), bg=PANEL, fg=TEXT,
                 font=app.f_body, anchor="w").pack(fill="x")
        self.var_label = tk.StringVar()
        app._entry(body, self.var_label).pack(fill="x", ipady=4, pady=(2, 12))

        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x")
        self.btn_start = app._button(row, app.t("format_start"), self.accept,
                                     accent=True)
        self.btn_start.pack(side="left")
        app._button(row, app.t("drive_close"), self.destroy).pack(
            side="left", padx=(8, 0))

        # Sama kropka wskaznika nie odroznia sie tu od pozostalych, wiec
        # zaznaczona pozycje wyroznia dodatkowo kolor i grubosc napisu.
        self.var_format.trace_add("write", lambda *_: self._repaint())
        self.var_mode.trace_add("write", lambda *_: self._repaint())
        self._repaint()

        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_window()

    def _repaint(self) -> None:
        app = self.app
        for group, chosen in (
            (self.format_buttons, self.var_format.get()),
            (self.mode_buttons, self.var_mode.get()),
        ):
            for key, button in group.items():
                active = key == chosen
                button.configure(
                    fg=ACCENT if active else TEXT,
                    font=app.f_bold if active else app.f_body,
                )
        self._update_density_note()

    def _update_density_note(self) -> None:
        app = self.app
        key = self.var_format.get()
        if key in self.native:
            self.lbl_density.configure(text=app.t("format_native"), fg=GOOD)
            self.btn_start.configure(state="normal")
            return

        if os.name == "nt":
            letter = self.drive.path.replace("\\\\.\\", "").rstrip(":")
            size = FLOPPY_FORMATS[key].size_kb
            self.lbl_density.configure(
                text=app.t("format_ll_windows", letter=letter, size=size),
                fg=ALERT)
            self.btn_start.configure(state="disabled")
        elif usbfloppy.low_level_tool():
            # Ostrzezenie o otworze musi paść zanim uzytkownik kliknie,
            # bo po fakcie dyskietka przestaje sie czytac w tym napedzie.
            self.lbl_density.configure(
                text=app.t("format_ll_ready") + "\n\n" + app.t("ll_hole"),
                fg=ACCENT)
            self.btn_start.configure(state="normal")
        else:
            self.lbl_density.configure(
                text=app.t("format_ll_missing"), fg=ALERT)
            self.btn_start.configure(state="disabled")

    def accept(self) -> None:
        key = self.var_format.get()
        self.result = (key, self.var_mode.get(),
                       self.var_label.get().strip(),
                       key not in self.native)
        self.destroy()


class ReportDialog(tk.Toplevel):
    """Raport z operacji, z mozliwoscia zapisania do pliku tekstowego."""

    def __init__(self, master, text: str):
        super().__init__(master, bg=SCREEN)
        self.app = master.app
        self.text = text
        app = self.app

        self.title(app.t("report_title"))
        self.configure(padx=12, pady=12)
        self.transient(master)

        panel = Panel(self, app.t("report_title"), app.f_title)
        panel.pack(fill="both", expand=True)
        body = panel.body

        widget = tk.Text(
            body, width=66, height=20, bg=FIELD, fg=TEXT, font=app.f_small,
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=FRAME, insertbackground=ACCENT, wrap="none",
        )
        widget.insert("1.0", text)
        widget.configure(state="disabled")
        widget.pack(fill="both", expand=True)

        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x", pady=(10, 0))
        app._button(row, app.t("report_save"), self.save).pack(side="left")
        app._button(row, app.t("drive_close"), self.destroy).pack(
            side="left", padx=(8, 0))

        self.status = tk.Label(body, text="", bg=PANEL, fg=GOOD,
                               font=app.f_small, anchor="w")
        self.status.pack(fill="x", pady=(6, 0))
        self.bind("<Escape>", lambda e: self.destroy())

    def save(self) -> None:
        app = self.app
        target = filedialog.asksaveasfilename(
            parent=self, title=app.t("dlg_save_report"),
            defaultextension=".txt", initialfile="raport.txt",
            initialdir=app.config_data.get("outdir", str(_real_home())),
            filetypes=[(app.t("filter_text"), "*.txt"),
                       (app.t("dlg_filter_all"), "*.*")],
        )
        if not target:
            return
        try:
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(self.text + "\n")
            hand_back(target)
        except OSError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        self.status.configure(text=app.t("report_saved", path=target))
