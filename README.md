# DizyTV

DizyTV is a planned Windows, Android and macOS television application with an imported channel catalogue, an XMLTV programme guide, integrated playback, and recordings saved to the storage location chosen on each device.

## Project status

This repository starts with the product scope, architecture and development roadmap. It does not yet contain a working application, installer, APK or deployed backend. Playlist import, playback, recording and EPG coverage still require implementation and device validation.

DizyTV is a separate project alongside DizyTrades and DizyChat. DizyServer is the intended host for its catalogue and guide backend. Creating this repository does not modify those applications or the live server.

## Agreed scope

- Native Windows, Android and macOS applications with a DizyTV interface and integrated video playback.
- Downloadable Windows `.exe` installer, Android `.apk` and Mac `.pkg` containing the DizyTV `.app`.
- Automatically refreshed channel import from the playlist documented by search-ace.stream.
- Channel search, categories and favourites.
- XMLTV guide with now/next listings and a programme grid.
- Multiple guide sources and editable channel-to-guide mappings.
- Instant recording, with manual stop, a duration, or the scheduled programme end.
- EPG scheduled recording with configurable start and end padding.
- Direct recording to a selected Windows or Mac folder/drive, or an accessible Android storage folder.
- A recordings screen with playback, deletion, storage information and clear recording status.
- Persistent recording timers, free-space checks and interruption reporting.

Optional recording on DizyServer is a later capability for jobs that should run while the viewing device is off. Local recording remains the default design.

## Components

| Component | Responsibility |
| --- | --- |
| DizyServer backend | Refresh and cache the channel catalogue and XMLTV feeds; serve channel and guide data |
| Windows application | Guide, playback, local storage selection, background recorder and Windows scheduling |
| Android application | Guide, playback, storage selection, native scheduling and background recording |
| macOS application | Native Mac client, guide, playback, local storage selection and Mac background recorder |
| Ace Stream engine | Receive the selected P2P stream and expose it to the application through its documented API |
| libVLC | Embedded playback; recording output is validated separately on each platform |

The application owns the user interface. Windows and Android integration starts with a separately installed Ace Stream engine. The official engine downloads currently list Windows, Android and Linux, with no macOS build listed. The initial Mac integration therefore targets an explicitly configured, reachable Windows/Linux engine while recording the resulting stream locally on the Mac. A self-contained Mac engine remains a feasibility question, not an included capability. Bundling or modifying third-party components requires checking the licences of the exact components and binaries used.

## Planned downloads

| Platform | Release artifact | Release requirement |
| --- | --- | --- |
| Windows | `DizyTV-Setup-<version>-<arch>.exe` | Install, playback, recording and upgrade validation; signed application and installer for the public release |
| Android | `DizyTV-<version>-<abi>.apk` | Release signing with a retained update key; native storage and background recording validation |
| macOS | `DizyTV-<version>-<arch>.pkg` containing `DizyTV.app` | Native Mac build, a documented engine connection, Developer ID signing and Apple notarization |

These are release targets; no downloadable builds exist yet. Supported OS versions and processor architectures will be published after the native dependencies and device tests pass. Public downloads will use a public release location; releases in a private GitHub repository are not available to everyone. See the [distribution plan](docs/DISTRIBUTION.md).

## Project documents

- [Design and acceptance criteria](docs/superpowers/specs/2026-10-11-dizytv-design.md)
- [Development roadmap](ROADMAP.md)
- [Installers and public distribution](docs/DISTRIBUTION.md)

## Integration references

- [search-ace.stream playlist documentation](https://search-ace.stream/doc)
- [Ace Stream playback API](https://docs.acestream.media/developers/start-playback/)
- [Ace Stream Android integration](https://docs.acestream.media/developers/running-engine-android/)
- [Ace Stream engine download platforms](https://docs.acestream.media/products/)
- [libVLC](https://www.videolan.org/vlc/libvlc.html)
- [XMLTV format](https://github.com/XMLTV/xmltv/blob/master/xmltv.dtd)

A directory listing does not establish that a stream is currently working or permitted for redistribution. No stream collection, guide dataset or third-party binary is bundled in this documentation foundation. Source coverage and availability will be measured during the first development milestone.
