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
> **0.1.12 alpha is a development build.** The features below are implemented. Package checks run on native Windows/Mac hosts and Android CI; live Ace Stream playback, physical-device storage, unattended recording and installer upgrades still need device testing. Desktop packages are unsigned for public distribution; Android uses a debug key. See [verification and known limits](docs/BUILD-VERIFICATION.md).

## Features

| Feature | Included in the native alpha |
| --- | --- |
| 📺 **Live TV** | Embedded libVLC player, channel search and now/next information |
| 🔎 **Imported channels** | Sixteen desktop playlist presets on fresh installs: existing UK/US/Ace sources, Canada/Australia/NZ/South Africa/Singapore/Hong Kong HTTP feeds, plus classic TV, series, movie, comedy and public sports categories; offline failures preserve last-good data |
| 🗓️ **XMLTV guide** | UK Freeview and US-lite XMLTV presets, automatic ID/unique-name mapping, manual overrides and periodic refresh |
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

**Direct native installers:** these links download the actual executable/package, **not a ZIP**. The `0.1.12-alpha` pre-release is for early device testing; installation, live playback and unattended recording still need real-world validation.

| Platform | Direct download | Target |
| --- | --- | --- |
| **Windows** | [DizyTV Windows installer (.exe)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.12-alpha/DizyTV-Setup-0.1.12-alpha-windows-x64.exe) | x64 |
| **Android** | [DizyTV Android installer (.apk)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.12-alpha/DizyTV-0.1.12-alpha-android-universal-debug.apk) | Android 8+ / API 26+ |
| **MacBook / Apple Silicon** | [DizyTV Mac installer (.pkg)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.12-alpha/DizyTV-0.1.12-alpha-macos-arm64.pkg) | macOS 13+ / arm64 |
| **MacBook / Intel** | [DizyTV Mac installer (.pkg)](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.12-alpha/DizyTV-0.1.12-alpha-macos-x86_64.pkg) | macOS 13+ / x86_64 |

<p align="center">
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.12-alpha/DizyTV-Setup-0.1.12-alpha-windows-x64.exe"><img alt="Download Windows EXE directly" src="https://img.shields.io/badge/Download-Windows%20EXE-0078d4?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.12-alpha/DizyTV-0.1.12-alpha-android-universal-debug.apk"><img alt="Download Android APK directly" src="https://img.shields.io/badge/Download-Android%20APK-3ddc84?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.12-alpha/DizyTV-0.1.12-alpha-macos-arm64.pkg"><img alt="Download Mac Apple Silicon PKG directly" src="https://img.shields.io/badge/Download-Mac%20Apple%20Silicon%20PKG-374151?style=for-the-badge" /></a>
  <a href="https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.12-alpha/DizyTV-0.1.12-alpha-macos-x86_64.pkg"><img alt="Download Mac Intel PKG directly" src="https://img.shields.io/badge/Download-Mac%20Intel%20PKG-374151?style=for-the-badge" /></a>
</p>

[All releases](https://github.com/DizygoticCode/DizyTV/releases) · [SHA-256 checksums](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.12-alpha/SHA256SUMS.txt) · [Native CI evidence](https://github.com/DizygoticCode/DizyTV/actions/workflows/native-builds.yml) · [Build checks](docs/BUILD-VERIFICATION.md)

**Windows upgrade protection (0.1.3):** The installer now embeds the missing preflight script and detects the detached DizyTV recording worker that can remain active after its window closes. It stops only a verified idle DizyTV worker, never an active recording or a job due within two minutes; in those cases it explains why the upgrade must wait. Existing playlists, favourites and recordings remain in the separate user data folder. The installer may still ask to close a genuinely open DizyTV window. This is a targeted fix for Windows file-in-use/write-denied errors, not a fix for system-wide file permissions.

**Browser/security note:** Direct asset links solve the Actions ZIP/sign-in/expiry problem, **not** security reputation. The Windows installer is unsigned, the Mac PKGs are not Developer ID signed/notarized, and Android is signed with a build-specific CI debug key. Chrome, SmartScreen, Gatekeeper or Android may still warn or block a download/install. Do not disable security software to install DizyTV; see [distribution guidance](docs/DISTRIBUTION.md) and check the published checksum. Android test builds may require uninstalling before an update because the debug signing key is not retained. Back up settings first.

## Getting started

1. Install DizyTV for your platform.
2. **Windows:** install VLC 3 x64 and separately install/open Ace Stream. **Android:** separately install/open the engine; libVLC is included in the APK.
3. **Mac:** install VLC 3 for the app's CPU architecture and configure a reachable Windows/Linux Ace Stream engine in Settings. The PKG includes the native Mac client and does not include a Mac engine.
4. Let the default free playlists import on first launch. UK Freeview and US-lite XMLTV guide URLs are preconfigured; refresh the guide and use **Map EPG** when a name is ambiguous or no programme data exists. You can enable/disable any playlist or guide URL in **Settings**.
5. Choose your recording folder and leave timezone on **auto**, or choose an IANA zone. Android also needs exact-alarm access when scheduling and permission for recording notifications.
6. Use country/genre/type filters and favourites. **Edit categories** fills gaps in source metadata; **Use source categories** clears an edit.

## Channels and the guide

DizyTV imports publicly listed playlists directly on the device: [search-ace.stream](https://search-ace.stream/doc), [Free-TV UK / worldwide](https://github.com/Free-TV/IPTV), and [IPTV-org](https://github.com/iptv-org/iptv) country/category feeds. New defaults include public HTTP/HLS lists for Canada, Australia, New Zealand, South Africa, Singapore and Hong Kong, plus separate **Classic**, **Series**, **Movies**, **Comedy** and **Sports** playlists to help discover 24/7-style programme and film channels. These are catalogues of available streams, not guaranteed English-only, always-on, officially licensed, or currently playable content; regional availability and provider rights still apply. Existing installations keep their configured sources; choose **Settings → Add built-in free playlists** to add the new presets without replacing personal URLs. An optional, much larger IPTV-org worldwide index can still be added in Settings. Each source refreshes independently; a failed source retains its cached entries. Identical stream identifiers/URLs are deduplicated, and stable IDs preserve favourites, mappings and category edits across refreshes. No channel dataset is bundled. Public links can be broken, geo-restricted, or subject to broadcaster access requirements.

Country filters use explicit M3U metadata, recognised country groups and bracketed country tags such as `[RU]` and `[UK]`. Genres use source metadata and mapped XMLTV programme categories. TV/radio follows source metadata or saved edits; transport follows the stream. Missing metadata appears as **Unspecified**. Quality tags such as `[HD]` are not countries.

Built-in guide URLs point to [Freeview-EPG](https://github.com/dp247/Freeview-EPG) (UK) and [EPGTalk](https://github.com/acidjesuz/EPGTalk) (US lite). These are public third-party services queried directly by the app, not copied or redistributed in the release. Guide refresh runs automatically on initial use and periodically on desktop; Android supports manual refresh. Matching first uses explicit TVG-IDs and saved mappings, then unique display names (including safe spacing, punctuation and number-word variants). Similar but uncertain XMLTV channels are suggested in a searchable **Map EPG** picker for explicit confirmation; ambiguous regional variants are never assigned automatically. Times are parsed into UTC and displayed locally; channels can play without a guide match. Listings do not establish stream availability or distribution rights.

## Recording and backups

| Platform | Scheduling behaviour in this alpha |
| --- | --- |
| **Windows / Mac** | Detached recorder continues after the window closes while the computer is awake. Open DizyTV after reboot to restart it. Wake-from-sleep is not implemented. |
| **Android** | Exact alarms, a visible foreground service and reboot recovery are implemented. Force-stop, engine availability, storage permissions and vendor battery restrictions affect execution and need device testing. |

The recorder checks write access and free space where the provider reports it, rejects overlapping timers and preserves partial output. Older recordings are not automatically deleted.

On desktop, use **Tools → Save local backup** or **Tools → Restore local backup** from the top toolbar (no separate Backup tab). **Backup** saves your setup to a local JSON file. **Restore** previews replacement, resets storage permissions and pauses future timers. Video files and EPG cache are excluded. Choose storage and rearm timers after restoring. Backups can move preferences between platforms; see [backup format](docs/BACKUP-FORMAT.md).

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

## Ace Stream installation (Windows)

The optional **Ace Stream engine** is a separate, proprietary P2P component; it is not bundled into the DizyTV EXE. The Windows installer can offer an **unchecked** choice to open the [official Ace Stream Windows downloads page](https://docs.acestream.net/products/) after DizyTV finishes installing. The DizyTV Live TV page also offers **Set up Ace Stream engine**. Users install the provider's genuine software themselves, accepting that provider's terms; the setup never silently downloads or executes another installer. Once installed, DizyTV can automatically start the Windows engine in the background for supported Ace streams. Ordinary HTTP/HLS streams do not use the Ace engine. Use only sources you are entitled to watch; P2P software may consume upload bandwidth and display provider advertisements.

## Television viewing modes (0.1.9-alpha)

Open a channel to watch in the app. **Cinema** uses the available space within the DizyTV window; **Screen** opens native fullscreen video on the selected display with its own playback controls and exit button. Use **Quick Guide** to switch channels and **Info** to see current/next EPG programmes. The video also shows a brief now-playing programme banner. The player has a volume slider, Play, Stop, Pause, 30-second rewind, seek slider and **LIVE**. Pause/rewind/scrub only work for streams where VLC reports a seekable DVR window—ordinary live streams without a DVR window cannot yet be rewound (a separate bounded local timeshift buffer is planned). No stream or recording data is modified just to enable the new display modes.

## Experimental device-local live timeshift (0.1.9-alpha)

**Off by default.** In Windows/macOS: Settings → enable local live pause/rewind, set a 1–240 minute window, a 0.25–32 GiB maximum storage allowance and an optional device folder (defaults to DizyTV application data). On Android: Settings → enable temporary live pause/rewind, set duration (1–240 minutes) and maximum buffer size (GiB). Android stores the cache in private app storage.

For compatible **clear MPEG-TS over HTTP** and **unencrypted HLS playlists containing MPEG-TS segments**, DizyTV ingests the current channel into a bounded series of temporary on-device segments, serves them to its own player via a random-token loopback HLS endpoint, and can start earlier cached playback via 30-second rewind or slider and return to Live. A capture must run before there is video to rewind.

- The **time limit and storage quota both apply**: whichever fills first discards the oldest fragments. DizyTV maintains at least 1 GiB of disk free-space reserve, separately from saved recordings. A four-hour setting **does not guarantee** four hours at every source bitrate if the chosen quota fills earlier.
- Cached fragments are deleted when playback stops or the app closes; a stale cache from a crash is eligible for cleanup after 24 hours.
- This is an **experimental alpha**. Smooth pause/rewind depends on libVLC and device-specific HLS playlist behavior. The first tune may wait for several seconds of cache; an unsupported stream falls back to ordinary live viewing.
- Encrypted/DRM HLS, fMP4/CMAF, DASH, unpredictable HLS discontinuities and unsupported stream formats are *not* captured. Nothing circumvents content protection. Local loopback only; no cloud storage or persistent video recording is introduced.
- Live scheduled recordings remain independent of the timeshift cache. Do not use the cache as a substitute for saving a programme.

The previous 0.1.6 release remains available. See [the timeshift development issue](https://github.com/DizygoticCode/DizyTV/issues/9) for remaining playback edge cases.

## DizyTV 0.1.12-alpha — rolling buffer and subtitles testing

This build adds desktop subtitle-track selection and styling, with opt-in offline Vosk captions (the Windows installer bundles FFmpeg and a small English model). Android timeshift improvements include a longer local live-HLS window, safe handling of unsupported HLS formats, and local HTTP MPEG-TS/HLS fixture coverage in CI. Neither official Ace Stream nor Outpace is silently bundled in these installers.

**Physical playback checks are still outstanding.** Native CI verifies the build and application startup but cannot prove real broadcaster and Ace channels on Windows or Huawei Android. On Windows, first finish any recordings, exit DizyTV, run the upgrade installer, try a direct MPEG-TS/HLS channel, test Pause / 30s Back / Live, and check that normal recording still works. Android may require backup and uninstall before using the newly debug-signed APK.

## DizyTV 0.1.9-alpha — Windows TV player and readability pass

Windows users can resize the app down to a small window (minimum 480 × 360 logical pixels) while the horizontal control and header toolbars scroll instead of forcing an oversized minimum width. **Settings → Interface scale** supports 75–150%; **Button size** offers Compact, Normal and Large independently. Select **Green** (original default), **Dark**, or **Light** beside the DizyTV name or under Settings → Appearance theme. The choice persists with your local settings and backups and also recolours the TV Guide and detached controls. Live TV, TV Guide and Recordings use compact rounded tabs with overflow scrolling; Backup/Restore moved to **Tools**. The main player uses redesigned playback buttons, seek and volume sliders.

**Pop out** moves the existing libVLC video surface into a separate modeless resizable window while the DizyTV main catalogue/EPG remains usable. The separate player has Play/Pause, 30-second rewind, LIVE, guide and info, fullscreen toggle, volume and progress controls that disappear after inactivity and return on mouse movement. Escape or **Back to app** restores the embedded player without opening a second stream.

The Windows Ace Stream engine is **not bundled**. DizyTV now searches both 32/64-bit registry install records and common AppData/Program Files paths, starts an installed official engine from its own working folder, or allows choosing the already-installed `ace_console.exe` / `ace_engine.exe` explicitly in Settings. If the engine cannot be reached on the configured HTTP port, the error explains next checks.

After a failed or timed-out ordinary HTTP/HLS stream DizyTV performs a limited source-response check to show a specific HTTP 401/403/404/410/429/5xx error or an apparent HLS-vs-HTML issue, rather than assuming every broken source is geoblocked. A response of 200 doesn't establish decode/segment availability; no VPN or DRM bypass is performed.

Local timeshift retains a wider live playlist for VLC, and cautiously reconnects to the same on-device cache on a stalled/buffering/error stream **only while not paused or intentionally behind LIVE**. Video/audio decode counters help detect freezes where VLC still reports Playing. As before, real feed reliability depends on the source.

**UK Radio:** BBC Radio and clearly identified station streams are shown in the Radio country subsection even if a previously cached catalogue called them TV. Original URLs/guide IDs and favourites remain unchanged. Android application code was not otherwise modified in this Windows-focused pass; native release version numbers are kept aligned across packages.

## DizyTV 0.1.9-alpha: global search and TV playback usability

**Windows: Ctrl+K** (or click **Search all channels & programmes**) searches the full imported catalogue, including Ace Stream, HTTP/HLS, UK TV and Radio, even if the current country, genre, playlist, category, local search or favourites filters hide a match. Search current/upcoming XMLTV programme titles, channels, groups and countries. Results arrive in pages of 150; choose **Watch**, **Show in TV Guide**, or **Record programme** (which asks for confirmation). Channels without XMLTV remain searchable.

The TV Guide now contains **all channels matching the current filters**, not the former first 250. Only the viewport's visible rows are painted for responsive scrolling through thousands of stations; guide density can be set separately in Settings (55–130%). Programme matches navigate to their channel and time, temporarily clearing hiding filters. User's original category overrides, EPG IDs, favourites and source URLs are not rewritten.

The native TV pop-out uses a **transparent floating background** behind compact, slightly translucent controls. Its video/window dimensions do **not** change when controls appear or auto-hide. Both built-in player and pop-out have ±30-second seek buttons; mouse-wheel seek works only when hovering over the timeline (one notch = 30 seconds) if the stream or local buffer is seekable. Live/buffering/stopped lights pulse green/amber/red (direct streams correctly stay green while VLC is playing); the pop-out's hide timer respects the cursor on any desktop position. Ace Engine checks distinguish engine API availability from absent stream peers; no proprietary binaries are bundled.

**Early-test caveat:** A listed channel does not guarantee an available playable stream. Live timeshift, engine playback and overlay behaviour still require actual Windows device testing; package CI is necessary but not sufficient.

## Subtitles and closed captions (desktop)

**CC Subtitles** is available on the embedded TV player and floating player. Select the subtitle or closed-caption track the channel actually carries, switch it off, or attach your own SRT, ASS, SSA, VTT or SUB file. Live channels and third-party playlists may supply no caption tracks; the UI reports that rather than inventing programme text.

Settings → **Subtitles / closed captions** controls the default on/off state and preferred English track. **Text size (12–64 px), font (Sans/Serif/Monospace), text colour (White/Yellow/Cyan/Green/Black) and screen position (Bottom/Raised/High)** are saved with settings and portable backups. Renderer changes take effect when DizyTV is restarted, without interrupting active streams or scheduled recordings. Embedded text subtitles are painted by VLC onto the same video surface, including when the video pops out; picture-based DVB subtitles may ignore text appearance settings.

**Experimental local speech-generated captions** work without an online transcription service. The optional Vosk engine is included in desktop builds, but is **off by default**. To use it, install FFmpeg separately, obtain and extract an appropriately licensed offline speech model from [the official Vosk models directory](https://alphacephei.com/vosk/models), then use Settings → **Offline auto-caption model** (and FFmpeg executable if not on PATH). With a playable, authorised direct HTTP/HLS or local video stream open, choose **CC Subtitles → Generate live subtitles (offline Vosk + FFmpeg)**. DizyTV opens a second audio-only stream connection for local Vosk speech recognition and displays text over the video; choose Stop in the same menu or change channel to end it. It never opens the microphone or sends audio to a cloud speech API; it does consume CPU and memory, may have a noticeable delay, can be inaccurate, and some protected/nonstandard sources will not work. Live local timeshift is intentionally unsupported while generating captions. Speech models and FFmpeg are not bundled, and this native feature still needs real Windows/macOS device testing.


## 0.1.12-alpha — Ace Stream session playback (experimental)

The engine detection previously proved only that port 6878 accepted TCP connections. Ace content is now started through the official `format=json` playback middleware; its validated playback URL is passed to libVLC and engine/session errors are surfaced instead of leaving the player indefinitely at Connecting. New playlist refreshes preserve `infohash` vs `content_id` and supported codec options when rewriting URLs to the user's configured Ace engine. The user still needs an installed, running Ace engine plus VLC 3 on Windows. An online engine does not mean a given source has peers, supports the current session, or is authorized for playback. Real Windows device/stream validation is required before stable release.
