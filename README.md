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

## Requirements

- Python 3.10+
- [ffmpeg and ffprobe](https://ffmpeg.org/) on your `PATH` - the app will
  offer to help install these on first run if they're missing (Help →
  FFmpeg Setup…).

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

> **Platform support:** only the Linux build is currently tested and
> published as a release. Building for macOS/Windows works via the
> commands above, but neither has had real testing yet, and the macOS
> build in particular needed a couple of packaging-specific fixes before
> it would even launch - expect rough edges. Contributions and forks
> that get either platform properly working and tested are very
> welcome.

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
