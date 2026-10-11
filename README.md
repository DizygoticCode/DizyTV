<p align="center">
  <img src="assets/branding/dizytv-logo.png" alt="DizyTV retro television logo" width="280" />
</p>

<h1 align="center">DizyTV</h1>

<p align="center">
  <strong>Live channels. A proper TV guide. Recordings on your own storage.</strong>
</p>

<p align="center">
  Native television apps for Windows, Android and macOS — alpha implementation in progress.
</p>

<p align="center">
  <img alt="Status: alpha development" src="https://img.shields.io/badge/status-alpha%20development-f59e0b?style=for-the-badge" />
  <a href="#platforms-and-installers"><img alt="Windows EXE planned" src="https://img.shields.io/badge/Windows-EXE%20planned-0078d4?style=for-the-badge" /></a>
  <a href="#platforms-and-installers"><img alt="Android APK planned" src="https://img.shields.io/badge/Android-APK%20planned-3ddc84?style=for-the-badge&amp;logo=android&amp;logoColor=white" /></a>
  <a href="#platforms-and-installers"><img alt="macOS PKG planned" src="https://img.shields.io/badge/macOS-PKG%20planned-374151?style=for-the-badge&amp;logo=apple&amp;logoColor=white" /></a>
</p>

<p align="center">
  <a href="#planned-features"><img alt="Explore planned features" src="https://img.shields.io/badge/Explore-Features-699769?style=for-the-badge" /></a>
  <a href="ROADMAP.md"><img alt="Read the roadmap" src="https://img.shields.io/badge/Read-Roadmap-5865f2?style=for-the-badge" /></a>
  <a href="docs/superpowers/specs/2026-10-11-dizytv-design.md"><img alt="Read the design" src="https://img.shields.io/badge/Read-Design-374151?style=for-the-badge" /></a>
  <a href="docs/DISTRIBUTION.md"><img alt="View the installer plan" src="https://img.shields.io/badge/View-Installer%20Plan-699769?style=for-the-badge" /></a>
</p>

> [!IMPORTANT]
> **Current stage: native alpha development.** The repository now includes the Python catalogue/XMLTV core, native Qt desktop client, detached local recorder, portable backup format and automated tests. Android implementation and platform packaging are underway. No signed public release or deployed backend is claimed. Live engine playback, storage permissions and unattended recording still require real-device validation.

## Planned features

| Feature | DizyTV plan |
| --- | --- |
| 📺 **Live television** | A DizyTV interface with embedded video playback and clear stream/buffering status |
| 🔎 **Channel browser** | Automatically refreshed catalogue import, search, categories and favourites |
| 🗓️ **TV guide** | XMLTV now/next listings and a programme grid, multiple guide sources and editable channel mappings |
| ⏺️ **Record now** | Start recording immediately; stop manually, after a chosen duration or at the current programme's scheduled end |
| ⏰ **Scheduled recording** | Select an EPG programme, save a timer and adjust the start/end padding |
| 💾 **Your storage** | Save directly to a selected Windows/Mac folder or drive, or an accessible Android storage folder |
| 🎞️ **Recording library** | Play and delete recordings; see file sizes, storage information and completed/partial/failed status |
| 🔄 **Persistent timers** | Keep jobs across restarts, check storage space and report missed or interrupted recordings |
| ⭐ **Favourites** | A persistent favourites list and favourites-only channel browser, preserved during catalogue refresh |
| 📦 **Local backup / restore** | Save settings, channels, favourites, guide mappings and timers as a local JSON file; reselect storage and rearm restored timers |
| 🌍 **Your timezone** | Automatic device detection, manual IANA timezone selection and an EPG offset; UTC timers stay fixed through daylight-saving changes |

The first release targets **one recording at a time per device**. Same-channel viewing may share a session where supported; viewing another channel while recording needs engine validation. Instant recording starts from the available live stream and does not provide retrospective recording.

## Platforms and installers

| Platform | Planned download | Playback and recording approach |
| --- | --- | --- |
| **Windows** | `DizyTV-Setup-<version>-<arch>.exe` | Native application, installed Ace Stream engine, embedded playback and selected-folder recordings |
| **Android** | `DizyTV-<version>-<abi>.apk` | Native application, supported engine startup, Android folder permissions and a background recording service |
| **macOS / MacBook** | `DizyTV-<version>-<arch>.pkg` containing `DizyTV.app` | Native Mac application, an explicitly configured compatible engine connection and recordings saved locally on the Mac |

**Downloads are not available yet.** The badges above link to this platform plan, not to installers. Supported OS versions and CPU architectures will be listed after the dependency builds and device tests pass; Apple Silicon and Intel Macs are validated separately.

Public releases will use a signed Windows application/installer, a release-signed Android APK with a retained update key, and a Developer ID-signed, notarized Mac app/package. Public visibility has been requested; the owner must change the visibility setting because this connector cannot edit repository settings. See [repository setup](docs/REPOSITORY-SETUP.md). Full details are in the [installer and distribution plan](docs/DISTRIBUTION.md).

### Mac playback dependency

The official [Ace Stream downloads](https://docs.acestream.media/products/) list Windows, Android and Linux, with no native macOS engine listed. The initial Mac design therefore connects to a reachable Windows/Linux engine while keeping the player and recording storage on the Mac. A self-contained Mac engine or local helper needs a separate feasibility check before it can be included in the package.

## Channels and the programme guide

Channel import starts with the playlist export documented by [search-ace.stream](https://search-ace.stream/doc), rather than HTML scraping. The catalogue service will cache the last successful import and preserve favourites and manual EPG mappings during refreshes.

EPG data comes from configured **XMLTV sources**. Multiple feeds and manual mapping are part of the design because one global feed is not guaranteed to cover every imported channel or regional variant. Programme times are stored in UTC and displayed in the selected local timezone. A channel without a guide match remains playable.

A listing does not guarantee a working stream or permission to redistribute it. This repository does not bundle a channel/guide dataset or third-party engine binaries.

## Recording on your device

The recorder will save the original stream without re-encoding where supported, starting with MPEG-TS output. Recordings use the selected destination, with write-access checks, free-space monitoring where available and clear partial/failed outcomes. Existing recordings are not automatically deleted.

| Platform | Scheduled recording requirement |
| --- | --- |
| **Windows** | A validated background recorder; optional wake from sleep where hardware and system settings support it. A powered-off PC cannot record locally. |
| **Android** | Native timers, storage permission and an appropriate foreground service with a visible recording notification. Battery restrictions, reboot and force-stop behaviour need device testing. |
| **macOS** | A validated per-user background recorder. Initial scheduling requires an awake Mac and a signed-in user; wake from sleep is not yet promised. |

Closing the main UI must not silently cancel an active recording once the platform's background mechanism is implemented and validated. Overlapping timers and stream-session conflicts will be shown clearly.

**Optional DizyServer recording** is planned later for jobs that should run while the viewing device is off. Those recordings stay on the server until downloaded; local recording remains the default.

## How the parts fit together

| Component | Responsibility |
| --- | --- |
| **DizyTV clients** | Channel browsing, guide display, embedded playback, local storage, timers and recording library |
| **DizyServer metadata backend** | Refresh/cache the catalogue and XMLTV feeds; serve channel and programme data |
| **Ace Stream engine** | Receive the selected P2P stream and expose it through the supported session API |
| **libVLC** | Embedded playback; recording output must be validated on each platform |
| **Optional server recorder** | A later worker for jobs explicitly assigned to server storage |

The app owns the DizyTV interface. Windows and Android start with a separately installed engine; third-party bundling depends on the exact component licences and distribution permissions. The desktop alpha uses Python 3.12 and PySide6 6.11.2 for native Qt interfaces, with python-vlc bindings. Android uses Kotlin and native libVLC. See [the implementation plan](docs/superpowers/plans/2026-10-11-native-apps.md).

DizyTV is a separate project alongside DizyTrades and DizyChat. DizyServer is the intended metadata host; this repository setup does not deploy anything or change those existing services.

## Development roadmap

1. **Prove the integrations** — inspect the playlist, measure XMLTV coverage and test playback/local recording early on Windows, Android and Mac.
2. **Build Windows and the metadata backend** — add the channel browser, guide, favourites and playback controls.
3. **Deliver local recording** — add instant recording, EPG timers, storage selection, job persistence and failure handling.
4. **Deliver Android** — integrate native storage, notifications, timers and background recording.
5. **Deliver macOS** — build the native Mac client, engine setup and local recorder; package the `.app` inside a `.pkg`.
6. **Prepare public downloads** — validate installation/upgrades, configure signing, and publish versioned EXE/APK/PKG artifacts with checksums and notices.
7. **Add optional server recording** — introduce explicitly selected server jobs, authenticated downloads and quotas.

See [ROADMAP.md](ROADMAP.md) for the acceptance work at each stage. Simultaneous multi-channel recording, series recording, timeshift and catch-up/VOD are outside the first release.

## Development

```bash
python -m venv .venv
# Activate the virtual environment, then:
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m dizytv
```

Install VLC 3 for the app CPU architecture and install/configure the Ace Stream engine separately. Configure XMLTV URLs and choose a recording folder in Settings. No guide feed is preselected because coverage and regional channel mapping must be verified.

[Native build workflow](https://github.com/DizygoticCode/DizyTV/actions/workflows/native-builds.yml) · [Backup format](docs/BACKUP-FORMAT.md) · [Repository visibility/About setup](docs/REPOSITORY-SETUP.md)

## Project documents

- [Product design and acceptance criteria](docs/superpowers/specs/2026-10-11-dizytv-design.md)
- [Development roadmap](ROADMAP.md)
- [Installers and public distribution](docs/DISTRIBUTION.md)
- [Logo and branding](docs/BRANDING.md)

## Integration references

- [search-ace.stream playlist documentation](https://search-ace.stream/doc)
- [Ace Stream playback API](https://docs.acestream.media/developers/start-playback/)
- [Ace Stream Android integration](https://docs.acestream.media/developers/running-engine-android/)
- [Ace Stream engine platforms](https://docs.acestream.media/products/)
- [libVLC](https://www.videolan.org/vlc/libvlc.html)
- [XMLTV format](https://github.com/XMLTV/xmltv/blob/master/xmltv.dtd)

---

<p align="center">
  <strong>Part of the Dizy family</strong><br />
  <a href="https://github.com/DizygoticCode/DizyTrades">DizyTrades</a> ·
  <a href="https://github.com/DizygoticCode/dizychat-server">DizyChat</a> ·
  <strong>DizyTV</strong>
</p>
