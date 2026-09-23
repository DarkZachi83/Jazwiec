# Test dymny pod Windows — lista kontrolna

RetroZachar — FFD Disk Maker — Jaźwiec, wersja 2.0

Celem nie jest wyłapanie wszystkich błędów, tylko rozstrzygnięcie, czy pod
Windowsem **w ogóle działa** to, co pod Linuksem działa na pewno. Cały kod
windowsowy nie wykonał się ani razu — ani u mnie, bo nie mam tam dostępu, ani
u Ciebie.

Przewidywany czas: 20–30 minut bez punktu I.

Przy każdym kroku podałem, **jaki fragment kodu sprawdza**. Gdy coś zawiedzie,
zanotuj numer kroku i pełną treść błędu — to wystarczy, żeby trafić w przyczynę
bez zgadywania.

---

## Przygotowanie

- [ ] Python **z python.org**, nie ze Sklepu Windows. Ten ze Sklepu działa
      w kontenerze z przekierowanym zapisem i już raz uniemożliwił zbudowanie
      `.exe` Nuitką.
- [ ] Przy instalacji zaznaczone **Add Python to PATH**.
- [ ] Wszystkie pliki projektu w jednym katalogu, najlepiej o prostej ścieżce
      bez spacji i znaków specjalnych, na przykład `C:\jazwiec`.
- [ ] Przygotuj katalog testowy z kilkoma plikami i podkatalogami, w tym jeden
      **pusty podkatalog** i jeden plik większy niż 1,44 MB.

```bat
python --version
python -c "import tkinter; print('tkinter OK')"
```

---

## A. Start programu

| | Krok | Oczekiwany wynik | Co sprawdza |
|---|---|---|---|
| A1 | `python main.py` | Okno się otwiera | importy, `silniki.py` |
| A2 | Wygląd okna | Czcionka o stałej szerokości, układ jak na Linuksie | wybór czcionki, `Consolas` |
| A3 | Ikona na pasku zadań | Głowa borsuka, nie domyślna ikona Pythona | `_znajdz_ikone`, PNG w Tk |
| A4 | Grafika pod przyciskiem | Scena z borsukiem, nieprzycięta | `jazwiec-panel.png` |
| A5 | Dolny pasek klawiszy | Widoczny w całości, nieucięty | kolejność pakowania |

**Uwaga do A3 i A4:** Tkinter czyta PNG dopiero od wersji 8.6. Gdyby ikon
brakowało, sprawdź `python -c "import tkinter; print(tkinter.TkVersion)"` —
powinno być 8.6 lub więcej.

---

## B. Tworzenie obrazów

| | Krok | Oczekiwany wynik | Co sprawdza |
|---|---|---|---|
| B1 | Wskaż katalog docelowy przyciskiem `...` | Okno wyboru katalogu Windows | `filedialog.askdirectory` |
| B2 | Utwórz obraz 1,44 MB z etykietą | Pasek stanu: „Zapisano nowy obraz: ...” z pełną ścieżką | zapis pliku, `hand_back` |
| B3 | Ścieżka w pasku nad listą | Litera dysku i ukośniki windowsowe | obsługa ścieżek |
| B4 | Utwórz obrazy 360 KB, 720 KB i 1,2 MB | Każdy się otwiera, pojemność się zgadza | wszystkie formaty |
| B5 | Utwórz obraz PC-98 (zakładka *Inne formaty*) | Otwiera się, sektor 1024 B w opisie | sektory inne niż 512 |
| B6 | Spróbuj nadpisać istniejący plik | Pytanie o potwierdzenie, nie ciche nadpisanie | zabezpieczenie |

---

## C. Pliki i katalogi

| | Krok | Oczekiwany wynik | Co sprawdza |
|---|---|---|---|
| C1 | **Dodaj pliki** — wskaż kilka | Pojawiają się na liście, nazwy skrócone do 8.3 | `import_file` |
| C2 | Plik o długiej nazwie ze spacjami | Komunikat o skróceniu z listą zmian | `to_short_name` |
| C3 | **Dodaj katalog** (F4) | Podgląd zawartości i podsumowanie przed kopiowaniem | `_measure_folder` |
| C4 | Skopiuj katalog z podkatalogami | Cała struktura odtworzona, pusty podkatalog też | `import_tree` |
| C5 | Wejdź w podkatalog dwuklikiem, wróć klawiszem Backspace | Ścieżka w pasku się zmienia | nawigacja |
| C6 | **Wypakuj** (F9) pojedynczy plik | Zapisany na dysk, rozmiar zgodny | `export_file` |
| C7 | Zaznacz kilka pozycji z Ctrl i wypakuj | Wszystkie trafiają do wskazanego katalogu | wypakowanie wielu |
| C8 | Usuń plik (F8) | Znika, wolne miejsce rośnie | `remove` |

**Najważniejsze w tej części:** krok C4. Ścieżki wewnątrz obrazu używają
ukośnika `/`, a windowsowe `\`. Konwersja jest w `fat12._split_path`, ale
nigdy nie wykonała się na prawdziwym Windowsie.

---

## D. Edytor tekstu

| | Krok | Oczekiwany wynik | Co sprawdza |
|---|---|---|---|
| D1 | Dwuklik na pliku tekstowym | Otwiera się edytor | `edit_selected` |
| D2 | Wpisz w pole `Alt+` kod `186`, Enter | Wstawia się `║` | `char_for_code` |
| D3 | **Tablica znaków** | Siatka 256 kodów, najechanie pokazuje numer | `_build_table` |
| D4 | Narysuj ramkę kodami 201, 205, 187 | Wygląda jak ramka | strona kodowa |
| D5 | Zapisz i otwórz ponownie | Ramka nietknięta | bezstratność konwersji |
| D6 | Przełącz stronę kodową na CP852 | Plik wczytany od nowa, podświetlenie się zmienia | `_switch_codepage` |
| D7 | Wpisz polskie znaki przy CP437 i zapisz | Ostrzeżenie z listą znaków | `unmappable` |
| D8 | **Pliki → Nowy plik tekstowy** | Powstaje, zapisuje się z końcami wierszy CR LF | nowy plik |

---

## E. Komplet dyskietek

| | Krok | Oczekiwany wynik | Co sprawdza |
|---|---|---|---|
| E1 | **Dyskietka → Komplet dyskietek** | Okno kreatora | `KompletDialog` |
| E2 | Wskaż katalog źródłowy | Nazwa docelowa podpowiada się sama | `popraw_nazwe` |
| E3 | Wpisz nazwę z kropką, na przykład `GRA.EXE` | Odrzucona z wyjaśnieniem | `sprawdz_nazwe` |
| E4 | Zaplanuj | Plan z podziałem na dyskietki | `zaplanuj` |
| E5 | **Zapisz plan do .txt** | Plik powstaje, polskie znaki czytelne w Notatniku | zapis UTF-8 |
| E6 | Nagraj obrazy | Pliki `DYSK01.img` i dalsze we wskazanym katalogu | `zbuduj` |
| E7 | Otwórz `DYSK01.img` w programie | Są `INSTALL.BAT`, `SETUP.BAT`, `SPIS.TXT` | poprawność obrazu |
| E8 | Wypakuj `SETUP.BAT` i otwórz w Notatniku | Końce wierszy poprawne, bez pustych linii | kodowanie wsadu |
| E9 | Podłącz `DYSK01.img` w 86Box i uruchom `INSTALL` | Instalacja przechodzi do końca | całość |

**Krok E5 jest wart uwagi:** plan zapisuję w UTF-8, a Notatnik w starszych
Windowsach zakłada domyślnie stronę kodową systemu. Jeśli polskie znaki się
sypią, powiedz — zmienię na UTF-8 ze znacznikiem BOM.

---

## F. Język i ustawienia

| | Krok | Oczekiwany wynik | Co sprawdza |
|---|---|---|---|
| F1 | **Język → English** | Całe okno po angielsku, obraz pozostaje otwarty | przebudowa okna |
| F2 | Wróć na polski | Bez błędów, lista nietknięta | `_writable_list` |
| F3 | Zamknij i uruchom ponownie | Język zapamiętany | zapis ustawień |
| F4 | Sprawdź `%USERPROFILE%\.retrozachar.json` | Plik istnieje, czytelny | `_real_home` pod Windows |

---

## G. Okno napędów — tu zaczyna się nieznane

**Ta część kodu nigdy się nie wykonała.** Wywołuje `ctypes` i funkcje
systemowe Windows. Nie podłączaj napędu ani Greaseweazle — chodzi wyłącznie
o sprawdzenie, czy samo otwarcie okna nie wywraca programu.

| | Krok | Oczekiwany wynik | Co sprawdza |
|---|---|---|---|
| G1 | **Napęd → Napędy dyskietek** | Okno się otwiera, program nie znika | `CreateFileW`, `DeviceIoControl` |
| G2 | Treść komunikatu | „Nie znaleziono żadnego napędu dyskietek” albo lista | `_windows_drives` |
| G3 | **Szukaj ponownie** | Nic się nie psuje | ponowne odpytanie |
| G4 | Zamknij okno, popracuj dalej | Reszta programu działa normalnie | brak skutków ubocznych |

Gdy program **zniknie bez komunikatu**, uruchom go z `cmd` przez
`python main.py` — w konsoli zostanie ślad po wyjątku. To najcenniejsza
informacja z całego testu.

---

## H. Wiersz poleceń

```bat
python fat12.py create proba.img --format 1440 --label TEST
python fat12.py add proba.img jakis_plik.txt
python fat12.py list proba.img
python fat12.py addtree proba.img C:\katalog\testowy
python fat12.py --lang en list proba.img
python usbfloppy.py list
```

| | Oczekiwany wynik | Co sprawdza |
|---|---|---|
| H1 | Każde polecenie kończy się bez wyjątku | CLI pod Windows |
| H2 | Komunikaty czytelne w `cmd` | kodowanie konsoli |
| H3 | `usbfloppy.py list` nie wywala się | `ctypes` poza oknem |

Komunikaty są celowo bez polskich znaków, więc `cmd` nie powinien mieć z nimi
kłopotu. Gdyby jednak coś się sypało — zanotuj, to sygnał, że trzeba wykrywać
stronę kodową konsoli.

---

## I. Budowa pliku .exe (opcjonalnie, na koniec)

```bat
python -m PyInstaller --onefile --windowed --icon=jazwiec.ico ^
    --add-data "jazwiec.png;." --add-data "jazwiec-32.png;." ^
    --add-data "jazwiec-panel.png;." --add-data "jazwiec-gw.png;." ^
    --name Jazwiec main.py
```

| | Oczekiwany wynik | Co sprawdza |
|---|---|---|
| I1 | Budowa kończy się bez błędu | wykrywanie zależności |
| I2 | `dist\Jazwiec.exe` uruchamia się | pakowanie |
| I3 | Ikona i grafika na miejscu | `--add-data` |
| I4 | Tworzenie obrazu działa | całość w paczce |

**Spodziewam się tu kłopotu.** Po spakowaniu pliki leżą w katalogu
tymczasowym, a `_znajdz_ikone` szuka ich obok skryptu. Jeśli ikona i grafika
znikną, to właśnie ta przyczyna — poprawka jest prosta, wystarczy uwzględnić
`sys._MEIPASS`. Zgłoś wynik, dopiszę to.

---

## Co zanotować przy błędzie

1. Numer kroku z tej listy.
2. Pełna treść komunikatu, najlepiej zrzut ekranu.
3. Gdy program znika bez śladu — uruchomienie z `cmd` i treść wyjątku.
4. Wersja Windows i wynik `python --version`.

---

## Czego ta lista celowo nie obejmuje

Obsługi fizycznych napędów pod Windowsem i Greaseweazle. To osobny temat,
wymagający sprzętu, i należy do drugiego wydania. Punkt G sprawdza wyłącznie,
czy sama obecność tego kodu nie przeszkadza reszcie programu.
