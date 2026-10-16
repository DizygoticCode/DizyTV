# DizyTV native Linux alpha (Ubuntu/Debian x86-64)

## Native architecture

The Qt/PySide6 application and Python playback core use the same codebase as
Windows and macOS. Linux uses PyInstaller to produce an ELF executable packaged
inside an installable Debian package. System **libVLC 3** and its video codecs
are used for playback. Ace Stream is a **separate installed engine** which
returns an HTTP playback session to DizyTV's embedded libVLC player. DizyTV does not redistribute the proprietary engine. The forthcoming .deb bundles a native AGPL-licensed Outpace helper for compatible public Ace swarms, plus an opt-in original-vendor bootstrap.

The first supported build target is Ubuntu 24.04 x86-64 (other Debian-family
distros need testing). Wayland-native video embedding may require XWayland/X11
and platform-specific checking; all Qt CI uses an offscreen smoke test, **not**
proof of a live video frame.

## Install the DizyTV .deb

On a desktop Ubuntu/Debian-compatible host with a supported libVLC package:
```sh
sudo apt install ./DizyTV-0.1.17-alpha-linux-amd64.deb
dizytv
```

The package uses the system's libvlc5, vlc-plugin-base, vlc-plugin-video-output,
libgl1, libxcb-cursor0 and libxkbcommon-x11-0. The application saves private
data in `~/.local/share/DizyTV` (or `$XDG_DATA_HOME/DizyTV`).
The package does not install/enable an Ace server during APT installation. On the forthcoming build, optional setup is handled inside DizyTV, only with explicit consent.

## Original Ace Stream bootstrap in the forthcoming Linux installer

The **unreleased** Linux .deb includes an in-app bootstrap under **Tools → Set up Ace Stream engine**, not the proprietary software itself. Users can review the vendor licence and P2P warning, then explicitly approve the download. DizyTV fetches the original Ubuntu 22.04 tarball directly from the official publisher over HTTPS; checks a fixed recorded SHA-256; rejects off-publisher redirects, oversized/unsafe archives and partial files; and atomically installs only into the user's `~/.local/opt/acestream`. It never runs downloaded scripts during installation, does not silently add a service, and never overwrites an existing engine. Downloads are optional and cancellable.

**Compatibility limitation:** Ace Stream currently lists an Ubuntu 22.04 x86-64/Python 3.10 archive. DizyTV's normal Linux CI target is **Ubuntu 24.04**. The bootstrap refuses unsupported operating systems rather than executing an unverified 22.04 engine on them. **The Ubuntu 24.04 proprietary Ace Engine bootstrap remains unsupported; a separately licensed Outpace engine is bundled instead, with real peer playback still requiring device validation.** A trusted local or remote engine can still be configured, and ordinary HTTP/HLS playback needs no Ace software. The recorded SHA-256 is independently documented, not a cryptographic publisher signature.

These features are in development on `wip/complete-dependency-gates` and **not** in the published v0.1.17-alpha .deb.

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
the forthcoming .deb declares `ffmpeg` as an APT dependency and includes the original English Vosk model with the Vosk Python runtime. The published 0.1.17-alpha still requires the earlier separate setup. Transcription is opt-in and requires
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
