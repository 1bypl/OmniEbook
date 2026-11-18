# OmniEbook 1.3.0

**Darmowy program do wyszukiwania, czytania i katalogowania ebooków,
dokumentów oraz audiobooków.** Łączy lokalną bibliotekę z wyszukiwaniem
w legalnych, otwartych źródłach internetowych.

> **Wersja 1.3.0** dodaje gwiazdkę „Do ulubionych" w czytniku ebooków
> i odtwarzaczu audiobooków. Zachowuje wszystkie poprawki wersji 1.2.x
> (motywy, obrazki, kodowanie, szybkie otwieranie książek).

Autor: **1bypl** — [GitHub](https://github.com/1bypl)  
Licencja: **GNU General Public License v3.0-or-later** (plik `LICENSE`)

Pobierz instalator dla Windows 10/11x64 - (https://drive.proton.me/urls/KQ9RFM2WN8#3LSVDqWMyeDH)

Pobierz instalator dla Debian/Ubuntu - (https://drive.proton.me/urls/2N21QCVZC4#kw6yetLZEInz)

Pobierz instalator dla Fedora - (https://drive.proton.me/urls/Q253EKZ36C#mtKPmbaRBPsn)
---

## Co nowego w wersji 1.3.0

* **Gwiazdka w czytniku i odtwarzaczu** — przycisk ☆/⭐ na pasku narzędzi
  dodaje bieżącą książkę lub audiobook do Ulubionych (i usuwa z nich)
  bez konieczności wracania do biblioteki. Stan gwiazdki jest widoczny
  od razu, a licznik w zakładce „Ulubione" się aktualizuje.
* **Gotowe pakiety** — pliki instalacyjne dla Fedory, Debiana i Ubuntu
  znajdują się w katalogu `dist/`.

## Co nowego w wersji 1.2.2

* **Zmiana wyglądu do poprawki** — główna przyczyna: Ustawienia tworzyły
  nową instancję `ThemeManager`, więc stare arkusze CSS zostawały na ekranie.
  Motywy są teraz współdzielone, poprzedni arkusz jest usuwany, a „Systemowy"
  naprawdę podąża za schematem systemu. Nie ma już białej karty z niewidocznym
  tekstem po przejściu z Jasnego/Sepi/Lasu do Systemowego.
* **Czytnik — obrazki** — typ grafiki rozpoznajemy po zawartości pliku, nie po
  rozszerzeniu (JPEG zapisany jako `.png` wyświetla się poprawnie). Pliki
  okładek (`cover`) w EPUB-ach nie są już pomijane.
* **Czytnik — kodowanie** — rozpoznajemy deklarację kodowania głębiej w nagłówku
  i więcej nazw kodowań (cp1250, cp1251, iso-8859-2, koi8, gb2312…), co
  ogranicza „dziwne znaki".
* **Szybsze otwieranie** — ponowne otwarcie pobranej wcześniej książki korzysta
  z pliku lokalnego bez łączenia z serwerem; podczas pierwszego pobierania
  widoczny jest licznik czasu.
* **Wolne Lektury** — przycisk „Dodaj / napraw" znika po usunięciu źródła.

## Co nowego w wersji 1.2.1

* Motywy: usuwanie starego arkusza CSS i `Adw.ColorScheme.DEFAULT`.
* Ulubione: „Czytaj"/„Słuchaj" odblokowane po wyjściu z trybu zaznaczania.
* Instrukcja własnych źródeł w Ustawieniach i w README.

## Co nowego w wersji 1.2.0

* **Masowe usuwanie pozycji** — działa w „Mojej bibliotece", „Ulubionych",
  „Zbiorach" oraz w „Wynikach wyszukiwania". Można zaznaczyć wiele kafelków
  i usunąć je jednym przyciskiem (szczegóły poniżej).
* **Odtwarzacz audiobooków** — przycisk „Stop" zachowuje pozycję, więc
  ponowne kliknięcie „Słuchaj" wznawia ścieżkę od miejsca zatrzymania.
* **Pakiety dla Linuksa** — plik `.deb` dla Debian/Ubuntu oraz `.rpm`
  dla Fedory. Budowa nie wymaga już `dpkg-deb`, `rpmbuild`, `meson` ani
  `ninja` — skrypty mają wbudowany budowniczy w czystym Pythonie.
* **Poprawki błędów** — konflikt katalogów `/usr/bin` i `/usr/lib` z pakietem
  `filesystem` w Fedorze, błędny `PYTHONPATH` launchera (program nie startował
  z katalogu domowego), brakujące znaczniki `region` w RPM; usuwanie kafelka
  z wyników natychmiast odświeża listę; przy usuwaniu książek czyszczone są
  powiązane wpisy w zbiorach; usunięto duplikaty kluczy w tłumaczeniach.

---

## Możliwości

* **Lokalna biblioteka** z importem plików i folderów, kolekcjami,
  ulubionymi, tagami, usuwaniem duplikatów oraz **masowym usuwaniem**.
  Nowo dodane pozycje są wyróżnione, a ich lokalizacja jest dostępna
  w bibliotece.
* **Wyszukiwarka internetowa i lokalna** z wynikami w formie kafelków,
  okładkami, opisami oraz odnośnikami do źródła i pobierania. Wbudowane
  źródła obejmują Project Gutenberg, Open Library, Internet Archive, arXiv,
  DOAJ i LibriVox.
* **Własne źródła**: katalogi OPDS/Atom, kanały RSS/Atom oraz strony HTML
  konfigurowane selektorami CSS. Można tworzyć własne kategorie i zmieniać
  ich nazwy oraz ikonki.
* **Czytnik dokumentów** z paginacją, spisem treści EPUB, zapamiętywaniem
  postępu oraz regulacją czcionki, interlinii, marginesów i motywu.
  Ilustracje osadzone w EPUB są wyświetlane w treści; strony graficzne
  zachowują kolejność. Gwiazdka ☆/⭐ na pasku dodaje książkę do Ulubionych.
* **Odtwarzacz audiobooków** z regulacją prędkości i głośności, przewijaniem
  o 15 sekund oraz gwiazdką ☆/⭐ do Ulubionych. Po naciśnięciu „Stop"
  odtwarzanie wznawia się od miejsca zatrzymania.
* **27 kategorii tematycznych**, m.in. nauka, podręczniki, kuchnia, ogród,
  wędkarstwo, grzyby, biografie, historia i hobby.
* **7 języków interfejsu**: polski, angielski, niemiecki, rosyjski,
  hiszpański, francuski i włoski.
* **6 motywów**: systemowy, jasny, ciemny, sepia, północ i las; można również
  wybrać kolor akcentu.

Korzystaj z zasobów zgodnie z ich licencjami i regulaminami stron. Dodając
własne źródła lub adresy, użytkownik odpowiada za uprawniony dostęp do treści.
OmniEbook nie obchodzi zabezpieczeń DRM.

## Obsługiwane formaty

Poniższa tabela rozróżnia formaty odczytywane przez OmniEbook bezpośrednio
od formatów rozpoznawanych, których otwieranie może wymagać zewnętrznego
programu.

| Rodzaj | Formaty | Obsługa |
|---|---|---|
| Ebooki i tekst | EPUB, FB2, TXT, MD, HTML | Wbudowany czytnik |
| Dokumenty | PDF, DOCX, ODT, RTF | Odczyt w aplikacji |
| Komiksy i grafiki | CBZ; JPEG/JPG, PNG, GIF, WebP, BMP, TIFF/TIF | Grafiki jako strony; obrazy mogą być też osadzone w EPUB |
| Inne dokumenty | DOC, XLS/XLSX, PPT/PPTX, ODS/ODP/ODG, DjVu, CHM | Rozpoznawane; mogą wymagać zewnętrznej aplikacji lub konwertera |
| Ebooki Kindle | MOBI, AZW/AZW3/AZW4, KFX, KF8, PRC | Konwersja części plików wymaga Calibre; część może być chroniona DRM |
| Audiobooki/audio | MP3, M4A/M4B, AAC, FLAC, Ogg/OGA, Opus, WAV, WMA, AIFF/AIF, MP4, WebM, MPEG/MPG | Odtwarzanie przez GStreamer; zależy od kodeka w pliku |
| Archiwa | ZIP, LPF, CBR | ZIP może zawierać pliki audio; CBR wymaga modułu `rarfile` i unrar lub 7-Zip |

Teksty są dekodowane z UTF-8 i UTF-16 (BOM), z uwzględnieniem deklaracji
kodowania dokumentu oraz popularnych starszych kodowań, w tym Windows-1250,
DOS CP852 i wybranych kodowań cyrylicznych. Niektóre bardzo stare publikacje
mogą używać nietypowego lub uszkodzonego kodowania.

## Dodatkowe oprogramowanie

Do zwykłego korzystania z instalatora **nie trzeba osobno instalować Pythona,
GTK/libadwaita ani GStreamera** — w wersji Windows są dołączone do aplikacji,
a w wersji Linux instalują się jako zależności systemowe. Wyszukiwanie
i pobieranie zasobów internetowych wymaga połączenia z Internetem.

Niektóre rzadziej spotykane typy dokumentów mogą wymagać dodatkowych narzędzi:

* **Calibre** (`ebook-convert`) — konwersja części plików MOBI/AZW/KFX/PRC.
* **DjVuLibre** (`djvutxt`) — wyciąganie tekstu z DjVu.
* **LibreOffice** lub inna aplikacja biurowa — otwieranie części dokumentów
  Office, których czytnik OmniEbook nie odczytuje bezpośrednio.
* **Moduł `rarfile` oraz unrar lub 7-Zip** — odczyt archiwów CBR.

## Masowe usuwanie ebooków i audiobooków (NOWOŚĆ)

1. Wejdź w **Moja biblioteka**, **Ulubione**, **Zbiory** albo w **wyniki
   wyszukiwania** — pasek zaznaczania jest dostępny w każdym z tych widoków.
2. Kliknij przycisk **Zaznacz pozycje** nad siatką kafelków.
3. Zaznacz wybrane kafelki — kliknij ich okładkę albo pole wyboru
   w lewym górnym rogu. Przycisk **Zaznacz wszystkie** zaznaczy wszystkie.
   Liczba zaznaczonych pozycji jest widoczna na przycisku usuwania.
4. Kliknij **Usuń zaznaczone (N)** i potwierdź w oknie dialogowym.

Usuwane są tylko wpisy w bibliotece — **pliki na dysku zostają na miejscu**,
tak samo jak przy usuwaniu pojedynczego kafelka. Wyjście z trybu zaznaczania
przez ponowne kliknięcie **Zaznacz pozycje** czyści zaznaczenie.

Pozycje usunięte z **wyników wyszukiwania** pochodzą ze źródeł internetowych —
nic nie zostaje utracone, bo ponowne wyszukanie tej samej książki doda ją
z powrotem do biblioteki.

## Instalacja — Debian i Ubuntu

Pobierz plik `omniebook_1.3.0-1_all.deb` (katalog `dist/debian/` albo
`dist/ubuntu/` — oba systemy używają tego samego pakietu) i uruchom:

```sh
sudo apt install ./omniebook_1.3.0-1_all.deb
```

* Ustawienia i baza biblioteki: `~/.config/OmniEbook`
* Dane i pamięć podręczna: `~/.local/share/OmniEbook`, `~/.cache/OmniEbook`
* Domyślny folder pobierania: `~/Downloads`

## Instalacja — Fedora

Pobierz plik `omniebook-1.3.0-1.fc45.noarch.rpm` (katalog `dist/fedora/`)
i uruchom:

```sh
sudo dnf install ./omniebook-1.3.0-1.fc45.noarch.rpm
```

Pakiet jest przeznaczony dla Fedory 40 i nowszych (wersja bez kodu
natywnego, `noarch`). Metadane zawierają `License: GPL-3.0-or-later`.

> Jeśli Discover nadal odmawia instalacji **niepodpisanego** pakietu,
> użyj terminala:
>
> ```sh
> sudo dnf install ./omniebook-1.3.0-1.fc45.noarch.rpm
> ```
>
> `dnf` zapyta o potwierdzenie instalacji pakietu bez podpisu.

## Instalacja — Windows

Uruchom `OmniEbook-Setup-1.0.0.exe` i wykonaj kroki instalatora. Nie trzeba
instalować MSYS2 ani uruchamiać skryptów PowerShell.

> **Uwaga:** dołączony instalator Windows to wydanie 1.0.0. Funkcję masowego
> usuwania z wersji 1.3.0 można dodać, przebudowując instalator na Windowsie
> poleceniem z sekcji „Budowa pakietów".

* Ustawienia i baza biblioteki: `%APPDATA%\OmniEbook`
* Pliki tymczasowe i logi: `%LOCALAPPDATA%\OmniEbook`
* Domyślny folder pobierania: `Downloads` (zmienisz go w ustawieniach)
* Log aplikacji: `%LOCALAPPDATA%\OmniEbook\logs\application.log`

Wczytywanie dużych kolekcji oraz pobieranie ebooków z sieci może potrwać
kilkanaście sekund, zależnie od rozmiaru zasobów, szybkości dysku i łącza.

## Budowa pakietów ze źródeł

Jednym poleceniem zbudujesz pakiety dla wszystkich trzech systemów:

```sh
./packaging/build_all.sh
```

Wyniki trafiają do katalogów:

| System | Plik |
|---|---|
| Debian | `dist/debian/omniebook_1.3.0-1_all.deb` |
| Ubuntu | `dist/ubuntu/omniebook_1.3.0-1_all.deb` |
| Fedora | `dist/fedora/omniebook-1.3.0-1.fc45.noarch.rpm` |

Skrypty `build_deb.sh` i `build_rpm.sh` używają systemowych narzędzi, gdy
są dostępne (`dpkg-deb`, `rpmbuild`, `meson`, `ninja`), a w przeciwnym razie
automatycznie przełączają się na wbudowane budownicze w Pythonie
(`build_deb_py.py`, `build_rpm_py.py`). Nie wymagają one instalowania
żadnych dodatkowych modułów.

Testy rdzenia (bez interfejsu graficznego):

```sh
PYTHONPATH="$PWD/.venv/Lib/site-packages:$PWD" python3 -m unittest discover -s tests
```

Na Windowsie użyj `powershell -ExecutionPolicy Bypass -File .\tests\run_windows_tests.ps1`.
Instalator Windows buduje się poleceniem
`powershell -ExecutionPolicy Bypass -File .\packaging\windows\build_standalone.ps1`
w środowisku MSYS2 UCRT64 z zależnościami opisanymi w tym skrypcie.

## Własne źródła i kategorie

W **Ustawienia → Własne źródła OPDS/Atom i HTML** dodaj adres wyszukiwania
z placeholderem `{query}`, np. `https://katalog.example/search?q={query}`.
Można również używać `{category}`, `{language}` i `{limit}`. Dla źródła HTML
podaj selektory CSS dla kontenera wyniku, tytułu i odnośnika; okładka, opis,
autor i link pobierania są opcjonalne. Źródła można włączać i wyłączać.

### Jak poprawnie wpisać link — krótka instrukcja

Tę samą instrukcję znajdziesz w Ustawieniach, w rozwijanym wpisie
**„Instrukcja: jak wpisać adres źródła"**.

1. **Wklejaj adres wyszukiwarki, nie link do jednej książki.** Program sam
   podstawia wpisane słowo w miejsce `{query}`.
2. **Adres musi mieć schemat HTTP/HTTPS** — `https://…` jest zalecane.
   Nie używaj `file://`, `localhost`, `127.0.0.1` ani adresów wymagających
   logowania. Nie wklejaj spacji, cudzysłowów ani całego zapytania z paska
   przeglądarki z dodatkowymi parametrami sesji.
3. **OPDS i strony HTML — `{query}` jest wymagany:**
   `https://katalog.example/szukaj?q={query}`.
4. **RSS/Atom — `{query}` się nie daje.** Wklej bezpośredni adres pliku
   `https://example.org/feed.xml`; program pobierze wpisy i przefiltruje je
   lokalnie według wpisanego tekstu.
5. **Dla HTML uzupełnij selektory CSS:** `results_selector` (kontener jednego
   wyniku), `title_selector` i `link_selector` są wymagane. Opcjonalne są
   `cover_selector`, `description_selector`, `author_selector` i
   `download_selector`. Bez nich kafelki nie będą miały danych.
6. **Testuj po jednym źródle.** Dodaj jedno źródło i na chwilę wyłącz
   pozostałe przełącznikami — łatwo zobaczysz, które z nich działa. Jeśli
   wyszukiwanie zwolni lub zacznie pokazywać błędy, wyłącz lub usuń
   problematyczne źródło przyciskiem **Usuń**.

Gotowa konfiguracja **Wolne Lektury** jest dostępna jednym kliknięciem
przycisku „Dodaj / napraw" — nie trzeba jej wpisywać ręcznie.

W ustawieniach można edytować wygląd kategorii, ustawiać własne nazwy i
ikonki. Wyszukiwanie oraz pobieranie z danego serwisu zależy od jego
dostępności i zasad dostępu.

## Skróty klawiaturowe

| Skrót | Funkcja |
|---|---|
| `Ctrl+F` / `Ctrl+K` | Wyszukiwarka |
| `Ctrl+,` | Ustawienia |
| `Alt+Home` | Strona główna |
| `Ctrl+Q` | Wyjście |

---

© 2026 1bypl · [GitHub](https://github.com/1bypl) · GPL-3.0-or-later
