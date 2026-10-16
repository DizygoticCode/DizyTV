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

**Current public build:** [v0.1.18-alpha](https://github.com/DizygoticCode/DizyTV/releases/tag/v0.1.18-alpha) — all five platform builds and release publication [passed in GitHub Actions](https://github.com/DizygoticCode/DizyTV/actions/runs/38954068009). This is an **experimental development release**, not a verified replacement for a licensed TV service. Third-party channels may be unavailable, region-restricted or unsuitable for embedded playback; build success does **not** establish real-device playback reliability.

**New in 0.1.18-alpha:** packaged VideoLAN VLC 3.0.24 on Windows and both Mac architectures, integrated desktop FFmpeg and bundled English offline Vosk model, original-source [Outpace](https://github.com/jamezrin/outpace) 0.2.0 for compatible public Ace swarms on macOS/Linux, an optional consent-based original Ace Stream setup flow on Windows, improved per-source playback diagnostics, safe alternate saved-source selection, and further worker/playback lifecycle tests. Android remains a distinct native Kotlin/libVLC app without desktop Vosk/FFmpeg parity. See [the release notes below](#new-in-0118-alpha) and [outstanding device tests](#known-limitations-and-unverified-behaviour).

## Downloads

Direct installer links (no ZIP extraction required):

| Platform | Download | Requirement |
| --- | --- | --- |
| **Windows** | [Windows x64 installer (.exe)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/DizyTV-Setup-0.1.18-alpha-windows-x64.exe) | Windows x64; VLC 3, FFmpeg and English Vosk bundled; original Ace engine optional |
| **Android** | [Universal APK (.apk)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/DizyTV-0.1.18-alpha-android-universal-debug.apk) | Android 8+; embedded libVLC, debug-signed |
| **Mac Apple Silicon** | [arm64 installer (.pkg)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/DizyTV-0.1.18-alpha-macos-arm64.pkg) | macOS 13+; private VLC 3, FFmpeg, English Vosk and Outpace bundled |
| **Mac Intel** | [x86-64 installer (.pkg)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/DizyTV-0.1.18-alpha-macos-x86_64.pkg) | macOS 13+; private VLC 3, FFmpeg, English Vosk and Outpace bundled |
| **Linux** | [Ubuntu/Debian x64 installer (.deb)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/DizyTV-0.1.18-alpha-linux-amd64.deb) | Ubuntu 24.04 x64 CI-tested; APT-managed VLC/FFmpeg, bundled English Vosk and Outpace |

<p align="center">
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/DizyTV-Setup-0.1.18-alpha-windows-x64.exe"><img alt="Download Windows EXE directly" src="https://img.shields.io/badge/Download-Windows%20EXE-0078d4?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/DizyTV-0.1.18-alpha-android-universal-debug.apk"><img alt="Download Android APK directly" src="https://img.shields.io/badge/Download-Android%20APK-3ddc84?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/DizyTV-0.1.18-alpha-macos-arm64.pkg"><img alt="Download Mac Apple Silicon PKG directly" src="https://img.shields.io/badge/Download-Mac%20Apple%20Silicon%20PKG-374151?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/DizyTV-0.1.18-alpha-macos-x86_64.pkg"><img alt="Download Mac Intel PKG directly" src="https://img.shields.io/badge/Download-Mac%20Intel%20PKG-374151?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/DizyTV-0.1.18-alpha-linux-amd64.deb"><img alt="Download Ubuntu Linux DEB directly" src="https://img.shields.io/badge/Download-Linux%20DEB-237804?style=for-the-badge&amp;logo=linux&amp;logoColor=white" /></a>
</p>

[All releases](https://github.com/DizygoticCode/DizyTV/releases) · [SHA-256 checksums](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.18-alpha/SHA256SUMS.txt) · [Installation and security notes](docs/DISTRIBUTION.md)

> [!CAUTION]
> These alpha packages are not yet publicly code-signed: Windows EXE is unsigned, Mac PKGs are unnotarized and the Android APK is debug-signed. **Do not disable browser or device security protections** to get around a security warning. Save a backup before changing test versions; Android debug signing keys can prevent in-place upgrades.

## Quick start — how to use DizyTV

1. **Install DizyTV** using the native installer for your device. Windows and macOS include private VLC 3; Linux uses distribution packages installed through APT; Android includes libVLC. Direct HTTP/HLS needs no Ace engine. On Mac/Linux, compatible *public* Ace streams can use bundled Outpace; on Windows, an original Ace Stream engine is optional (unchecked third-party setup task or a separately installed engine). Android Ace support remains dependent on an external compatible app/engine.
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
| Optional original Ace engine (Windows); bundled native Outpace (Mac/Linux, compatible public streams) | Country, category, genre and playlist filters | Device-local recording storage |
| Cinema, fullscreen and resizable pop-out | Global channel/programme search (Ctrl+K) | Local backup and restore |
| Optional supported live timeshift | Favourites, manual channel hiding, timezone-aware guide | Basic channel reachability checks |

DizyTV **does not bundle paid IPTV subscriptions, provide DRM circumvention or guarantee any individual stream**. It can list a channel for which the broadcaster has no playable video on your network. Public links are not a substitute for authorised access.

## New in 0.1.18-alpha

- **Windows and macOS VLC included:** native desktop installers ship private VideoLAN VLC **3.0.24** and plugins rather than requiring a system VLC installation. Native CI loads the packaged runtime and tests local synthetic audio/video decoding; actual broadcaster/device playback still needs acceptance testing.
- **Desktop captions out of the box:** Windows, both Mac architectures and Linux include English Vosk speech models; Windows/Mac bundle FFmpeg and Linux installs FFmpeg through APT. Transcription is opt-in, and additional supported language models are managed in DizyTV Settings.
- **Mac and Linux native Outpace:** native **Outpace 0.2.0** binaries compiled from pinned upstream source ship with their separate AGPL licence for supported public, unencrypted Ace-compatible swarms. No proprietary Ace engine is embedded. Private/local engine ownership checks protect existing engines and detached recordings; genuine swarm playback/recording needs testing.
- **Windows optional original Ace setup:** an **unchecked** installer task can attempt to retrieve the original publisher's installer through allowlisted HTTPS and check its Authenticode identity. It does not bundle or silently install Ace, accept its EULA, or enable P2P for ordinary channels. The actual publisher signer/redirect and installed-engine detection on all supported machines still need field verification; if that verification fails, the optional task fails safely.
- **Channel/source diagnostics:** distinguishes HTML landing pages from media, improves privacy-safe network failure classifications, shows imported source provenance and offers **Try another saved source** when eligible alternatives are present. This cannot make unavailable, encrypted or region-restricted ITV2/E4 streams playable.
- **Playback stability and upgrade safety:** expanded regression coverage for the live buffer, closed caption shutdown, Windows installer idle-recording-worker upgrades, queued recordings and Outpace attachment/shutdown races. Windows **Not Responding** reports are not yet proven fixed on real devices.
- **Release evidence:** [0.1.18 main-branch workflow](https://github.com/DizygoticCode/DizyTV/actions/runs/38954068009) passed Windows, Linux, Android, Intel Mac, Apple Silicon Mac and direct release publication. [PR #37](https://github.com/DizygoticCode/DizyTV/pull/37) is merged.

## Known limitations and unverified behaviour

This is an **alpha**, not a guarantee of playable imported IPTV or full cross-platform feature parity. Physical testing is still needed for clean Windows/macOS/Linux installations; sustained Windows playback without UI hangs; subtitle Off and Vosk lifecycle; ITV2/E4 source failures; legitimate Ace peer availability; Android device behaviour; and recording continuity. Track [Windows dependencies #27](https://github.com/DizygoticCode/DizyTV/issues/27), [cross-platform acceptance #28](https://github.com/DizygoticCode/DizyTV/issues/28), [ITV2/E4 diagnostics #30](https://github.com/DizygoticCode/DizyTV/issues/30), and [Windows playback freeze #32](https://github.com/DizygoticCode/DizyTV/issues/32). See the [0.1.18 device acceptance checklist](docs/0.1.18-CANDIDATE-ACCEPTANCE.md).

**Third-party redistribution and development signing:** The package includes third-party VLC, FFmpeg, Vosk and (on Mac/Linux) AGPL Outpace components. The exact source/relinking and redistribution compliance review remains outstanding; read [component licences and notices](THIRD-PARTY-NOTICES.md). Windows releases are unsigned; Mac packages are unnotarized; Android uses a CI debug key that may prevent upgrades. Do not disable device security features to install an unfamiliar binary.

## New in 0.1.17-alpha

- **Desktop subtitle synchronization:** independent Vosk text delay and optional rolling-timeshift video/audio holdback, adjustable from Settings and the CC menu. Delay is approximate, manually tuned, and requires a compatible stream.
- **Subtitles Off and recovery:** CC all-off stops Vosk, clears queued text and retries turning off embedded tracks after stream retunes; recognition cleanup/restart and stalled cached playback have additional safeguards.
- **Desktop stability:** asynchronous timeshift cleanup and nonblocking state snapshots reduce UI-blocking paths, with opt-in local Qt hang logging to investigate remaining Windows Not Responding reports.
- **UI sizing:** toolbar and sidebar heights are re-evaluated on launch and scale changes so text is not vertically cropped, with scrolling where space is limited.
- **Vosk model management:** desktop users can download optional language models, see progress, cancel downloads and remove verified app-managed models safely; custom external models are protected.
- **Platform boundaries:** the separate Android Kotlin app is repackaged at 0.1.17 but does not gain desktop PySide6 features. Actual video freezes, Vosk sync/drift, third-party streams and OS-specific operation require device testing.

## Earlier 0.1.16-alpha changes

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
