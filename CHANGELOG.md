# Historia zmian

Numery wersji odpowiadają wartości `APP_VERSION` w `styles.py`.

## 1.16

- **Raport w osobnym oknie** — w oknie Greaseweazle i w oknie płyt.
  Dotąd siedział w oknie operacji i jako jedyna rozciągliwa część oddawał
  miejsce wszystkiemu innemu; na niższym ekranie kurczył się do paska
  wysokości jednej linijki. Nowe okno można powiększyć, zmaksymalizować,
  przenieść na drugi ekran i zostawić otwarte obok; jego rozmiar jest
  zapamiętywany. Po zakończeniu pracy pokazuje się samo.
- Okno operacji Greaseweazle zmalało z 990 do 785 pikseli, więc mieści się
  bez żadnych sztuczek.
- Usunięte zwijanie opisu, skracanie pola raportu i chowanie podpowiedzi
  z wersji 1.15.1 i 1.15.2. Były podpórkami pod problem, który teraz
  zniknął u źródła — a jedna z nich zachowywała się różnie na różnych
  systemach i nie dało się tego powtórzyć u mnie.

## 1.15.2

- Okno Greaseweazle pozwala **zwinąć opis** i ścieżkę do narzędzia. Po
  sprawdzeniu narzędzia nie są już potrzebne, a to one zabierały miejsce
  raportowi — na ekranie 1080 zwinięcie powiększa raport ze 197 do 260
  pikseli. Stan jest zapamiętywany. Zgłoszone przez testera.
- Gdy miejsca nadal brakuje, ustępują kolejno napisy objaśniające, potem
  legenda — a nigdy przyciski i mapa. Kolejność ustępstw jest tu regułą:
  podpowiedź mówi to, co widać po chwili używania, a przycisk schowany za
  krawędzią ekranu przestaje istnieć.

## 1.15.1

- **Nazwy formatów w oknie Greaseweazle tłumaczą się.** W angielskim oknie
  były polskie („jednostronna", „8 sektorow"), bo tablica nośników
  powstaje raz, przy wczytaniu modułu, i zapamiętywała nazwę w języku
  sprzed przełączenia. Teraz nazwa powstaje w chwili wyświetlenia, razem
  z separatorem dziesiętnym: `1.44 MB` po angielsku, `1,44 MB` po polsku.
  Zgłoszone przez testera.
- **Okno Greaseweazle i okno płyt mieszczą się na ekranie.** Dolna część
  chowała się za paskiem zadań i raportu nie było widać wcale. Program
  skraca teraz pole raportu, a gdy to nie wystarcza, narzuca wysokość
  okna — raport ma własny przewijak, więc traci widok, a nie treść;
  przyciski schowane za krawędzią przestałyby istnieć.

## 1.15

- **Dyskietki Atari ST.** Program rozpoznaje je mimo braku sygnatury
  `55 AA`, której Atari nie zapisywało — dotąd odrzucał je, zanim zajrzał
  do bloku parametrów. Przy jej braku wymaga, żeby deklarowana liczba
  sektorów zgadzała się z rozmiarem pliku co do bajta, a geometria
  mieściła się w granicach dyskietki; losowy plik ani obcięty obraz tego
  nie spełniają.
- Dwa nowe formaty: **Atari ST 800 KB** (10 sektorów na ścieżkę) i
  **880 KB** (11). Atarowskie 360 i 720 KB nie różnią się niczym od
  pecetowych, więc nie dostały osobnych pozycji — dwie nazwy na to samo
  tylko myliłyby na liście.
- Zapis do obrazu Atari nie dopisuje sygnatury: obraz zostaje taki, jaki
  był. Poprawność potwierdza `fsck.fat`.
- Uruchamiacz testów sam znajduje moduły `test_*.py`. Lista wpisana
  ręcznie była jedynym miejscem, gdzie nowy zestaw testów mógł zniknąć
  po cichu — zdarzyło się to przy czterech naraz.

## 1.14.2

- Testy okna ustawiają język wprost, zaraz po utworzeniu okna. Dotąd
  polegały na domyślnym, więc zmiana domyślnego na angielski wywracała
  kilkanaście testów, które z językiem nie miały nic wspólnego.

## 1.14.1

- Okno i menu nazywają się teraz „Płyty CD", bez DVD. Płyta DVD z danymi
  w ISO 9660 zgrywa się tak samo — sektor to sektor — ale sprawdzone
  zostały tylko CD, a nazwa obiecująca więcej niż potwierdzone jest gorsza
  niż skromna.

## 1.14

- **Domyślnym językiem jest angielski.** Program trafia do ludzi spoza
  Polski i pierwszy ekran musi być dla nich czytelny; polski wybiera się
  z menu Language, a wybór zostaje zapamiętany.
- Moduł płyt mówi w obu językach: uwagi, komunikaty błędów i cały raport
  ze zgrywania. Dotąd okno było tłumaczone, a raport wychodził po polsku
  niezależnie od wyboru.
- Kody błędów systemowych też są tłumaczone.
- Testy ustawiają język wprost, zamiast polegać na domyślnym. Test, który
  zakłada jakikolwiek domyślny, pada przy następnej takiej zmianie i nie
  mówi wtedy nic o samym programie.

## 1.13.8

- **Spis treści płyty pod Windows: bufor był o osiem bajtów za mały.**
  Windows wymaga miejsca na pełne sto wpisów, a program dawał je na
  dziewięćdziesiąt dziewięć i dostawał kod 122 („za mały bufor"). Objaw
  wyglądał identycznie jak płyta bez ścieżek, co kosztowało kilka błędnych
  diagnoz. Uprawnienia administratora nie były potrzebne — pytanie
  o rozmiar działało na tym samym uchwycie.
- Kody błędów systemowych są tłumaczone na słowa: „kod błędu 122 (za mały
  bufor odpowiedzi)" zamiast samej liczby.

## 1.13.7

- Polecenie `optical.py diag URZĄDZENIE` pokazuje krok po kroku, co
  odpowiada system: które otwarcie napędu się udaje, które pytanie do
  sterownika przechodzi, ile bajtów zwraca i jak wygląda początek
  odpowiedzi. Powstało, bo pod Windows spis treści zawodzi, a po kolejnych
  poprawkach zmienia się tylko objaw.
- Usunięta druga, starsza funkcja diagnostyczna — zostały dwie naraz.

## 1.13.6

- Szukanie plików graficznych obejmuje katalog aplikacji spakowanej przez
  PyInstaller (`sys._MEIPASS`) oraz katalog pliku uruchamianego. Dotąd
  działało to przy budowie jednoplikowej przypadkiem, a przy katalogowej
  wcale — program startował bez ikon i bez tła raportów.

## 1.13.5

- Spis treści płyty pod Windows kończył się odmową dostępu (kod 5).
  Przyczyna: pytanie o rozmiar działa na uchwycie otwartym bez żadnego
  dostępu, a pytanie o spis treści wymaga prawa odczytu danych — program
  brał pierwszy otwarty uchwyt i na nim próbował obu rzeczy. Teraz każde
  pytanie dostaje uchwyt z właściwym poziomem, a przy odmowie próbuje
  drugiego.
- `ctypes.get_last_error` istnieje tylko pod Windows; sięganie po nie
  wprost wywracało program na innych systemach.

## 1.13.4

- Pod Windows program otwiera napęd najpierw bez żądania dostępu do danych.
  Tak otwarty uchwyt wystarcza do wypytywania sterownika i nie wymaga
  podniesionych uprawnień — podejrzenie, że to one blokowały odczyt spisu
  treści.
- Gdy spis treści się nie uda, uwaga zawiera kod błędu systemowego.
  Bez niego nie da się odróżnić odmowy systemu od płyty bez ścieżek.
- Nowe polecenie `python3 optical.py toc /dev/sr0` pokazuje surową
  odpowiedź sterownika — do diagnozy takich przypadków.

## 1.13.3

- Spis treści płyty pod Windows nie działał, choć zgrywanie tak: uchwyt do
  urządzenia jest tam liczbą 64-bitową, a bez wyraźnej deklaracji typów
  Python obcinał go do 32 bitów. Sterownik dostawał śmieć i odmawiał, więc
  płyta wyglądała jak płyta bez ścieżek — a zabezpieczenie przed zgrywaniem
  płyt z samą muzyką nie miało na czym działać.
- Gdy spisu treści nie da się odczytać, program mówi to wprost. Milczenie
  sugerowało, że muzyki na płycie nie ma.

## 1.13.2

- **Zgrywanie płyt pod Windows.** Rozmiaru nośnika nie da się tam ustalić
  przesunięciem na koniec urządzenia — program pytał o to systemu w sposób,
  który pod Windows zwraca zero, więc nie wiedział, ile ma zgrywać i nie
  zgrywał nic. Teraz pyta sterownik wprost, a gdy ten milczy, bierze liczbę
  bloków z opisu wolumenu samej płyty.
- Spis treści płyty pod Windows czytany własną drogą: tam pole kontrolne
  siedzi w młodszych czterech bitach, odwrotnie niż pod Linuksem. Wpis
  zamykający płytę nie jest liczony jako ścieżka.
- Napędy pokazują się jako litera dysku, a nie jako ścieżka `\\.\D:`.
- Zgłoszone z prawdziwego Windowsa po zbudowaniu `.exe`.

## 1.13.1

- Raport w oknie płyt ma własne tło z borsukiem, tak jak okno Greaseweazle.
- Pole raportu z tłem przeniesione do `styles.py` — dotąd mieszkało w oknie
  Greaseweazle, a okno płyt musiałoby je powielić albo importować z modułu,
  który wymaga Greaseweazle. Teraz oba korzystają z jednego kodu.

## 1.13

- **Okno płyt CD** w menu Napęd, pod Greaseweazle: wybór napędu,
  opis płyty z ostrzeżeniami, liczba prób na sektor, pasek postępu
  z licznikiem nieczytelnych sektorów, przerwanie i raport na dole.
- Płytę z samą muzyką okno rozpoznaje i nie pozwala zacząć zgrywania,
  pokazując powód na czerwono.
- Raport ze zgrywania jest wspólny dla okna i wiersza poleceń: zawiera
  napęd, etykietę płyty, liczbę sektorów, prędkość i listę nieczytelnych
  miejsc. Można go zapisać do `.txt`.

## 1.12

- **Płyty z samą muzyką są rozpoznawane i odrzucane** z wyjaśnieniem.
  Muzyka nie leży w sektorach z danymi, więc napęd odmawia czytania jej
  jak danych: program schodził do pojedynczych sektorów, mielił po pięć
  prób na każdy i po trzech minutach był na dziewięciu procentach, a plik
  i tak byłby bezwartościowy. Teraz mówi to od razu i podpowiada, że do
  płyt audio służą programy zgrywające do WAV albo FLAC.
  Zgłoszone z prawdziwego napędu.
- Płyta mieszana — gra z muzyką na ścieżkach CD — nadal się zgrywa;
  program tylko uprzedza, że muzyki w obrazie nie będzie.
- Gdy napęd nie odda ani jednego z pierwszych 64 sektorów, zgrywanie
  kończy się komunikatem zamiast pracować godzinami.

## 1.11.2

- Krótszy odczyt niż zamówiony nie jest już uznawany za udany. Program
  dopełniał wtedy resztę zerami i szedł dalej — czyli po cichu wstawiał
  puste miejsca w obraz. Teraz schodzi do pojedynczych sektorów i ustala
  dokładnie, których brakuje.
- Przerwanie zgrywania klawiszem kończy się komunikatem, a nie śladem
  wyjątku. Przerwanie płyty to normalna droga wyjścia, nie awaria.
- Pasek postępu pokazuje na bieżąco liczbę nieczytelnych sektorów — widać
  wtedy od razu, czy powolne zgrywanie bierze się ze stanu płyty.

## 1.11.1

- Odczyt spisu treści płyty nie działał: bufor zapytania miał osiem bajtów
  zamiast dwunastu, a znacznik formatu adresu trafiał pod zły indeks.
  Sterownik odmawiał, więc płyta wyglądała jak płyta bez ścieżek i
  **ostrzeżenie o muzyce nigdy by nie padło**. Wykryte na prawdziwym
  napędzie: w opisie płyty brakowało wiersza o ścieżkach.
- Porcja odczytu zwiększona z 64 do 256 sektorów, z możliwością zmiany
  przez `--chunk`. Na porysowanych płytach mniejsza bywa lepsza, bo po
  niepowodzeniu program schodzi do pojedynczych sektorów.

## 1.11

- Nowy moduł `optical.py`: zgrywanie płyt CD do pliku `.iso`,
  na razie z wiersza poleceń. Wykrywa napędy, rozpoznaje płytę po opisie
  wolumenu ISO 9660 i bierze z niego prawdziwą liczbę bloków — rozmiar
  urządzenia bywa zawyżony o sektory wyrównujące.
- Uszkodzone sektory nie przerywają pracy: program schodzi z porcji do
  pojedynczych sektorów, ponawia odczyt, a nieczytelne wypełnia zerami
  i wypisuje w raporcie. Z porysowanej płyty odzyskuje całą resztę.
- Przed zgrywaniem ostrzega, gdy płyta ma ścieżki CD-Audio: nie wejdą one
  do obrazu `.iso`, więc gra dostałaby dane bez muzyki. Mówi też, gdy nie
  widzi opisu wolumenu ISO 9660.

## 1.10

- Okno postępu przy kopiowaniu wielu plików i całych katalogów, z licznikiem,
  paskiem i możliwością przerwania. Wcześniej program przy kilkuset plikach
  nie pokazywał niczego i wyglądał na zawieszony.
- Kopiowanie katalogu na dysk twardy: `import_tree` ma teraz ten sam zestaw
  parametrów i to samo podsumowanie co przy dyskietce. Wcześniej wywołanie
  z okna kończyłoby się błędem, bo podpisy obu silników się różniły.
- Skracanie nazw na dysku daje prawdziwą postać 8.3. Raport pokazywał
  wcześniej nazwy w rodzaju `SID MEIERS C` — ze spacjami i dwunastoznakowe —
  które nigdzie nie istniały. Kropki pośrednie znikają, tak jak w DOS-ie:
  `a.b.c.txt` staje się `ABC.TXT`.

## 1.9

- **Zapis do obrazu dysku w oknie**: pozycja „Odblokuj zapis do obrazu"
  w menu Dyskietka. Program ostrzega przed zapisem do obrazu używanego
  przez uruchomioną maszynę i radzi zrobić kopię; dopiero po potwierdzeniu
  otwiera obraz ponownie w trybie zapisu i odblokowuje przyciski.
- Zapis do obrazu **niepełnego** — na przykład niedokończonego pobierania,
  którego tablica bloków wskazuje poza koniec pliku — jest odrzucany.
  Trafiłby za koniec pliku, rozdmuchał go i zostawił stopkę w środku,
  zamieniając obraz niepełny w całkiem zepsuty. Odczyt nadal działa.
- Komunikat o skracaniu nazw do 8.3 mówi „nośnik", nie „dyskietka".
- Sprawdzone od początku do końca: odblokowanie w oknie, wniesienie plików
  do obrazu rozszerzalnego i `fsck.fat` bez zastrzeżeń.

## 1.8

- Silnik FAT16 zapisuje: pliki, katalogi, kasowanie, zmiana nazwy i etykieta
  wolumenu. Kolejność operacji dobrana tak, by przerwanie w połowie
  zostawiało niewykorzystane klastry, a nie wpis wskazujący na przypadkową
  treść. Obie kopie tablicy FAT trzymane są zgodne.
- Wynik zapisu potwierdza `fsck.fat` — bez zastrzeżeń dla FAT16 i FAT12,
  po utworzeniu plików, katalogów, skasowaniu, zmianie nazwy i etykiety.
- **Obraz otwarty z menu jest zawsze tylko do odczytu.** Zapis wymaga
  sięgnięcia po silnik wprost; w oknie pojawi się w kolejnym kroku.
- Wyszukiwanie plików rozpoznaje nazwy także po skróceniu do 8.3, więc
  program odnajduje plik, który przed chwilą sam zapisał.

## 1.7

- Warstwa zapisu do obrazów dysków: sektory można zapisywać w obrazach
  surowych oraz VHD stałych i rozszerzalnych. Przy rozszerzalnych zapis
  w obszar, którego w pliku jeszcze nie ma, dokłada cały blok, przesuwa
  stopkę i uzupełnia tablicę — w kolejności, która po przerwaniu zostawia
  plik nadal dający się otworzyć.
- Obrazy otwierają się domyślnie tylko do odczytu; zapis wymaga wyraźnego
  wskazania. To pierwszy z trzech kroków — silnik FAT16 nadal nie zapisuje.

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
