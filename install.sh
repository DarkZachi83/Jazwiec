#!/bin/bash
#
# Instalator RetroZachar FFD Disk Maker dla Linuksa.
#
#   sudo ./install.sh              instalacja dla wszystkich (/usr/local)
#        ./install.sh --user       instalacja tylko dla mnie (~/.local)
#   sudo ./install.sh --uninstall  odinstalowanie
#
# Po instalacji program uruchamia sie poleceniem "retrozachar" albo z menu
# systemowego. NIE uruchamiaj go przez sudo - tworzone obrazy nalezalyby
# wtedy do roota i nie dalyby sie pozniej edytowac.

set -euo pipefail

APP_NAME="retrozachar"
APP_TITLE="RetroZachar - FFD Disk Maker - Jaźwiec"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="install"
PREFIX="/usr/local"

for arg in "$@"; do
    case "$arg" in
        --user)      PREFIX="$HOME/.local" ;;
        --uninstall) MODE="uninstall" ;;
        --prefix=*)  PREFIX="${arg#*=}" ;;
        -h|--help)
            sed -n '3,12p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "Nieznana opcja: $arg (uzyj --help)" >&2
            exit 1
            ;;
    esac
done

LIB_DIR="$PREFIX/lib/$APP_NAME"
BIN_FILE="$PREFIX/bin/$APP_NAME"
DESKTOP_FILE="$PREFIX/share/applications/$APP_NAME.desktop"
ICON_DIR="$PREFIX/share/icons/hicolor"
UDEV_RULE="/etc/udev/rules.d/99-$APP_NAME-floppy.rules"

# --- odinstalowanie -------------------------------------------------------

if [ "$MODE" = "uninstall" ]; then
    rm -rf "$LIB_DIR"
    rm -f "$BIN_FILE" "$DESKTOP_FILE"
    for R in 256x256 64x64 32x32; do
        rm -f "$ICON_DIR/$R/apps/$APP_NAME.png"
    done
    rm -f "$ICON_DIR/scalable/apps/$APP_NAME.svg"
    if [ "$(id -u)" -eq 0 ] && [ -f "$UDEV_RULE" ]; then
        rm -f "$UDEV_RULE"
        command -v udevadm >/dev/null 2>&1 &&
            udevadm control --reload-rules 2>/dev/null || true
        echo "Usunieto regule udev dla napedow dyskietek."
    fi
    command -v update-desktop-database >/dev/null 2>&1 &&
        update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
    echo "Odinstalowano $APP_TITLE z $PREFIX."
    echo "Ustawienia w ~/.retrozachar.json zostaly nietkniete - usun je recznie,"
    echo "jesli nie sa juz potrzebne."
    exit 0
fi

# --- kontrola przed instalacja --------------------------------------------

for file in main.py gui_main.py ui_panels.py styles.py system.py features.py dialogs_files.py fat12.py languages.py dostext.py engines.py; do
    if [ ! -f "$SOURCE_DIR/$file" ]; then
        echo "BLAD: brakuje pliku $file obok instalatora." >&2
        exit 1
    fi
done

if ! command -v python3 >/dev/null 2>&1; then
    echo "BLAD: nie znaleziono python3. Zainstaluj go i sprobuj ponownie." >&2
    exit 1
fi

PYTHON_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 9) else 0)')
if [ "$PYTHON_OK" != "1" ]; then
    echo "BLAD: wymagany jest Python 3.9 lub nowszy." >&2
    python3 --version >&2
    exit 1
fi

TK_MISSING=""
python3 -c 'import tkinter' 2>/dev/null || TK_MISSING="tak"

if [ "$PREFIX" = "/usr/local" ] && [ "$(id -u)" -ne 0 ]; then
    echo "BLAD: instalacja w $PREFIX wymaga uprawnien administratora." >&2
    echo "Uruchom:  sudo ./install.sh" >&2
    echo "albo zainstaluj tylko dla siebie:  ./install.sh --user" >&2
    exit 1
fi

# --- instalacja -----------------------------------------------------------

echo "Instaluje $APP_TITLE w $PREFIX"

install -d "$LIB_DIR" "$(dirname "$BIN_FILE")" \
           "$(dirname "$DESKTOP_FILE")"

install -m 644 "$SOURCE_DIR/main.py" "$SOURCE_DIR/gui_main.py" \
               "$SOURCE_DIR/ui_panels.py" "$SOURCE_DIR/styles.py" \
               "$SOURCE_DIR/system.py" "$SOURCE_DIR/features.py" \
               "$SOURCE_DIR/dialogs_files.py" \
               "$SOURCE_DIR/fat12.py" \
               "$SOURCE_DIR/languages.py" "$SOURCE_DIR/dostext.py" \
               "$SOURCE_DIR/engines.py" "$LIB_DIR/"

# Greaseweazle - niezalezny od stacji USB, dziala tylko przy zainstalowanym gw.
if [ -f "$SOURCE_DIR/gwbridge.py" ]; then
    install -m 644 "$SOURCE_DIR/gwbridge.py" "$SOURCE_DIR/dialogs_gw.py" \
                   "$LIB_DIR/"
fi

# Kreator kompletu dyskietek jest dodatkiem - bez niego reszta dziala.
if [ -f "$SOURCE_DIR/diskset.py" ]; then
    install -m 644 "$SOURCE_DIR/diskset.py" "$SOURCE_DIR/dialogs_diskset.py" \
                   "$LIB_DIR/"
fi

# Obsluga fizycznych napedow jest opcjonalna. Bez tego pliku program dziala
# normalnie, tylko bez menu "Naped" - dzieki temu ten sam instalator obsluguje
# wydanie z obsluga napedow i bez niej.
DRIVES=""
if [ -f "$SOURCE_DIR/usbfloppy.py" ]; then
    install -m 644 "$SOURCE_DIR/usbfloppy.py" "$SOURCE_DIR/dialogs_drive.py" \
                   "$LIB_DIR/"
    # Most do Greaseweazle - opcjonalny, dziala tylko przy zainstalowanym gw.

    DRIVES="tak"
fi
[ -f "$SOURCE_DIR/README.md" ] &&
    install -m 644 "$SOURCE_DIR/README.md" "$LIB_DIR/"

# Ikona w trzech rozmiarach. Male kadry pokazuja sama glowe - cala sylwetka
# zlewa sie ponizej 48 pikseli w nieczytelna plame.
for PARA in "256x256:jazwiec.png" "64x64:jazwiec-64.png" "32x32:jazwiec-32.png"
do
    ROZMIAR="${PARA%%:*}"
    PLIK="${PARA##*:}"
    if [ -f "$SOURCE_DIR/$PLIK" ]; then
        install -d "$ICON_DIR/$ROZMIAR/apps"
        install -m 644 "$SOURCE_DIR/$PLIK" \
                "$ICON_DIR/$ROZMIAR/apps/$APP_NAME.png"
    fi
done

# Ikona jest tez potrzebna w katalogu programu - stamtad bierze ja okno.
for PLIK in jazwiec.png jazwiec-64.png jazwiec-32.png jazwiec-panel.png jazwiec-gw.png; do
    [ -f "$SOURCE_DIR/$PLIK" ] && install -m 644 "$SOURCE_DIR/$PLIK" "$LIB_DIR/"
done

# Program uruchamiany przez krotki skrypt, zeby dzialal niezaleznie
# od katalogu, w ktorym akurat jestesmy.
cat > "$BIN_FILE" <<EOF
#!/bin/sh
# $APP_TITLE
exec python3 "$LIB_DIR/main.py" "\$@"
EOF
chmod 755 "$BIN_FILE"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$APP_TITLE
GenericName=Edytor obrazow dyskietek
Comment=Tworzenie i edycja obrazow dyskietek FAT12 dla 86Box, PCem i DOSBox
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Categories=Utility;FileTools;
Keywords=dyskietka;floppy;FAT12;obraz;img;86Box;PCem;DOSBox;retro;
StartupNotify=true
EOF
chmod 644 "$DESKTOP_FILE"

# Regula udev daje dostep do stacji dyskietek bez uprawnien administratora.
# Bez niej odczyt nosnika wymagalby uruchamiania calego programu przez sudo.
UDEV_INSTALLED=""
if [ -n "$DRIVES" ] && [ "$(id -u)" -eq 0 ] \
        && [ -f "$SOURCE_DIR/99-$APP_NAME-floppy.rules" ]; then
    install -d /etc/udev/rules.d
    install -m 644 "$SOURCE_DIR/99-$APP_NAME-floppy.rules" "$UDEV_RULE"
    UDEV_INSTALLED="tak"
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger --subsystem-match=block 2>/dev/null || true
    fi
fi

command -v update-desktop-database >/dev/null 2>&1 &&
    update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null 2>&1 &&
    gtk-update-icon-cache -qtf "$ICON_DIR" 2>/dev/null || true

# --- podsumowanie ---------------------------------------------------------

echo
echo "Gotowe. Uruchomienie: retrozachar  (albo z menu systemowego)"
if [ "$(id -u)" -eq 0 ]; then
    echo "Odinstalowanie:       sudo $SOURCE_DIR/install.sh --uninstall"
else
    echo "Odinstalowanie:       $SOURCE_DIR/install.sh --user --uninstall"
fi

if [ -n "$UDEV_INSTALLED" ]; then
    echo
    echo "Zainstalowano regule udev dla stacji dyskietek."
    echo "Podlacz naped ponownie - program siegnie do niego bez sudo."
elif [ -n "$DRIVES" ] && [ "$(id -u)" -ne 0 ]; then
    echo
    echo "Uwaga: odczyt fizycznych dyskietek wymaga reguly udev, ktorej"
    echo "instalacja tylko dla siebie nie obejmuje. Dopisz ja poleceniem:"
    echo "  sudo $SOURCE_DIR/install.sh"
fi

if [ -z "$DRIVES" ]; then
    echo
    echo "Wydanie bez obslugi fizycznych napedow (brak usbfloppy.py)."
    echo "Tworzenie i edycja obrazow dziala bez zmian."
fi

if [ -n "$TK_MISSING" ]; then
    echo
    echo "UWAGA: brakuje Tkintera, bez ktorego okno sie nie otworzy."
    if command -v apt >/dev/null 2>&1; then
        echo "  sudo apt install python3-tk"
    elif command -v dnf >/dev/null 2>&1; then
        echo "  sudo dnf install python3-tkinter"
    elif command -v pacman >/dev/null 2>&1; then
        echo "  sudo pacman -S tk"
    else
        echo "  doinstaluj pakiet z Tkinterem dla swojej dystrybucji"
    fi
fi

case ":$PATH:" in
    *":$PREFIX/bin:"*) ;;
    *)
        echo
        echo "UWAGA: $PREFIX/bin nie jest w PATH. Dopisz do ~/.bashrc:"
        echo "  export PATH=\"\$PATH:$PREFIX/bin\""
        ;;
esac
