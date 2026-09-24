"""
languages.py - napisy interfejsu RetroZachar FFD Disk Maker.

Czesc projektu "RetroZachar FFD Disk Maker".

Komunikaty silnika (bledy FAT12, etykiety formatow, wiersz polecen) mieszkaja
osobno, w module fat12, zeby dalo sie go uzywac samodzielnie. Tutaj sa
wylacznie napisy okna.

Dodanie kolejnego jezyka sprowadza sie do dopisania nowego slownika o tym
samym zestawie kluczy. Braki nie wywalaja programu - napis zostanie wziety
z polskiego.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "pl"

# Nazwy jezykow zawsze w ich wlasnym jezyku - tak, zeby dalo sie je znalezc
# nawet po przypadkowym przelaczeniu na nieznany sobie jezyk.
LANGUAGE_NAMES: dict[str, str] = {
    "pl": "Polski",
    "en": "English",
}

TRANSLATIONS: dict[str, dict[str, str]] = {

    # ======================================================================
    "pl": {
        # --- pasek tytulowy i menu ---
        "app_subtitle": "obrazy dyskietek FAT12 dla 86Box i PCem",
        "menu_disk": " Dyskietka ",
        "menu_files": " Pliki ",
        "menu_language": " Jezyk ",
        "menu_help": " Pomoc ",
        "menu_open": "Otworz obraz...",
        "menu_close": "Zamknij obraz",
        "menu_label": "Zmien etykiete...",
        "menu_release": "Zestaw dyskietek (Jazwiec)...",
        "rel_title": "Zestaw dyskietek",
        "rel_intro": "Rozklada program wiekszy niz dyskietka na kilka "
                     "nosnikow i dodaje instalator,\nktory zlozy go z "
                     "powrotem na maszynie DOS. Instalator uzywa wylacznie "
                     "polecen\nwbudowanych w COMMAND.COM - na maszynie "
                     "docelowej nic nie jest potrzebne.",
        "rel_source": "Katalog z programem:",
        "rel_output": "Katalog na obrazy:",
        "rel_pick": "...",
        "rel_name": "Nazwa programu:",
        "rel_dest": "Katalog docelowy w DOS:",
        "rel_drive": "Naped zrodlowy:",
        "rel_label": "Etykieta dyskietek:",
        "rel_format": "Format dyskietki:",
        "rel_boot": "Zostaw na dyskietce 1 miejsce na system DOS",
        "rel_boot_note": "Program nie uczyni dyskietki startowa - pliki "
                         "systemowe naleza do DOS-a.\nZostawi tylko miejsce; "
                         "reszte zrobisz poleceniem SYS A: na maszynie DOS.",
        "rel_calc": "Przelicz plan",
        "rel_build": "Nagraj dyskietki",
        "rel_need_source": "Wskaz katalog z programem.",
        "rel_need_plan": "Najpierw przelicz plan.",
        "rel_plan_head": "{files} plikow, {size} B  ->  {disks} dyskietek",
        "rel_disk": "Dyskietka {n}: {items} pozycji, zajete {used} B, "
                    "wolne {free} B",
        "rel_split": "Podzielone miedzy dyskietki: {list}",
        "rel_building": "Nagrywanie dyskietki {n} z {total}...",
        "rel_done": "Nagrano {n} dyskietek w {path}",
        "rel_done_boot": "Nagrano {n} dyskietek. Dyskietka 1 ma miejsce na "
                         "system - uczyn ja startowa poleceniem SYS A:.",
        "rel_howto": "Na maszynie DOS wloz dyskietke 1 i uruchom: A:INSTALL",
        "menu_quit": "Zakoncz",
        "menu_add": "Dodaj pliki...",
        "menu_add_folder": "Dodaj katalog z podkatalogami...",
        "menu_gw": "Greaseweazle...",
        "gw_title": "Greaseweazle",
        "gw_legend_pending": "oczekuje",
        "gw_legend_active": "w pracy",
        "gw_legend_ok": "w porzadku",
        "gw_legend_retried": "po ponownych probach",
        "gw_legend_bad": "uszkodzona",
        "gw_legend_misplaced": "problem napedu",
        "gw_track_head": "C{cyl} H{head} - {state}",
        "gw_track_sectors": "sektory {found} z {total}",
        "gw_track_attempts": "prob: {count}",
        "gw_track_foreign": "sektory z cylindra {cyls}",
        "gw_hover_hint": "Najedz na sciezke, zeby zobaczyc szczegoly.",
        "gw_this_pass": "To przejscie:",
        "gw_collected": "Zebrane dane:",
        "gw_collected_none": "brak obrazu - zgraj dyskietke",
        "gw_collected_other": "plik ma rozmiar innego nosnika "
                              "({size} B) - nie da sie go zestawic "
                              "z wybranym formatem",
        "gw_collected_count": "{done} z {total} sektorow",
        "gw_merge_ask": "Plik juz istnieje:\n{path}\n\nDolozyc do niego "
                        "sektory, ktorych w nim brakuje, czy nadpisac go "
                        "nowym odczytem?\n\nTak - dolozyc brakujace\n"
                        "Nie - nadpisac\nAnuluj - nie robic nic",
        "gw_merge_new": "odzyskano {count} nowych",
        "gw_report_saved": "Raport przejscia: {path}",
        "gw_intro": "Greaseweazle czyta strumien magnetyczny prosto z glowicy "
                    "napedu z epoki. Naped i format\ntrzeba wskazac - gw nie "
                    "rozpoznaje ich sam, w odroznieniu od stacji USB.",
        "gw_checking": "Sprawdzanie urzadzenia...",
        "gw_ready": "{model}, firmware {firmware}, port {port}   "
                    "(narzedzia gw {tool})",
        "gw_recheck": "Sprawdz ponownie",
        "gw_pick_tool": "Wskaz plik gw...",
        "gw_pick_tool_title": "Wskaz plik gw (gw.exe pod Windows)",
        "gw_tool_hint": "Narzedzia Greaseweazle rozpakowane poza PATH? Wskaz "
                        "plik gw - program go zapamieta.",
        "gw_drive": "Naped:",
        "gw_drive_hint": "A i B - tasma IBM (ze skrzyzowaniem i prosta), "
                         "0-2 - tryb Shugart.",
        "gw_retries": "Prob na sciezke:",
        "gw_retries_hint": "Wiecej prob to dluzszy odczyt, ale i wieksza "
                           "szansa na sciezki zakurzone.",
        "gw_format": "Format:",
        "gw_read": "Zgraj do pliku {ext}",
        "gw_write": "Zapisz obraz na dyskietke",
        "gw_format_disk": "Formatuj dyskietke",
        "gw_cancel": "Przerwij",
        "gw_save_report": "Zapisz raport do .txt",
        "gw_progress": "Sciezka {done} z {total}",
        "gw_reading": "Odczyt dyskietki...",
        "gw_writing": "Zapis na dyskietke...",
        "gw_formatting": "Formatowanie dyskietki...",
        "gw_cancelling": "Przerywanie...",
        "gw_done": "Gotowe.",
        "gw_pick_save": "Gdzie zapisac obraz dyskietki",
        "gw_pick_open": "Obraz do zapisania na dyskietke",
        "gw_confirm_write": "Zawartosc dyskietki w napedzie {drive} zostanie "
                            "nadpisana obrazem:\n{path}\n\nKontynuowac?",
        "gw_confirm_format": "Dyskietka w napedzie {drive} zostanie "
                             "sformatowana jako {format}.\nCala jej zawartosc "
                             "zostanie utracona.\n\nKontynuowac?",
        "gw_label": "Etykieta wolumenu (mozna zostawic pusta):",
        "gw_open_read": "Otworzyc zgrany obraz w oknie glownym?",
        "gw_busy_close": "Trwa operacja na dyskietce. Przerwac ja i zamknac "
                         "okno?",
        "gw_size_switch": "Obraz ma rozmiar dyskietki {image}, a wybrany jest "
                          "format {chosen}.\n\nZapisac jako {image}?",
        "gw_size_unknown": "Rozmiar obrazu ({size} B) nie odpowiada zadnemu "
                           "obslugiwanemu formatowi dyskietki.",
        "menu_komplet": "Komplet dyskietek (Jazwiec)...",
        "kpl_title": "Rozlozenie programu na dyskietki",
        "kpl_intro": "Program wiekszy niz dyskietka zostanie rozlozony na "
                     "kolejne nosniki.\nNa pierwszym znajdzie sie instalator, "
                     "ktory zlozy wszystko z powrotem\nna dysku twardym - "
                     "bez zadnych narzedzi po stronie DOS-a.",
        "kpl_source": "Katalog z programem:",
        "kpl_format": "Nosnik:",
        "kpl_target_drive": "Dysk i katalog na maszynie docelowej:",
        "kpl_target_hint2": "Instalator pokaze cel i poczeka na "
                            "potwierdzenie, a takze wypisze, ktore dyski\n"
                            "sa dostepne. Wsad DOS-a nie potrafi wczytac "
                            "sciezki z klawiatury, wiec wybor zapada tutaj\n"
                            "albo parametrem wywolania: INSTALL D:",
        "kpl_target_hint": "Najwyzej 8 znakow, bez kropki i spacji - taki "
                           "jest limit DOS-a.\nPropozycja bierze sie z nazwy "
                           "katalogu zrodlowego; popraw ja, jesli wyszla "
                           "dziwna.",
        "kpl_output": "Gdzie zapisac obrazy:",
        "kpl_boot": "Pierwsza dyskietka na podstawie obrazu startowego",
        "kpl_boot_hint": "Program nie tworzy dyskietek startowych - nie wolno "
                         "mu rozprowadzac plikow systemowych.\nPrzygotuj "
                         "dyskietke poleceniem FORMAT /S, zapisz jako obraz "
                         "i wskaz go tutaj.",
        "kpl_plan": "Zaplanuj",
        "kpl_build": "Nagraj obrazy",
        "kpl_save_plan": "Zapisz plan do .txt",
        "kpl_pick_source": "Katalog z programem do rozlozenia",
        "kpl_pick_output": "Gdzie zapisac obrazy dyskietek",
        "kpl_pick_boot": "Obraz startowej dyskietki",
        "kpl_need_source": "Wskaz katalog z programem.",
        "kpl_need_plan": "Najpierw zaplanuj rozlozenie.",
        "kpl_planned": "Zaplanowano {count} dyskietek.",
        "kpl_building": "Nagrywanie {name} ({numer} z {ile})...",
        "kpl_done": "Nagrano {count} obrazow w {path}",
        "kpl_confirm": "Zostanie nagranych {count} obrazow dyskietek "
                       "w katalogu:\n{path}\n\nIstniejace pliki o tych "
                       "nazwach zostana nadpisane. Kontynuowac?",
        "menu_edit": "Edytuj plik tekstowy...",
        "menu_new_text": "Nowy plik tekstowy...",
        "editor_title": "Edytor: {name}",
        "editor_new_title": "Nowy plik tekstowy",
        "editor_codepage": "Strona kodowa:",
        "editor_crlf": "Konce wierszy DOS (CR LF)",
        "editor_code": "Alt+",
        "editor_code_hint": "wpisz kod 1-255 i nacisnij Enter",
        "editor_table": "Tablica znakow",
        "editor_hover": "Alt+{code}   (0x{hex})   {char}",
        "editor_code_bad": "Kod {code} to znak sterujacy - nie da sie go "
                           "wstawic do tekstu.",
        "editor_save": "Zapisz na dyskietke",
        "editor_close": "Zamknij",
        "editor_saved": "Zapisano {name} ({size} B).",
        "editor_intro": "Bajty DOS-owe sa tu pokazane jako znaki Unicode, "
                        "wiec ramki i polskie litery\nwygladaja normalnie. "
                        "Przy zapisie wracaja do wybranej strony kodowej.",
        "editor_binary": "{name} nie wyglada na plik tekstowy - zawiera "
                         "bajty typowe dla programow.\n\nOtworzyc mimo to? "
                         "Zapis moze go uszkodzic.",
        "editor_unmappable": "Strona kodowa {codepage} nie zna tych "
                             "znakow:\n\n    {chars}\n\n"
                             "Po zapisie zamienia sie w pytajniki. "
                             "Dla polskich liter wybierz CP852.\n\n"
                             "Zapisac mimo to?",
        "editor_switch": "Zmiana strony kodowej wczyta plik od nowa "
                         "i porzuci niezapisane zmiany.\n\nKontynuowac?",
        "editor_dirty": "Sa niezapisane zmiany. Zamknac mimo to?",
        "editor_name": "Nazwa nowego pliku (format 8.3):",
        "editor_readonly": "Podglad dyskietki jest tylko do odczytu.",
        "status_edited": "Zapisano {name} na obrazie ({size} B).",
        "tree_title": "Kopiowanie katalogu",
        "tree_source": "Katalog zrodlowy:",
        "tree_change": "Zmien...",
        "tree_preview": "Zawiera:",
        "tree_more": "   ... i {count} wiecej",
        "tree_single": "Ten katalog zawiera tylko jeden podkatalog. Jesli "
                       "chodzilo Ci o jego zawartosc,\nuzyj przycisku "
                       "Zmien i wejdz do niego dwuklikiem.",
        "tree_content": "Zawartosc: {files} plikow w {dirs} katalogach, "
                        "razem {size} B",
        "tree_free": "Wolne na dyskietce: {free} B",
        "tree_fits": "Zmiesci sie.",
        "tree_too_big": "NIE ZMIESCI SIE - brakuje {missing} B. Czesc plikow "
                        "zostanie pominieta, a program wypisze ktore.",
        "tree_how": "Sposob kopiowania:",
        "tree_with_root": "Utworz na dyskietce katalog {name}",
        "tree_contents": "Skopiuj sama zawartosc do biezacego katalogu",
        "tree_note": "Nazwy dluzsze niz 8.3 zostana skrocone - dotyczy to "
                     "takze nazw katalogow.",
        "tree_start": "Kopiuj",
        "tree_empty": "Wybrany katalog jest pusty.",
        "tree_done": "Skopiowano {files} plikow i {dirs} katalogow. "
                     "Obraz zapisany na dysku.",
        "tree_partial": "Skopiowano {files} plikow i {dirs} katalogow, "
                        "pominieto {failed}.",
        "tree_failed_list": "Nie udalo sie skopiowac:\n\n{list}",
        "menu_extract": "Wypakuj zaznaczone...",
        "menu_new_folder": "Nowy katalog...",
        "menu_rename": "Zmien nazwe...",
        "menu_delete": "Usun zaznaczone...",
        "menu_refresh": "Odswiez",
        "menu_shortcuts": "Skroty klawiszowe",
        "menu_about": "O programie",

        # --- panel tworzenia ---
        "tab_popular": "Popularne formaty",
        "tab_other": "Inne formaty",
        "chosen": "Wybrano: {label}",
        "geometry": "{size} B  |  {sectors} sektorow  |  "
                    "{root} pozycji w katalogu glownym",
        "geometry_sector": "  |  sektor {bytes} B",
        "field_filename": "Nazwa pliku obrazu",
        "field_filename_note": "rozszerzenie .img zostanie dodane",
        "field_volume": "Etykieta wolumenu (do 11 znakow)",
        "field_outdir": "Katalog docelowy",
        "button_create": "Utworz dyskietke",

        # --- panel zawartosci ---
        "panel_contents": " Zawartosc nosnika ",
        "button_open": "Otworz",
        "button_add": "Dodaj pliki",
        "button_add_folder": "Dodaj katalog",
        "button_extract": "Wypakuj",
        "button_new_folder": "Nowy katalog",
        "button_delete": "Usun",
        "column_name": "Nazwa",
        "column_size": "Rozmiar",
        "column_date": "Zmodyfikowano",
        "column_attr": "Atrybuty",
        "row_up": "<w gore>",
        "row_dir": "<KATALOG>",
        "capacity_none": "Nie wybrano nosnika",
        "filepath_none": "Nie otwarto zadnego obrazu",
        "filepath": "Plik: {path}",
        "filepath_device": "Naped: {path}",
        "autosave": "Zmiany zapisywane sa od razu do pliku obrazu.",
        "status_created_full": "Zapisano nowy obraz: {path}",
        "status_copied_saved": "Skopiowano {count} plikow. "
                               "Obraz zapisany na dysku.",
        "status_removed_saved": "Usunieto {count} pozycji. "
                                "Obraz zapisany na dysku.",
        "status_folder_saved": "Utworzono katalog {name}{note}. "
                               "Obraz zapisany na dysku.",
        "capacity": "Zajete {used} B   |   wolne {free} B   z   {total} B",

        # --- klawisze funkcyjne ---
        "key_help": "Pomoc",
        "key_refresh": "Odswiez",
        "key_open": "Otworz",
        "key_add": "Pliki",
        "key_add_folder": "Katalog+",
        "key_rename": "Nazwa",
        "key_folder": "Nowy kat.",
        "key_delete": "Usun",
        "key_extract": "Wypakuj",
        "key_quit": "Koniec",

        # --- okna dialogowe ---
        "dlg_outdir": "Katalog na obrazy dyskietek",
        "dlg_open": "Wybierz obraz dyskietki",
        "dlg_filter_images": "Obrazy dyskietek",
        "dlg_filter_all": "Wszystkie pliki",
        "dlg_add": "Pliki do skopiowania na dyskietke",
        "dlg_add_folder": "Katalog do skopiowania - wejdz do niego "
                          "dwuklikiem",
        "dlg_save_as": "Zapisz plik jako",
        "dlg_dest_folder": "Katalog docelowy",
        "dlg_new_label": "Nowa etykieta wolumenu (do 11 znakow):",
        "dlg_new_folder": "Nazwa nowego katalogu (maksymalnie 8 znakow):",
        "dlg_new_name": "Nowa nazwa w formacie 8.3:",
        "dlg_overwrite": "Plik juz istnieje:\n{path}\n\n"
                         "Nadpisac go? Cala dotychczasowa zawartosc "
                         "przepadnie.",
        "dlg_delete": "Usunac z dyskietki: {names}?",
        "dlg_delete_dirs": "\n\nKatalogi zostana usuniete wraz z zawartoscia.",

        # --- paski stanu ---
        "status_ready": "Gotowy.",
        "ext_reloaded": "Plik obrazu zmienil sie poza programem - wczytano "
                        "go ponownie.",
        "ext_warning": "Plik obrazu zmienil sie poza programem.\n\n"
                       "Zwykle znaczy to, ze emulator zapisal cos na te "
                       "dyskietke. Program trzyma caly obraz w pamieci "
                       "i zapisujac nadpisze plik w calosci - tamte zmiany "
                       "przepadna.\n\n"
                       "TAK  - wczytaj plik ponownie i porzuc te operacje\n"
                       "NIE  - zapisz mimo to, nadpisujac zmiany z zewnatrz\n"
                       "ANULUJ - nie rob nic",
        "ext_lost": "Zapisano, nadpisujac zmiany wprowadzone poza "
                    "programem.",
        "status_need_name": "Podaj nazwe pliku obrazu.",
        "status_cancelled": "Anulowano - plik pozostal nietkniety.",
        "status_created": "Utworzono {name} - {fmt}",
        "status_opened": "Otwarto {name} - {fmt}",
        "status_closed": "Zamknieto obraz.",
        "status_label": "Etykieta: {label}",
        "status_copied": "Skopiowano {count} plikow na dyskietke.",
        "status_copied_partial": "Skopiowano {ok}, pominieto {failed}.",
        "status_saved": "Zapisano {name}",
        "status_extracted": "Wypakowano {count} plikow do {path}",
        "status_extracted_partial": " ({count} pominieto)",
        "status_folder_created": "Utworzono katalog {name}{note}",
        "status_shortened": " (skrocono z {name})",
        "status_renamed": "Nowa nazwa: {name}",
        "status_removed": "Usunieto {count} pozycji.",
        "status_pick_extract": "Zaznacz najpierw, co wypakowac.",
        "status_pick_delete": "Zaznacz najpierw, co usunac.",
        "status_pick_one": "Zaznacz dokladnie jedna pozycje "
                           "do zmiany nazwy.",
        "status_empty_folder": "W wybranym katalogu nie ma plikow.",
        "status_language": "Jezyk interfejsu: Polski",

        # --- ostrzezenia ---
        "warn_copy": "Skopiowano {ok} z {total} plikow.\n\nPominieto:\n{list}",
        "warn_skipped": "Pominieto:\n{list}",
        "warn_not_removed": "Nie usunieto:\n{list}",
        "warn_shortened": "DOS dopuszcza wylacznie nazwy 8.3, wiec czesc "
                          "plikow trafila na dyskietke pod skrocona "
                          "nazwa:\n\n{list}",
        "and_more": " i {count} innych",

        # --- pomoc ---
        "help_title": "Skroty klawiszowe",
        "help_body": "F1   pomoc\n"
                     "F2   odswiez liste\n"
                     "F3   otworz obraz\n"
                     "F4   dodaj katalog z podkatalogami\n"
                     "F5   dodaj pliki na dyskietke\n"
                     "F6   zmien nazwe\n"
                     "F7   nowy katalog\n"
                     "F8   usun zaznaczone (takze Delete)\n"
                     "F9   wypakuj na dysk twardy\n"
                     "F10  zakoncz\n\n"
                     "Ctrl+L    zmiana etykiety wolumenu\n"
                     "Backspace katalog wyzej\n"
                     "Enter / dwuklik   wejdz do katalogu\n\n"
                     "Zaznaczanie wielu pozycji: Ctrl lub Shift.",
        "about_title": "O programie {app}",
        "about_body": "{app} {version}\n\n"
                      "Tworzy i edytuje obrazy dyskietek FAT12 dla\n"
                      "emulatorow 86Box, PCem i DOSBox.\n\n"
                      "System plikow zapisywany jest bezposrednio, bajt po\n"
                      "bajcie, wiec program nie potrzebuje mkfs.fat,\n"
                      "montowania ani uprawnien administratora i dziala\n"
                      "tak samo na Linuksie i na Windowsie.\n\n"
                      "Popularne formaty:\n{popular}\n\n"
                      "Inne formaty:\n{other}\n\n"
                      "Nazwy plikow sa skracane do formatu 8.3, ktory\n"
                      "jako jedyny jest czytelny dla DOS-a.",
        "error_no_gui": "Nie udalo sie uruchomic interfejsu graficznego: "
                        "{error}",
        "error_no_tk": "Na Linuksie moze brakowac pakietu python3-tk.",
        "unknown_format": "Nie rozpoznano formatu pliku {name}.\n\n"
                          "Program obsluguje: {formats}.\n\n"
                          "Jesli to obraz dyskietki innego systemu - na "
                          "przyklad Amigi - jego obsluga bedzie dodana "
                          "w przyszlosci.",
        "error_no_engine": "Nie znaleziono modulu fat12.py.\n"
                           "Plik fat12.py musi lezec w tym samym katalogu "
                           "co retrozachar.py.",

        # --- fizyczny naped dyskietek ---
        "menu_drive": " Naped ",
        "menu_drive_panel": "Napedy dyskietek...",
        "drive_title": "Napedy dyskietek",
        "drive_intro": "Naped USB oddaje sektory logiczne, nie strumien "
                       "magnetyczny. Odczyta dyskietke\nPC 1,44 MB albo "
                       "720 KB. Nosnikow Amigi nie odczyta zaden naped PC "
                       "- Amiga\nzapisuje 11 sektorow na sciezke we wlasnym "
                       "kodowaniu. To samo dotyczy\nzabezpieczen "
                       "antykopiowych i formatow niestandardowych.",
        "drive_working": "Odczyt z napedu...",
        "drive_scan": "Szukaj ponownie",
        "drive_read": "Zgraj do pliku .img",
        "drive_write": "Zapisz obraz na dyskietke",
        "drive_close": "Zamknij",
        "drive_cancel": "Przerwij",
        "drive_none": "Nie znaleziono zadnego napedu dyskietek.",
        "drive_found": "Wykryte napedy: {count}",
        "drive_no_media": "brak dyskietki",
        "drive_pick": "Zaznacz naped na liscie.",
        "drive_needs_media": "W tym napedzie nie ma dyskietki.",
        "drive_no_root": "Brak praw do napedu. Zainstaluj regule udev "
                         "poleceniem  sudo ./install.sh  i podlacz naped "
                         "ponownie.",
        "drive_no_admin": "Surowy dostep do napedu wymaga uprawnien "
                          "Administratora.",
        "drive_elevate_ask": "Odczyt dyskietki wymaga uprawnien "
                             "Administratora.\n\nUruchomic program "
                             "ponownie z tymi uprawnieniami?",
        "drive_elevate_failed": "Nie udalo sie uruchomic programu "
                                "z uprawnieniami Administratora.",
        "dlg_save_image": "Zapisz zgrana dyskietke jako",
        "dlg_pick_image": "Obraz do zapisania na dyskietce",
        "drive_progress": "Sektor {done} z {total}   |   uszkodzonych: {bad}",
        "drive_reading": "Zgrywanie dyskietki...",
        "drive_writing": "Zapisywanie na dyskietke...",
        "drive_verifying": "Weryfikacja zapisu...",
        "drive_cancelled": "Przerwano. Plik nie zostal zapisany.",
        "drive_read_ok": "Zgrano {name}: {sectors} sektorow w {time} s, "
                         "bez bledow.",
        "drive_read_bad": "Zgrano {name}: {sectors} sektorow, "
                          "{bad} uszkodzonych.",
        "drive_bad_report": "Nie udalo sie odczytac {count} sektorow. "
                            "Wypelniono je bajtem 0xF6, reszta danych "
                            "jest nienaruszona.\n\nSektory:\n{ranges}",
        "drive_write_confirm": "Cala zawartosc dyskietki w napedzie "
                               "zostanie nadpisana.\n\n"
                               "Naped:  {device}\n"
                               "Nosnik: {media}\n"
                               "Obraz:  {image}\n\n"
                               "Tej operacji nie da sie cofnac. Kontynuowac?",
        "drive_write_ok": "Zapisano dyskietke w {time} s. "
                          "Weryfikacja wypadla pomyslnie.",
        "drive_write_noverify": "Zapisano dyskietke w {time} s.",
        "drive_write_bad": "Zapis zakonczony z problemami w {count} "
                           "sektorach. Dyskietka moze byc uszkodzona.",
        "drive_verify_failed": "Weryfikacja wykryla roznice w {count} "
                               "sektorach. Dyskietka jest prawdopodobnie "
                               "uszkodzona - sprobuj innej.",
        "drive_busy": "Trwa juz operacja na napedzie.",
        "sudo_note": "Uruchomiono przez sudo - nowe pliki dostana "
                     "wlasciciela {user}.",

        # --- formatowanie i raport ---
        "drive_format": "Formatuj dyskietke",
        "drive_browse": "Podejrzyj zawartosc",
        "browse_opened": "Podglad dyskietki w {device} - {count} pozycji. "
                         "Pliki mozna wypakowac klawiszem F9.",
        "browse_damaged": "Podglad dyskietki: {count} sektorow nie dalo sie "
                          "odczytac. Lista plikow moze byc niepelna.",
        "browse_readonly": " (podglad dyskietki - tylko odczyt) ",
        "browse_hint": "Podglad czyta tylko obszar systemowy; przy "
                       "wypakowywaniu dochodza klastry wybranego pliku.",
        "format_title": "Formatowanie dyskietki",
        "format_intro": "Formatowanie kasuje cala zawartosc dyskietki.\n"
                        "Format zgodny z nosnikiem zapisywany jest od razu; "
                        "pozostale wymagaja\nnajpierw zmiany gestosci "
                        "zapisu, ktora wykonuje program ufiformat.",
        "format_which": "Format:",
        "format_mode": "Tryb:",
        "format_quick": "Szybki - sam system plikow",
        "format_full": "Pelny - z testem calej powierzchni",
        "format_full_note": "Test powierzchni przechodzi nosnik "
                            "czterokrotnie i trwa kilka minut.\n"
                            "Wykryte uszkodzone klastry zostana oznaczone "
                            "i wylaczone z uzycia.",
        "format_label": "Etykieta wolumenu:",
        "format_start": "Formatuj",
        "format_confirm": "Cala zawartosc dyskietki zostanie skasowana.\n\n"
                          "Naped:  {device}\n"
                          "Format: {media}\n"
                          "Tryb:   {mode}\n\n"
                          "Kontynuowac?",
        "format_done": "Sformatowano w {time} s.",
        "format_done_bad": "Sformatowano w {time} s, "
                           "{count} klastrow oznaczono jako uszkodzone.",
        "stage_read": "Odczyt",
        "stage_write": "Zapis",
        "stage_test": "Test powierzchni - zapis",
        "stage_scan": "Test powierzchni - odczyt",
        "stage_verify": "Weryfikacja",
        "drive_progress_stage": "{stage}   |   sektor {done} z {total}   "
                                "|   uszkodzonych: {bad}",
        "report_title": "Raport operacji",
        "report_save": "Zapisz do pliku .txt",
        "report_saved": "Zapisano raport: {path}",
        "dlg_save_report": "Zapisz raport jako",
        "filter_text": "Pliki tekstowe",
        "stage_lowlevel": "Formatowanie niskopoziomowe",
        "hd_hole_warn": "UWAGA - dyskietka HD formatowana na {size} KB\n\n"
                        "Naped rozpoznaje gestosc po otworze w rogu obudowy, "
                        "a nie po zapisie. Ten nosnik ma otwor HD, wiec po "
                        "sformatowaniu na nizsza gestosc naped nadal bedzie "
                        "czytal go w trybie HD i nie odczyta niczego. "
                        "Dyskietka bedzie wygladac na uszkodzona.\n\n"
                        "Zeby z niej korzystac, trzeba zakleic otwor HD "
                        "nieprzezroczysta tasma - to rog przeciwlegly do "
                        "suwaka zabezpieczenia przed zapisem. Tak wlasnie "
                        "przygotowuje sie nosniki dla Amigi.\n\n"
                        "Powrot do stanu poprzedniego:  "
                        "ufiformat -f 1440 {device}\n\n"
                        "Kontynuowac mimo to?",
        "ll_hole": "Zaklej otwor rozpoznawania HD, zanim zaczniesz.\n"
                   "Naped odczytuje gestosc z otworu w obudowie, nie "
                   "z zapisu. Bez zaklejenia\ndyskietka po przestawieniu "
                   "na 720 KB przestanie sie czytac w tym napedzie.",
        "ll_warning": "UWAGA - operacja na poziomie urzadzenia\n\n"
                      "Dyskietka HD ma w rogu obudowy otwor rozpoznawania "
                      "gestosci, przeciwlegly do suwaka zabezpieczenia "
                      "przed zapisem. Naped czyta gestosc wlasnie stamtad, "
                      "a nie z zapisu magnetycznego.\n\n"
                      "ZAKLEJ TEN OTWOR nieprzezroczysta tasma przed "
                      "przestawieniem nosnika na {size} KB. Inaczej naped "
                      "nadal uzna dyskietke za HD i przestanie ja "
                      "odczytywac.\n\n"
                      "Zmiana gestosci wysyla napedowi polecenie FORMAT "
                      "UNIT. Tansze naped\u0079 zglaszaja sie jako zgodne "
                      "z tym poleceniem, ale go nie wykonuja poprawnie "
                      "i potrafia sie po nim zawiesic do czasu odlaczenia "
                      "od zasilania.\n\n"
                      "Ponizej odpowiedz Twojego napedu na pytanie "
                      "o obslugiwane formaty:\n\n{inquiry}\n\n"
                      "Jesli nie widac tam {size} KB, nie kontynuuj.\n\n"
                      "Uruchomic zmiane gestosci?",
        "ll_recover": "Jesli naped przestal reagowac: wyjmij dyskietke, "
                      "odlacz kabel USB i podlacz ponownie. Stan sterownika "
                      "kasuje wylacznie odciecie zasilania.",
        "format_native": "zgodny z nosnikiem",
        "format_needs_ll": "wymaga zmiany gestosci",
        "format_ll_ready": "Zmiana gestosci zostanie wykonana programem "
                           "ufiformat, a zaraz po niej\nnosnik dostanie "
                           "nowy system plikow. Potrwa to kilka minut.",
        "format_ll_missing": "Wybrany format wymaga zmiany gestosci, a nie "
                             "znaleziono programu ufiformat.\n"
                             "Zainstaluj go:  sudo apt install ufiutils",
        "format_ll_windows": "Wybrany format wymaga zmiany gestosci. "
                             "Pod Windowsem wykonaj w wierszu\npolecen "
                             "jako Administrator:    format {letter}: "
                             "/F:{size}",
        "format_ll_running": "Zmiana gestosci nosnika - to potrwa "
                             "kilka minut...",
        "density_intro": "Zmiana gestosci zapisu, np. 1,44 MB na 720 KB "
                         "pod dyskietki Amigi,\nwymaga formatowania "
                         "niskopoziomowego, ktorego ten program nie "
                         "wykonuje.",
        "density_cmd": "Wykonaj w terminalu:\n    {command}",
        "density_missing": "Potrzebny jest program ufiformat "
                           "(pakiet ufiutils):\n    sudo apt install "
                           "ufiutils\n    ufiformat -f 720 {device}",
    },

    # ======================================================================
    "en": {
        # --- title bar and menus ---
        "app_subtitle": "FAT12 floppy images for 86Box and PCem",
        "menu_disk": " Disk ",
        "menu_files": " Files ",
        "menu_language": " Language ",
        "menu_help": " Help ",
        "menu_open": "Open image...",
        "menu_close": "Close image",
        "menu_label": "Change volume label...",
        "menu_release": "Disk set (Jazwiec)...",
        "rel_title": "Disk set",
        "rel_intro": "Splits a program larger than one floppy across several "
                     "disks and adds an\ninstaller that puts it back "
                     "together on the DOS machine. The installer uses only\n"
                     "commands built into COMMAND.COM - nothing is needed on "
                     "the target machine.",
        "rel_source": "Folder with the program:",
        "rel_output": "Folder for the images:",
        "rel_pick": "...",
        "rel_name": "Program name:",
        "rel_dest": "Destination folder in DOS:",
        "rel_drive": "Source drive:",
        "rel_label": "Disk label:",
        "rel_format": "Floppy format:",
        "rel_boot": "Leave room for the DOS system on disk 1",
        "rel_boot_note": "The program will not make the disk bootable - the "
                         "system files belong to DOS.\nIt only leaves room; "
                         "do the rest with SYS A: on the DOS machine.",
        "rel_calc": "Work out the plan",
        "rel_build": "Write the disks",
        "rel_need_source": "Point to the folder with the program.",
        "rel_need_plan": "Work out the plan first.",
        "rel_plan_head": "{files} files, {size} B  ->  {disks} disks",
        "rel_disk": "Disk {n}: {items} entries, used {used} B, free {free} B",
        "rel_split": "Split across disks: {list}",
        "rel_building": "Writing disk {n} of {total}...",
        "rel_done": "Wrote {n} disks to {path}",
        "rel_done_boot": "Wrote {n} disks. Disk 1 has room for the system - "
                         "make it bootable with SYS A:.",
        "rel_howto": "On the DOS machine insert disk 1 and run: A:INSTALL",
        "menu_quit": "Quit",
        "menu_add": "Add files...",
        "menu_add_folder": "Add folder with subfolders...",
        "menu_gw": "Greaseweazle...",
        "gw_title": "Greaseweazle",
        "gw_legend_pending": "waiting",
        "gw_legend_active": "in progress",
        "gw_legend_ok": "fine",
        "gw_legend_retried": "after retries",
        "gw_legend_bad": "damaged",
        "gw_legend_misplaced": "drive problem",
        "gw_track_head": "C{cyl} H{head} - {state}",
        "gw_track_sectors": "sectors {found} of {total}",
        "gw_track_attempts": "attempts: {count}",
        "gw_track_foreign": "sectors from cylinder {cyls}",
        "gw_hover_hint": "Point at a track to see its details.",
        "gw_this_pass": "This pass:",
        "gw_collected": "Collected data:",
        "gw_collected_none": "no image yet - read a floppy",
        "gw_collected_other": "the file has the size of another medium "
                              "({size} B) - it cannot be matched against "
                              "the chosen format",
        "gw_collected_count": "{done} of {total} sectors",
        "gw_merge_ask": "The file already exists:\n{path}\n\nFill in the "
                        "sectors it is missing, or overwrite it with the "
                        "new read?\n\nYes - fill in what is missing\n"
                        "No - overwrite\nCancel - do nothing",
        "gw_merge_new": "{count} newly recovered",
        "gw_report_saved": "Pass report: {path}",
        "gw_intro": "Greaseweazle reads the magnetic flux straight from the "
                    "head of a period drive. The drive\nand format must be "
                    "chosen - unlike a USB drive, gw does not detect them.",
        "gw_checking": "Checking the device...",
        "gw_ready": "{model}, firmware {firmware}, port {port}   "
                    "(gw tools {tool})",
        "gw_recheck": "Check again",
        "gw_pick_tool": "Locate gw file...",
        "gw_pick_tool_title": "Locate the gw file (gw.exe on Windows)",
        "gw_tool_hint": "Greaseweazle tools unpacked outside PATH? Point to "
                        "the gw file - the program will remember it.",
        "gw_drive": "Drive:",
        "gw_drive_hint": "A and B - IBM cable (twisted and straight), "
                         "0-2 - Shugart mode.",
        "gw_retries": "Retries per track:",
        "gw_retries_hint": "More retries means a slower read, but a better "
                           "chance with dusty tracks.",
        "gw_format": "Format:",
        "gw_read": "Read to {ext} file",
        "gw_write": "Write image to floppy",
        "gw_format_disk": "Format floppy",
        "gw_cancel": "Cancel",
        "gw_save_report": "Save report to .txt",
        "gw_progress": "Track {done} of {total}",
        "gw_reading": "Reading the floppy...",
        "gw_writing": "Writing to the floppy...",
        "gw_formatting": "Formatting the floppy...",
        "gw_cancelling": "Cancelling...",
        "gw_done": "Done.",
        "gw_pick_save": "Where to save the floppy image",
        "gw_pick_open": "Image to write to the floppy",
        "gw_confirm_write": "The floppy in drive {drive} will be overwritten "
                            "with the image:\n{path}\n\nContinue?",
        "gw_confirm_format": "The floppy in drive {drive} will be formatted "
                             "as {format}.\nAll of its contents will be "
                             "lost.\n\nContinue?",
        "gw_label": "Volume label (may be left empty):",
        "gw_open_read": "Open the read image in the main window?",
        "gw_busy_close": "An operation on the floppy is running. Cancel it "
                         "and close the window?",
        "gw_size_switch": "The image has the size of a {image} floppy, but "
                          "{chosen} is selected.\n\nWrite it as {image}?",
        "gw_size_unknown": "The image size ({size} B) does not match any "
                           "supported floppy format.",
        "menu_komplet": "Disk set (Jazwiec)...",
        "kpl_title": "Splitting a program across floppies",
        "kpl_intro": "A program larger than one floppy is spread over several "
                     "disks.\nThe first one carries an installer that puts it "
                     "back together on the\nhard disk - with no tools needed "
                     "on the DOS side.",
        "kpl_source": "Folder with the program:",
        "kpl_format": "Medium:",
        "kpl_target_drive": "Drive and folder on the target machine:",
        "kpl_target_hint2": "The installer shows the target and waits for "
                            "confirmation, and lists which drives\nare "
                            "available. A DOS batch cannot read a path from "
                            "the keyboard, so the choice is made\nhere or "
                            "as a parameter: INSTALL D:",
        "kpl_target_hint": "At most 8 characters, no dot and no space - that "
                           "is the DOS limit.\nThe suggestion comes from the "
                           "source folder name; correct it if it came out "
                           "odd.",
        "kpl_output": "Where to save the images:",
        "kpl_boot": "First floppy based on a bootable image",
        "kpl_boot_hint": "The program does not create bootable floppies - it "
                         "may not distribute system files.\nPrepare one with "
                         "FORMAT /S, save it as an image and point here.",
        "kpl_plan": "Plan it",
        "kpl_build": "Write images",
        "kpl_save_plan": "Save plan to .txt",
        "kpl_pick_source": "Folder with the program to split",
        "kpl_pick_output": "Where to save the floppy images",
        "kpl_pick_boot": "Bootable floppy image",
        "kpl_need_source": "Choose the folder with the program.",
        "kpl_need_plan": "Plan the layout first.",
        "kpl_planned": "Planned {count} floppies.",
        "kpl_building": "Writing {name} ({numer} of {ile})...",
        "kpl_done": "Wrote {count} images to {path}",
        "kpl_confirm": "{count} floppy images will be written to:\n{path}\n\n"
                       "Existing files with those names will be overwritten. "
                       "Continue?",
        "menu_edit": "Edit text file...",
        "menu_new_text": "New text file...",
        "editor_title": "Editor: {name}",
        "editor_new_title": "New text file",
        "editor_codepage": "Code page:",
        "editor_crlf": "DOS line endings (CR LF)",
        "editor_code": "Alt+",
        "editor_code_hint": "type a code 1-255 and press Enter",
        "editor_table": "Character table",
        "editor_hover": "Alt+{code}   (0x{hex})   {char}",
        "editor_code_bad": "Code {code} is a control character - it cannot "
                           "be inserted into text.",
        "editor_save": "Save to floppy",
        "editor_close": "Close",
        "editor_saved": "Saved {name} ({size} B).",
        "editor_intro": "DOS bytes are shown here as Unicode characters, so "
                        "box drawing and accented\nletters look right. On "
                        "saving they return to the chosen code page.",
        "editor_binary": "{name} does not look like a text file - it holds "
                         "bytes typical of programs.\n\nOpen it anyway? "
                         "Saving may damage it.",
        "editor_unmappable": "Code page {codepage} does not know these "
                             "characters:\n\n    {chars}\n\n"
                             "They will turn into question marks. For "
                             "Central European letters choose CP852.\n\n"
                             "Save anyway?",
        "editor_switch": "Changing the code page reloads the file and "
                         "discards unsaved changes.\n\nContinue?",
        "editor_dirty": "There are unsaved changes. Close anyway?",
        "editor_name": "Name of the new file (8.3 format):",
        "editor_readonly": "The floppy preview is read only.",
        "status_edited": "Saved {name} on the image ({size} B).",
        "tree_title": "Copying a folder",
        "tree_source": "Source folder:",
        "tree_change": "Change...",
        "tree_preview": "Holds:",
        "tree_more": "   ... and {count} more",
        "tree_single": "This folder holds a single subfolder. If you meant "
                       "its contents,\nuse Change and enter it with "
                       "a double click.",
        "tree_content": "Contents: {files} files in {dirs} folders, "
                        "{size} B in total",
        "tree_free": "Free on the floppy: {free} B",
        "tree_fits": "It fits.",
        "tree_too_big": "IT WILL NOT FIT - {missing} B short. Some files "
                        "will be skipped and the program will list them.",
        "tree_how": "How to copy:",
        "tree_with_root": "Create folder {name} on the floppy",
        "tree_contents": "Copy the contents into the current folder",
        "tree_note": "Names longer than 8.3 will be shortened - folder "
                     "names included.",
        "tree_start": "Copy",
        "tree_empty": "The chosen folder is empty.",
        "tree_done": "Copied {files} files and {dirs} folders. "
                     "Image saved to disk.",
        "tree_partial": "Copied {files} files and {dirs} folders, "
                        "skipped {failed}.",
        "tree_failed_list": "Could not copy:\n\n{list}",
        "menu_extract": "Extract selected...",
        "menu_new_folder": "New folder...",
        "menu_rename": "Rename...",
        "menu_delete": "Delete selected...",
        "menu_refresh": "Refresh",
        "menu_shortcuts": "Keyboard shortcuts",
        "menu_about": "About",

        # --- creation panel ---
        "tab_popular": "Common formats",
        "tab_other": "Other formats",
        "chosen": "Selected: {label}",
        "geometry": "{size} B  |  {sectors} sectors  |  "
                    "{root} root directory entries",
        "geometry_sector": "  |  {bytes} B sectors",
        "field_filename": "Image file name",
        "field_filename_note": "the .img extension will be added",
        "field_volume": "Volume label (up to 11 characters)",
        "field_outdir": "Output folder",
        "button_create": "Create floppy",

        # --- contents panel ---
        "panel_contents": " Disk contents ",
        "button_open": "Open",
        "button_add": "Add files",
        "button_add_folder": "Add folder",
        "button_extract": "Extract",
        "button_new_folder": "New folder",
        "button_delete": "Delete",
        "column_name": "Name",
        "column_size": "Size",
        "column_date": "Modified",
        "column_attr": "Attributes",
        "row_up": "<up>",
        "row_dir": "<FOLDER>",
        "capacity_none": "No disk selected",
        "filepath_none": "No image opened",
        "filepath": "File: {path}",
        "filepath_device": "Drive: {path}",
        "autosave": "Changes are written to the image file immediately.",
        "status_created_full": "New image saved: {path}",
        "status_copied_saved": "Copied {count} files. Image saved to disk.",
        "status_removed_saved": "Deleted {count} entries. "
                                "Image saved to disk.",
        "status_folder_saved": "Created folder {name}{note}. "
                               "Image saved to disk.",
        "capacity": "Used {used} B   |   free {free} B   of   {total} B",

        # --- function keys ---
        "key_help": "Help",
        "key_refresh": "Refresh",
        "key_open": "Open",
        "key_add": "Files",
        "key_add_folder": "Folder+",
        "key_rename": "Rename",
        "key_folder": "New fldr",
        "key_delete": "Delete",
        "key_extract": "Extract",
        "key_quit": "Quit",

        # --- dialogs ---
        "dlg_outdir": "Folder for floppy images",
        "dlg_open": "Choose a floppy image",
        "dlg_filter_images": "Floppy images",
        "dlg_filter_all": "All files",
        "dlg_add": "Files to copy onto the floppy",
        "dlg_add_folder": "Folder to copy - enter it with a double click",
        "dlg_save_as": "Save file as",
        "dlg_dest_folder": "Destination folder",
        "dlg_new_label": "New volume label (up to 11 characters):",
        "dlg_new_folder": "Name of the new folder (8 characters at most):",
        "dlg_new_name": "New name in 8.3 format:",
        "dlg_overwrite": "File already exists:\n{path}\n\n"
                         "Overwrite it? Everything it currently holds "
                         "will be lost.",
        "dlg_delete": "Delete from the floppy: {names}?",
        "dlg_delete_dirs": "\n\nFolders will be deleted with "
                           "everything inside.",

        # --- status line ---
        "status_ready": "Ready.",
        "ext_reloaded": "The image file changed outside the program - "
                        "it was reloaded.",
        "ext_warning": "The image file changed outside the program.\n\n"
                       "Usually this means an emulator wrote something to "
                       "this floppy. The program keeps the whole image in "
                       "memory and writing rewrites the file in full - "
                       "those changes would be lost.\n\n"
                       "YES    - reload the file and abandon this operation\n"
                       "NO     - write anyway, overwriting outside changes\n"
                       "CANCEL - do nothing",
        "ext_lost": "Written, overwriting changes made outside "
                    "the program.",
        "status_need_name": "Enter a name for the image file.",
        "status_cancelled": "Cancelled - the file was left untouched.",
        "status_created": "Created {name} - {fmt}",
        "status_opened": "Opened {name} - {fmt}",
        "status_closed": "Image closed.",
        "status_label": "Label: {label}",
        "status_copied": "Copied {count} files onto the floppy.",
        "status_copied_partial": "Copied {ok}, skipped {failed}.",
        "status_saved": "Saved {name}",
        "status_extracted": "Extracted {count} files to {path}",
        "status_extracted_partial": " ({count} skipped)",
        "status_folder_created": "Created folder {name}{note}",
        "status_shortened": " (shortened from {name})",
        "status_renamed": "New name: {name}",
        "status_removed": "Deleted {count} entries.",
        "status_pick_extract": "Select what to extract first.",
        "status_pick_delete": "Select what to delete first.",
        "status_pick_one": "Select exactly one entry to rename.",
        "status_empty_folder": "The chosen folder holds no files.",
        "status_language": "Interface language: English",

        # --- warnings ---
        "warn_copy": "Copied {ok} of {total} files.\n\nSkipped:\n{list}",
        "warn_skipped": "Skipped:\n{list}",
        "warn_not_removed": "Not deleted:\n{list}",
        "warn_shortened": "DOS only allows 8.3 names, so some files "
                          "landed on the floppy under a shortened "
                          "name:\n\n{list}",
        "and_more": " and {count} more",

        # --- help ---
        "help_title": "Keyboard shortcuts",
        "help_body": "F1   help\n"
                     "F2   refresh the list\n"
                     "F3   open an image\n"
                     "F4   add a folder with subfolders\n"
                     "F5   add files to the floppy\n"
                     "F6   rename\n"
                     "F7   new folder\n"
                     "F8   delete selected (also Delete)\n"
                     "F9   extract to the hard disk\n"
                     "F10  quit\n\n"
                     "Ctrl+L    change the volume label\n"
                     "Backspace go up one folder\n"
                     "Enter / double-click   enter a folder\n\n"
                     "Select several entries with Ctrl or Shift.",
        "about_title": "About {app}",
        "about_body": "{app} {version}\n\n"
                      "Creates and edits FAT12 floppy images for the\n"
                      "86Box, PCem and DOSBox emulators.\n\n"
                      "The file system is written directly, byte by byte,\n"
                      "so the program needs no mkfs.fat, no mounting and\n"
                      "no administrator rights, and behaves the same on\n"
                      "Linux and on Windows.\n\n"
                      "Common formats:\n{popular}\n\n"
                      "Other formats:\n{other}\n\n"
                      "File names are shortened to the 8.3 format, the\n"
                      "only one DOS can read.",
        "error_no_gui": "Could not start the graphical interface: {error}",
        "error_no_tk": "On Linux the python3-tk package may be missing.",
        "unknown_format": "The format of {name} was not recognised.\n\n"
                          "The program supports: {formats}.\n\n"
                          "If this is a floppy image of another system - "
                          "an Amiga one, say - support for it will be "
                          "added later.",
        "error_no_engine": "Module fat12.py not found.\n"
                           "fat12.py must sit in the same folder as "
                           "retrozachar.py.",

        # --- physical floppy drive ---
        "menu_drive": " Drive ",
        "menu_drive_panel": "Floppy drives...",
        "drive_title": "Floppy drives",
        "drive_intro": "A USB drive returns logical sectors, not a magnetic "
                       "stream. It reads PC\nfloppies of 1.44 MB or 720 KB. "
                       "No PC drive reads Amiga media - the Amiga\nwrites 11 "
                       "sectors per track in its own encoding. The same goes "
                       "for\ncopy protection and non-standard formats.",
        "drive_working": "Reading from the drive...",
        "drive_scan": "Scan again",
        "drive_read": "Read into an .img file",
        "drive_write": "Write image to floppy",
        "drive_close": "Close",
        "drive_cancel": "Cancel",
        "drive_none": "No floppy drive found.",
        "drive_found": "Drives found: {count}",
        "drive_no_media": "no floppy",
        "drive_pick": "Select a drive from the list.",
        "drive_needs_media": "There is no floppy in this drive.",
        "drive_no_root": "No rights to the drive. Install the udev rule "
                         "with  sudo ./install.sh  and reconnect "
                         "the drive.",
        "drive_no_admin": "Raw access to the drive requires Administrator "
                          "rights.",
        "drive_elevate_ask": "Reading a floppy requires Administrator "
                             "rights.\n\nRestart the program with "
                             "those rights?",
        "drive_elevate_failed": "Could not restart the program with "
                                "Administrator rights.",
        "dlg_save_image": "Save the read floppy as",
        "dlg_pick_image": "Image to write onto the floppy",
        "drive_progress": "Sector {done} of {total}   |   bad: {bad}",
        "drive_reading": "Reading the floppy...",
        "drive_writing": "Writing to the floppy...",
        "drive_verifying": "Verifying the write...",
        "drive_cancelled": "Cancelled. No file was written.",
        "drive_read_ok": "Read {name}: {sectors} sectors in {time} s, "
                         "no errors.",
        "drive_read_bad": "Read {name}: {sectors} sectors, {bad} bad.",
        "drive_bad_report": "{count} sectors could not be read. They were "
                            "filled with byte 0xF6; the rest of the data is "
                            "intact.\n\nSectors:\n{ranges}",
        "drive_write_confirm": "Everything on the floppy in the drive will "
                               "be overwritten.\n\n"
                               "Drive:  {device}\n"
                               "Medium: {media}\n"
                               "Image:  {image}\n\n"
                               "This cannot be undone. Continue?",
        "drive_write_ok": "Floppy written in {time} s. "
                          "Verification passed.",
        "drive_write_noverify": "Floppy written in {time} s.",
        "drive_write_bad": "Writing finished with problems in {count} "
                           "sectors. The floppy may be damaged.",
        "drive_verify_failed": "Verification found differences in {count} "
                               "sectors. The floppy is probably damaged - "
                               "try another one.",
        "drive_busy": "A drive operation is already running.",
        "sudo_note": "Started through sudo - new files will be owned "
                     "by {user}.",

        # --- formatting and report ---
        "drive_format": "Format floppy",
        "drive_browse": "Browse contents",
        "browse_opened": "Browsing the floppy in {device} - {count} entries. "
                         "Files can be extracted with F9.",
        "browse_damaged": "Browsing the floppy: {count} sectors could not be "
                          "read. The file list may be incomplete.",
        "browse_readonly": " (floppy preview - read only) ",
        "browse_hint": "The preview reads only the system area; extracting "
                       "adds the clusters of the chosen file.",
        "format_title": "Formatting a floppy",
        "format_intro": "Formatting erases everything on the floppy.\n"
                        "The format matching the medium is written straight "
                        "away; the others need\na density change first, "
                        "which the ufiformat program performs.",
        "format_which": "Format:",
        "format_mode": "Mode:",
        "format_quick": "Quick - file system only",
        "format_full": "Full - with a whole-surface test",
        "format_full_note": "The surface test passes over the medium four "
                            "times and takes several minutes.\n"
                            "Any bad clusters found will be marked and "
                            "taken out of use.",
        "format_label": "Volume label:",
        "format_start": "Format",
        "format_confirm": "Everything on the floppy will be erased.\n\n"
                          "Drive:  {device}\n"
                          "Format: {media}\n"
                          "Mode:   {mode}\n\n"
                          "Continue?",
        "format_done": "Formatted in {time} s.",
        "format_done_bad": "Formatted in {time} s, "
                           "{count} clusters marked bad.",
        "stage_read": "Reading",
        "stage_write": "Writing",
        "stage_test": "Surface test - writing",
        "stage_scan": "Surface test - reading",
        "stage_verify": "Verifying",
        "drive_progress_stage": "{stage}   |   sector {done} of {total}   "
                                "|   bad: {bad}",
        "report_title": "Operation report",
        "report_save": "Save to a .txt file",
        "report_saved": "Report saved: {path}",
        "dlg_save_report": "Save report as",
        "filter_text": "Text files",
        "stage_lowlevel": "Low-level format",
        "hd_hole_warn": "WARNING - an HD floppy formatted to {size} KB\n\n"
                        "The drive picks the density from the hole in the "
                        "corner of the shell, not from what is recorded. "
                        "This medium has the HD hole, so after formatting to "
                        "a lower density the drive will still read it in HD "
                        "mode and get nothing. The floppy will look "
                        "damaged.\n\n"
                        "To use it, cover the HD hole with opaque tape - it "
                        "is the corner opposite the write-protect slider. "
                        "That is how media for the Amiga are prepared.\n\n"
                        "Going back:  ufiformat -f 1440 {device}\n\n"
                        "Continue anyway?",
        "ll_hole": "Cover the HD detection hole before you start.\n"
                   "The drive reads density from the hole in the shell, not "
                   "from the recording.\nWithout covering it, a floppy "
                   "switched to 720 KB stops being readable in this drive.",
        "ll_warning": "WARNING - device-level operation\n\n"
                      "An HD floppy has a density detection hole in the "
                      "corner of its shell, opposite the write-protect "
                      "slider. The drive reads the density from there, not "
                      "from the magnetic recording.\n\n"
                      "COVER THAT HOLE with opaque tape before switching "
                      "the medium to {size} KB. Otherwise the drive will "
                      "still treat the floppy as HD and stop reading "
                      "it.\n\n"
                      "Changing density sends the drive a FORMAT UNIT "
                      "command. Cheaper drives report themselves as "
                      "supporting it but do not carry it out correctly, "
                      "and can hang until power is removed.\n\n"
                      "Below is your drive's answer about the formats it "
                      "supports:\n\n{inquiry}\n\n"
                      "If {size} KB is not listed there, do not continue."
                      "\n\nStart the density change?",
        "ll_recover": "If the drive stopped responding: take the floppy "
                      "out, unplug the USB cable and plug it back in. Only "
                      "cutting power clears the controller state.",
        "format_native": "matches the medium",
        "format_needs_ll": "needs a density change",
        "format_ll_ready": "The density change will be done by ufiformat, "
                           "and the medium will get\na fresh file system "
                           "right after. This takes a few minutes.",
        "format_ll_missing": "The chosen format needs a density change and "
                             "ufiformat was not found.\n"
                             "Install it:  sudo apt install ufiutils",
        "format_ll_windows": "The chosen format needs a density change. "
                             "On Windows run this in a\ncommand prompt as "
                             "Administrator:    format {letter}: /F:{size}",
        "format_ll_running": "Changing the density of the medium - this "
                             "takes a few minutes...",
        "density_intro": "Changing the recording density, say 1.44 MB to "
                         "720 KB for Amiga disks,\nneeds a low-level "
                         "format, which this program does not perform.",
        "density_cmd": "Run in a terminal:\n    {command}",
        "density_missing": "The ufiformat program is needed "
                           "(package ufiutils):\n    sudo apt install "
                           "ufiutils\n    ufiformat -f 720 {device}",
    },
}


def translate(lang: str, key: str, **kwargs) -> str:
    """
    Napis w wybranym jezyku. Nieznany jezyk albo brakujacy klucz cofa sie
    do polskiego, zeby literowka w tlumaczeniu nie wywalila okna.
    """
    table = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
    text = table.get(key)
    if text is None:
        text = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    return text.format(**kwargs) if kwargs else text
