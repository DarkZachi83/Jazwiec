#!/usr/bin/env python3
"""
RetroZachar FFD Disk Maker
Tworzenie i edycja obrazow dyskietek FAT12 dla emulatorow (86Box, PCem, DOSBox).

Program dziala tak samo na Linuksie i na Windowsie. Nie wymaga uprawnien
administratora, nie montuje niczego w systemie i nie korzysta z zewnetrznych
narzedzi - obrazy sa budowane bajt po bajcie przez modul fat12.

Interfejs jest dostepny po polsku i po angielsku; wybor zapamietuje sie
w pliku ~/.retrozachar.json.

Uruchomienie:  python3 main.py
"""

from __future__ import annotations

import os

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

try:
    from languages import DEFAULT_LANGUAGE, LANGUAGE_NAMES, translate
except ImportError:
    sys.exit(
        "Nie znaleziono modulu languages.py.\n"
        "Plik languages.py musi lezec w katalogu programu."
    )

try:
    import dostext
except ImportError:
    sys.exit(
        "Nie znaleziono modulu dostext.py.\n"
        "Plik dostext.py musi lezec w katalogu programu."
    )

try:
    import engines
    from engines import ImageError, UnknownFormat
except ImportError:
    sys.exit(
        "Nie znaleziono modulu engines.py.\n"
        "Plik engines.py musi lezec w katalogu programu."
    )

try:
    import fat12
    from fat12 import FLOPPY_FORMATS
except ImportError:
    sys.exit(translate(DEFAULT_LANGUAGE, "error_no_engine"))

from features import (
    DRIVES_AVAILABLE, GW_AVAILABLE, PACZKA_AVAILABLE, DriveDialog,
    GwDialog, KompletDialog, fat16, usbfloppy, wybierz_partycje,
)
from styles import StyleMixin
from ui_panels import PanelsMixin


from styles import (
    APP_NAME, APP_VERSION, SCREEN, ACCENT, ALERT, GOOD, _pick_font,
)
from dialogs_files import FolderDialog, PostepKopiowania, TextEditor
from system import (
    CONFIG_FILE, hand_back, wzorce_plikow,
    _stamp, _human,
)


class RetroZachar(StyleMixin, PanelsMixin, tk.Tk):

    def __init__(self) -> None:
        super().__init__()
        self.configure(bg=SCREEN)
        self.minsize(940, 720)
        self.geometry("1100x860")

        self.config_data = self._load_config()
        self.lang = self.config_data.get("language", DEFAULT_LANGUAGE)
        if self.lang not in LANGUAGE_NAMES:
            self.lang = DEFAULT_LANGUAGE
        fat12.set_language(self.lang)
        if DRIVES_AVAILABLE:
            usbfloppy.set_language(self.lang)

        mono = _pick_font(self, [
            "Consolas", "DejaVu Sans Mono", "Liberation Mono",
            "Courier New", "Menlo", "Monaco",
        ])
        self.f_body = (mono, 10)
        self.f_bold = (mono, 10, "bold")
        self.f_title = (mono, 11, "bold")
        self.f_banner = (mono, 16, "bold")
        self.f_small = (mono, 9)

        # Typ obrazu zalezy od silnika, ktory rozpoznal plik.
        self.image = None
        self.image_path: Path | None = None
        self.image_title: str | None = None
        self.image_readonly = False
        self.image_stamp = None
        self.cwd = "/"
        self.rows: dict[str, object] = {}

        # Zmienne przezywaja przebudowe okna przy zmianie jezyka.
        self.var_format = tk.StringVar(value="1440")
        self.var_format.trace_add("write", lambda *_: self._update_hint())
        self.var_filename = tk.StringVar()
        self.var_label = tk.StringVar()
        self.var_outdir = tk.StringVar(
            value=self.config_data.get("outdir", str(Path.home()))
        )
        self.var_lang = tk.StringVar(value=self.lang)
        self.var_status = tk.StringVar()
        self.var_capacity = tk.StringVar()
        self.var_location = tk.StringVar(value="")
        self.var_filepath = tk.StringVar()
        self.format_tab = 0

        self._ustaw_ikone()
        self._build_styles()
        self._build_ui()
        self.status(self.t("status_ready"))

        self.protocol("WM_DELETE_WINDOW", self.quit_app)


    # -- jezyk -------------------------------------------------------------

    def t(self, key: str, **kwargs) -> str:
        """Napis interfejsu w biezacym jezyku."""
        return translate(self.lang, key, **kwargs)

    def set_language(self, lang: str) -> None:
        """
        Przelacza jezyk. Okno jest budowane od nowa, bo tlumaczenia siedza
        takze w naglowkach tabeli i pozycjach menu, ktorych nie da sie
        podpiac pod zmienne. Otwarty obraz i biezacy katalog zostaja.
        """
        if lang == self.lang or lang not in LANGUAGE_NAMES:
            self.var_lang.set(self.lang)
            return

        self.lang = lang
        self.var_lang.set(lang)
        fat12.set_language(lang)
        if DRIVES_AVAILABLE:
            usbfloppy.set_language(lang)
        self.config_data["language"] = lang
        self._save_config()

        for widget in self.winfo_children():
            widget.destroy()
        self.configure(menu="")
        # Obie listy trzymaja widgety starego okna. Bez wyczyszczenia obu
        # kolejne odswiezenie signeloby po zniszczonych przyciskach.
        self._guarded_list = []
        self._writable_list = []
        self._build_ui()
        if self.image:
            self.refresh_listing()
        self.status(self.t("status_language"), "ok")


    # -- wyglad ------------------------------------------------------------







    # -- menu --------------------------------------------------------------


    # -- naglowek ----------------------------------------------------------


    # -- glowna czesc ------------------------------------------------------






    # -- stan interfejsu ---------------------------------------------------






    def status(self, text: str, kind: str = "info") -> None:
        colour = {"info": ACCENT, "ok": GOOD, "error": ALERT}.get(kind, ACCENT)
        self.var_status.set(text)
        self.lbl_status.configure(fg=colour)
        self.status_mark.configure(bg=colour)

    def _error(self, exc: Exception) -> None:
        messagebox.showerror(APP_NAME, str(exc), parent=self)
        self.status(str(exc).replace("\n", " "), "error")

    # -- tworzenie obrazu --------------------------------------------------

    def pick_outdir(self) -> None:
        chosen = filedialog.askdirectory(
            parent=self, title=self.t("dlg_outdir"),
            initialdir=self.var_outdir.get() or str(Path.home()),
        )
        if chosen:
            self.var_outdir.set(chosen)

    def create_image(self) -> None:
        name = self.var_filename.get().strip()
        if not name:
            self.status(self.t("status_need_name"), "error")
            return
        outdir = Path(self.var_outdir.get().strip() or Path.home())
        if not name.lower().endswith(".img"):
            name += ".img"
        target = outdir / name

        try:
            outdir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._error(exc)
            return

        if target.exists():
            if not messagebox.askyesno(
                APP_NAME, self.t("dlg_overwrite", path=target),
                icon="warning", default="no", parent=self,
            ):
                self.status(self.t("status_cancelled"))
                return

        fmt = FLOPPY_FORMATS[self.var_format.get()]
        try:
            fat12.format_image(
                target, fmt, self.var_label.get().strip(), overwrite=True
            )
        except (ImageError, OSError) as exc:
            self._error(exc)
            return

        hand_back(target)
        self.config_data["outdir"] = str(outdir)
        self._save_config()
        # Czyscimy oba pola. Zostawienie samej etykiety sprawialo, ze kolejna
        # dyskietka po cichu dziedziczyla nazwe wolumenu poprzedniej.
        self.var_filename.set("")
        self.var_label.set("")
        self._open_path(target)
        self.status(self.t("status_created_full", path=target), "ok")

    # -- obraz -------------------------------------------------------------

    def open_image(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title=self.t("dlg_open"),
            initialdir=self.config_data.get("outdir", str(Path.home())),
            filetypes=[
                (self.t("dlg_filter_images"),
                 wzorce_plikow(engines.all_extensions())),
                (self.t("dlg_filter_all"), "*.*"),
            ],
        )
        if path:
            self._open_path(Path(path))

    def _open_path(self, path: Path) -> None:
        try:
            image = engines.open_image(path)
        except UnknownFormat:
            # Osobno, bo sam komunikat "nieznany format" nic nie mowi.
            # Warto podac, co program w ogole potrafi otworzyc.
            self._error(ImageError(self.t(
                "unknown_format", name=Path(path).name,
                formats=engines.describe_supported())))
            return
        except (ImageError, OSError) as exc:
            self._error(exc)
            return
        if self.image:
            self.image.close()
        self.image = image
        self.image_path = path
        self.image_title = None
        # Obrazy dyskow twardych sa tylko do odczytu i same to o sobie
        # mowia. Wczesniej okno zakladalo, ze kazdy otwarty plik da sie
        # zmieniac, wiec przyciski zapisu byly czynne i konczyly sie bledem.
        self.image_readonly = bool(getattr(image, "read_only", False))
        self.image_stamp = _stamp(path)
        self.cwd = "/"
        self._refresh_controls()
        self.refresh_listing()
        self.status(self.t(
            "status_opened", name=path.name, fmt=image.format_name), "ok")
        # Przy kilku czytelnych partycjach pytamy od razu, ktora pokazac -
        # inaczej uzytkownik widzi pierwsza i nie wie, ze sa inne.
        if self._partycje_do_wyboru() and wybierz_partycje is not None:
            self.choose_partition(pytaj_zawsze=False)

    def _obraz_dysku(self) -> bool:
        """Czy otwarty obraz to dysk twardy, a nie dyskietka w napedzie."""
        return hasattr(self.image, "partitions")

    def _partycje_do_wyboru(self) -> bool:
        partycje = getattr(self.image, "partitions", None) or []
        return len([p for p in partycje if p.readable]) > 1

    def choose_partition(self, pytaj_zawsze: bool = True) -> None:
        """
        Pokazuje inna partycje tego samego obrazu.

        Obraz otwieramy od nowa, bo kazda partycja to osobny system plikow
        i osobna tablica FAT.
        """
        if not self.image or wybierz_partycje is None:
            return
        partycje = getattr(self.image, "partitions", None) or []
        if not partycje:
            return
        biezaca = getattr(self.image, "partition_index", None)
        wybor = wybierz_partycje(self, partycje, biezaca)
        if wybor is None or (not pytaj_zawsze and wybor == biezaca):
            return
        sciezka = self.image_path
        try:
            nowy = fat16.HardDiskImage(sciezka, partition=wybor)
        except (ImageError, OSError) as exc:
            self._error(exc)
            return
        self.image.close()
        self.image = nowy
        self.image_readonly = True
        self.cwd = "/"
        self._refresh_controls()
        self.refresh_listing()
        self.status(self.t("status_partition", index=wybor,
                           label=nowy.get_label() or nowy.format_name), "ok")

    def unlock_disk(self) -> None:
        """
        Otwiera obraz dysku do zapisu, po wyraznym potwierdzeniu.

        Obrazy dyskow otwieraja sie tylko do odczytu i tak ma zostac przy
        zwyklym otwarciu pliku. Zapis do obrazu, ktorego uzywa wlasnie
        maszyna wirtualna, niszczy caly system plikow - decyzja musi byc
        swiadoma, a nie skutkiem klikniecia nie tam.
        """
        if not self.image or not self._obraz_dysku():
            self.status(self.t("unlock_nothing"), "error")
            return
        if not self.image_readonly:
            self.status(self.t("unlock_locked"), "ok")
            return
        if not messagebox.askyesno(
                APP_NAME, self.t("unlock_warn", path=self.image_path),
                icon="warning", default="no", parent=self):
            return
        partycja = getattr(self.image, "partition_index", None)
        try:
            nowy = fat16.HardDiskImage(self.image_path, read_only=False,
                                       partition=partycja)
        except (ImageError, OSError) as exc:
            self.status(self.t("unlock_failed", reason=exc), "error")
            return
        self.image.close()
        self.image = nowy
        self.image_readonly = False
        self.image_stamp = _stamp(self.image_path)
        self._refresh_controls()
        self.refresh_listing()
        self.status(self.t("unlock_done", path=self.image_path.name), "ok")

    def close_image(self) -> None:
        if self.image:
            self.image.close()
        self.image = None
        self.image_path = None
        self.image_title = None
        self.image_readonly = False
        self.cwd = "/"
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        self.browser_panel.set_title(self.t("panel_contents"))
        self.var_location.set("")
        self.var_capacity.set(self.t("capacity_none"))
        self.var_filepath.set(self.t("filepath_none"))
        self._draw_gauge()
        self._refresh_controls()
        self.status(self.t("status_closed"))

    def change_label(self) -> None:
        if not self.image:
            return
        new = simpledialog.askstring(
            APP_NAME, self.t("dlg_new_label"),
            initialvalue=self.image.get_label(), parent=self,
        )
        if new is None or not self._guard_write():
            return
        try:
            self.image.set_label(new)
        except (ImageError, OSError) as exc:
            self._error(exc)
            return
        self._saved()
        self.status(
            self.t("status_label", label=self.image.get_label()), "ok")

    # -- lista plikow ------------------------------------------------------

    def _external_change(self) -> bool:
        """
        Czy plik obrazu zmienil sie poza programem.

        Ma znaczenie, gdy ten sam .img jest jednoczesnie zamontowany
        w emulatorze. Program trzyma caly obraz w pamieci i przy zapisie
        odklada plik w calosci, wiec bez tej kontroli po cichu skasowalby
        wszystko, co goscia zapisal w miedzyczasie.
        """
        if (not self.image or self.image_readonly
                or self.image_path is None or self.image_stamp is None):
            return False
        return _stamp(self.image_path) != self.image_stamp

    def _reload_image(self) -> bool:
        """Wczytuje obraz od nowa z dysku, zachowujac biezacy katalog."""
        if self.image_path is None:
            return False
        where = self.cwd
        try:
            fresh = engines.open_image(self.image_path)
        except (ImageError, OSError) as exc:
            self._error(exc)
            return False
        if self.image:
            self.image.close()
        self.image = fresh
        self.image_stamp = _stamp(self.image_path)
        self.cwd = where if fresh.exists(where) else "/"
        return True

    def _guard_write(self) -> bool:
        """
        Pyta, co zrobic, gdy plik zmienil sie poza programem.
        Zwraca True, jesli operacja moze isc dalej.
        """
        if not self._external_change():
            return True
        answer = messagebox.askyesnocancel(
            APP_NAME, self.t("ext_warning"), icon="warning", parent=self)
        if answer is None:
            self.status(self.t("status_cancelled"))
            return False
        if answer:
            if self._reload_image():
                self.refresh_listing()
                self.status(self.t("ext_reloaded"), "error")
            return False
        self.status(self.t("ext_lost"), "error")
        return True

    def _saved(self) -> None:
        """Po wlasnym zapisie: zapamietaj nowy stan pliku i odswiez liste."""
        self.image_stamp = _stamp(self.image_path)
        self.refresh_listing()

    def refresh_listing(self) -> None:
        # Zmiana pliku spoza programu - pokazujemy jego biezaca tresc,
        # zamiast trwac przy nieaktualnej kopii z pamieci.
        if self._external_change() and self._reload_image():
            self.status(self.t("ext_reloaded"), "error")

        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        if not self.image:
            return

        try:
            entries = self.image.listdir(self.cwd)
        except ImageError as exc:
            self.cwd = "/"
            entries = self.image.listdir("/")
            self.status(str(exc), "error")

        if self.cwd != "/":
            iid = self.tree.insert(
                "", "end", text="..",
                values=(self.t("row_up"), "", ""), tags=("up",),
            )
            self.rows[iid] = ".."

        for entry in entries:
            size = self.t("row_dir") if entry.is_dir else _human(entry.size)
            when = entry.modified.strftime("%Y-%m-%d %H:%M") \
                if entry.modified else ""
            tags = ["dir"] if entry.is_dir else []
            if entry.is_hidden:
                tags.append("hidden")
            iid = self.tree.insert(
                "", "end", text=entry.name,
                values=(size, when, entry.attr_string()), tags=tuple(tags),
            )
            self.rows[iid] = entry

        label = self.image.get_label()
        if label.upper() in ("NO NAME", "BEZ NAZWY"):
            label = ""          # brak etykiety, nie etykieta o tresci "brak"
        title = self.image_title or f" {self.image_path.name} "
        if label:
            title += f"[{label}] "
        if self.image_readonly:
            # Podglad dyskietki w napedzie i obraz dysku twardego sa oba
            # tylko do odczytu, ale z zupelnie innych powodow - napis ma
            # mowic, na co uzytkownik patrzy.
            title += self.t("browse_readonly_disk" if self._obraz_dysku()
                            else "browse_readonly")
        self.browser_panel.set_title(title)
        # Litera napedu wedlug tego, na co patrzymy: dyskietki to A:,
        # dyski twarde C:. Drobiazg, ale wprowadzalby w blad.
        litera = "C:" if self._obraz_dysku() else "A:"
        self.var_location.set(
            litera + self.cwd.replace("/", "\\")
            + "        " + self.image.format_name
        )
        key = ("filepath" if not self.image_readonly or self._obraz_dysku()
               else "filepath_device")
        self.var_filepath.set(self.t(key, path=self.image_path))
        self._update_capacity()



    def _selection(self) -> list:
        return [
            self.rows[iid] for iid in self.tree.selection()
            if self.rows.get(iid) != ".."
        ]

    def _on_activate(self, _event=None) -> str:
        iid = self.tree.focus()
        item = self.rows.get(iid)
        if item == "..":
            self.go_up()
        elif item is not None and item.is_dir:
            self.cwd = self.image.join(self.cwd, item.name)
            self.refresh_listing()
        elif item is not None:
            # Dwuklik na pliku otwiera go w edytorze - to najkrotsza droga
            # do poprawienia autoexec.bat czy config.sys.
            self.edit_selected()
        return "break"

    def go_up(self) -> None:
        if self.image and self.cwd != "/":
            self.cwd = self.image.parent(self.cwd)
            self.refresh_listing()

    # -- operacje na plikach -----------------------------------------------

    def add_files(self) -> None:
        if not self.image:
            return
        paths = filedialog.askopenfilenames(
            parent=self, title=self.t("dlg_add"),
            initialdir=self.config_data.get("lastadd", str(Path.home())),
        )
        if paths:
            self.config_data["lastadd"] = str(Path(paths[0]).parent)
            self._save_config()
            self._copy_in([Path(p) for p in paths])

    def add_folder(self) -> None:
        """Kopiuje katalog wraz z podkatalogami i ich zawartoscia."""
        if not self.image or self.image_readonly:
            return
        chosen = filedialog.askdirectory(
            parent=self, title=self.t("dlg_add_folder"),
            initialdir=self.config_data.get("lastadd", str(Path.home())),
        )
        if not chosen:
            return
        # Zapamietujemy sam wybrany katalog, nie jego rodzica - inaczej przy
        # kazdym kolejnym kopiowaniu trzeba by schodzic w dol od nowa.
        self.config_data["lastadd"] = chosen
        self._save_config()

        options = FolderDialog(self, Path(chosen)).result
        if options is None or not self._guard_write():
            return
        source = options["source"]

        # Liczba pozycji jest juz policzona w oknie podsumowania, wiec
        # pasek moze pokazac prawdziwy postep, a nie samo tykanie.
        ile = options.get("files", 0) + options.get("dirs", 0) or None
        postep = PostepKopiowania(self, ile)
        try:
            info = self.image.import_tree(
                source, self.cwd, include_root=options["with_root"],
                on_item=lambda sciezka: postep.krok(os.path.basename(sciezka)))
        except (ImageError, OSError) as exc:
            postep.zamknij()
            self._error(exc)
            return
        postep.zamknij()

        self._saved()
        if postep.przerwane:
            self.status(self.t("busy_cancelled",
                               count=info["files"] + info["dirs"]), "error")
            return
        if info["renamed"]:
            messagebox.showinfo(
                APP_NAME,
                self.t("warn_shortened",
                       list="\n".join(info["renamed"][:14])),
                parent=self)
        if info["failed"]:
            messagebox.showwarning(
                APP_NAME,
                self.t("tree_failed_list",
                       list="\n".join(info["failed"][:14])),
                parent=self)
            self.status(self.t(
                "tree_partial", files=info["files"], dirs=info["dirs"],
                failed=len(info["failed"])), "error")
        else:
            self.status(self.t(
                "tree_done", files=info["files"], dirs=info["dirs"]), "ok")

    def _copy_in(self, paths: list[Path]) -> None:
        if not self._guard_write():
            return
        copied, renamed, failed = 0, [], []
        # Przy kilku plikach okno postepu tylko by mignelo; przy kilkuset
        # bez niego program wyglada na zawieszony.
        postep = (PostepKopiowania(self, len(paths))
                  if len(paths) > 8 else None)
        przerwane = False
        for path in paths:
            if postep is not None and not postep.krok(path.name):
                przerwane = True
                break
            try:
                final = self.image.import_file(path, self.cwd)
                copied += 1
                if final.upper() != path.name.upper():
                    renamed.append(f"{path.name} -> {final}")
            except (ImageError, OSError) as exc:
                failed.append(f"{path.name}: {exc}")
        if postep is not None:
            postep.zamknij()

        self._saved()
        if przerwane:
            self.status(self.t("busy_cancelled", count=copied), "error")
            return
        if failed:
            messagebox.showwarning(
                APP_NAME,
                self.t("warn_copy", ok=copied, total=len(paths),
                       list="\n".join(failed[:12])),
                parent=self,
            )
            self.status(self.t(
                "status_copied_partial", ok=copied, failed=len(failed)),
                "error")
            return

        if renamed:
            messagebox.showinfo(
                APP_NAME,
                self.t("warn_shortened", list="\n".join(renamed[:12])),
                parent=self,
            )
        self.status(self.t("status_copied_saved", count=copied), "ok")

    def extract_selected(self) -> None:
        if not self.image:
            return
        items = self._selection()
        if not items:
            self.status(self.t("status_pick_extract"), "error")
            return

        files = [e for e in items if not e.is_dir]
        if len(items) == 1 and files:
            entry = files[0]
            target = filedialog.asksaveasfilename(
                parent=self, title=self.t("dlg_save_as"),
                initialfile=entry.name.lower(),
                initialdir=self.config_data.get("lastsave", str(Path.home())),
            )
            if not target:
                return
            self.config_data["lastsave"] = str(Path(target).parent)
            self._save_config()
            try:
                self.image.export_file(
                    self.image.join(self.cwd, entry.name), target)
                hand_back(target)
            except (ImageError, OSError) as exc:
                self._error(exc)
                return
            self.status(
                self.t("status_saved", name=Path(target).name), "ok")
            return

        outdir = filedialog.askdirectory(
            parent=self, title=self.t("dlg_dest_folder"),
            initialdir=self.config_data.get("lastsave", str(Path.home())),
        )
        if not outdir:
            return
        self.config_data["lastsave"] = outdir
        self._save_config()

        count, failed = 0, []
        for entry in items:
            try:
                count += self._extract_entry(entry, self.cwd, Path(outdir))
            except (ImageError, OSError) as exc:
                failed.append(f"{entry.name}: {exc}")

        note = (self.t("status_extracted_partial", count=len(failed))
                if failed else "")
        self.status(
            self.t("status_extracted", count=count, path=outdir) + note,
            "error" if failed else "ok",
        )
        if failed:
            messagebox.showwarning(
                APP_NAME, self.t("warn_skipped", list="\n".join(failed[:12])),
                parent=self)

    def _extract_entry(self, entry, src_dir: str, dest: Path) -> int:
        """Wypakowuje plik albo caly katalog. Zwraca liczbe plikow."""
        src = self.image.join(src_dir, entry.name)
        if not entry.is_dir:
            target = dest / entry.name.lower()
            self.image.export_file(src, target)
            hand_back(target)
            return 1
        sub = dest / entry.name.lower()
        sub.mkdir(parents=True, exist_ok=True)
        total = 0
        for child in self.image.listdir(src):
            total += self._extract_entry(child, src, sub)
        return total

    def new_folder(self) -> None:
        if not self.image:
            return
        name = simpledialog.askstring(
            APP_NAME, self.t("dlg_new_folder"), parent=self)
        if not name or not self._guard_write():
            return
        try:
            final = self.image.mkdir(self.image.join(self.cwd, name))
        except (ImageError, OSError) as exc:
            self._error(exc)
            return
        self._saved()
        note = ("" if final.upper() == name.upper()
                else self.t("status_shortened", name=name))
        self.status(
            self.t("status_folder_saved", name=final, note=note), "ok")

    def rename_selected(self) -> None:
        if not self.image:
            return
        items = self._selection()
        if len(items) != 1:
            self.status(self.t("status_pick_one"), "error")
            return
        entry = items[0]
        new = simpledialog.askstring(
            APP_NAME, self.t("dlg_new_name"),
            initialvalue=entry.name, parent=self,
        )
        if not new or new == entry.name or not self._guard_write():
            return
        try:
            final = self.image.rename(self.image.join(self.cwd, entry.name), new)
        except (ImageError, OSError) as exc:
            self._error(exc)
            return
        self._saved()
        self.status(self.t("status_renamed", name=final), "ok")

    def delete_selected(self) -> None:
        if not self.image:
            return
        items = self._selection()
        if not items:
            self.status(self.t("status_pick_delete"), "error")
            return

        names = ", ".join(e.name for e in items[:6])
        if len(items) > 6:
            names += self.t("and_more", count=len(items) - 6)
        question = self.t("dlg_delete", names=names)
        if any(e.is_dir for e in items):
            question += self.t("dlg_delete_dirs")
        if not messagebox.askyesno(
            APP_NAME, question, icon="warning", default="no", parent=self
        ):
            return
        if not self._guard_write():
            return

        removed, failed = 0, []
        for entry in items:
            try:
                self.image.remove(
                    self.image.join(self.cwd, entry.name), recursive=True)
                removed += 1
            except (ImageError, OSError) as exc:
                failed.append(f"{entry.name}: {exc}")

        self._saved()
        if failed:
            messagebox.showwarning(
                APP_NAME,
                self.t("warn_not_removed", list="\n".join(failed[:12])),
                parent=self)
        self.status(
            self.t("status_removed" if failed else "status_removed_saved",
                   count=removed), "error" if failed else "ok")

    # -- fizyczny naped ----------------------------------------------------

    def open_drive_panel(self) -> None:
        if not DRIVES_AVAILABLE:
            return
        usbfloppy.set_language(self.lang)
        existing = getattr(self, "_drive_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_set()
            return
        self._drive_window = DriveDialog(self)

    def open_gw_panel(self) -> None:
        """Okno Greaseweazle - jedno naraz, jak okno napedow."""
        if not GW_AVAILABLE:
            return
        existing = getattr(self, "_gw_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_set()
            return
        self._gw_window = GwDialog(self)

    def open_floppy_preview(self, image, drive) -> None:
        """Pokazuje w glownym panelu system plikow fizycznej dyskietki."""
        if self.image:
            self.image.close()
        self.image = image
        self.image_path = Path(drive.path)
        self.image_title = f" {drive.path} "
        self.image_readonly = True
        self.cwd = "/"
        self._refresh_controls()
        self.refresh_listing()

    def after_image_written(self, path) -> None:
        """Nowy plik ma nalezec do uzytkownika, a nie do roota."""
        hand_back(path)

    def open_komplet(self) -> None:
        """Kreator rozkladajacy program wiekszy niz dyskietka."""
        if PACZKA_AVAILABLE:
            KompletDialog(self)

    # -- edytor tekstu -----------------------------------------------------

    def edit_selected(self) -> None:
        """Otwiera zaznaczony plik w edytorze ze swiadomoscia stron kodowych."""
        if not self.image:
            return
        items = [e for e in self._selection() if not e.is_dir]
        if len(items) != 1:
            self.status(self.t("status_pick_one"), "error")
            return
        entry = items[0]
        full = self.image.join(self.cwd, entry.name)
        try:
            data = self.image.read_file(full)
        except (ImageError, OSError) as exc:
            self._error(exc)
            return

        if dostext.looks_binary(data) and not messagebox.askyesno(
            APP_NAME, self.t("editor_binary", name=entry.name),
            icon="warning", default="no", parent=self,
        ):
            return
        TextEditor(self, full, entry.name, data)

    def new_text_file(self) -> None:
        """Zaklada pusty plik tekstowy i od razu otwiera go w edytorze."""
        if not self.image:
            return
        if self.image_readonly:
            self.status(self.t("editor_readonly"), "error")
            return
        name = simpledialog.askstring(
            APP_NAME, self.t("editor_name"), parent=self)
        if not name:
            return
        short = self.image.short_name(name)
        TextEditor(self, self.image.join(self.cwd, short), short, b"")

    # -- pomoc -------------------------------------------------------------

    def show_help(self) -> None:
        messagebox.showinfo(
            self.t("help_title"), self.t("help_body"), parent=self)

    def show_about(self) -> None:
        def listing(group: str) -> str:
            return "\n".join(
                f"  {f.label}" for f in FLOPPY_FORMATS.values()
                if f.group == group
            )
        messagebox.showinfo(
            self.t("about_title", app=APP_NAME),
            self.t("about_body", app=APP_NAME, version=APP_VERSION,
                   popular=listing("popular"), other=listing("other")),
            parent=self,
        )

    # -- ustawienia i zamkniecie -------------------------------------------

    def _load_config(self) -> dict:
        try:
            with open(CONFIG_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_config(self) -> None:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
                json.dump(self.config_data, fh, indent=2)
            hand_back(CONFIG_FILE)
        except OSError:
            pass

    def quit_app(self) -> None:
        if self.image:
            self.image.close()
        self._save_config()
        self.destroy()


def main() -> int:
    try:
        app = RetroZachar()
    except tk.TclError as exc:
        print(translate(DEFAULT_LANGUAGE, "error_no_gui", error=exc))
        print(translate(DEFAULT_LANGUAGE, "error_no_tk"))
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
