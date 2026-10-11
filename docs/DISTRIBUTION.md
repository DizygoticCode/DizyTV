# DizyTV installers and distribution

**0.1.5-alpha native test packages are built and published as individual GitHub Release files.** Downloads do not require extracting a GitHub Actions ZIP or signing into GitHub. These are development packages: native-host package/startup checks and Android compilation/lint/signature checks have passed, but physical-device tests are pending. See [verification](BUILD-VERIFICATION.md) and the [README download buttons](../README.md#downloads).

## Outputs

| Platform | Artifact contents | Signing status |
| --- | --- | --- |
| Windows x64 | `DizyTV-Setup-0.1.5-alpha-windows-x64.exe` and checksum | Unsigned development installer |
| Android 8.0+ / API 26 | `DizyTV-0.1.5-alpha-android-universal-debug.apk` and checksum | Verified CI debug signature; no retained release key |
| Apple Silicon Mac | `DizyTV-0.1.5-alpha-macos-arm64.pkg` and checksum | Ad-hoc app signature; unsigned/unnotarized PKG |
| Intel Mac | `DizyTV-0.1.5-alpha-macos-x86_64.pkg` and checksum | Ad-hoc app signature; unsigned/unnotarized PKG |

Mac packages target macOS 13+. Windows builds target x64. Build settings and CI runner results establish package targets; fresh installation and compatibility on user devices are still to be tested.

## Install and configure

Download the native .exe, .apk or .pkg directly from the [0.1.5-alpha pre-release](https://github.com/DizygoticCode/DizyTV/releases/tag/v0.1.5-alpha) and verify against its [SHA256SUMS.txt](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.5-alpha/SHA256SUMS.txt). Run the Windows EXE, install the APK through Android's permitted sideload flow, or open the matching Mac PKG to install `DizyTV.app` in Applications. Unsigned/development builds may trigger browser or operating-system trust warnings. Do not disable protective software to proceed.

- **Windows:** install VLC 3 x64 and a separately installed Ace Stream engine. Start the engine before playback/recording. The app installs per user, without requiring an administrator by default.
- **Android:** libVLC is embedded; install/open Ace Stream separately. Select a folder through Settings and retain its read/write grant. Allow recording notifications and grant exact-alarm access when scheduling.
- **Mac:** install VLC 3 for the app architecture and configure a reachable Windows/Linux engine endpoint. No Mac Ace Stream engine is bundled. The player and output files stay on the Mac.

In DizyTV Settings, select the recording destination, optional additional M3U URLs, XMLTV feed URLs, timezone/guide correction and timer padding. Five public playlists and two guide URLs are configured by default; imports happen on the device with per-source failure-safe cache. Refresh the guide, map missing channels and edit country/genre/type categories where needed. Some feeds are geo-restricted, use DRM, or do not provide compatible streams. DizyTV does not circumvent those restrictions.

One recorder runs per device. Desktop recording requires an awake machine; closing the window leaves the detached worker running. Open the app after reboot. Android alarms/foreground recording/reboot recovery are implemented, but battery management, force-stop and engine availability need real-device validation.

## Windows upgrade from 0.1.0/0.1.1

Older builds leave the DizyTV.exe recorder running after the window closes, which can lock the installer files. The 0.1.3 installer embeds its previously omitted safety script and runs a Windows-only preflight before replacing files: it identifies only the worker started from the exact installed executable, refuses to stop it during recording or within two minutes of a queued timer, and otherwise stops that idle worker. No blanket taskkill and no removal of the AppData settings/recordings. If the installer reports an active recording, finish it and retry. If it reports that it cannot inspect/stop the worker, stop and troubleshoot rather than forcibly deleting application files. Restart DizyTV after upgrading to restore background scheduling.

## Backups and updates

Use Backup before changing development builds. JSON restores channels, favourites, category edits, mappings, preferences and timer definitions across platforms. It excludes video files, file paths and storage permissions. Choose the folder again and rearm paused timers after restoring.

Android CI debug keys are generated on build hosts and do not provide a guaranteed update identity. A retained release keystore is required before a stable upgrade path is promised. Desktop upgrade behaviour also needs installer testing.

## Distribution status

The public repository now uses a gated release job: after all four native builds pass on a push to `main`, GitHub Actions creates a **pre-release tagged `v0.1.5-alpha`** and uploads all four files plus a consolidated SHA-256 manifest. If that version already exists, it is not silently overwritten. The release assets are direct downloads without the 30-day GitHub Actions artifact expiry or login requirement.

- [Windows .exe](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.5-alpha/DizyTV-Setup-0.1.5-alpha-windows-x64.exe)
- [Android .apk](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.5-alpha/DizyTV-0.1.5-alpha-android-universal-debug.apk)
- [Mac arm64 .pkg](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.5-alpha/DizyTV-0.1.5-alpha-macos-arm64.pkg)
- [Mac x86_64 .pkg](https://github.com/DizygoticCode/DizyTV/releases/download/v0.1.5-alpha/DizyTV-0.1.5-alpha-macos-x86_64.pkg)

Direct links do **not** establish a file's reputation with Chrome, Microsoft Defender SmartScreen, Play Protect or Gatekeeper. These are explicitly **untrusted/development** packages: Windows is unsigned; Android is signed with a CI debug key that is not retained between runs; Mac PKGs are unsigned and unnotarized. Never instruct testers to turn off browser or operating-system malware protections. If Chrome reports that a file is harmful or malware, do not override the warning: investigate the exact warning and check the binaries and supply chain first. Routine publisher-identity warnings likewise mean these builds are not yet suitable for broadly trusted public distribution.

Public stable-release tasks remain: device acceptance, persistent Android release signing and upgrade testing, Windows code signing, Apple Developer ID signing/notarization, exact third-party source/relinking information and an owner-selected source licence. Licence texts and component notices are included in the packages; see [third-party notices](../THIRD-PARTY-NOTICES.md).

The engine is separately installed/configured; this project does not rename or redistribute Ace Stream binaries. DizyServer metadata and optional server recording are separate future milestones. Engine endpoints should be configured for trusted networks; this work does not expose a public unauthenticated engine service.

## Build hosts

The workflow uses Windows 2022 x64, macOS 15 Apple Silicon, macOS 15 Intel and Ubuntu 24.04 Android build hosts. Desktop packaging uses PyInstaller 6.22.3, Inno Setup 6 and macOS `pkgbuild`; Android uses JDK 17, Gradle 8.13 and AGP 8.11.1. Compile SDK 36 satisfies libVLC 3.7.5's AAR requirement while target remains 35 and minimum remains 26.

## Primary references

- [Ace Stream engine products](https://docs.acestream.media/products/)
- [Android app signing](https://developer.android.com/studio/publish/app-signing)
- [Apple Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates)
- [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
- [Microsoft SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)

## Optional third-party Ace Stream setup (next Windows alpha)

DizyTV Setup offers an **unchecked** task, "Open the official Ace Stream download page after installing DizyTV." If selected, it opens https://docs.acestream.net/products/ in the default browser; **no Ace executable is embedded, downloaded or silently executed** by DizyTV. Users may obtain the unchanged installer from the publisher and accept its own terms, which include P2P networking and advertising. The Live TV tab also includes a setup link for people who skipped the installer option. DizyTV auto-starts an existing engine on Windows, but no known redistribution/integration permission is implied by these changes. Once installed, regular HTTP/HLS playback remains entirely independent of Ace Stream. Desktop libVLC/VLC 3 requirements are separate.
