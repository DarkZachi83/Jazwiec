# RetroZachar — FFD Disk Maker — Jaźwiec

*[English version of this file](README.md)*

Tworzenie i edycja obrazów dyskietek FAT12 dla emulatorów 86Box, PCem i DOSBox.
Program jest pythonową wersją skryptu powłoki, ale bez jego dwóch ograniczeń:
nie wywołuje `mkfs.fat` i nie montuje niczego w systemie, więc działa tak samo
na Linuksie i na Windowsie — i nie potrzebuje `sudo`.

## Pliki

| Plik | Rola |
|---|---|
| `main.py` | punkt startowy — sprawdza, czy da się otworzyć okno |
| `gui_main.py` | okno główne: akcje, stan, język, ustawienia |
| `ui_panels.py` | układ okna: menu, baner, panele, stopka, klawisze |
| `features.py` | wykrywanie części opcjonalnych (napędy, kreator) |
| `styles.py` | wygląd: nazwa, wersja, paleta, czcionki, ikona, fabryki widżetów |
| `system.py` | sudo, katalog domowy, ustawienia, odnajdywanie ikon |
| `dialogs_files.py` | okno kopiowania katalogu i edytor plików tekstowych |
| `dialogs_drive.py` | okna napędów: lista, formatowanie, raport (z `usbfloppy.py`) |
| `dialogs_diskset.py` | kreator kompletu dyskietek (z `diskset.py`) |
| `gwbridge.py` | most do Greaseweazle: uruchamia `gw` i rozbiera jego wyjście |
| `dialogs_gw.py` | okno Greaseweazle (z `gwbridge.py`) |
| `fat12.py` | silnik FAT12 — formatowanie i operacje na plikach |
| `languages.py` | napisy interfejsu (polski, angielski) |
| `dostext.py` | konwersja tekstu między stronami kodowymi DOS |
| `engines.py` | wybór silnika systemu plików dla otwieranego obrazu |
| `diskset.py` | dzielenie programu na komplet dyskietek |
| `usbfloppy.py` | obsługa fizycznych stacji dyskietek |
| `99-retrozachar-floppy.rules` | reguła udev dla napędów (Linux) |
| `install.sh` | instalator dla Linuksa |
| `jazwiec.png` | ikona 256×256 (cała postać) |
| `jazwiec-64.png`, `jazwiec-32.png` | ikona w małych rozmiarach (sama głowa) |
| `jazwiec.ico` | ikona dla Windows, do PyInstallera |
| `jazwiec-panel.png` | grafika pod przyciskiem tworzenia dyskietki |
| `jazwiec-gw.png` | tło raportu w oknie Greaseweazle |

Wszystkie pliki `.py` muszą leżeć w tym samym katalogu.
`diskset.py` jest opcjonalny — bez niego znika tylko kreator kompletu.

## Ikona

Program ma ikonę w trzech rozmiarach. Duża pokazuje całą postać, a 64 i 32
piksele — samą głowę. Nie jest to kaprys: poniżej mniej więcej 48 pikseli
sylwetka z dyskietką zlewa się w nieczytelną plamę, podczas gdy pasy na pysku
borsuka pozostają rozpoznawalne nawet przy 16 pikselach.

Do budowania `.exe` PyInstallerem służy `jazwiec.ico`, zawierający wszystkie
sześć rozmiarów:

```bat
python -m PyInstaller --onefile --windowed --icon=jazwiec.ico ^
    --name RetroZachar main.py
```

## Greaseweazle

[Greaseweazle](https://github.com/keirf/greaseweazle) podłącza do komputera
prawdziwy napęd z epoki i czyta strumień magnetyczny prosto z głowicy.
`gwbridge.py` uruchamia polecenie `gw` i zamienia jego wyjście na raport.

W programie: **Napęd → Greaseweazle**. Osobne okno, a nie pozycja w oknie
stacji USB, bo przepływ pracy jest inny — napęd i format trzeba wskazać, `gw`
nie rozpoznaje ich sam. Okno sprawdza obecność narzędzia i urządzenia,
pozwala zgrać dyskietkę do obrazu, zapisać obraz na dyskietkę i ją
sformatować, a raport pokazuje od razu u siebie. Wybrany napęd i format są
zapamiętywane.

### Mapa ścieżek

Zamiast paska postępu okno pokazuje mapę ścieżek: rząd na każdą stronę
dyskietki, kolumnę na każdy cylinder. Tak samo rysuje swoją mapę `gw` i tak
rysował X-Copy na Amidze. Układ odpowiada fizycznej geometrii, więc wzór
uszkodzenia od razu mówi, co się stało — jeden czerwony kwadrat to
uszkodzone miejsce na nośniku, cały czerwony rząd to martwa głowica.

| Kolor | Znaczenie |
|---|---|
| szary | ścieżka czeka |
| żółty | ścieżka w pracy |
| zielony | w porządku |
| brązowy | odczytana dopiero po ponownych próbach — jeszcze działa, ale słabnie |
| czerwony | sektory nie do odczytania — uszkodzony nośnik |
| purpurowy | sektory z obcego cylindra — **problem napędu, nie dyskietki** |

Czerwony i purpurowy znaczą coś zupełnie innego: pierwszy dotyczy nośnika,
drugi napędu — i tylko ten drugi mówi „nie wkładaj tu niczego cennego".

Gdy **żadna** ścieżka nie daje ani jednego sektora, program nie mówi
o uszkodzeniu, tylko podpowiada najczęstszą przyczynę: inny format niż
wybrany. Dyskietka Amigi czytana jako pecetowa wygląda dokładnie tak —
sprawdzone na prawdziwym nośniku. Drugim wytłumaczeniem jest dyskietka
niesformatowana. Problem napędu sprawdzany jest wcześniej, bo zablokowana
głowica daje ten sam obraz, a rozróżnia je tylko cylinder zapisany
w nagłówkach znalezionych sektorów.

Czerwony nie jest wyrokiem na dyskietkę. Ścieżka zapisana słabo albo
rozmagnesowana wygląda tak samo jak uszkodzona powierzchnia, a formatowanie
i ponowny zapis potrafią ją przywrócić do użytku — sprawdzone na dyskietce,
której ścieżkę rozmagnesował uszkodzony napęd. Dopiero gdy sektory zostają
nieczytelne po świeżym zapisie, nośnik jest naprawdę uszkodzony. Najpierw
warto zgrać z niego, co się da, bo formatowanie kasuje zawartość.

`gw` wypisuje linię po skończeniu ścieżki, nie na jej początku. Żółta jest
więc ścieżka, która wciąż się męczy ponownymi próbami, a gdy takiej nie ma —
następna w kolejności. Przy zapisie `gw` nie raportuje weryfikacji ścieżka
po ścieżce, więc zapisane ścieżki są zielone od razu, a wynik weryfikacji
pokazuje linia stanu.

Najechanie myszą na kwadrat pokazuje szczegóły ścieżki: ile sektorów
odczytano, ile było prób i czy trafiły się sektory z innego cylindra.

Raport z zapisu i formatowania zawiera **mapę ścieżek** — dwa wiersze po
osiemdziesiąt kolumn, po jednym znaku na ścieżkę. `gw` zapisuje całe ścieżki
naraz i nie wypisuje wtedy mapy sektorów, więc dokładniejszej informacji nie
ma skąd wziąć; mapa nazywa się inaczej właśnie po to, żeby tego nie
sugerować.

Raport z odczytu zawiera mapę sektorów w tym samym układzie, w jakim
wypisuje ją `gw`: kolumna to cylinder, wiersz to strona i numer sektora,
kropka to sektor odczytany, `X` — nieczytelny. W oknie znaki `X` są
czerwone, żeby dało się je wypatrzeć na tle obrazu; w zapisanym pliku `.txt`
mapa jest zwykłym tekstem, jak w `gw`. Okno nie da się zwęzić poniżej
szerokości mapy, bo zawinięta mapa straciłaby układ kolumn.

Raport wyświetla się na tle obrazu. Obraz jest przyciemniony czarnym filtrem
o kryciu 70% i ma wygaszone brzegi, a każda linijka tekstu ma pod sobą cień —
na jasnych fragmentach sam tekst tracił kontrast. Tło stoi w miejscu, przewija
się tylko tekst. Pod raportem zostaje wolne miejsce, żeby po przewinięciu do
końca rozpoznanie zatrzymało się nad tytułem wtopionym w obraz. Zaznaczania
tekstu myszą tu nie ma; raport zapisuje się do pliku przyciskiem.

Formatowanie to zapis pustego obrazu FAT12 przez `gw write`. Greaseweazle
zapisuje całą ścieżkę razem z nagłówkami sektorów, więc to pełne
formatowanie niskopoziomowe.

Zapis uznawany jest za udany dopiero wtedy, gdy `gw` potwierdzi weryfikację
zdaniem `All tracks verified`.

Jeśli polecenia `gw` nie ma w ścieżce systemowej — pod Windowsem narzędzia
rozpakowuje się zwykle do dowolnego katalogu — przycisk **Wskaż plik gw**
kieruje program wprost do niego, a wybór zostaje zapamiętany. Bez tego
polecenie potrafi działać w konsoli, a program uruchomiony z Eksploratora
nie widzi go wcale, bo ma inny katalog roboczy.

Dyskietka, która przeleżała lata w kopercie, najgorzej czyta się za pierwszym
razem. Wykładzina wewnątrz koperty zbiera pył przy każdym obrocie, więc nośnik
czyści się sam w trakcie czytania — dyskietka, która w pierwszym podejściu
zgubiła 33 sektory, w drugim oddała wszystkie 1760. Dlatego raport liczy
ścieżki wymagające powtórzeń i, gdy takie są, zaleca ponowny odczyt. Pole
**Prób na ścieżkę** podnosi liczbę podejść, jakie `gw` wykona, zanim odpuści
ścieżkę; z wiersza poleceń robi to `--retries`, a `--seek-retries` każe
dodatkowo dojechać do ścieżki od nowa.

Moduł działa też z wiersza poleceń:

```bash
python3 gwbridge.py info
python3 gwbridge.py read obraz.img --format 1440 --drive A --retries 10
python3 gwbridge.py write obraz.img --format 1440 --drive A
python3 gwbridge.py parse zapisane_wyjscie.txt --format 1440
python3 gwbridge.py --gw /sciezka/do/gw info
```

Formaty pogrupowane są w zakładki według rodzin:

| Zakładka | Formaty | Plik |
|---|---|---|
| PC / DOS | 180 KB, 320 KB, 360 KB, 720 KB, 1,2 MB, 1,25 MB (NEC PC-98), 1,44 MB, 2,88 MB | `.img` |
| Amiga | 880 KB (DD), 1,76 MB (HD) | `.adf` |
| Atari ST | 360 KB, 720 KB, 800 KB, 880 KB | `.st` |

Nazwy formatów sprawdzone na liście z `gw read --help`. Dla 3,5" 360 KB
jednostronnego `gw` nie ma odpowiednika, więc okno go nie proponuje.
Napędy: `A` i `B` na taśmie IBM, `0`–`2` w trybie Shugart.

Rozszerzenie pliku dobiera się samo do wybranego nośnika, bo `gw` po nim
wybiera przekształcenie — dyskietka Amigi zapisana jako `.img` dałaby obrazu,
którego żaden emulator nie otworzy.

**Amigę i Atari można zgrywać i zapisywać, ale nie formatować.** Formatowanie
polega u nas na zapisaniu pustego obrazu, a taki umiemy zbudować tylko
silnikiem FAT12. Przy tych rodzinach przycisk jest wyłączony. Dyskietkę
sformatujesz na maszynie docelowej albo zapiszesz na nią gotowy obraz.

Zgranego obrazu Amigi ani Atari program nie otworzy w oknie głównym — to
zadanie dla przyszłych silników systemów plików. Na razie jest to droga
archiwalna: nośnik do pliku i z powrotem, bit w bit.

Commodore 1541 czeka na swoją kolej: zapisuje różną liczbę sektorów na
ścieżkę zależnie od strefy, co wymaga osobnej obsługi.

**Czego stacja USB nie powie.** Stacja USB na nieczytelną ścieżkę odpowiada
„błąd sektora" i nic więcej. Z wyjścia Greaseweazle da się odczytać,
*dlaczego*. Raport rozróżnia trzy przypadki, które na stacji USB wyglądałyby
identycznie:

- **ścieżka martwa** — głowica stoi dobrze, ale nie da się odkodować żadnego
  sektora; uszkodzony nośnik,
- **sektory z obcego cylindra** — nagłówki podają inny cylinder niż zadany;
  głowica nie dojechała, czyli problem napędu, a lista „złych" sektorów nie
  opisuje stanu dyskietki,
- **głowica milczy** — jedna strona nie czyta niczego, choć druga czyta;
  uszkodzona albo brudna głowica.

To ostatnie ma znaczenie praktyczne: napęd z uszkodzoną głowicą potrafi
zetrzeć ścieżkę, nad którą stoi. Nie wkładaj do niego cennych dyskietek.

Raport podaje też prędkość obrotową napędu, liczoną z czasów odczytu —
przy starych napędach cenna informacja, której stacja USB nie zna.

Polecenie `parse` analizuje zapisane wcześniej wyjście `gw read`, bez
podłączonego urządzenia.

## Testy

```bash
python3 tests/run.py            # wszystko
python3 tests/run.py fat12      # jeden moduł
```

Testy nie dotykają ustawień użytkownika — dostają własny, tymczasowy katalog
domowy. Wcześniejsze wersje zestawu zapisywały do `~/.retrozachar.json`;
jeśli uruchamiałeś je od wersji 2.4, sprawdź ten plik: mogą w nim zostać
ślady w rodzaju katalogu `/sciezka/do/gry`.

Nie wymagają niczego poza biblioteką standardową. Część sprawdzeń potrzebuje
narzędzi, których może nie być — te są pomijane, nie zgłaszane jako błędy:
`fsck.fat` z pakietu `dosfstools` służy jako niezależne potwierdzenie
poprawności obrazów, a testy okna wymagają serwera graficznego. Pod Linuksem
bez pulpitu pomaga `xvfb-run -a python3 tests/run.py`.

Najmocniejszym sprawdzeniem jest symulacja instalatora: wykonuje wygenerowany
plik wsadowy tak, jak zrobiłby to `COMMAND.COM` — razem ze zmianami dyskietek
i sklejaniem plików podzielonych — a na koniec porównuje odtworzone drzewo ze
źródłem bajt w bajt. Bez DOS-a pod ręką to jedyny sposób, żeby sprawdzić
instalator naprawdę, a nie tylko obejrzeć go wzrokiem.

Zestaw powstał po dwóch regresjach, które faktycznie wystąpiły: zniknęła cała
klasa edytora tekstu przy nieuważnej przebudowie pliku, a to samo
niedopatrzenie z podświetlaniem wybranej pozycji powtórzyło się kolejno
w czterech oknach. Oba przypadki mają teraz swoje testy.

## Instalacja w systemie (Linux)

```bash
sudo ./install.sh
```

Program pojawi się w menu systemowym i będzie się uruchamiał poleceniem
`retrozachar` z dowolnego katalogu. Pliki trafiają do `/usr/local`:

| Ścieżka | Zawartość |
|---|---|
| `/usr/local/lib/retrozachar/` | kod programu |
| `/usr/local/bin/retrozachar` | polecenie uruchamiające |
| `/usr/local/share/applications/` | wpis w menu |
| `/usr/local/share/icons/hicolor/` | ikony 256, 64 i 32 piksele |
| `/etc/udev/rules.d/` | reguła dostępu do napędów |

Bez uprawnień administratora instalujesz tylko dla siebie, w `~/.local`:

```bash
./install.sh --user
```

Odinstalowanie: `sudo ./install.sh --uninstall` (lub z `--user`).

**Nie uruchamiaj programu przez `sudo`.** Uprawnienia administratora są
potrzebne wyłącznie do samej instalacji. Uruchomiony jako root zapisałby
ustawienia do `/root/.retrozachar.json`, a utworzone obrazy `.img` należałyby
do roota i nie dałbyś rady ich później edytować.

## Uruchomienie bez instalacji

```bash
python3 main.py
```

Wymagany jest tylko Python 3.9 lub nowszy. Windows i macOS mają Tkinter
w standardowej instalacji; na Debianie i Ubuntu trzeba doinstalować pakiet:

```bash
sudo apt install python3-tk
```

Pod Windowsem wygodniej zapisać plik jako `main.pyw` — wtedy nie
otwiera się okno konsoli.

## Co program potrafi

Dziewięć historycznych formatów, z geometrią zgodną z oryginalnymi napędami.
W interfejsie są podzielone na dwie zakładki.

**Popularne formaty**

| Format | Klucz CLI | Pojemność | Klastry | Katalog główny |
|---|---|---|---|---|
| 5,25" 360 KB (PC/XT) | `360` | 368 640 B | 354 | 112 |
| 5,25" 1,2 MB (AT/286) | `1200` | 1 228 800 B | 2371 | 224 |
| 3,5" 720 KB (DD) | `720` | 737 280 B | 713 | 112 |
| 3,5" 1,44 MB (HD) | `1440` | 1 474 560 B | 2847 | 224 |

**Inne formaty**

| Format | Klucz CLI | Pojemność | Klastry | Katalog główny |
|---|---|---|---|---|
| 5,25" 180 KB (jednostronna) | `180` | 184 320 B | 351 | 64 |
| 5,25" 320 KB (8 sektorów) | `320` | 327 680 B | 315 | 112 |
| 3,5" 360 KB (jednostronna DD) | `360_35` | 368 640 B | 354 | 112 |
| 3,5" 1,25 MB (NEC PC-98) | `1250` | 1 261 568 B | 1221 | 192 |
| 3,5" 2,88 MB (Extra Density) | `2880` | 2 949 120 B | 2863 | 240 |

Format PC-98 jako jedyny używa sektorów po 1024 bajty zamiast 512 — to
oryginalna geometria NEC-a (77 ścieżek, 8 sektorów, 2 głowice).

Zamiast montowania obrazu program ma wbudowany menedżer plików. Można w nim
kopiować pliki w obie strony, zakładać i kasować katalogi, zmieniać nazwy oraz
etykietę wolumenu. Widać też na bieżąco, ile miejsca zostało.

Utworzony `.img` podłącza się w 86Box przez *Settings → Floppy drives*.

## Fizyczna stacja dyskietek

Menu **Napęd → Napędy dyskietek** wykrywa podłączone stacje, zgrywa nośnik
sektor po sektorze do pliku `.img` i zapisuje obraz z powrotem na dyskietkę.
Zgrany obraz otwiera się od razu w prawym panelu.

### Uprawnienia — bez uruchamiania programu z sudo

Surowy dostęp do urządzenia jest zastrzeżony, ale program nie musi z tego
powodu pracować jako root. `install.sh` zakłada regułę udev
(`/etc/udev/rules.d/99-retrozachar-floppy.rules`), która nadaje dostęp do
samych napędów dyskietek zalogowanemu użytkownikowi. Po jej instalacji
wystarczy podłączyć napęd ponownie.

Reguła obejmuje wyłącznie stacje dyskietek. Sprawdza klasę pamięci masowej
(`bInterfaceClass` `08`) i podklasę: napędy dyskietek zgłaszają się jako UFI
(`0x04`) albo SFF-8070i (`0x05`), podczas gdy pendrive'y używają SCSI
transparent (`0x06`) i pozostają poza jej zasięgiem. Objęty jest też napęd na
kontrolerze płyty głównej (`/dev/fd*`).

Dostęp nadaje `MODE="0666"`. Wcześniejsza wersja opierała się na
`TAG+="uaccess"`, czyli liście ACL przyznawanej przez systemd-logind osobie
zalogowanej lokalnie, ale ten mechanizm nie działa na części konfiguracji
i zostawiał napęd niedostępny. Ceną za pewność działania jest to, że na
komputerze wieloużytkownikowym każde konto może czytać i zapisywać włożoną
dyskietkę. Gdyby to przeszkadzało, wystarczy w pliku reguły zmienić `MODE`
na `0660` i dopisać `GROUP` z wybraną grupą.

Jeśli napęd mimo reguły pozostaje niedostępny, sprawdź, jaką podklasę zgłasza:

```bash
lsusb -v 2>/dev/null | grep -E "bInterfaceClass|bInterfaceSubClass"
```

Część starszych stacji podaje `0x06`. Wtedy lepiej dopisać regułę dla
konkretnego egzemplarza po `idVendor` i `idProduct`, niż obejmować całą
podklasę — należą do niej także pendrive'y i dyski zewnętrzne. Gotowy wzór
jest w komentarzu na końcu pliku reguły.

Pod Windowsem UAC obejść się nie da. Program startuje normalnie i prosi
o podniesienie uprawnień dopiero wtedy, gdy naprawdę sięgasz po napęd,
oferując restart jednym kliknięciem.

Gdyby ktoś mimo wszystko uruchomił program przez `sudo`, zadziała
zabezpieczenie: ustawienia trafią do katalogu domowego właściwego
użytkownika, a nie roota, a tworzone pliki dostaną jego własność.

### Czego taka stacja nie potrafi

Napęd USB oddaje sektory logiczne, a nie strumień magnetyczny. W praktyce
przeczyta zwykłą dyskietkę 1,44 MB albo 720 KB, rzadziej 1,2 MB. Nie poradzi
sobie z zabezpieczeniem antykopiowym, niestandardową liczbą sektorów ani
zapisem FM. Do poważnej archiwizacji służą kontrolery strumieniowe
(Greaseweazle, KryoFlux).

### Czego żaden napęd PC nie odczyta

Dyskietek Amigi. Amiga zapisuje 11 sektorów po 512 bajtów na ścieżkę we
własnym kodowaniu MFM, dekodowanym programowo przez `trackdisk.device`.
Kontroler PC oczekuje ściśle określonego układu sektorów i tego formatu nie
rozumie — to ograniczenie sprzętowe, nie brak funkcji w programie. Odczyt
takich nośników wymaga kontrolera strumieniowego (Greaseweazle, KryoFlux)
albo samej Amigi.

Objaw jest charakterystyczny: napęd ponawia próby przez dwie, trzy minuty
i wygląda na zawieszony. Program przerywa odczyt po 20 sekundach i podaje
przyczynę, zamiast czekać razem z napędem.

### Podgląd zawartości dyskietki

Przycisk **Podejrzyj zawartość** otwiera system plików włożonej dyskietki
wprost w prawym panelu. Działa tam wszystko, co przy obrazach: nawigacja po
katalogach, zaznaczanie wielu pozycji i wypakowywanie pojedynczych plików
klawiszem F9.

Odczyt jest leniwy. Żeby pokazać listę plików, program czyta wyłącznie obszar
systemowy — sektor rozruchowy, tablice FAT i katalog główny, czyli 33 sektory
z 2880 dla dyskietki 1,44 MB. Wejście do podkatalogu dociąga jego klastry,
a wypakowanie pliku tylko te, które ten plik zajmuje. W praktyce obejrzenie
zawartości i wyciągnięcie jednego pliku to około 2% powierzchni nośnika
zamiast 100%.

Ma to znaczenie przy dyskietkach w kiepskim stanie: nie męczysz całej
powierzchni, żeby zobaczyć, co na niej jest. Sektory, których nie da się
odczytać, nie przerywają podglądu — program je pomija i podaje ich liczbę.

Podgląd jest tylko do odczytu; przyciski zmieniające zawartość są w tym
trybie wyłączone. Żeby zapisać coś na dyskietkę, użyj zgrania do `.img`,
edycji obrazu i zapisania go z powrotem.

### Formatowanie dyskietki

Przycisk **Formatuj dyskietkę** w oknie napędu czyści nośnik i zapisuje na nim
świeży system plików FAT12. Do wyboru są dwa tryby:

- **szybki** — sam system plików, kilka sekund;
- **pełny** — najpierw test całej powierzchni wzorcem kontrolnym, potem zapis
  systemu plików. Uszkodzone klastry zostają oznaczone w tablicy FAT jako złe
  (`0xFF7`), więc DOS przestaje ich używać — dokładnie tak, jak robi to
  polecenie `FORMAT`. Test przechodzi nośnik czterokrotnie i trwa kilka minut.

Po zakończeniu otwiera się raport z listą uszkodzonych sektorów, liczbą
oznaczonych klastrów, utraconą pojemnością i wynikiem weryfikacji. Można go
zapisać do pliku `.txt`.

### Zmiana gęstości, na przykład 1,44 MB na 720 KB

Formaty niezgodne z włożoną dyskietką też są na liście, oznaczone jako
wymagające zmiany gęstości. Wybranie takiego uruchamia najpierw
przestawienie nośnika, a zaraz po nim normalne formatowanie — jednym
przyciskiem.

Zmiany gęstości nie da się zlecić przez system plików; potrzebne jest
polecenie FORMAT UNIT protokołu UFI. Pod Linuksem wykonuje je `ufiformat`
z pakietu `ufiutils`:

```bash
sudo apt install ufiutils
```

Bez niego pozycja pozostaje widoczna, ale przycisk *Formatuj* jest
nieaktywny, a okno podaje polecenie do zainstalowania.

Pod Windowsem program nie robi tego za Ciebie — wyświetla komendę do
uruchomienia w wierszu poleceń jako Administrator:

```
format A: /F:720
```

Po jej wykonaniu wróć do programu, odśwież listę napędów i sformatuj nośnik
normalnie.

Warto dodać, że dyskietki Amigi używają własnego formatu 880 KB, którego PC
nie zapisze. Zmiana gęstości przygotowuje sam nośnik; właściwe formatowanie
wykonuje się już na Amidze.

### Diagnostyka: `probe`

Zanim uznasz napęd za zepsuty, sprawdź go poleceniem, które nie zakłada
obecności systemu plików:

```bash
python3 usbfloppy.py probe /dev/sdb
```

Rozróżnia trzy sytuacje, które z zewnątrz wyglądają identycznie: nośnik
czytelny bez systemu plików (wystarczy sformatować, sprzęt sprawny), nośnik
nieoddający danych (zła gęstość albo uszkodzona dyskietka) oraz brak nośnika
w napędzie.

Komunikat menedżera plików „can't read superblock" pochodzi od udisks
i znaczy wyłącznie tyle, że na nośniku nie ma czytelnego systemu plików.
Nie mówi nic o sprawności napędu — jeśli `/dev/sdb` w ogóle istnieje,
enumeracja USB zadziałała.

### Dyskietka HD sformatowana na 720 KB

Napęd rozpoznaje gęstość po otworze w rogu obudowy dyskietki, a nie po tym,
co jest na niej zapisane. Dyskietka HD niskopoziomowo sformatowana na 720 KB
nadal ma otwarty otwór HD, więc napęd czyta ją w trybie wysokiej gęstości
i nie trafia w ścieżki zapisane w DD. Objaw: napęd zgłasza 1 440 KB,
a `probe` pokazuje zero odczytanych sektorów.

To nie jest awaria sprzętu. Dwa wyjścia:

1. **Zaklej otwór HD** nieprzezroczystą taśmą — róg przeciwległy do suwaka
   zabezpieczenia przed zapisem. Napęd rozpozna nośnik jako DD i odczyta
   zapis 720 KB. Tak przygotowuje się nośniki dla Amigi.
2. **Przywróć dyskietkę do HD**: `ufiformat -f 1440 /dev/sdb`, a potem
   sformatuj ją normalnie w programie.

Program ostrzega o tym przed zejściem z HD na DD i podaje polecenie powrotu.

### Gdy napęd przestanie reagować

Objaw: system próbuje odczytać dyskietkę, ale silnik nie rusza. Napęd
utknął w stanie wewnętrznym, którego nie skasuje żadne polecenie systemowe.

Postępowanie: wyjmij dyskietkę, odłącz kabel USB, odczekaj kilka sekund
i podłącz ponownie. Stan sterownika kasuje wyłącznie odcięcie zasilania —
`udevadm trigger` ani ponowne uruchomienie programu nic tu nie dadzą.

Przyczyną jest niemal zawsze polecenie `FORMAT UNIT`, czyli zmiana gęstości.
Tańsze napędy zgłaszają się jako zgodne z protokołem UFI, ale tego polecenia
nie wykonują poprawnie i potrafią po nim zawisnąć. Dlatego program przed
wysłaniem czegokolwiek odpytuje napęd o obsługiwane formaty i pokazuje
odpowiedź — jeśli żądanej pojemności tam nie ma, lepiej nie kontynuować.

Co program robi na urządzeniu poza zmianą gęstości: wyłącznie `open`, `seek`,
`read`, `write` i `fsync` na węźle blokowym. Są to zwykłe operacje na
zawartości nośnika; nie sięgają protokołu USB ani sterownika napędu i nie
mogą go przestawić w inny tryb. Zwykłe formatowanie, zgrywanie i zapis obrazu
nie wywołują żadnego polecenia zewnętrznego.

Diagnostyka na Linuksie:

```bash
dmesg | tail -40          # resety USB i błędy SCSI
lsof /dev/sdb             # czy coś trzyma urządzenie otwarte
which ufiformat           # czy zmiana gęstości była w ogóle możliwa
```

Ostatnie polecenie rozstrzyga najwięcej. Bez zainstalowanego `ufiformat`
przycisk zmiany gęstości jest nieaktywny, więc program nie miał czym wysłać
`FORMAT UNIT` — a wtedy przyczyny trzeba szukać w samym sprzęcie.

### Dwa różne progi dla uszkodzonych sektorów

Program rozróżnia sektory **martwe** i **słabe** — takie, które wracają
dopiero przy kolejnej próbie odczytu. Traktuje je inaczej w zależności od
tego, na jakie pytanie odpowiada dana operacja.

**Test powierzchni przy formatowaniu** jest surowy: jedna próba, a sektor
wymagający ponowienia zostaje oznaczony jako zły. Odpowiada na pytanie „czy
mogę tu bezpiecznie złożyć dane", więc lepiej odrzucić sektor z pogranicza,
niż zapisać na nim plik. Tak samo postępuje DOS-owy `FORMAT`.

**Weryfikacja po zapisie** jest łagodniejsza: tyle samo prób co przy zwykłym
odczycie. Odpowiada na pytanie „czy zapis się udał", a sektor odczytany za
drugim podejściem został zapisany poprawnie. Jedna próba zawyżała tu liczbę
błędów i straszyła bardziej, niż stan nośnika na to zasługiwał.

### Uszkodzone sektory

Odczyt idzie porcjami po 32 sektory. Kiedy porcja się nie uda, program schodzi
do pojedynczych sektorów, żeby ustalić, które dokładnie są wadliwe, i ponawia
każdy trzykrotnie. Sektorów nieodczytanych nie pomija — wypełnia je bajtem
`0xF6` i wypisuje ich listę. Z dyskietki uszkodzonej w kilku miejscach
odzyskujesz więc całą resztę zamiast niczego.

### Zabezpieczenia przy zapisie

Zapis na urządzenie fizyczne jest nieodwracalny, więc działają cztery zapory
naraz. Nośnik musi być wymienny, jego rozmiar musi co do bajtu odpowiadać
jednej ze znanych geometrii dyskietek, nie może przekraczać 4 MB i nie może
być zamontowany. Urządzenia większe niż limit nie trafiają nawet na listę —
pendrive ani dysk zewnętrzny nie mają jak się tam pojawić. Na koniec rozmiar
obrazu musi zgadzać się z rozmiarem nośnika, a po zapisie program czyta
dyskietkę z powrotem i porównuje ją z obrazem.

### Wiersz poleceń

```bash
python3 usbfloppy.py list
python3 usbfloppy.py read /dev/sdb kopia.img
python3 usbfloppy.py write /dev/sdb obraz.img
```

Bez zainstalowanej reguły udev te polecenia wymagają `sudo`.

## Język

Program startuje po polsku. Angielski wybierasz z menu **Język → English**;
wybór zapisuje się w `~/.retrozachar.json` i obowiązuje przy kolejnych
uruchomieniach. Przełączenie działa od razu i nie zamyka otwartego obrazu —
zostaje też bieżący katalog i zaznaczony format.

Tłumaczeniu podlegają nie tylko napisy okna, ale i komunikaty silnika oraz
opisy formatów, łącznie z separatorem dziesiętnym (`1,44 MB` kontra
`1.44 MB`). Nowy język dodaje się przez dopisanie słownika w `languages.py`
i w `fat12.MESSAGES` — brakujące klucze cofają się do polskiego, więc
niekompletne tłumaczenie nie wywali programu.

Wiersz poleceń przyjmuje `--lang`:

```bash
python3 fat12.py --lang en list dysk.img
```

## Budowa: silniki systemów plików (`engines.py`)

Interfejs nie wie, że czyta akurat FAT12. Otwierany plik trafia najpierw do
`engines.py`, który rozpoznaje format **po zawartości**, a nie po rozszerzeniu,
i zwraca obiekt obrazu o ustalonym zestawie metod. Ścieżki i skracanie nazw
też idą przez ten obiekt, bo każdy system plików ma tu własne zasady — FAT12
tnie nazwy do 8.3, AmigaDOS dopuszcza trzydzieści znaków.

Dołożenie kolejnego systemu plików sprowadza się dzięki temu do napisania
modułu i zarejestrowania go w `engines.py`, bez dotykania okna. Wzór takiej
rejestracji jest w komentarzu na początku tego pliku. Pierwszym kandydatem
jest AmigaDOS, czyli pliki `.adf`.

Gdy żaden silnik nie rozpoznaje pliku, program mówi wprost, co obsługuje,
zamiast wypisywać błąd parsowania.

## Edytor plików tekstowych

Dwuklik na pliku otwiera go w edytorze. Można też przez **Pliki → Edytuj plik
tekstowy** albo założyć nowy przez **Pliki → Nowy plik tekstowy**.

Sens tego jest jeden: pisanie `autoexec.bat` z ramkami pod DOS-em to udręka,
a w nowoczesnym edytorze rozbija się o kodowanie. Ramka `╔══╗` to w DOS-ie
bajty strony kodowej 437; zapisana jako UTF-8 rozsypie się przy pierwszym
uruchomieniu.

Edytor pokazuje bajty DOS-owe jako znaki Unicode, więc ramki i litery
diakrytyczne wyglądają tak, jak wyglądały na ekranie DOS, i poprawia się je
zwyczajnie. Przy zapisie wracają do wybranej strony kodowej.

| Strona kodowa | Do czego |
|---|---|
| CP437 | DOS US, pełny zestaw znaków półgraficznych |
| CP852 | Europa Środkowa, polskie znaki diakrytyczne |
| CP850 | Europa Zachodnia |

Wszystkie trzy przypisują każdemu z 256 bajtów inny znak, więc plik otwarty
i zapisany bez zmian wraca na dyskietkę **bajt w bajt** — sprawdzone testem
na pełnym zakresie. Można więc bezpiecznie zajrzeć nawet do pliku, którego
się nie zamierza zmieniać.

### Wpisywanie znaków po kodzie

Dosowe `Alt+186` nie zadziała — Tkinter nie obsługuje tej kombinacji
z klawiaturą numeryczną. Zamiast tego w edytorze jest pole **Alt+**: wpisujesz
`186`, naciskasz Enter i dostajesz `║`. Przyjmowane są też kody
szesnastkowe, na przykład `0xDB`.

Kto woli wybierać wzrokiem, ma przycisk **Tablica znaków** — siatkę
wszystkich 256 kodów bieżącej strony kodowej. Najechanie pokazuje numer
dziesiętny i szesnastkowy, kliknięcie wstawia znak w miejscu kursora.

Symbole ozdobne z zakresu 1–31 (`☺ ♥ ♪ ►`) też są dostępne, choć wymagało to
osobnej tablicy: pythonowe kodeki odwzorowują te bajty na znaki sterujące,
a nie na dosowe symbole. Kody, które w danej stronie kodowej byłyby
niejednoznaczne — jak `§` w CP852, mające już swój kod 245 — pozostają
w tablicy wygaszone, żeby zapis nie przestał być odwracalny.

Edytor pilnuje też dwóch rzeczy, o których łatwo zapomnieć: końce wierszy
zapisuje jako `CR LF`, a historyczny znacznik końca pliku `0x1A` odtwarza,
jeśli był w oryginale. Gdy wpiszesz znak, którego wybrana strona kodowa nie
zna — na przykład polskie litery przy CP437 — program wymieni je przed
zapisem i podpowie CP852.

## Wymiana plików z emulatorem

Ten sam plik `.img` może być jednocześnie zamontowany w 86Box i otwarty
w programie, co daje kanał wymiany plików między komputerem a emulowaną
maszyną — 86Box nie ma współdzielonych katalogów, więc bywa to najwygodniejsza
droga.

**Obowiązuje jedna zasada: naraz zapisuje tylko jedna strona.** Program trzyma
cały obraz w pamięci i przy zapisie odkłada plik w całości. Bez ostrożności
nadpisałby wszystko, co gość zapisał w międzyczasie.

Program pilnuje tego za Ciebie. Zapamiętuje stan pliku i sprawdza go przed
każdym zapisem oraz przy odświeżaniu listy:

- gdy plik zmienił się na dysku, a Ty tylko przeglądasz zawartość, program
  wczytuje go ponownie i mówi o tym w pasku stanu;
- gdy zmienił się, a Ty próbujesz coś zapisać, pyta, co zrobić: wczytać
  ponownie i porzucić operację, nadpisać mimo to, czy nic nie robić.

Kolejność, która działa bez niespodzianek:

1. **Z komputera do emulatora** — wrzuć pliki w programie, potem w 86Box wysuń
   i włóż dyskietkę ponownie (*Settings → Floppy drives*). Bez tego DOS nadal
   widzi starą zawartość, bo trzyma katalog w pamięci podręcznej.
2. **Z emulatora do komputera** — w 86Box wysuń dyskietkę, żeby zmiany trafiły
   do pliku, a w programie naciśnij F2. Zawartość wczyta się od nowa.

## Komplet dyskietek dla programu większego niż nośnik

**Dyskietka → Komplet dyskietek (Jaźwiec)** rozkłada katalog na kolejne
nośniki i dopisuje na pierwszym instalator, który składa wszystko z powrotem
na dysku twardym maszyny docelowej. Gra wielkości 4,3 MiB to cztery dyskietki
1,44 MB albo siedem 720 KB.

Instalator jest zwykłym plikiem wsadowym i używa **wyłącznie** poleceń
wbudowanych w `COMMAND.COM`: `MD`, `COPY`, `DEL`, `ECHO`, `PAUSE`, `IF EXIST`
i `GOTO`. Na maszynie docelowej nie trzeba więc niczego — ani archiwizatora,
ani żadnego narzędzia. Działa na czystym DOS-ie 3.3.

Na maszynie docelowej:

```
A:
INSTALL
```

### Dysk i katalog docelowy

Dysk wybierasz w kreatorze, obok nazwy katalogu — domyślnie `C:`, ale przy
maszynach z epoki dysk systemowy bywa ciasny i warto celować w inny.

Przed jakąkolwiek operacją instalator pokazuje cel, **wypisuje dostępne
dyski** i czeka na potwierdzenie klawiszem; Ctrl+C przerywa. Gdyby wskazany
dysk nie istniał, mówi o tym wprost, zamiast kończyć mylącym błędem `MD`.

Dysk można też podać przy uruchomieniu, razem z napędem źródłowym:

```
INSTALL D: B:
```

**Dlaczego instalator nie pyta o ścieżkę.** Wsad DOS-a nie potrafi wczytać
tekstu z klawiatury — `SET /P` pojawiło się dopiero w `cmd` z Windows 2000,
a `CHOICE.COM` czyta pojedynczy klawisz i jest plikiem Microsoftu, którego
nie wolno rozprowadzać. Wybór zapada więc przy nagrywaniu albo parametrem.
Listę dostępnych dysków da się jednak pokazać: `IF EXIST D:\NUL` sprawdza
w DOS-ie, czy dysk o tej literze istnieje.

### Nazwa katalogu docelowego

Kreator proponuje nazwę na podstawie katalogu źródłowego, ale **tylko
proponuje** — i warto ją poprawić. Katalogi z dysków mają nazwy opisowe,
a mechaniczne skrócenie `Pool of Radiance (1988)(Strategic Simulations,
Inc.) [Role-Playing (RPG)]` daje `POOLOFRA.)_R`, bo kropka przed `)` wygląda
jak początek rozszerzenia. Wpisz po prostu `POOL`.

Przyjmowanych jest najwyżej osiem znaków, bez kropki i spacji — taki jest
limit DOS-a. Nazwa jest sprawdzana przed planowaniem; przy niedozwolonych
znakach program mówi, które to.

Jeżeli po zaplanowaniu zobaczysz ostrzeżenie, że wszystkie pliki leżą
w jednym podkatalogu, prawdopodobnie wskazałeś katalog o poziom za wysoko —
cała gra wylądowałaby wtedy w zagnieżdżonym katalogu o skróconej nazwie.

### Nazwy zakładane przez instalator

Wsad instalatora ląduje w katalogu docelowym, obok plików programu, i jest
stamtąd wykonywany. Gdyby program miał plik o tej samej nazwie, skopiowanie go
nadpisałoby wsad **w trakcie działania** — a `COMMAND.COM` czyta wsad
przyrostowo, więc od tej chwili czytałby cudzy plik. Instalacja przerywa się
wtedy na pierwszej zmianie dyskietki.

Ryzyko nie jest teoretyczne: `SETUP.BAT` ma połowa gier z epoki. Dlatego wsad
nazywa się `JAZWIEC.BAT`, a program sprawdza przy planowaniu, czy taka nazwa
nie występuje w katalogu głównym programu. Gdy występuje — wybiera
`JAZWIEC1.BAT` i mówi o tym w planie. To samo dotyczy przedrostka nazw
tymczasowych części plików podzielonych.

### Dlaczego instalator jest dwuczęściowy

Instalator nie używa zmiennych środowiskowych. Środowisko DOS-a ma domyślnie
256 bajtów i `SET` potrafi się w nim nie zmieścić; nierozwinięte `%ZMIENNA%`
zamienia się wtedy w pusty ciąg, przez co `COPY` ładuje wsad na dyskietkę
zamiast na dysk twardy. Litery dysków są więc wpisane na stałe w osobnych
gałęziach, a dalej idą jako parametry wsadu.

`COMMAND.COM` czyta plik wsadowy przyrostowo — po każdej linii wraca na nośnik
po następną. Wsad leżący na dyskietce, który prosi o jej zmianę, przy kolejnej
linii czytałby już z innego nośnika i sypałby się w sposób trudny do
zdiagnozowania. Dlatego na dyskietce pierwszej jest tylko krótki `INSTALL.BAT`,
który kopiuje właściwy `SETUP.BAT` na dysk twardy i oddaje mu sterowanie.
Od tej chwili wykonywany wsad leży na dysku i zmiany dyskietek mu nie szkodzą.

### Co uwzględnia planowanie

Miejsce liczone w klastrach, nie w sumie rozmiarów. Limit wpisów w katalogu
głównym — 224 przy 1,44 MB, 112 przy 720 KB; przy wielu drobnych plikach to
on kończy się pierwszy, nie miejsce. Limit ścieżki DOS-a (64 znaki) i długości
linii wsadu. Pliki większe od dyskietki są dzielone na części i sklejane poleceniem
`COPY /B` po skopiowaniu wszystkich. Sklejanie idzie przyrostowo, ścieżkami
względnymi — jedna długa komenda z pełnymi ścieżkami przekraczała limit
długości wiersza DOS-a już przy pięciu częściach. Każda część jest kasowana
zaraz po doklejeniu, więc w szczycie potrzeba miejsca na gotowy plik i jedną
część, a nie na plik i wszystkie części naraz.

Katalogi są tworzone od najpłytszych, bo `MD` w DOS-ie nie zakłada ścieżek
wielopoziomowych. Odtwarzane są też katalogi puste w źródle — niejedna gra
wymaga istnienia katalogu na zapisy stanu i bez niego przerywa działanie.

Plan pokazywany jest w całości **przed** nagraniem i można go zapisać do `.txt`.

### Dyskietka startowa

Program jej nie utworzy i nie próbuje — wymagałoby to plików systemowych,
których nie wolno mu rozprowadzać. Zamiast tego przyjmuje gotowy obraz
startowy jako podstawę pierwszej dyskietki i dopisuje instalator w wolnym
miejscu. Dyskietkę przygotujesz poleceniem `FORMAT A: /S` w emulatorze
i zapiszesz jako obraz.

## Kopiowanie katalogów

**Pliki → Dodaj katalog z podkatalogami** przenosi na obraz całą strukturę:
katalogi, podkatalogi i pliki w środku. Nie trzeba już zakładać katalogów
ręcznie przed skopiowaniem zawartości.

Przed rozpoczęciem program pokazuje podsumowanie — ile plików i katalogów,
jaki rozmiar, ile zostało wolnego miejsca i czy się zmieści — oraz **podgląd
zawartości** wybranego katalogu.

Ten podgląd nie jest ozdobnikiem. Okno wyboru katalogu w Tk zwraca katalog
*otwarty*, a nie ten podświetlony na liście, więc żeby wskazać podkatalog,
trzeba w niego wejść dwuklikiem. Łatwo o pomyłkę o jeden poziom. Gdy w podglądzie
widać jedną pozycję w nawiasach kwadratowych zamiast spodziewanych plików,
wskazałeś za wysoko — a przycisk **Zmień** pozwala to poprawić bez zamykania
okna. Przy katalogu zawierającym wyłącznie jeden podkatalog program dodatkowo
o tym uprzedza. Do wyboru są dwa
warianty: utworzenie na dyskietce katalogu o nazwie źródłowego albo
skopiowanie samej zawartości do bieżącego miejsca.

Nazwy katalogów podlegają temu samemu skracaniu do 8.3 co nazwy plików, więc
`Dokumentacja PL` trafia na dyskietkę jako `DOKUMENT`. Program wypisuje listę
takich zamian po zakończeniu.

Gdy zawartość nie mieści się na nośniku, kopiowanie nie jest przerywane —
program przenosi tyle, ile się da, i wymienia konkretne pliki, które pominął.
Struktura katalogów pozostaje nienaruszona.

Dowiązania symboliczne są pomijane: na dyskietce nie mają odpowiednika,
a podążanie za nimi groziłoby zapętleniem.

Z wiersza poleceń:

```bash
python3 fat12.py addtree dysk.img ./gra --dest /
python3 fat12.py addtree dysk.img ./gra --contents-only
```

## Skróty klawiszowe

| Klawisz | Działanie |
|---|---|
| F1 | pomoc |
| F2 | odśwież listę |
| F3 | otwórz obraz |
| F5 | dodaj pliki na dyskietkę |
| F6 | zmień nazwę |
| F7 | nowy katalog |
| F8 | usuń zaznaczone |
| F9 | wypakuj na dysk twardy |
| F10 | zakończ |
| Ctrl+L | etykieta wolumenu |
| Backspace | katalog wyżej |

## Tryb wiersza poleceń

`fat12.py` działa również samodzielnie, co przydaje się w skryptach:

```bash
python3 fat12.py create dysk.img --format 1440 --label DANE
python3 fat12.py add dysk.img config.sys autoexec.bat
python3 fat12.py mkdir dysk.img /UTILS
python3 fat12.py list dysk.img
python3 fat12.py extract dysk.img README.TXT ./readme.txt
python3 fat12.py rm dysk.img /UTILS -r
```

## O czym warto wiedzieć

**Nazwy 8.3.** DOS czyta wyłącznie nazwy w formacie 8.3, więc `moje notatki.txt`
trafia na dyskietkę jako `MOJENOTA.TXT`. Program pokazuje listę takich zmian po
skopiowaniu plików. Przy kolizji nazw dokleja tyldę: `PLIK~1.TXT`.

**Katalog główny ma sztywny limit** — 112 albo 224 pozycji, zależnie od
formatu, niezależnie od wolnego miejsca. Przy większej liczbie plików trzeba
założyć podkatalog.

**Obrazy startowe.** Sektor rozruchowy zawiera poprawny blok BPB i krótki kod,
który wypisuje komunikat o braku systemu. Żeby dyskietka startowała, trzeba
przenieść na nią system osobno (`SYS A:` w emulowanym DOS-ie).

## Różnice wobec pierwotnego skryptu

Skrypt powłoki tworzył pusty plik przez `dd`, formatował go przez `mkfs.fat` i
montował przez `sudo mount -o loop`. Żadne z tych trzech narzędzi nie istnieje
pod Windowsem, więc system plików jest tu zapisywany bezpośrednio: sektor
rozruchowy, obie kopie tablicy FAT, katalog główny i obszar danych powstają
bajt po bajcie w Pythonie.

Zachowane zostało zabezpieczenie przed nadpisaniem istniejącego pliku — z tą
różnicą, że zamiast przerywać operację, program pyta o potwierdzenie.

Poprawność wyniku sprawdzono niezależnymi narzędziami: `fsck.fat` nie zgłasza
zastrzeżeń do żadnego z dziewięciu formatów — również po zapisaniu plików,
utworzeniu podkatalogów i ich zagnieżdżeniu — a `mtools` poprawnie odczytuje
całą zawartość.

## Jak to powstało

Program napisałem razem z Claude, asystentem AI firmy Anthropic. Decyzje
projektowe, wszystkie testy sprzętowe i sprawdzenie działania na prawdziwych
dyskietkach, napędach i emulatorach są moje. Sporo z tego, co program potrafi
— zwłaszcza w diagnostyce Greaseweazle — wzięło się z obserwacji poczynionych
podczas tych testów, a nie z teorii.

## Licencja

MIT — zobacz [LICENSE](LICENSE).

Copyright (c) 2026 Rafał Zacharski (Retro Zachar)
