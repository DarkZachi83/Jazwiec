# Historia zmian

Numery wersji odpowiadają wartości `APP_VERSION` w `styles.py`.

## 1.6.1

- Okno wyboru pliku pokazuje obrazy bez względu na wielkość liter
  w rozszerzeniu. 86Box zapisuje dyski jako `210MB.VHD`, a Tkinter pod
  Linuksem dopasowuje wzorce dosłownie, więc plik był niewidoczny i trzeba
  było przełączać na „wszystkie pliki". Pod Windowsem ten sam wzorzec
  działa, więc błąd ujawniał się tylko na jednym systemie.

## 1.6

- Obrazy dysków twardych otwierają się w oknie głównym: **Dyskietka →
  Otwórz obraz**, tak samo jak dyskietki. Zawartość partycji widać
  w prawym panelu razem z rozmiarami, datami i atrybutami.
- Przyciski zmieniające zawartość są przy dysku wyłączone, bo obraz jest
  tylko do odczytu. Wcześniej okno zakładało, że każdy otwarty plik da się
  zapisać — przyciski były czynne, a kliknięcie kończyło się błędem.
- Przy kilku czytelnych partycjach program pyta, którą pokazać, i pozwala
  przełączyć ją później przez **Dyskietka → Wybierz partycję**. Partycje,
  których nie umie czytać, wypisuje obok — żeby nie wyglądało, że dysk
  jest mniejszy, niż jest.
- Nagłówek i litera napędu rozróżniają dyskietkę od dysku: `A:` i `C:`.

## 1.5

- Nowy silnik `fat16.py`: odczyt partycji FAT16 i FAT12 z obrazów dysków
  twardych. Czyta leniwie — żeby pokazać katalog, sięga po blok BPB, tablicę
  FAT i obszar katalogu, a nie po cały dysk. O rodzaju FAT decyduje liczba
  klastrów, tak samo jak liczył DOS, a nie napis w sektorze rozruchowym.
- Obrazy dysków rozpoznaje warstwa silników, więc otwiera się je tą samą
  drogą co dyskietki. Przy kilku partycjach program bierze pierwszą
  czytelną; wskazanie innej jest już możliwe w module.
- **Tylko do odczytu.** Każda próba zapisu kończy się czytelnym błędem.
  Nadpisanie obrazu dysku w trakcie pracy maszyny niszczy cały system
  plików, a nie jedną dyskietkę.
- Sprawdzone na obrazie z 86Boxa: czyta katalog główny z `IO.SYS`,
  `MSDOS.SYS`, `COMMAND.COM` i katalogami `DOS`, `WINDOWS`, `NC`.

## 1.4

- Nowy moduł `partitions.py`: tablica partycji obrazów dysków twardych,
  razem z partycjami logicznymi wewnątrz rozszerzonej — na dyskach z epoki
  `C:` bywa podstawowy, a `D:` i `E:` leżą właśnie tam. Obsługuje obrazy
  VHD i surowe `.img`; o rodzaju decyduje zawartość pliku, nie nazwa.
  Uszkodzony łańcuch ogniw nie zapętla programu.
- `python3 partitions.py dysk.vhd` wypisuje partycje z typem, położeniem
  i rozmiarem.

## 1.3

- Nowy moduł `vhd.py`: odczyt obrazów dysków twardych w formacie VHD,
  w odmianie stałej i rozszerzalnej. Tę drugą zapisuje 86Box — dane leżą
  w niej w blokach po 2 MB, a kolejność opisuje tablica; obszary, do których
  nigdy nic nie zapisano, nie istnieją w pliku i czytają się jako zera.
  Obrazy różnicowe program odrzuca z wyjaśnieniem, zamiast pokazywać
  nieprawdziwą zawartość. Sprawdzone na obrazie z 86Boxa: rozpoznaje
  geometrię, tablicę partycji i sektor rozruchowy DOS-a.
  Odmiana stała oparta wyłącznie na opisie formatu — prawdziwego pliku
  tego rodzaju nie mieliśmy.
- Raport z odczytu mówi wprost, gdy zebrany obraz jest już kompletny.
  Rozpoznanie opisuje pojedyncze przejście, więc przejście z błędami
  potrafiło straszyć uszkodzeniami, choć w pliku niczego nie brakowało.

## 1.2.3

- Okno Greaseweazle pamięta własny katalog. Wcześniej brało go z ustawienia
  okna głównego („gdzie zapisać obrazy") i nigdy nie aktualizowało, więc
  każde okno wyboru wracało w to samo miejsce sprzed wielu dyskietek.
- Testy okna dostają z góry odmowną odpowiedź na każde pytanie. Pytanie bez
  podstawionej odpowiedzi nie kończyło się niepowodzeniem, tylko
  zawieszeniem całego zestawu.

## 1.2.2

- Składanie obrazu nie działało: plik roboczy nazywał się `obraz.adf.nowy`,
  a `gw` wybiera przekształcenie po rozszerzeniu i odrzuca nieznane —
  napęd nawet nie ruszał. Plik roboczy zachowuje teraz rozszerzenie
  nośnika. W raporcie widnieje obraz użytkownika, a nie plik roboczy.
- Atrapa `gw` w testach odrzuca nieznane rozszerzenia tak jak prawdziwa;
  wcześniej przyjmowała dowolne i przepuściła ten błąd.

## 1.2.1

- Mapa zebranych danych znika przy nowej operacji. Zostawiona z poprzedniej
  dyskietki pokazywała komplet, gdy bieżący odczyt był dopiero w połowie.
- Przy dokładaniu do istniejącego pliku dolna mapa pokazuje jego stan od
  razu, a nie dopiero po zakończeniu odczytu.

## 1.2

- Składanie obrazu z kilku odczytów. Gdy wskazany plik już istnieje, okno
  pyta, czy dołożyć do niego brakujące sektory. Różne odczyty tej samej
  dyskietki gubią różne sektory, więc kilka podejść daje razem komplet,
  którego żadne z osobna nie dało — sprawdzone na dyskietce Amigi, gdzie
  cztery odczyty różniły się jednym sektorem.
- Druga mapa pod pierwszą pokazuje **zebrane dane**: kolumny obu map
  pokrywają się, więc widać zarazem przebieg bieżącego odczytu i stan
  całego obrazu. Licznik podaje, ile sektorów zebrano i ile przybyło.
- Dziury rozpoznawane są po wypełnieniu, którym `gw` zastępuje nieodczytany
  sektor. Sektor z samych zer to prawidłowe dane i nigdy nie jest uznawany
  za brakujący.
- Raport z każdego przejścia zapisuje się obok obrazu, z numerem przejścia
  w nazwie (`Titan-przejscie-1.txt`).

## 1.1

- Liczba prób odczytu na ścieżkę do ustawienia w oknie Greaseweazle
  (domyślnie 3, do 30) i w wierszu poleceń przez `--retries`. Doszło też
  `--seek-retries`, każące głowicy dojechać do ścieżki od nowa.
- Raport liczy ścieżki odczytane dopiero po ponownych próbach i — gdy takie
  są albo gdy zostały nieczytelne sektory — zaleca powtórzenie odczytu.
  Podstawa: dyskietka Amigi, która za pierwszym razem zgubiła 33 sektory,
  a za drugim żadnego. Wykładzina w kopercie zbiera pył przy każdym obrocie,
  więc nośnik czyści się sam w trakcie czytania.

## 1.0.1

- Okno Greaseweazle pozwala wskazać plik `gw` ręcznie i zapamiętuje wybór.
  Pod Windowsem narzędzia rozpakowuje się do dowolnego katalogu; jeśli nie
  trafi on do zmiennej PATH, polecenie działa tylko w tym folderze, a
  program uruchomiony z Eksploratora ma inny katalog roboczy i nie widzi go
  wcale. Wiersz poleceń przyjmuje tę ścieżkę przez `--gw`.
- Poprawki testów: jeden z nich uruchamiał prawdziwe `gw` na komputerze,
  na którym było zainstalowane, a inny zależał od szerokości czcionki.

## 1.0 — pierwsze wydanie publiczne

Program w kształcie, w jakim trafia na GitHuba.

- Silnik FAT12 w czystym Pythonie: dziewięć historycznych formatów dyskietek
  od 180 KB do 2,88 MB, z geometrią zgodną z oryginalnymi napędami.
  Poprawność potwierdzona niezależnie przez `fsck.fat` i `mtools`.
- Interfejs w stylu tekstowego menedżera plików, dwujęzyczny (polski,
  angielski), bez zależności poza biblioteką standardową.
- Edytor plików tekstowych ze świadomością stron kodowych DOS (CP437, CP852,
  CP850), z tablicą znaków i odwracalnym zapisem bajt w bajt.
- Kreator kompletu dyskietek: rozkłada program większy niż nośnik na kolejne
  dyskietki i dopisuje instalator działający na czystym DOS-ie 3.3.
- Obsługa fizycznych stacji dyskietek USB: zgrywanie, zapis, formatowanie
  z testem powierzchni, podgląd zawartości bez czytania całego nośnika.
- Most do Greaseweazle: zgrywanie i zapis dyskietek PC, Amigi i Atari ST,
  graficzna mapa ścieżek, mapa sektorów w raporcie oraz diagnostyka
  rozróżniająca uszkodzony nośnik, problem napędu i obcy format.
- Zestaw 200 testów automatycznych, niezależnych od obecności `gw`
  i narzędzi systemowych.

## Historia rozwoju przed wydaniem

Poniższe numery pochodzą sprzed publikacji i nie są numerami wydań — projekt
dojrzewał wtedy poza systemem kontroli wersji. Zostawiam je, bo opisują,
skąd wzięły się poszczególne rozwiązania; wiele z nich powstało w odpowiedzi
na to, co wyszło przy testach na prawdziwym sprzęcie.

### 2.16

- Okno Greaseweazle dzieli formaty na zakładki według rodzin nośników:
  PC / DOS, Amiga i Atari ST.
- Zgrywanie i zapisywanie dyskietek Amigi (880 KB, 1,76 MB) oraz Atari ST
  (360, 720, 800 i 880 KB). Potwierdzone na prawdziwej dyskietce Amigi:
  obraz z okna jest bajt w bajt taki sam jak z `gw` uruchomionego wprost.
- Rozszerzenie pliku dobiera się do nośnika (`.img`, `.adf`, `.st`), bo `gw`
  po nim wybiera przekształcenie.
- Formatowanie pozostaje dostępne tylko dla dyskietek pecetowych — pusty
  obraz program umie zbudować jedynie silnikiem FAT12.
- Geometria nośników przeniesiona do tablicy niezależnej od systemu plików.

### 2.15

- Liczba obrotów w wyjściu `gw` bywa ułamkowa (`revs=1.1` przy AmigaDOS).
  Wcześniejszy rozbiór jej nie rozpoznawał i prędkość obrotowa wychodziła
  545 zamiast 300 obr./min.
- Formaty 180 KB, 320 KB, 2,88 MB i 1,25 MB (NEC PC-98) w oknie Greaseweazle.

### 2.14

- Rozpoznanie obcego formatu: gdy żadna ścieżka nie daje ani jednego
  sektora, program podpowiada inny format zamiast ogłaszać uszkodzenie.
  Zgłoszone po próbie odczytania dyskietki Amigi jako pecetowej.

### 2.13

- Po przerwanej pracy `gw` okno nie pyta już o otwarcie obrazu, którego nie
  ma. Wykryte przy odłączeniu przewodu USB w trakcie odczytu.

### 2.12

- Rozpoznanie uszkodzeń nośnika nie skazuje już dyskietki. Ścieżka
  rozmagnesowana wygląda tak samo jak zniszczona powierzchnia, a formatowanie
  i ponowny zapis potrafią ją przywrócić — sprawdzone na nośniku, którego
  ścieżkę rozmagnesował uszkodzony napęd.

### 2.11

- Raport z zapisu i formatowania zawiera mapę ścieżek. `gw` nie wypisuje
  wtedy mapy sektorów, więc mapa nosi inną nazwę.

### 2.10

- Podziałka mapy ścieżek pokazuje numer ostatniego cylindra (79 albo 39).

### 2.9

- Mapa sektorów w raporcie z odczytu, w układzie `gw`. W oknie znaki `X` są
  czerwone; w zapisanym pliku `.txt` mapa pozostaje zwykłym tekstem.

### 2.8

- Raport w oknie Greaseweazle wyświetla się na tle grafiki.

### 2.7

- Graficzna mapa ścieżek: rząd na stronę, kolumna na cylinder, sześć stanów
  z rozróżnieniem uszkodzonego nośnika i problemu napędu.

### 2.6

- Wyróżniany jest przycisk trwającej operacji, a nie stale ten sam.
- Zapis obrazu o rozmiarze innego formatu: program rozpoznaje go i pyta
  o przełączenie zamiast odrzucać surowym komunikatem.

### 2.5

- Okno Greaseweazle: wykrywanie urządzenia, odczyt, zapis i formatowanie,
  raport z rozpoznaniem.

### 2.4

- Pasek postępu przerysowuje się przy zmianie rozmiaru okna.
- Kreator kompletu dyskietek pamięta ostatni katalog źródłowy.

### 2.3

- Instalator kompletu dyskietek pozwala wskazać dysk docelowy, wypisuje
  dostępne dyski i sprawdza, czy podany istnieje.

### 2.2

- Wsad instalatora nazywa się `JAZWIEC.BAT` i zmienia nazwę przy kolizji.
  Program z własnym `SETUP.BAT` nadpisywał wcześniej wykonywany właśnie
  plik wsadowy i instalacja przerywała się przy drugiej dyskietce.

### 2.1

- Weryfikacja po zapisie ponawia odczyt tyle samo razy co zwykłe zgrywanie.
  Test powierzchni przy formatowaniu pozostaje surowy — to dwa różne
  pytania o nośnik.

### 2.0

- Grafika pod przyciskiem tworzenia dyskietki.
- Pasek klawiszy funkcyjnych i pasek stanu zawsze widoczne, niezależnie od
  rozmiaru okna.

### Seria 1.x

Podstawa programu: silnik FAT12 w czystym Pythonie z dziewięcioma formatami
dyskietek, interfejs w stylu tekstowego menedżera plików, obsługa fizycznych
napędów USB z testem powierzchni i izolacją uszkodzonych sektorów, edytor
plików tekstowych ze świadomością stron kodowych DOS, kreator kompletu
dyskietek z generowanym instalatorem, warstwa wyboru silnika systemu plików,
podział kodu na moduły, własna ikona oraz zestaw testów.
