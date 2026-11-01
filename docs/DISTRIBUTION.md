# DizyTV installers and distribution

## v0.1.19-alpha

This is a **development pre-release**, not a verified stable or production build. All five native installers have passed source QA and a candidate GitHub Actions build. The GitHub Release assets are published only after the five-platform build triggered by a `main` merge succeeds. The [release page](https://github.com/DizygoticCode/DizyTV/releases/tag/v0.1.19-alpha) and [checksums](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.19-alpha/SHA256SUMS.txt) must exist before claiming publication.

| Platform | Direct installer | Signing |
| --- | --- | --- |
| Windows x64 | [DizyTV-Setup-0.1.19-alpha-windows-x64.exe](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.19-alpha/DizyTV-Setup-0.1.19-alpha-windows-x64.exe) | Unsigned development installer |
| Android 8+ | [DizyTV-0.1.19-alpha-android-universal-debug.apk](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.19-alpha/DizyTV-0.1.19-alpha-android-universal-debug.apk) | Debug signature, not stable across CI runs |
| macOS Apple Silicon | [DizyTV-0.1.19-alpha-macos-arm64.pkg](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.19-alpha/DizyTV-0.1.19-alpha-macos-arm64.pkg) | Ad-hoc app, unnotarised package |
| macOS Intel | [DizyTV-0.1.19-alpha-macos-x86_64.pkg](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.19-alpha/DizyTV-0.1.19-alpha-macos-x86_64.pkg) | Ad-hoc app, unnotarised package |
| Ubuntu/Debian x64 | [DizyTV-0.1.19-alpha-linux-amd64.deb](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.19-alpha/DizyTV-0.1.19-alpha-linux-amd64.deb) | Unsigned experimental DEB |

### Installation and launch

- **Windows:** bundled private VLC 3, FFmpeg and English Vosk. The optional original publisher Ace Stream installer remains **unchecked** and requires separate consent. The final interactive Inno Setup screen offers **Run DizyTV now**, checked by default; silent upgrades do not launch the GUI.
- **macOS:** the architecture-matched PKG installs `DizyTV.app` into Applications, with private VLC, FFmpeg, English Vosk and a separately licensed Outpace helper for compatible public streams. The standard Installer.app completion summary explains how to open DizyTV from Applications; it has no Windows-style checkbox or unsafe automatic root launch.
- **Linux:** `sudo apt install ./DizyTV-0.1.19-alpha-linux-amd64.deb`, then launch `dizytv` from the app menu or terminal. VLC and FFmpeg are managed by APT; English Vosk/Outpace are packaged.
- **Android:** uses the Android installer’s ordinary **Open** action where offered. It includes native libVLC but **not** desktop Vosk/FFmpeg parity. Debug-key changes may mean uninstalling an older debug build and restoring from a DizyTV backup rather than upgrading in place.

**Matchday is limited and experimental.** Fixture data is not proof of an authorised free broadcast. A user may add an authorised webpage/HLS link for a fixture; native/web rendering, territory, video/audio and quality remain unverified. No paid/DRM-protected or unauthorised stream access is provided.

**Preserve ongoing recordings.** Windows upgrades identify idle background workers but refuse to replace an app with active or imminently queued recordings. Back up playlists, favourites and settings before upgrading. Physical Windows 30-minute playback/UI responsiveness, Vosk On/Off, macOS/Outpace, Android viewing, clean installs and third-party licensing require verification.

**Security:** Do not bypass Chrome, SmartScreen, Play Protect or Gatekeeper blocks. Development signatures are not production trust signals. Licence and corresponding-source obligations require review prior to broader distribution.

## Windows upgrade from 0.1.0/0.1.1

Older builds leave the DizyTV.exe recorder running after the window closes, which can lock the installer files. The 0.1.3 installer embeds its previously omitted safety script and runs a Windows-only preflight before replacing files: it identifies only the worker started from the exact installed executable, refuses to stop it during recording or within two minutes of a queued timer, and otherwise stops that idle worker. No blanket taskkill and no removal of the AppData settings/recordings. If the installer reports an active recording, finish it and retry. If it reports that it cannot inspect/stop the worker, stop and troubleshoot rather than forcibly deleting application files. Restart DizyTV after upgrading to restore background scheduling.

## Backups and updates

Use Backup before changing development builds. JSON restores channels, favourites, category edits, mappings, preferences and timer definitions across platforms. It excludes video files, file paths and storage permissions. Choose the folder again and rearm paused timers after restoring.

Android CI debug keys are generated on build hosts and do not provide a guaranteed update identity. A retained release keystore is required before a stable upgrade path is promised. Desktop upgrade behaviour also needs installer testing.

## Distribution status

GitHub Actions performs source and native smoke tests on the five platforms, then (only on `main`) publishes a versioned pre-release with the five native files and SHA-256 manifest. It refuses to overwrite an existing release. The previous [v0.1.18-alpha](https://github.com/DizygoticCode/DizyTV/releases/tag/v0.1.18-alpha) is preserved.

## Third-party engines and licensing

Windows may offer an **explicit opt-in** to download and run the unmodified original Ace Stream setup only when a trusted publisher/signature can be verified. No Ace Stream binary is redistributed. Mac/Linux include a separately licensed source-built Outpace helper for compatible public swarms; real-peer functionality and distribution obligations still require field/legal verification.

## 0.1.16-alpha playback note

This release includes fullscreen viewing controls, a quick EPG popup, and platform-native volume/seek UI. DVR pause and rewind are **conditional on source seekability**. An experimental bounded ring buffer is available for supported TS/HLS feeds; non-compatible streams remain unseekable. Windows includes FFmpeg and the Vosk small English model under DizyTV's private application folder; nothing is installed system-wide. No Ace Stream binary or external IPTV credentials are bundled.

## 0.1.16-alpha experimental rolling timeshift

Windows/macOS and Android can opt into a **locally buffered** viewing mode for direct HTTP MPEG-TS or clear HLS playlists with MPEG-TS segments. Configurable duration 1–240 minutes, independent disk quota from 256 MiB–32 GiB, minimum 1 GiB free-space reserve, cleanup on stop and old crash cache cleanup. The Android cache is inside the app's private device storage; desktop can use a user-chosen local folder. No DVR data leaves the user's device.

**Limitations:** experimental playback; provider streams are not guaranteed seekable by libVLC, although the buffer's own archive is seekable via a new replay manifest. HLS AES encryption, fMP4, DASH and DRM are excluded. For unsupported feeds, original live playback continues. Alpha users should check storage after a short test and report device/channel behavior. All cached fragments are transient and should not be treated as recordings.

## Windows usability and diagnostics (0.1.16-alpha)

This version's functional changes target the Windows Qt player: compact window layout, per-user font/button size preferences, styled native controls, modeless resizable TV pop-out, more reliable *existing* Ace Stream engine detection/startup, HTTP response diagnostics, and local HLS timeshift stall handling. Radio classification is shared core metadata logic; no Android screen work was done. Source status messages distinguish HTTP errors but cannot establish geo-blocking with certainty. All streams require the viewer's own legitimate access.

The Windows installer remains in-place upgrade safe for an **idle** detached recorder; finish any active recordings and close the UI before upgrading. Preserve existing state.json, recordings and favourites. The official Ace Stream engine is not redistributed.

## 0.1.16-alpha Windows release notes

Ctrl+K global search (all sources and programme titles); full filtered guide with no 250-channel cap and viewport-only rendering; separately scalable EPG; transparent auto-hiding overlay controls without video/window layout reflow; +30-second seek and mouse-wheel seek; diagnostic Ace engine status and animated live indicator. These changes target the desktop Qt player. Android packaging receives aligned build metadata only. Windows installer still respects active recording safety and preserves state. Native CI and real-device playback validation remain distinct.

## 0.1.16-alpha Windows bundled offline captions

The Windows EXE now embeds checksum-verified FFmpeg 8.1.2 and Vosk Small English US 0.15 into DizyTV's private `_internal/speech` directory; neither runs automatically on installation. To transcribe an authorised live channel, choose **CC Subtitles → Generate live subtitles**. Blank model and FFmpeg paths select the bundled copies automatically, and explicit paths override them. The installer is allowed to run only if the build stage downloads, verifies SHA-256 and packages both assets. CI also executes the installed FFmpeg binary and checks Vosk model directories. This changes Windows only: newer macOS versions bundle FFmpeg and English Vosk. Review bundled third-party GPL/source obligations in [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md) before distributing a stable release.

## 0.1.16-alpha Ace Stream playback handoff

The Windows/macOS app now requests an Ace JSON session and uses the returned local engine playback URL. Empty/failed engine sessions surface a channel-specific error even if the Ace engine API and TCP port are healthy. The engine may still lack peers, require access or return incompatible media. Source playlist `infohash` parameters are retained rather than coercing them to `id`. Re-import playlists to refresh old cached entries. Native regression tests run in CI, but genuine P2P playback needs manual testing. No unauthorized content or bypass of provider restrictions is enabled.
