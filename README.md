<p align="center"><img src="assets/branding/dizytv-logo.png" alt="DizyTV logo" width="220" /></p>
<h1 align="center">DizyTV</h1>
<p align="center"><strong>Live TV, a full programme guide and local recordings — in your own app.</strong></p>
<p align="center">
  <img alt="Native alpha" src="https://img.shields.io/badge/status-native%20alpha-f59e0b?style=for-the-badge" />
  <a href="#downloads"><img alt="Windows EXE" src="https://img.shields.io/badge/Windows-EXE-0078d4?style=for-the-badge" /></a>
  <a href="#downloads"><img alt="Android APK" src="https://img.shields.io/badge/Android-APK-3ddc84?style=for-the-badge&amp;logo=android&amp;logoColor=white" /></a>
  <a href="#downloads"><img alt="macOS PKG" src="https://img.shields.io/badge/macOS-PKG-374151?style=for-the-badge&amp;logo=apple&amp;logoColor=white" /></a>
  <a href="#downloads"><img alt="Linux DEB" src="https://img.shields.io/badge/Linux-DEB-237804?style=for-the-badge&amp;logo=linux&amp;logoColor=white" /></a>
</p>

<p align="center">
  <a href="#features"><img alt="Explore features" src="https://img.shields.io/badge/Explore-Features-699769?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/actions/workflows/native-builds.yml"><img alt="View native builds" src="https://img.shields.io/badge/View-Native%20Builds-5865f2?style=for-the-badge" /></a>
  <a href="docs/USER-GUIDE.md"><img alt="Full user guide" src="https://img.shields.io/badge/Read-User%20Guide-699769?style=for-the-badge" /></a>
  <a href="docs/DISTRIBUTION.md"><img alt="Installation guide" src="https://img.shields.io/badge/Read-Install%20Guide-699769?style=for-the-badge" /></a>
  <a href="ROADMAP.md"><img alt="Read roadmap" src="https://img.shields.io/badge/Read-Roadmap-374151?style=for-the-badge" /></a>
</p>

<p align="center">Windows · Android · macOS · Linux desktop (experimental Ubuntu/Debian x86-64 .deb)</p>

DizyTV brings M3U/IPTV playlists, XMLTV listings, Ace Stream and ordinary HTTP/HLS channels into a native TV interface. Browse by country, genre and category, find a programme with global search, save favourites and record broadcasts to your own storage.

**Current public build:** [v0.1.16-alpha](https://github.com/DizygoticCode/DizyTV/releases/tag/v0.1.16-alpha). This is a **development release**, not a verified replacement for a licensed TV service. Channels are imported from third parties, may be unavailable or geographically restricted, and may require an external player engine.

**New in 0.1.16-alpha:** native Linux `.deb` support, improved playback diagnostics, safer HLS/Ace handling, progressive channel health scanning, duplicate management and faster large-catalogue browsing. All five platform release CI jobs passed; physical-device playback and real large-channel catalogues still need testing.

## Downloads

Direct installer links (no ZIP extraction required):

| Platform | Download | Requirement |
| --- | --- | --- |
| **Windows** | [Windows x64 installer (.exe)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/DizyTV-Setup-0.1.16-alpha-windows-x64.exe) | Windows x64; VLC 3 x64 for playback |
| **Android** | [Universal APK (.apk)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/DizyTV-0.1.16-alpha-android-universal-debug.apk) | Android 8+ |
| **Mac Apple Silicon** | [arm64 installer (.pkg)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/DizyTV-0.1.16-alpha-macos-arm64.pkg) | macOS 13+; VLC 3 |
| **Mac Intel** | [x86-64 installer (.pkg)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/DizyTV-0.1.16-alpha-macos-x86_64.pkg) | macOS 13+; VLC 3 |
| **Linux** | [Ubuntu/Debian x64 installer (.deb)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/DizyTV-0.1.16-alpha-linux-amd64.deb) | Ubuntu 24.04 x64 CI-verified; other Debian-family distros require testing; system libVLC 3 |

<p align="center">
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/DizyTV-Setup-0.1.16-alpha-windows-x64.exe"><img alt="Download Windows EXE directly" src="https://img.shields.io/badge/Download-Windows%20EXE-0078d4?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/DizyTV-0.1.16-alpha-android-universal-debug.apk"><img alt="Download Android APK directly" src="https://img.shields.io/badge/Download-Android%20APK-3ddc84?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/DizyTV-0.1.16-alpha-macos-arm64.pkg"><img alt="Download Mac Apple Silicon PKG directly" src="https://img.shields.io/badge/Download-Mac%20Apple%20Silicon%20PKG-374151?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/DizyTV-0.1.16-alpha-macos-x86_64.pkg"><img alt="Download Mac Intel PKG directly" src="https://img.shields.io/badge/Download-Mac%20Intel%20PKG-374151?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/DizyTV-0.1.16-alpha-linux-amd64.deb"><img alt="Download Ubuntu Linux DEB directly" src="https://img.shields.io/badge/Download-Linux%20DEB-237804?style=for-the-badge&amp;logo=linux&amp;logoColor=white" /></a>
</p>

[All releases](https://github.com/DizygoticCode/DizyTV/releases) · [SHA-256 checksums](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.16-alpha/SHA256SUMS.txt) · [Installation and security notes](docs/DISTRIBUTION.md)

> [!CAUTION]
> These alpha packages are not yet publicly code-signed: Windows EXE is unsigned, Mac PKGs are unnotarized and the Android APK is debug-signed. **Do not disable browser or device security protections** to get around a security warning. Save a backup before changing test versions; Android debug signing keys can prevent in-place upgrades.

## Quick start — how to use DizyTV

1. **Install DizyTV** using the download for your device. For Ace Stream, separately install and run the appropriate engine. Direct HTTP/HLS channels do not need an Ace engine.
2. **Add channels:** Open **Settings → Channel playlists**. Use **Add built-in free playlists** to add presets, or paste M3U links one per line; save and choose **Refresh channels**.
3. **Add a programme guide:** Open **Settings → XMLTV sources**, save the guide URLs, then choose **Refresh guide**. Use **Map EPG** if a channel does not match its listings.
4. **Find something to watch:** Choose a channel from the list, filter by **Country / Category / Playlist**, or use **Ctrl+K** to search all channel and programme names. The **24/7 Shows & Loops** category is available when matching channels are imported.
5. **Watch:** Double-click a channel or press **Play**. Use **CC Subtitles**, **Cinema**, **Screen**, **Pop out** and **LIVE** as needed. Pause and rewind depend on source seekability or optional compatible timeshift.
6. **Save favourites or record:** Select **★ Add / remove favourite**. For recordings, first select a storage folder under Settings, then click **Record** or schedule from the guide.
7. **Maintain your lists:** Use **Tools → Check channel health** for a manual HTTP reachability check, and **Show disabled → Hide / restore selected** for reversible cleanup. Save your configuration with **Tools → Save local backup**.

**[Read the full step-by-step user guide →](docs/USER-GUIDE.md)**

## Features

| Watch | Organise | Record & manage |
| --- | --- | --- |
| Embedded libVLC video and subtitle tracks | M3U playlists and XMLTV programme guide | Record now or from EPG |
| Ace Stream via separately installed engine | Country, category, genre and playlist filters | Device-local recording storage |
| Cinema, fullscreen and resizable pop-out | Global channel/programme search (Ctrl+K) | Local backup and restore |
| Optional supported live timeshift | Favourites, manual channel hiding, timezone-aware guide | Basic channel reachability checks |

DizyTV **does not bundle paid IPTV subscriptions, provide DRM circumvention or guarantee any individual stream**. It can list a channel for which the broadcaster has no playable video on your network. Public links are not a substitute for authorised access.

## New in 0.1.16-alpha

The [0.1.16-alpha development work (PR #23)](https://github.com/DizygoticCode/DizyTV/pull/23) delivered these updates to the desktop app:

- **Linux x86-64:** native Ubuntu/Debian `.deb` packaging with PySide6 and installed VLC 3; optional separately installed Ace Stream Engine or an already running remote engine. Linux can use an installed FFmpeg and an optional Vosk language model for captions. [Linux setup guide](docs/LINUX.md).
- **Playback diagnostics and handling:** adjustable 1–12-second HTTP/HLS network buffer (4 seconds by default); passive warning for stalled video frames while audio continues; safer cancellation of delayed Ace playback requests; direct HTTP-form Ace stream cache guard.
- **Large catalogues:** more efficient category and search updates; lazy country-tree population. Synthetic 30,000-channel benchmarks improved substantially, but some large views may still block the UI briefly.
- **Channel maintenance:** opt-in progressive HTTP/HLS health checks in batches of 40, cancellation on close or app shutdown, stop after batch and pause on HTTP 429; saved check history; conservative duplicate-channel grouping with reversible hide/restore.
- **Tools → System usage:** local-only CPU, memory, disk, catalogue-size and available VLC decoder statistics.
- **UK FAST sources:** Settings action to add public Plex, Samsung TV Plus and Pluto TV playlists with matching XMLTV guide presets, without overwriting existing sources.

**Testing status:** 223 local Python/PySide6 tests passed with no failures or skips. Android Kotlin/JVM tests and Linux X11 synthetic HLS video checks passed. The [official five-platform release workflow](https://github.com/DizygoticCode/DizyTV/actions/runs/38817548197) successfully built and published all five installers with checksum files (macOS Apple Silicon CI retains five expected skips). HTTP reachability does not prove decoded video; real Windows catalogue performance, live third-party channels, Ace sessions and physical-device playback still need manual testing.

## Development and documents

Desktop uses **Python 3.12 / PySide6 / libVLC**; Android uses **Kotlin / libVLC**. Desktop source setup:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m dizytv
```

| Documentation | What it covers |
| --- | --- |
| [User guide](docs/USER-GUIDE.md) | Playlists, EPG, TV controls, search, recordings and troubleshooting |
| [Release notes](docs/RELEASE-NOTES.md) | Earlier alpha changes and longer technical descriptions |
| [Linux installation](docs/LINUX.md) | Native Ubuntu/Debian package, separately installed Ace Engine, libVLC and optional FFmpeg/Vosk |
| [Distribution](docs/DISTRIBUTION.md) | Native packages, signing limitations, upgrades |
| [Build verification](docs/BUILD-VERIFICATION.md) | CI tests and what still needs device testing |
| [Roadmap](ROADMAP.md) · [Licences](THIRD-PARTY-NOTICES.md) | Planned work and third-party obligations |

---

<p align="center"><strong>Part of the Dizy family</strong><br />
  <a href="https://github.com/DizygoticCode/DizyTrades">DizyTrades</a> ·
  <a href="https://github.com/DizygoticCode/dizychat-server">DizyChat</a> ·
  <strong>DizyTV</strong>
</p>
