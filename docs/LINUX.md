# DizyTV native Linux alpha (Ubuntu/Debian x86-64)

## Native architecture

The Qt/PySide6 application and Python playback core use the same codebase as
Windows and macOS. Linux uses PyInstaller to produce an ELF executable packaged
inside an installable Debian package. System **libVLC 3** and its video codecs
are used for playback. Ace Stream is a **separate installed engine** which
returns an HTTP playback session to DizyTV's embedded libVLC player. DizyTV
does not download, bundle or repackage Ace Stream.

The first supported build target is Ubuntu 24.04 x86-64 (other Debian-family
distros need testing). Wayland-native video embedding may require XWayland/X11
and platform-specific checking; all Qt CI uses an offscreen smoke test, **not**
proof of a live video frame.

## Install the DizyTV .deb

On a desktop Ubuntu/Debian-compatible host with a supported libVLC package:
```sh
sudo apt install ./DizyTV-0.1.16-alpha-linux-amd64.deb
dizytv
```

The package uses the system's libvlc5, vlc-plugin-base, vlc-plugin-video-output,
libgl1, libxcb-cursor0 and libxkbcommon-x11-0. The application saves private
data in `~/.local/share/DizyTV` (or `$XDG_DATA_HOME/DizyTV`).
The package deliberately does not install/enable an Ace server.

## Install an Ace Stream engine independently

Refer to the [Ace Stream Linux documentation](https://wiki.acestream.media/Install_Ubuntu)
for publisher installation instructions and verify that those instructions
still apply to your distribution. Select your installed **start-engine**
executable under Settings → Installed Ace engine. DizyTV probes the configured
endpoint before attempting to start the wrapper. It can search:

- `start-engine` in PATH
- `/opt/acestream/start-engine`
- `/usr/local/bin/start-engine`
- `~/acestream/start-engine`
- `~/.local/opt/acestream/start-engine`

If an installed engine is running on the configured localhost URL
(default `http://127.0.0.1:6878`), DizyTV connects without spawning a second
engine. A remote custom address is **connect-only** and is never auto-started;
remote engines should be restricted to a trusted/private network. Startup uses
`start-engine --client-console` from its installed directory. The engine is
still responsible for finding peers and preparing content; an open port alone
does not establish successful playback.

## Subtitles, Vosk and FFmpeg

Broadcast subtitles use the embedded libVLC track. For offline transcription,
install the distro's `ffmpeg` package and download the small English Vosk
model through DizyTV Settings (or choose a previously extracted local model).
The Vosk Python runtime comes with the packaged DizyTV application, but the
speech model is not bundled on Linux. Transcription is opt-in and requires
a separate stream connection, CPU and RAM.

## Playback troubleshooting and resource use

Tools → System usage displays current process CPU and memory when supported,
plus system memory, programme/channel counts, and available VLC counters. This
excludes external Ace Stream/FFmpeg processes and detached recorder workers.
Settings → HTTP/HLS network buffer changes **direct HTTP/HLS** libVLC
network-caching only (1,000–12,000 ms). A longer buffer may reduce intermittent
stalling but adds live delay. It cannot recover an expired HLS segment, missing
keyframe, provider DRM or unavailable geographic service.

Tools → Check channel health offers an opt-in progressive scan with a stop
control and progress counter; it still limits probes to 40 channels per batch,
with four concurrent checks. HTTP reachability is not decoded video proof.
A provider 429 rate-limit response stops automatic continuation. Ace channels
need native engine/peer playback, and are not scanned as plain HTTP endpoints.

## Build or verify from source

Install Python 3.12 and system VLC/libVLC development runtime libraries, then:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python -m dizytv --smoke-test
python scripts/build_desktop.py
python scripts/package_linux.py
```

The Linux GitHub Actions job verifies Python tests, source and packaged
startup, and Debian package metadata. Native video output, Bluetooth/audio,
actual network throughput and third-party engine availability still require
testing on a real Linux desktop. If an existing app installation is being
updated, back up local settings and finish active recordings first.
