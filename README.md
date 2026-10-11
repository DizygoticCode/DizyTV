<p align="center"><img src="assets/branding/dizytv-logo.png" alt="DizyTV retro television logo" width="280" /></p>
<h1 align="center">DizyTV</h1>
<p align="center"><strong>Live channels. A proper TV guide. Recordings on your own storage.</strong></p>
<p align="center">Native apps for Windows, Android and MacBook — favourites, local backups and your timezone.</p>

<p align="center">
  <img alt="Native alpha" src="https://img.shields.io/badge/status-native%20alpha-f59e0b?style=for-the-badge" />
  <a href="#downloads"><img alt="Windows EXE" src="https://img.shields.io/badge/Windows-EXE-0078d4?style=for-the-badge" /></a>
  <a href="#downloads"><img alt="Android APK" src="https://img.shields.io/badge/Android-APK-3ddc84?style=for-the-badge&amp;logo=android&amp;logoColor=white" /></a>
  <a href="#downloads"><img alt="macOS PKG" src="https://img.shields.io/badge/macOS-PKG-374151?style=for-the-badge&amp;logo=apple&amp;logoColor=white" /></a>
</p>

<p align="center">
  <a href="#features"><img alt="Explore features" src="https://img.shields.io/badge/Explore-Features-699769?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/actions/workflows/native-builds.yml"><img alt="View native builds" src="https://img.shields.io/badge/View-Native%20Builds-5865f2?style=for-the-badge" /></a>
  <a href="docs/DISTRIBUTION.md"><img alt="Installation guide" src="https://img.shields.io/badge/Read-Install%20Guide-699769?style=for-the-badge" /></a>
  <a href="ROADMAP.md"><img alt="Read roadmap" src="https://img.shields.io/badge/Read-Roadmap-374151?style=for-the-badge" /></a>
</p>

> [!IMPORTANT]
> **0.1.0 alpha is a development build.** The features below are implemented. Package checks run on native Windows/Mac hosts and Android CI; live Ace Stream playback, physical-device storage, unattended recording and installer upgrades still need device testing. Desktop packages are unsigned for public distribution; Android uses a debug key. See [verification and known limits](docs/BUILD-VERIFICATION.md).

## Features

| Feature | Included in the native alpha |
| --- | --- |
| 📺 **Live TV** | Embedded libVLC player, channel search and now/next information |
| 🔎 **Imported channels** | Automatic first import from the search-ace.stream playlist, refresh and last-good cache |
| 🗓️ **XMLTV guide** | Programme grid, multiple XMLTV URLs and editable channel mappings |
| 🗂️ **Country, genre & type** | Filter channels and EPG by country, genre, TV/radio and Ace Stream/HTTP; save category edits |
| ⭐ **Favourites** | Persistent favourites and a favourites-only channel browser and guide |
| ⏺️ **Record now** | Choose 30/60/120 minutes, the current programme's end, or manual stop with a 24-hour cap |
| ⏰ **EPG recording** | Programme timers with start/end padding and overlap checks |
| 💾 **Your storage** | Selected Windows/Mac folder or Android folder chosen through the native picker |
| 🎞️ **Recordings** | Play/delete files; completed, partial, failed and missed status; preserve interrupted segments |
| 📦 **Local backup / restore** | Portable JSON for listings, favourites, category edits, mappings, preferences and timers |
| 🌍 **Your timezone** | Automatic device timezone, manual IANA selection, daylight-saving display and EPG correction |
| 🔄 **Saved timers** | UTC times survive restart; restored timers stay paused until storage is selected and they are rearmed |

One recording runs at a time per device. The recorder saves the available live MPEG-TS stream without re-encoding. Instant recording starts when requested; earlier footage is not recovered. Accepted UTC timers do not move when the display timezone or EPG correction changes.

## Downloads

| Platform | Build target | Installer inside the artifact |
| --- | --- | --- |
| **Windows** | x64 | `DizyTV-Setup-0.1.0-alpha-windows-x64.exe` |
| **Android** | Universal; API 26 / Android 8.0+ | `DizyTV-0.1.0-alpha-android-universal-debug.apk` |
| **MacBook / macOS** | Apple Silicon; macOS 13+ package target | `DizyTV-0.1.0-alpha-macos-arm64.pkg` |
| **MacBook / macOS** | Intel; macOS 13+ package target | `DizyTV-0.1.0-alpha-macos-x86_64.pkg` |

<p align="center">
  <a href="https://github.com/DizygoticCode/DizyTV/actions/runs/38148508455/artifacts/11706355501"><img alt="Download Windows EXE" src="https://img.shields.io/badge/Download-Windows%20EXE-0078d4?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/actions/runs/38148508455/artifacts/11706585013"><img alt="Download Android APK" src="https://img.shields.io/badge/Download-Android%20APK-3ddc84?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/actions/runs/38148508455/artifacts/11705895526"><img alt="Download Mac Apple Silicon PKG" src="https://img.shields.io/badge/Download-Mac%20Apple%20Silicon%20PKG-374151?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/actions/runs/38148508455/artifacts/11705474676"><img alt="Download Mac Intel PKG" src="https://img.shields.io/badge/Download-Mac%20Intel%20PKG-374151?style=for-the-badge" /></a>
</p>

Verified [native build run](https://github.com/DizygoticCode/DizyTV/actions/runs/38148508455) · [Build checks](docs/BUILD-VERIFICATION.md)

Open the verified run, choose the platform artifact and extract the ZIP. SHA-256 checksums are included. Actions artifacts require GitHub sign-in and repository access and expire after 30 days; durable public release downloads are a later milestone. Minimum targets reflect build configuration, rather than completed hardware compatibility testing.

Windows has an unsigned installer. The Mac app has an ad-hoc signature; its PKG is not Developer ID signed or notarized. Android uses a CI debug key, with no consistent upgrade signing yet. Operating systems may show trust warnings. Back up your setup before changing development builds.

Public visibility has been requested. The owner must change visibility and About text because the connected file tools cannot edit repository settings. See [repository setup](docs/REPOSITORY-SETUP.md) for the exact description and steps.

## Getting started

1. Install DizyTV for your platform.
2. **Windows:** install VLC 3 x64 and separately install/open Ace Stream. **Android:** separately install/open the engine; libVLC is included in the APK.
3. **Mac:** install VLC 3 for the app's CPU architecture and configure a reachable Windows/Linux Ace Stream engine in Settings. The PKG includes the native Mac client and does not include a Mac engine.
4. Let channels import. Add XMLTV URLs in **Settings**, press **Refresh guide**, and use **Map EPG** for unmatched channels.
5. Choose your recording folder and leave timezone on **auto**, or choose an IANA zone. Android also needs exact-alarm access when scheduling and permission for recording notifications.
6. Use country/genre/type filters and favourites. **Edit categories** fills gaps in source metadata; **Use source categories** clears an edit.

## Channels and the guide

Import uses the [documented playlist export](https://search-ace.stream/doc). Stable stream IDs preserve favourites, manual mappings and category edits during refreshes. The feed is imported on the device; no dataset is bundled.

Country filters use explicit M3U metadata, recognised country groups and bracketed country tags such as `[RU]` and `[UK]`. Genres use source metadata and mapped XMLTV programme categories. TV/radio follows source metadata or saved edits; transport follows the stream. Missing metadata appears as **Unspecified**. Quality tags such as `[HD]` are not countries.

XMLTV URLs are configurable because one global feed may not cover every channel or regional variant. Times are parsed into UTC and displayed locally; channels can play without a guide match. Listings do not establish stream availability or distribution rights.

## Recording and backups

| Platform | Scheduling behaviour in this alpha |
| --- | --- |
| **Windows / Mac** | Detached recorder continues after the window closes while the computer is awake. Open DizyTV after reboot to restart it. Wake-from-sleep is not implemented. |
| **Android** | Exact alarms, a visible foreground service and reboot recovery are implemented. Force-stop, engine availability, storage permissions and vendor battery restrictions affect execution and need device testing. |

The recorder checks write access and free space where the provider reports it, rejects overlapping timers and preserves partial output. Older recordings are not automatically deleted.

**Backup** saves your setup to a local JSON file. **Restore** previews replacement, resets storage permissions and pauses future timers. Video files and EPG cache are excluded. Choose storage and rearm timers after restoring. Backups can move preferences between platforms; see [backup format](docs/BACKUP-FORMAT.md).

## Development

Desktop: Python 3.12, PySide6 6.11.2, python-vlc 3.0.21203. Android: Kotlin 2.1.20/JDK 17, AGP 8.11.1, Gradle 8.13, compile SDK 36 / target 35, libVLC 3.7.5.

```bash
python -m venv .venv
# Activate the environment, then:
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m dizytv

# Android, with JDK 17, Android SDK and Gradle 8.13:
gradle -p android testDebugUnitTest lintDebug assembleDebug
```

The [native workflow](.github/workflows/native-builds.yml) packages Windows and separate Apple Silicon/Intel Mac builds, checks packaged desktop launch and Mac payload/signature, and builds/verifies the Android APK. Installer scripts, pinned dependencies and [third-party notices](THIRD-PARTY-NOTICES.md) are included.

DizyTV currently imports feeds and records locally. A DizyServer metadata service and server recorder are future work. This project does not deploy or change DizyTrades, DizyChat or the existing server.

## Project documents

- [Build verification and device checks](docs/BUILD-VERIFICATION.md)
- [Installers and distribution](docs/DISTRIBUTION.md)
- [Roadmap](ROADMAP.md)
- [Product design](docs/superpowers/specs/2026-10-11-dizytv-design.md)
- [Implementation plan](docs/superpowers/plans/2026-10-11-native-apps.md)
- [Logo and branding](docs/BRANDING.md)

---

<p align="center"><strong>Part of the Dizy family</strong><br />
  <a href="https://github.com/DizygoticCode/DizyTrades">DizyTrades</a> ·
  <a href="https://github.com/DizygoticCode/dizychat-server">DizyChat</a> ·
  <strong>DizyTV</strong>
</p>
