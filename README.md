# RetroZachar — FFD Disk Maker — Jaźwiec

*[Polska wersja tego pliku](README.pl.md)*

Create and edit FAT12 floppy images for the 86Box, PCem and DOSBox emulators.
The program is a Python rewrite of a shell script, but without its two
limitations: it never calls `mkfs.fat` and never mounts anything, so it
behaves identically on Linux and Windows — and needs no `sudo`.

## Files

| File | Role |
|---|---|
| `main.py` | entry point — checks whether a window can be opened |
| `gui_main.py` | main window: actions, state, language, settings |
| `ui_panels.py` | window layout: menu, banner, panels, footer, function keys |
| `features.py` | detection of optional parts (drives, disk-set wizard) |
| `styles.py` | looks: name, version, palette, fonts, icon, widget factories |
| `system.py` | sudo, home directory, settings, locating icons |
| `dialogs_files.py` | folder-copy window and the text file editor |
| `dialogs_drive.py` | drive windows: list, formatting, report (with `usbfloppy.py`) |
| `dialogs_diskset.py` | disk-set wizard (with `diskset.py`) |
| `gwbridge.py` | Greaseweazle bridge: runs `gw` and parses its output |
| `vhd.py` | reading VHD disk images |
| `partitions.py` | partition table of disk images |
| `fat16.py` | FAT16/FAT12 engine for hard disks |
| `dialogs_disk.py` | partition chooser window |
| `dialogs_gw.py` | Greaseweazle window (with `gwbridge.py`) |
| `fat12.py` | FAT12 engine — formatting and file operations |
| `languages.py` | interface strings (Polish, English) |
| `dostext.py` | text conversion between DOS code pages |
| `engines.py` | picks the filesystem engine for an image being opened |
| `diskset.py` | splitting a program across a set of floppies |
| `usbfloppy.py` | physical floppy drive support |
| `99-retrozachar-floppy.rules` | udev rule for drives (Linux) |
| `install.sh` | Linux installer |
| `jazwiec.png` | 256×256 icon (whole character) |
| `jazwiec-64.png`, `jazwiec-32.png` | small icons (head only) |
| `jazwiec.ico` | Windows icon, for PyInstaller |
| `jazwiec-panel.png` | artwork below the create-disk button |
| `jazwiec-gw.png` | report background in the Greaseweazle window |

All `.py` files must sit in the same directory. `diskset.py` is optional —
without it only the disk-set wizard disappears.

## Icon

The program ships three icon sizes. The large one shows the whole character;
64 and 32 pixels show only the head. This is not a whim: below roughly 48
pixels the figure holding a floppy blurs into an unreadable smudge, while the
stripes on a badger's face stay recognisable even at 16 pixels.

`jazwiec.ico` contains all six sizes and is used when building an `.exe`:

```bat
python -m PyInstaller --onefile --windowed --icon=jazwiec.ico ^
    --name RetroZachar main.py
```

## Greaseweazle

[Greaseweazle](https://github.com/keirf/greaseweazle) connects a genuine
period drive to the computer and reads the magnetic flux straight from the
head. `gwbridge.py` runs the `gw` command and turns its output into a report.

In the program: **Drive → Greaseweazle**. A separate window rather than an
entry in the USB drive window, because the workflow differs — the drive and
format have to be chosen, as `gw` does not detect them. The window checks for
the tool and the device, reads a floppy into an image, writes an image back
and formats a disk, and shows the report in place. The chosen drive and
format are remembered.

### Track map

Instead of a progress bar the window shows a track map: one row per disk
side, one column per cylinder. `gw` draws its own map the same way, and so
did X-Copy on the Amiga. The layout matches the physical geometry, so the
pattern of damage tells you what happened at a glance — a single red square
is a damaged spot on the medium, a whole red row is a dead head.

| Colour | Meaning |
|---|---|
| grey | track waiting |
| yellow | track in progress |
| green | fine |
| brown | read only after retries — still works, but weakening |
| red | sectors cannot be read — damaged medium |
| purple | sectors from a foreign cylinder — **a drive problem, not a disk one** |

Red and purple mean entirely different things: the first concerns the medium,
the second the drive — and only the second says "do not put anything valuable
in here".

When **no** track yields a single sector, the program does not report damage.
It suggests the most likely cause instead: a format other than the one
selected. An Amiga floppy read as a PC one looks exactly like that — verified
on a real disk. The other explanation is an unformatted medium. A drive
problem is checked first, because a stuck head produces the same picture, and
only the cylinder recorded in the headers of the sectors found tells them
apart.

Red is not a death sentence for a floppy. A weakly written or demagnetised
track looks the same as a damaged surface, and formatting plus a fresh write
can bring it back — verified on a disk whose track a faulty drive had
demagnetised. Only when sectors stay unreadable after a fresh write is the
medium truly damaged. Read off whatever you can first, because formatting
erases everything.

`gw` prints a line after finishing a track, not when starting it. The yellow
square is therefore the track still struggling through retries, or — when
there is none — the next one in order. When writing, `gw` does not report
verification track by track, so written tracks turn green immediately and the
verification result is shown on the status line.

Pointing at a square shows the track's details: how many sectors were read,
how many attempts it took and whether sectors from another cylinder turned up.

The report from a write or a format contains a **track map** — two rows of
eighty columns, one character per track. `gw` writes whole tracks at a time
and prints no sector map then, so no finer information exists; the map is
named differently precisely so it does not suggest otherwise.

The report from a read contains a sector map in the same layout `gw` prints
it: a column per cylinder, a row per side and sector number, a dot for a
sector read and `X` for an unreadable one. In the window the `X` marks are
red so they can be spotted against the background image; in the saved `.txt`
file the map is plain text, as in `gw`. The window cannot be made narrower
than the map, because a wrapped map would lose its columns.

The report is displayed over a background image. The image is darkened with
a black filter at 70% opacity and has faded edges, and every line of text has
a shadow beneath it — on bright parts of the picture plain text lost contrast.
The background stays put; only the text scrolls. Free space is left below the
report so that scrolling to the end stops the diagnosis above the title baked
into the image. Selecting text with the mouse is not possible here; the report
is saved to a file with a button.

Formatting means writing a blank FAT12 image through `gw write`. Greaseweazle
writes the whole track together with the sector headers, so this is a full
low-level format.

A write counts as successful only once `gw` confirms verification with the
line `All tracks verified`.

If the `gw` command is not on the system PATH — on Windows the tools are
often unpacked into an arbitrary directory — the **Locate gw file** button
points the program at it and the choice is remembered. Without this the
command can work in a console while the program started from Explorer sees
nothing, because it has a different working directory.

If a floppy has spent years in its sleeve, the first read is often the worst
one. The liner inside the shell picks up dust on every turn, so the medium
cleans itself as it is read — a disk that lost 33 sectors on the first pass
returned all 1,760 on the second. That is why the report counts tracks that
needed retries and, when there are any, suggests reading the disk again. The
**Retries per track** field raises the number of attempts `gw` makes before
giving up on a track; from the command line `--retries` does the same and
`--seek-retries` additionally makes the head travel to the track anew.

### Building one image from several reads

Different reads of the same floppy lose different sectors, so several passes
together can yield a complete image where no single pass did — verified on an
Amiga disk whose four reads differed by exactly one sector.

When the file you point at already exists, the window asks whether to fill in
the sectors it is missing or to overwrite it. A second map below the first
shows the **collected data**: the columns of both maps line up, so a glance
down one column tells you both how the current pass went and what the image
holds overall. The counter says how many sectors have been gathered and how
many the latest pass added.

Holes are recognised by the filler `gw` writes in place of a sector it could
not read. A sector of zeros is valid data — an empty area of a floppy looks
exactly like that — and is never treated as missing, because that would
overwrite good content during a merge.

The new read goes to a file alongside and replaces the image only once the
merge succeeds, so work already gathered cannot be lost to a failed pass.
A report from every pass is saved next to the image, numbered in its name
(`Titan-przejscie-1.txt`).

The module also works from the command line:

```bash
python3 gwbridge.py info
python3 gwbridge.py read image.img --format 1440 --drive A --retries 10
python3 gwbridge.py write image.img --format 1440 --drive A
python3 gwbridge.py parse saved_output.txt --format 1440
python3 gwbridge.py --gw /path/to/gw info
```

Formats are grouped into tabs by family:

| Tab | Formats | File |
|---|---|---|
| PC / DOS | 180 KB, 320 KB, 360 KB, 720 KB, 1.2 MB, 1.25 MB (NEC PC-98), 1.44 MB, 2.88 MB | `.img` |
| Amiga | 880 KB (DD), 1.76 MB (HD) | `.adf` |
| Atari ST | 360 KB, 720 KB, 800 KB, 880 KB | `.st` |

Format names were checked against the list printed by `gw read --help`. For
the single-sided 3.5" 360 KB format `gw` has no counterpart, so the window
does not offer it. Drives: `A` and `B` on the IBM cable, `0`–`2` in Shugart
mode.

The file extension follows the selected medium, because `gw` picks its
conversion from it — an Amiga floppy saved as `.img` would produce an image
no emulator can open.

**Amiga and Atari disks can be read and written, but not formatted.**
Formatting here means writing a blank image, and such an image can only be
built with the FAT12 engine. For those families the button is disabled.
Format the disk on the target machine, or write a ready image onto it.

The program will not open an Amiga or Atari image in the main window — that
is a job for future filesystem engines. For now this is an archival route:
medium to file and back, bit for bit.

Commodore 1541 is waiting its turn: it records a different number of sectors
per track depending on the zone, which needs separate handling.

**What a USB drive will not tell you.** A USB drive answers an unreadable
track with "sector error" and nothing more. Greaseweazle's output says *why*.
The report tells apart three cases that would look identical on a USB drive:

- **dead track** — the head is positioned correctly, but no sector can be
  decoded; a damaged medium,
- **sectors from a foreign cylinder** — the headers report a different
  cylinder than requested; the head did not arrive, so this is a drive
  problem, and the list of "bad" sectors says nothing about the disk,
- **a silent head** — one side reads nothing while the other does; a damaged
  or dirty head.

The last one matters in practice: a drive with a damaged head can wipe the
track it rests on. Do not put valuable floppies in it.

The report also gives the drive's rotation speed, computed from the read
times — valuable information for old drives that a USB drive knows nothing
about.

The `parse` command analyses previously saved `gw read` output, with no
device attached.

## Tests

```bash
python3 tests/run.py            # everything
python3 tests/run.py fat12      # a single module
```

The tests do not touch user settings — they get their own temporary home
directory. Earlier versions of the suite wrote to `~/.retrozachar.json`; if
you ran them from version 2.4 onwards, check that file: traces such as
a `/sciezka/do/gry` directory may be left in it.

They need nothing beyond the standard library. Some checks need tools that
may be missing — those are skipped, not reported as errors: `fsck.fat` from
the `dosfstools` package serves as independent confirmation that the images
are correct, and the window tests need a graphical server. On a headless
Linux box, `xvfb-run -a python3 tests/run.py` helps.

The strongest check is the installer simulation: it executes the generated
batch file the way `COMMAND.COM` would — including disk swaps and the
reassembly of split files — and finally compares the restored tree with the
source byte for byte. Without DOS at hand this is the only way to really test
the installer instead of merely eyeballing it.

The suite grew out of two regressions that actually happened: a whole text
editor class vanished during a careless file restructuring, and the same
oversight with highlighting the selected item repeated across four windows in
turn. Both cases now have their tests.

## System installation (Linux)

```bash
sudo ./install.sh
```

The program appears in the system menu and runs with the `retrozachar`
command from any directory. Files go to `/usr/local`:

| Path | Contents |
|---|---|
| `/usr/local/lib/retrozachar/` | program code |
| `/usr/local/bin/retrozachar` | launcher command |
| `/usr/local/share/applications/` | menu entry |
| `/usr/local/share/icons/hicolor/` | 256, 64 and 32 pixel icons |
| `/etc/udev/rules.d/` | drive access rule |

Without administrator rights you install for yourself only, in `~/.local`:

```bash
./install.sh --user
```

To uninstall: `sudo ./install.sh --uninstall` (or with `--user`).

**Do not run the program through `sudo`.** Administrator rights are needed
for the installation itself and nothing else. Running as root would write
settings to `/root/.retrozachar.json`, and the `.img` files created would
belong to root, leaving you unable to edit them later.

## Running without installing

```bash
python3 main.py
```

All you need is Python 3.9 or newer. Windows and macOS ship Tkinter as part
of the standard installation; on Debian and Ubuntu one package has to be
added:

```bash
sudo apt install python3-tk
```

On Windows it is more convenient to save the file as `main.pyw` — then no
console window opens.

## What the program can do

Nine historical formats, with geometry matching the original drives. The
interface splits them into two tabs.

**Popular formats**

| Format | CLI key | Capacity | Clusters | Root directory |
|---|---|---|---|---|
| 5.25" 360 KB (PC/XT) | `360` | 368,640 B | 354 | 112 |
| 5.25" 1.2 MB (AT/286) | `1200` | 1,228,800 B | 2371 | 224 |
| 3.5" 720 KB (DD) | `720` | 737,280 B | 713 | 112 |
| 3.5" 1.44 MB (HD) | `1440` | 1,474,560 B | 2847 | 224 |

**Other formats**

| Format | CLI key | Capacity | Clusters | Root directory |
|---|---|---|---|---|
| 5.25" 180 KB (single-sided) | `180` | 184,320 B | 351 | 64 |
| 5.25" 320 KB (8 sectors) | `320` | 327,680 B | 315 | 112 |
| 3.5" 360 KB (single-sided DD) | `360_35` | 368,640 B | 354 | 112 |
| 3.5" 1.25 MB (NEC PC-98) | `1250` | 1,261,568 B | 1221 | 192 |
| 3.5" 2.88 MB (Extra Density) | `2880` | 2,949,120 B | 2863 | 240 |

The PC-98 format is the only one using 1024-byte sectors instead of 512 —
that is NEC's original geometry (77 tracks, 8 sectors, 2 heads).

Instead of mounting an image, the program has a built-in file manager. It
copies files both ways, creates and deletes directories, renames files and
changes the volume label. It also shows how much space is left as you work.

The `.img` file you create is attached in 86Box through
*Settings → Floppy drives*.

## Physical floppy drive

The **Drive → Floppy drives** menu detects attached drives, reads a medium
sector by sector into an `.img` file and writes an image back onto a disk.
The image just read opens straight away in the right-hand panel.

### Permissions — without running the program as root

Raw device access is restricted, but that is no reason for the program to run
as root. `install.sh` adds a udev rule
(`/etc/udev/rules.d/99-retrozachar-floppy.rules`) granting access to floppy
drives only to the logged-in user. After installing it, just plug the drive
in again.

The rule covers floppy drives exclusively. It checks the mass storage class
(`bInterfaceClass` `08`) and the subclass: floppy drives report themselves as
UFI (`0x04`) or SFF-8070i (`0x05`), while flash drives use SCSI transparent
(`0x06`) and stay out of its reach. A drive on the mainboard controller
(`/dev/fd*`) is covered too.

Access is granted with `MODE="0666"`. An earlier version relied on
`TAG+="uaccess"`, the ACL granted by systemd-logind to the locally logged-in
person, but that mechanism does not work on some configurations and left the
drive inaccessible. The price of certainty is that on a multi-user machine
every account can read and write an inserted floppy. If that is a problem,
change `MODE` to `0660` in the rule file and add a `GROUP` of your choice.

If the drive stays inaccessible despite the rule, check which subclass it
reports:

```bash
lsusb -v 2>/dev/null | grep -E "bInterfaceClass|bInterfaceSubClass"
```

Some older drives report `0x06`. In that case it is better to add a rule for
that particular unit by `idVendor` and `idProduct` than to cover the whole
subclass — flash drives and external disks belong to it as well. A ready
pattern sits in a comment at the end of the rule file.

On Windows there is no way around UAC. The program starts normally and asks
for elevation only when you actually reach for the drive, offering a restart
in one click.

Should someone run the program through `sudo` anyway, a safeguard kicks in:
settings go to the real user's home directory rather than root's, and files
created get that user's ownership.

### What such a drive cannot do

A USB drive hands over logical sectors, not magnetic flux. In practice it
will read an ordinary 1.44 MB or 720 KB floppy, and a 1.2 MB one less often.
It will not cope with copy protection, a non-standard sector count or FM
encoding. Serious archival work needs flux-level controllers (Greaseweazle,
KryoFlux).

### What no PC drive will read

Amiga floppies. The Amiga writes 11 sectors of 512 bytes per track in its own
MFM encoding, decoded in software by `trackdisk.device`. A PC controller
expects a strictly defined sector layout and does not understand that format —
this is a hardware limitation, not a missing feature. Reading such media
requires a flux-level controller (Greaseweazle, KryoFlux) or an Amiga itself.

The symptom is characteristic: the drive retries for two or three minutes and
looks hung. The program aborts the read after 20 seconds and states the
reason instead of waiting along with the drive.

### Previewing a floppy's contents

The **Preview contents** button opens the filesystem of the inserted floppy
directly in the right-hand panel. Everything that works with images works
there: navigating directories, selecting several entries and extracting
individual files with F9.

Reading is lazy. To show the file list the program reads the system area
only — the boot sector, the FAT tables and the root directory, that is 33
sectors out of 2880 for a 1.44 MB floppy. Entering a subdirectory pulls in
its clusters, and extracting a file only the ones that file occupies. In
practice, looking at the contents and pulling out one file touches about 2%
of the medium instead of 100%.

This matters for floppies in poor condition: you do not wear out the whole
surface just to see what is on it. Sectors that cannot be read do not abort
the preview — the program skips them and reports how many there were.

The preview is read-only; buttons that change contents are disabled in this
mode. To write something onto a floppy, read it into an `.img`, edit the
image and write it back.

### Formatting a floppy

The **Format floppy** button in the drive window wipes the medium and writes
a fresh FAT12 filesystem onto it. Two modes are available:

- **quick** — the filesystem only, a few seconds;
- **full** — first a test of the entire surface with a check pattern, then
  the filesystem. Damaged clusters are marked bad in the FAT (`0xFF7`), so
  DOS stops using them — exactly as the `FORMAT` command does. The test
  passes over the medium four times and takes a few minutes.

When it finishes, a report opens listing the damaged sectors, the number of
marked clusters, the capacity lost and the verification result. It can be
saved to a `.txt` file.

### Changing density, for example 1.44 MB to 720 KB

Formats that do not match the inserted floppy are on the list too, marked as
requiring a density change. Choosing one first switches the medium over and
then formats it normally — with a single button.

A density change cannot be requested through the filesystem; it needs the
FORMAT UNIT command of the UFI protocol. On Linux `ufiformat` from the
`ufiutils` package performs it:

```bash
sudo apt install ufiutils
```

Without it the entry stays visible, but the *Format* button is inactive and
the window gives the command to install.

On Windows the program does not do this for you — it shows the command to run
in a command prompt as Administrator:

```
format A: /F:720
```

Once it finishes, return to the program, refresh the drive list and format
the medium normally.

It is worth adding that Amiga floppies use their own 880 KB format, which a
PC cannot write. A density change prepares the medium itself; the actual
formatting is done on the Amiga.

### Diagnostics: `probe`

Before writing a drive off as broken, check it with a command that assumes no
filesystem:

```bash
python3 usbfloppy.py probe /dev/sdb
```

It tells apart three situations that look identical from the outside: a
readable medium without a filesystem (just format it, the hardware is fine),
a medium returning no data (wrong density or a damaged disk), and no medium
in the drive.

The file manager's "can't read superblock" message comes from udisks and
means only that there is no readable filesystem on the medium. It says
nothing about the drive's health — if `/dev/sdb` exists at all, USB
enumeration worked.

### An HD floppy formatted to 720 KB

A drive recognises density by the hole in the corner of the floppy's shell,
not by what is recorded on it. An HD floppy low-level formatted to 720 KB
still has its HD hole open, so the drive reads it in high-density mode and
misses the tracks written in DD. The symptom: the drive reports 1,440 KB
while `probe` shows zero sectors read.

This is not a hardware failure. Two ways out:

1. **Cover the HD hole** with opaque tape — the corner opposite the
   write-protect slider. The drive will recognise the medium as DD and read
   the 720 KB recording. This is how media for the Amiga are prepared.
2. **Restore the floppy to HD**: `ufiformat -f 1440 /dev/sdb`, then format it
   normally in the program.

The program warns about this before stepping down from HD to DD and gives the
command to go back.

### When the drive stops responding

The symptom: the system tries to read a floppy, but the motor does not start.
The drive is stuck in an internal state that no system command will clear.

What to do: remove the floppy, unplug the USB cable, wait a few seconds and
plug it back in. Only cutting the power clears the controller's state —
neither `udevadm trigger` nor restarting the program will help.

The cause is almost always the `FORMAT UNIT` command, that is a density
change. Cheaper drives report themselves as UFI-compliant but do not execute
that command properly and can hang afterwards. That is why the program asks
the drive about supported formats before sending anything and shows the
answer — if the capacity you want is not there, it is better not to continue.

What the program does to the device apart from a density change: only `open`,
`seek`, `read`, `write` and `fsync` on the block node. These are ordinary
operations on the medium's contents; they do not reach the USB protocol or
the drive's firmware and cannot switch it into another mode. Ordinary
formatting, reading and writing an image invoke no external command at all.

Diagnostics on Linux:

```bash
dmesg | tail -40          # USB resets and SCSI errors
lsof /dev/sdb             # whether anything holds the device open
which ufiformat           # whether a density change was possible at all
```

The last command settles the most. Without `ufiformat` installed the density
change button is inactive, so the program had no way to send `FORMAT UNIT` —
and then the cause has to be sought in the hardware itself.

### Two different thresholds for bad sectors

The program distinguishes **dead** sectors from **weak** ones — those that
come back only on a further read attempt. It treats them differently
depending on the question a given operation answers.

**The surface test during formatting** is strict: one attempt, and a sector
needing a retry is marked bad. It answers "can I safely put data here", so it
is better to reject a borderline sector than to store a file on it. DOS's
`FORMAT` behaves the same way.

**Verification after a write** is gentler: as many attempts as an ordinary
read. It answers "did the write succeed", and a sector read on the second
attempt was written correctly. A single attempt inflated the error count here
and was more frightening than the state of the medium deserved.

### Bad sectors

Reading goes in chunks of 32 sectors. When a chunk fails, the program drops
down to single sectors to establish exactly which ones are faulty, retrying
each three times. Sectors that cannot be read are not skipped — they are
filled with the byte `0xF6` and listed. From a floppy damaged in a few places
you therefore recover all the rest instead of nothing.

### Safeguards when writing

Writing to a physical device is irreversible, so four barriers work at once.
The medium must be removable, its size must match one of the known floppy
geometries to the byte, it must not exceed 4 MB and it must not be mounted.
Devices larger than the limit never even reach the list — a flash drive or an
external disk has no way of appearing there. Finally the image size must
match the medium's size, and after writing the program reads the floppy back
and compares it with the image.

### Command line

```bash
python3 usbfloppy.py list
python3 usbfloppy.py read /dev/sdb copy.img
python3 usbfloppy.py write /dev/sdb image.img
```

Without the udev rule installed these commands need `sudo`.

## Language

The program starts in Polish. English is chosen from the **Język → English**
menu; the choice is saved in `~/.retrozachar.json` and applies to later runs.
Switching works immediately and does not close the open image — the current
directory and the selected format stay as they were.

Translation covers not only the window labels but also the engine's messages
and the format descriptions, including the decimal separator (`1,44 MB`
versus `1.44 MB`). A new language is added by writing a dictionary in
`languages.py` and in `fat12.MESSAGES` — missing keys fall back to Polish, so
an incomplete translation will not break the program.

The command line accepts `--lang`:

```bash
python3 fat12.py --lang en list disk.img
```

## Design: filesystem engines (`engines.py`)

The interface does not know it is reading FAT12. A file being opened goes
first to `engines.py`, which recognises the format **by its contents** rather
than by the extension, and returns an image object with a fixed set of
methods. Paths and name shortening go through that object too, because every
filesystem has its own rules here — FAT12 cuts names down to 8.3, AmigaDOS
allows thirty characters.

Adding another filesystem therefore comes down to writing a module and
registering it in `engines.py`, without touching the window. A pattern for
that registration sits in a comment at the top of the file. The first
candidate is AmigaDOS, that is `.adf` files.

When no engine recognises a file, the program says plainly what it supports
instead of printing a parsing error.

## Text file editor

Double-clicking a file opens it in the editor. You can also use **Files →
Edit text file**, or create a new one through **Files → New text file**.

There is one reason for this: writing an `autoexec.bat` with box-drawing
frames under DOS is agony, and in a modern editor it founders on encoding.
The frame `╔══╗` is code page 437 bytes in DOS; saved as UTF-8 it falls apart
on the first run.

The editor shows DOS bytes as Unicode characters, so frames and accented
letters look the way they looked on a DOS screen and are edited normally. On
saving they return to the chosen code page.

| Code page | For what |
|---|---|
| CP437 | DOS US, full set of box-drawing characters |
| CP852 | Central Europe, Polish diacritics |
| CP850 | Western Europe |

All three assign a different character to each of the 256 bytes, so a file
opened and saved unchanged returns to the floppy **byte for byte** — verified
by a test over the full range. You can therefore safely look inside even a
file you do not intend to change.

### Typing characters by code

The DOS `Alt+186` will not work — Tkinter does not support that combination
with the numeric keypad. Instead the editor has an **Alt+** field: you type
`186`, press Enter and get `║`. Hexadecimal codes such as `0xDB` are accepted
too.

If you prefer to pick by eye, there is a **Character table** button — a grid
of all 256 codes of the current code page. Pointing at one shows its decimal
and hexadecimal number; clicking inserts the character at the cursor.

The decorative symbols in the 1–31 range (`☺ ♥ ♪ ►`) are available as well,
although it took a separate table: Python's codecs map those bytes to control
characters rather than to the DOS symbols. Codes that would be ambiguous in a
given code page — like `§` in CP852, which already has its own code 245 —
stay greyed out in the table, so that saving remains reversible.

The editor also looks after two things that are easy to forget: it saves line
endings as `CR LF`, and restores the historical end-of-file marker `0x1A` if
the original had one. When you type a character the chosen code page does not
know — Polish letters under CP437, for instance — the program lists them
before saving and suggests CP852.

## Exchanging files with the emulator

The same `.img` file can be mounted in 86Box and open in the program at the
same time, which gives a channel for exchanging files between the computer
and the emulated machine — 86Box has no shared folders, so this is often the
most convenient route.

**One rule applies: only one side writes at a time.** The program keeps the
whole image in memory and writes the file out as a whole. Without care it
would overwrite everything the guest had written in the meantime.

The program looks after this for you. It remembers the file's state and
checks it before every write and when refreshing the listing:

- when the file changed on disk and you are only browsing, the program
  reloads it and says so on the status line;
- when it changed and you try to save something, it asks what to do: reload
  and abandon the operation, overwrite anyway, or do nothing.

The order that works without surprises:

1. **From the computer to the emulator** — drop the files in via the program,
   then in 86Box eject and re-insert the floppy (*Settings → Floppy drives*).
   Without that DOS still sees the old contents, because it keeps the
   directory in its cache.
2. **From the emulator to the computer** — eject the floppy in 86Box so the
   changes reach the file, then press F2 in the program. The contents reload.

## A set of floppies for a program larger than the medium

**Disk → Disk set (Jaźwiec)** spreads a directory across successive media and
adds an installer to the first one, which puts everything back together on
the target machine's hard disk. A 4.3 MiB game makes four 1.44 MB floppies or
seven 720 KB ones.

The installer is an ordinary batch file and uses **only** commands built into
`COMMAND.COM`: `MD`, `COPY`, `DEL`, `ECHO`, `PAUSE`, `IF EXIST` and `GOTO`.
Nothing is needed on the target machine — no archiver, no tools at all. It
works on plain DOS 3.3.

On the target machine:

```
A:
INSTALL
```

### Target drive and directory

The drive is chosen in the wizard, next to the directory name — `C:` by
default, but on period machines the system disk is often cramped and another
one is worth aiming at.

Before doing anything the installer shows the target, **lists the available
drives** and waits for a keypress; Ctrl+C aborts. Should the chosen drive not
exist, it says so plainly instead of ending with a confusing `MD` error.

The drive can also be given at startup, along with the source drive:

```
INSTALL D: B:
```

**Why the installer does not ask for a path.** A DOS batch file cannot read
text from the keyboard — `SET /P` appeared only in the `cmd` of Windows 2000,
and `CHOICE.COM` reads a single key and is a Microsoft file that may not be
redistributed. The choice is therefore made when recording, or through a
parameter. Listing the available drives is possible, though: `IF EXIST D:\NUL`
checks in DOS whether a drive with that letter exists.

### The target directory name

The wizard proposes a name based on the source directory, but it **only
proposes** — and it is worth correcting. Directories on a hard disk have
descriptive names, and mechanically shortening `Pool of Radiance
(1988)(Strategic Simulations, Inc.) [Role-Playing (RPG)]` yields
`POOLOFRA.)_R`, because the dot before `)` looks like the start of an
extension. Just type `POOL`.

At most eight characters are accepted, with no dot or space — that is the DOS
limit. The name is checked before planning; with disallowed characters the
program says which ones they are.

If after planning you see a warning that all the files sit in a single
subdirectory, you probably pointed one level too high — the whole game would
then land in a nested directory with a shortened name.

### Names the installer creates

The installer's batch file lands in the target directory, next to the
program's files, and is executed from there. If the program had a file of the
same name, copying it would overwrite the batch file **while it is running** —
and `COMMAND.COM` reads a batch file incrementally, so from that moment it
would be reading someone else's file. The installation then breaks at the
first disk swap.

The risk is not theoretical: half the games of the era have a `SETUP.BAT`.
That is why the batch file is called `JAZWIEC.BAT`, and the program checks
during planning whether such a name occurs in the program's root directory.
When it does, it picks `JAZWIEC1.BAT` and says so in the plan. The same
applies to the prefix of the temporary parts of split files.

### Why the installer comes in two parts

The installer uses no environment variables. The DOS environment is 256 bytes
by default and `SET` may not fit in it; an unexpanded `%VARIABLE%` then turns
into an empty string, which makes `COPY` load the batch file onto the floppy
instead of the hard disk. Drive letters are therefore hard-coded into
separate branches, and travel onwards as batch parameters.

`COMMAND.COM` reads a batch file incrementally — after every line it returns
to the medium for the next one. A batch file sitting on a floppy that asks
for that floppy to be swapped would, on the following line, already be
reading from a different medium and would fail in ways that are hard to
diagnose. That is why the first floppy holds only a short `INSTALL.BAT`,
which copies the real `SETUP.BAT` onto the hard disk and hands control to it.
From then on the batch file being executed is on the disk and disk swaps do
it no harm.

### What the planning takes into account

Space counted in clusters, not as a sum of sizes. The limit on root directory
entries — 224 at 1.44 MB, 112 at 720 KB; with many small files it is that
limit which runs out first, not the space. The DOS path limit (64 characters)
and the batch line length. Files larger than a floppy are split into parts
and joined with `COPY /B` once all of them have been copied. Joining proceeds
incrementally, with relative paths — a single long command with full paths
exceeded the DOS line length limit at five parts already. Each part is
deleted right after being appended, so at peak you need room for the finished
file and one part, not for the file and all its parts at once.

Directories are created from the shallowest, because `MD` in DOS does not
create multi-level paths. Directories empty in the source are recreated too —
many a game needs a directory for saved games to exist and gives up without
it.

The plan is shown in full **before** recording and can be saved to a `.txt`
file.

### A bootable floppy

The program will not create one and does not try — that would require system
files it may not redistribute. Instead it takes a ready bootable image as the
basis for the first floppy and adds the installer in the free space. Prepare
such a floppy with `FORMAT A: /S` in the emulator and save it as an image.

## Hard disk images

A disk image opens the same way as a floppy — **Disk → Open image**. The
program reads VHD files, both fixed and dynamic (86Box writes the latter),
as well as raw `.img` images. The kind of file is decided by its contents,
not by its name.

On the disk it finds the partition table, including logical partitions
inside an extended one — on period machines `C:` is often primary while
`D:` and `E:` live there. With several readable partitions the program asks
which one to show; you can switch later through **Disk → Choose partition**.
Partitions it cannot read are listed alongside, so the disk does not look
smaller than it is.

It reads FAT16 and FAT12 partitions lazily: to show a directory it fetches
the parameter block, the FAT and the directory area, not the whole disk.
Which FAT it is follows from the cluster count, exactly as DOS worked it out
— the string in the boot sector can be misleading.

**Disk images are read-only.** Buttons that change contents are disabled.
Overwriting an image while the virtual machine is running destroys a whole
filesystem rather than one floppy, so writing will get its own safeguards
and its own stage of work.

From the command line:

```bash
python3 vhd.py info disk.vhd
python3 partitions.py disk.vhd
```

## Copying directories

**Files → Add folder with subfolders** moves a whole structure onto the
image: directories, subdirectories and the files inside. There is no need to
create directories by hand before copying the contents any more.

Before starting, the program shows a summary — how many files and
directories, what size, how much free space is left and whether it will fit —
along with a **preview of the contents** of the chosen directory.

That preview is not decoration. Tk's directory chooser returns the *opened*
directory rather than the one highlighted in the list, so to pick a
subdirectory you have to enter it with a double click. It is easy to be off
by one level. When the preview shows a single entry in square brackets
instead of the files you expected, you pointed too high — and the **Change**
button lets you fix it without closing the window. For a directory containing
nothing but a single subdirectory the program warns about it as well. Two
variants are available: creating a directory on the floppy named after the
source one, or copying the contents alone into the current location.

Directory names undergo the same 8.3 shortening as file names, so
`Dokumentacja PL` lands on the floppy as `DOKUMENT`. The program lists such
replacements when it finishes.

When the contents do not fit on the medium, copying is not aborted — the
program moves as much as it can and lists the specific files it skipped. The
directory structure stays intact.

Symbolic links are skipped: they have no counterpart on a floppy, and
following them would risk looping.

From the command line:

```bash
python3 fat12.py addtree disk.img ./game --dest /
python3 fat12.py addtree disk.img ./game --contents-only
```

## Keyboard shortcuts

| Key | Action |
|---|---|
| F1 | help |
| F2 | refresh the listing |
| F3 | open an image |
| F5 | add files to the floppy |
| F6 | rename |
| F7 | new directory |
| F8 | delete selected |
| F9 | extract to the hard disk |
| F10 | quit |
| Ctrl+L | volume label |
| Backspace | parent directory |

## Command line mode

`fat12.py` also works on its own, which is handy in scripts:

```bash
python3 fat12.py create disk.img --format 1440 --label DATA
python3 fat12.py add disk.img config.sys autoexec.bat
python3 fat12.py mkdir disk.img /UTILS
python3 fat12.py list disk.img
python3 fat12.py extract disk.img README.TXT ./readme.txt
python3 fat12.py rm disk.img /UTILS -r
```

## Worth knowing

**8.3 names.** DOS reads only names in the 8.3 format, so `my notes.txt`
lands on the floppy as `MYNOTES.TXT`. The program lists such changes after
copying files. On a name collision it appends a tilde: `FILE~1.TXT`.

**The root directory has a hard limit** — 112 or 224 entries depending on the
format, regardless of free space. With more files you have to create a
subdirectory.

**Bootable images.** The boot sector contains a valid BPB block and a short
piece of code that prints a "no system" message. For a floppy to boot, the
system has to be transferred onto it separately (`SYS A:` in emulated DOS).

## Differences from the original script

The shell script created an empty file with `dd`, formatted it with
`mkfs.fat` and mounted it with `sudo mount -o loop`. None of those three
tools exists on Windows, so here the filesystem is written directly: the boot
sector, both copies of the FAT, the root directory and the data area are
produced byte by byte in Python.

The safeguard against overwriting an existing file was kept — with the
difference that instead of aborting, the program asks for confirmation.

The correctness of the result was checked with independent tools: `fsck.fat`
raises no objections to any of the nine formats — including after files have
been written, subdirectories created and nested — and `mtools` reads the
entire contents correctly.

## How this was built

The program was written together with Claude, Anthropic's AI assistant. The
design decisions, all hardware testing and the verification on real floppies,
drives and emulators are the author's. Plenty of what the program does —
particularly in the Greaseweazle diagnostics — came from findings made during
that testing rather than from theory.

## Licence

MIT — see [LICENSE](LICENSE).

Copyright (c) 2026 Rafał Zacharski (Retro Zachar)
