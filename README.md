# VidKonverter

A desktop GUI for converting and batch-converting video files with
ffmpeg. Built with PySide6 (Qt for Python).

## Features

- **Single file or batch folder** conversion (recursive folder scan
  supported), with a per-file queue and progress for batch jobs.
- **Container / codec** selection - MP4, MOV, MKV, WebM, with the video
  and audio codecs each container actually supports (H.264, H.265/HEVC,
  VP9, ProRes 4444, AAC, MP3, Opus, FLAC, or stream copy).
- **Quality control** via CRF or a target bitrate, plus the standard
  x264/x265 encoder presets.
- **Resolution and crop**, decoupled from each other - pick any output
  resolution and a crop scales proportionally with it, so the cropped
  region always lands correctly in the final frame. A live preview shows
  the crop against the full source frame, with a scrubber to check it at
  different points in the video.
- **Trim** - pick an in/out range against a scrubbable preview.
- **Alpha channel handling** - preserve alpha (restricted to alpha-capable
  codecs like ProRes 4444 or VP9) or flatten onto a chosen matte color.
- **Settings profiles** - save/load/update named presets of all the above.
- **Command preview and size estimate** before you commit to a conversion.
- Detects whether ffmpeg/ffprobe are installed and can help install them
  (via the system package manager on Linux, Homebrew on macOS, or a link
  to the official Windows build) if not.

## Installing ffmpeg

VidKonverter doesn't bundle ffmpeg - it needs `ffmpeg` and `ffprobe`
installed on your computer. Both come in the same package. The steps
below are for a first-time install; if you already have ffmpeg, you can
skip this section.

### macOS

The easiest route is [Homebrew](https://brew.sh), a package manager for
macOS.

1. **Open Terminal** (press Cmd+Space, type "Terminal", press Enter).
2. **Install Homebrew** by pasting the command from the front page of
   [brew.sh](https://brew.sh) and pressing Enter. It asks for your Mac
   password (nothing shows as you type - that's normal) and may offer to
   install Apple's Command Line Tools first; say yes. This can take a
   few minutes.
3. **Add Homebrew to your PATH.** When the installer finishes it prints a
   "Next steps" section - don't skip it. On an Apple Silicon Mac (M1 or
   later) it looks like this; run both lines:

   ```bash
   echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
   eval "$(/opt/homebrew/bin/brew shellenv)"
   ```

   On an Intel Mac the path is `/usr/local/bin/brew` instead of
   `/opt/homebrew/bin/brew`. If you're unsure, copy the exact lines the
   installer printed. Without this step, Terminal won't recognise the
   `brew` command.
4. **Install ffmpeg:**

   ```bash
   brew install ffmpeg
   ```

   This downloads a fair amount of software and can take several minutes.
5. **Check it worked** - this should print a version number:

   ```bash
   ffmpeg -version
   ```

Then (re)start VidKonverter. It looks for ffmpeg in Homebrew's standard
locations itself, so it finds it even when launched by double-clicking
rather than from Terminal.

### Windows

The simplest route is `winget`, which is built into Windows 10 (version
1809 or later) and Windows 11.

1. **Open a terminal** - right-click the Start button and choose
   "Terminal" or "Windows PowerShell".
2. **Install ffmpeg:**

   ```powershell
   winget install -e --id Gyan.FFmpeg
   ```

   Accept the source agreement if asked.
3. **Close and reopen the terminal, and restart VidKonverter.** Windows
   only gives programs the updated PATH when they start, so a
   VidKonverter window that was already open won't see the new install.
4. **Check it worked** in the new terminal - this should print a version
   number:

   ```powershell
   ffmpeg -version
   ```

**If `winget` isn't available**, install manually:

1. Download a "release essentials" build from
   [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) and
   extract the zip somewhere permanent, e.g. `C:\ffmpeg` (so that
   `C:\ffmpeg\bin\ffmpeg.exe` exists).
2. Add its `bin` folder to your PATH: press the Windows key, search for
   "Edit the system environment variables", click **Environment
   Variables...**, select `Path` under "User variables", click **Edit...**
   then **New**, and enter `C:\ffmpeg\bin`. Click OK on each window.
3. Open a new terminal, run `ffmpeg -version` to check, and restart
   VidKonverter.

### Linux

Install `ffmpeg` with your distribution's package manager, e.g.
`sudo apt install ffmpeg` (Debian/Ubuntu), `sudo dnf install ffmpeg`
(Fedora - may need the RPM Fusion repository enabled), or
`sudo pacman -S ffmpeg` (Arch). The `.deb` and `.rpm` packages list
ffmpeg as a recommended dependency.

## macOS: opening the app for the first time

The macOS build isn't signed with a paid Apple Developer ID or notarized
by Apple (that costs $99 a year), so the first time you open it macOS
will say it can't verify the app is free of malware. The app is open
source and you can read exactly what it does in this repository - to
open it anyway, use either of these once:

- **Right-click (or Control-click) `VidKonverter.app` and choose Open**,
  then click **Open** in the dialog. A plain double-click won't offer
  that button the first time, but this route does.
- Or double-click it, dismiss the warning, then go to **System Settings →
  Privacy & Security**, scroll down to the message about VidKonverter,
  and click **Open Anyway**.

macOS remembers your choice, so later launches work normally. If you
downloaded the zip and the app is still blocked, you can also clear the
download quarantine flag in Terminal:

```bash
xattr -dr com.apple.quarantine /path/to/VidKonverter.app
```

## Requirements

- Python 3.10+
- [ffmpeg and ffprobe](https://ffmpeg.org/) - see
  [Installing ffmpeg](#installing-ffmpeg) above. The app will also offer
  to help install them on first run if they're missing (Help → FFmpeg
  Setup…).

## Running from source

```bash
pip install -r requirements.txt
python main.py
```

## Building a standalone executable

Packaging uses [PyInstaller](https://pyinstaller.org/) and must be run
separately on each target OS - it does not cross-compile.

```bash
pip install -r requirements.txt -r packaging/requirements-build.txt
python packaging/build.py
```

Output lands in `dist/`:
- Linux: `dist/VidKonverter`
- macOS: `dist/VidKonverter.app`
- Windows: `dist/VidKonverter.exe`

ffmpeg/ffprobe are **not** bundled into the executable - this keeps the
build small and avoids shipping stale codec binaries. Install them
separately, or let the app help you on first run.

> **Platform support:** Linux and macOS builds are published with each
> release and have been tested on real hardware. The Windows build is
> published too but has had no testing yet - expect rough edges.
> Contributions and forks that help any platform along are very welcome.

### Linux: installing a desktop launcher

After building, register the binary as a proper application (so it shows
up in your application menu instead of needing to be run from a
terminal):

```bash
packaging/install_linux.sh
```

This installs a `.desktop` entry and icon under `~/.local/share/`. Pass a
different binary path as an argument if you've moved `dist/VidKonverter`
elsewhere.

### Linux: building a .deb or .rpm

Build the PyInstaller binary first (above), then:

```bash
python packaging/build_deb.py   # requires dpkg-deb - dist/vidkonverter_<version>_amd64.deb
python packaging/build_rpm.py   # requires rpmbuild  - dist/vidkonverter-<version>-1.<dist>.x86_64.rpm
```

Both packages install the binary, a desktop entry, an icon, and the
GPLv3 license text (`/usr/share/licenses/vidkonverter/` on the RPM,
Debian's copyright format under `/usr/share/doc/vidkonverter/` on the
deb).

## Project layout

```
main.py                    Entry point
videoconverter/
  main_window/              Main window, split by concern (see its
                            __init__.py for the per-file map)
  command_builder.py         Settings -> ffmpeg command translation
  probe.py                   ffprobe wrapper / media info
  converter.py                Runs ffmpeg and reports progress
  crop_dialog.py, crop_overlay.py, trim_panel.py  Crop/trim UI
  profiles.py                 Settings profile persistence
  ffmpeg_installer.py         Detects/installs ffmpeg per platform
packaging/                  PyInstaller spec, .deb/.rpm build scripts
```

## License

GPLv3 - see [LICENSE](LICENSE). VidKonverter invokes ffmpeg as a separate
system process at runtime; it is not bundled or modified.
