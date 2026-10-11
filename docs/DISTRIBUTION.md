# DizyTV installers and distribution

**0.1.0-alpha packages have been built.** These are development artifacts, with native-host package/startup checks and Android compilation/lint/signature checks. See [verification](BUILD-VERIFICATION.md) and the [README download buttons](../README.md#downloads).

## Outputs

| Platform | Artifact contents | Signing status |
| --- | --- | --- |
| Windows x64 | `DizyTV-Setup-0.1.0-alpha-windows-x64.exe` and checksum | Unsigned development installer |
| Android 8.0+ / API 26 | `DizyTV-0.1.0-alpha-android-universal-debug.apk` and checksum | Verified CI debug signature; no retained release key |
| Apple Silicon Mac | `DizyTV-0.1.0-alpha-macos-arm64.pkg` and checksum | Ad-hoc app signature; unsigned/unnotarized PKG |
| Intel Mac | `DizyTV-0.1.0-alpha-macos-x86_64.pkg` and checksum | Ad-hoc app signature; unsigned/unnotarized PKG |

Mac packages target macOS 13+. Windows builds target x64. Build settings and CI runner results establish package targets; fresh installation and compatibility on user devices are still to be tested.

## Install and configure

Extract the selected artifact ZIP and check its SHA-256 file against the installer. Run the Windows EXE, install the APK through Android's permitted sideload flow, or open the matching Mac PKG to install `DizyTV.app` in Applications. Unsigned/development builds may trigger operating-system trust warnings.

- **Windows:** install VLC 3 x64 and a separately installed Ace Stream engine. Start the engine before playback/recording. The app installs per user, without requiring an administrator by default.
- **Android:** libVLC is embedded; install/open Ace Stream separately. Select a folder through Settings and retain its read/write grant. Allow recording notifications and grant exact-alarm access when scheduling.
- **Mac:** install VLC 3 for the app architecture and configure a reachable Windows/Linux engine endpoint. No Mac Ace Stream engine is bundled. The player and output files stay on the Mac.

In DizyTV Settings, select the recording destination, XMLTV feed URLs, timezone/guide correction and timer padding. The playlist imports automatically on first launch. Refresh the guide, map missing channels and edit country/genre/type categories where needed.

One recorder runs per device. Desktop recording requires an awake machine; closing the window leaves the detached worker running. Open the app after reboot. Android alarms/foreground recording/reboot recovery are implemented, but battery management, force-stop and engine availability need real-device validation.

## Backups and updates

Use Backup before changing development builds. JSON restores channels, favourites, category edits, mappings, preferences and timer definitions across platforms. It excludes video files, file paths and storage permissions. Choose the folder again and rearm paused timers after restoring.

Android CI debug keys are generated on build hosts and do not provide a guaranteed update identity. A retained release keystore is required before a stable upgrade path is promised. Desktop upgrade behaviour also needs installer testing.

## Distribution status

GitHub Actions artifacts require GitHub sign-in and repository access, and expire after 30 days. The owner has requested public source visibility; the connector cannot change the setting or About text. Instructions are in [repository setup](REPOSITORY-SETUP.md). No GitHub Release or store listing has been published.

Public release work remains: device acceptance, durable versioned downloads, Windows signing, Android release signing, Apple Developer ID signing/notarization, exact third-party sources/relinking information and an owner-selected source licence. Licence texts and component notices are included in the packages; see [third-party notices](../THIRD-PARTY-NOTICES.md).

The engine is separately installed/configured; this project does not rename or redistribute Ace Stream binaries. DizyServer metadata and optional server recording are separate future milestones. Engine endpoints should be configured for trusted networks; this work does not expose a public unauthenticated engine service.

## Build hosts

The workflow uses Windows 2022 x64, macOS 15 Apple Silicon, macOS 15 Intel and Ubuntu 24.04 Android build hosts. Desktop packaging uses PyInstaller 6.22.3, Inno Setup 6 and macOS `pkgbuild`; Android uses JDK 17, Gradle 8.13 and AGP 8.11.1. Compile SDK 36 satisfies libVLC 3.7.5's AAR requirement while target remains 35 and minimum remains 26.

## Primary references

- [Ace Stream engine products](https://docs.acestream.media/products/)
- [Android app signing](https://developer.android.com/studio/publish/app-signing)
- [Apple Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates)
- [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
- [Microsoft SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
