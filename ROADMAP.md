# DizyTV roadmap

## Native alpha — implemented

- Native Qt apps for Windows/macOS and experimental Ubuntu/Debian x64 Linux, plus a separate Kotlin Android app with libVLC.
- Playlist import/cache, stable IDs, search, favourites and country/genre/type filters.
- Saved category edits preserved through refresh and portable backup/restore.
- XMLTV sources, now/next, programme grid and manual channel mappings.
- Automatic/manual timezone, daylight-saving display and guide correction; fixed UTC timers.
- Record now, padded EPG timers, overlap checks and one recorder per device.
- Selected local folders, persistent jobs, preserved partial segments and recording playback/deletion.
- Detached desktop recorder; Android exact alarms, foreground notification and reboot recovery.
- Local JSON backup/restore with destination reset and explicit timer rearming.
- Windows EXE, Apple Silicon/Intel Mac PKGs, Ubuntu Linux x64 DEB, and universal Android debug APK built in CI, with checksums and licence notices.
- 0.1.16-alpha desktop adds adjustable HTTP/HLS network buffering, more resilient Ace playback lifecycle, local system usage, progressive health scanning, conservative duplicate management, and UK FAST playlist/guide pairing.

See [build verification](docs/BUILD-VERIFICATION.md) for actual evidence. Successful builds do not establish physical-device acceptance.

## Next — device acceptance

- Fresh install and upgrade on Windows x64, Intel Mac, Apple Silicon Mac, Ubuntu Linux x64 (including X11 versus Wayland behaviour) and Android; include Huawei P30/Android 10.
- Live playback through separately installed engines; Mac connects to a reachable Windows/Linux engine.
- Record/replay permitted live streams, including scheduled recording with the main UI closed.
- Measure XMLTV coverage and mapping across representative countries and genres.
- Test storage removal, low space, engine/stream loss, Android screen-off/reboot/permissions and vendor battery restrictions.
- Confirm upgrades preserve favourites, category edits, mappings, timers and recording history.

Desktop sleep/wake and automatic recorder startup after reboot are not implemented. Android background behaviour needs device evidence before reliability claims.

## Public alpha distribution and remaining trust work

- Source repository made public — verified 11 October 2026; owner maintains the GitHub About description and repository settings.
- Select the DizyTV source licence and finish third-party source/relinking requirements.
- Configure Windows signing, a retained Android release key, and Apple Developer ID signing/notarization.
- Versioned GitHub Releases provide direct alpha installers and checksum manifests after gated five-platform CI. GitHub Actions artifacts are temporary; real-device acceptance and code-signing remain requirements before a trusted stable release.

## Later — DizyServer integration

- Optional cached catalogue/EPG service.
- Explicit **Record on DizyServer** destination, separate worker, authenticated access, quotas and downloads.
- Deploy only when requested; retain local recording and keep existing Dizy services separate.

Simultaneous multi-channel recording, series recording, timeshift and catch-up/VOD are later work. A self-contained Mac Ace Stream engine also requires a separate feasibility and redistribution check.

## Free playlist and XMLTV import (0.1.1-alpha)

Implemented for Windows, macOS and Android: selectable public playlist URLs, source-aware refresh with last-good fallback, UK/US/free international preset sources, UK/US XMLTV guide presets and conservative EPG matching. Streams are user-accessed on-device without redistributing feeds. Stream validation, licensing review, stable Android release signing, Ace engine integration, Xtream Codes accounts, broader EPG guide collection and the self-hosted metadata service remain separate work.

## Windows upgrade repair (0.1.2-alpha)

Added Windows installer preflight for hidden DizyTV background recorder processes after the UI closes. Only exactly matched idle workers are terminated; active or near-due recordings prevent installation. Native Windows CI exercises this upgrade helper against a running packaged worker; physical-machine upgrade confirmation is still pending. Bundled Ace Stream engine, VLC binary distribution and Xtream credentials are **not** part of this installer-focused change.

## Installer regression (0.1.3-alpha)

Embed the previously omitted pre-install PowerShell safety helper; verify an actual compiled Windows Setup updating an installation with a running idle detached recorder. This fixes installation failure due to locked DizyTV.exe/libcrypto-3.dll. End-user verification still required.

## 0.1.4 alpha playback and EPG follow-up

- Safe Freeview EPG name/ID aliases and manual regional mapping for BBC One/ITV1.
- Better HTTP/HLS playback and failure statuses, background Windows Ace engine launch if engine is separately installed. Android detects a stopped engine without UI-thread networking.
- Native CI must pass before a new tagged release; streaming availability, geoblocks, DRM and proprietary engine redistribution remain external limitations.

## 0.1.5-alpha: country/category browser and optional Ace engine setup

Display-only name normalization; country and genre/category hierarchy in both native UIs without changing stored channel IDs or XMLTV mappings. Provide explicit official Ace Stream Windows setup page option, rather than bundling unlicensed proprietary binaries. Future integration may support properly licensed/offline engine distribution if a redistribution and SDK agreement is obtained from Ace Stream.

## 0.1.6-alpha TV-screen experience

Native TV playback: two fullscreen styles, quick programme guide, now/next and auto-hide now-playing banner, proper play/pause/volume and conditional DVR seeking. **Next**: a bounded local ring-buffer service for genuine live pause/rewind on nonseekable HTTP and HLS feeds, with per-device disk quota, retention, seeking and recording coordination. Avoid claiming universal live timeshift until tested. Retain no copy on disk where not explicitly enabled.

## Rolling timeshift (0.1.7-alpha experimental)

Added on-device bounded short-term MPEG-TS/HLS segment capture and playback bridge (default off). Remaining: real-device long-run soak on Windows/Android, continuous HLS playlist seek accuracy, stream reconnect/discontinuity handling and smooth live↔replay transitions, backfill segment errors, optional hardware-accelerated remux for more formats. Preserve quota and free-space reserve. Issue #9 remains open until reliable pause/resume and rewind on *nonseekable* sources are demonstrated, not merely that segment buffering and playback controls exist.

## 0.1.8-alpha Windows TV polish

The compact/resizable native player and modeless pop-out were developed with a two-phase Windows focus. Improve TV keyboard/remote navigation and consider independent full EPG dock layout after user tests. For sources, keep actionable transport diagnostics distinct from the public playlist's reliability (a listed channel is not a promise it works). Continue device-level timeshift stall/long-duration soak and proper Ace Stream installation validation.

## 0.1.9-alpha guide/search follow-up

Windows global channel/programme search includes all imported sources, current and upcoming EPG, navigable matching programmes, pagination and in-guide tuning. Full guide displays every filtered channel and virtualises painting. Future enhancements: fuzzy multi-term suggestions, remote-control keyboard navigation, category-specific programme facets, scheduled recording from search with storage-state prechecks. No new scraping or paid feeds are introduced.
