# DizyTV installers and distribution

Status: planned release outputs. This repository contains documentation, not working applications or downloadable builds.

## Deliverables

| Platform | Intended download | Application |
| --- | --- | --- |
| Windows | `DizyTV-Setup-<version>-<arch>.exe` | Installed native Windows application |
| Android | `DizyTV-<version>-<abi>.apk` | Installed native Android application |
| macOS | `DizyTV-<version>-<arch>.pkg` | Native `DizyTV.app`, installed in Applications |

The installer extension does not establish compatibility. Minimum OS versions, CPU architectures and required engine versions are selected from the first integration tests and listed beside each release. Apple Silicon and Intel Macs require separate validation; a universal Mac app is offered only if all bundled native libraries support both.

## Engine setup

Windows and Android initially use a separately installed, supported Ace Stream engine. Bundling it is a separate decision based on the exact binary's distribution permission and installation behaviour.

The official [Ace Stream products](https://docs.acestream.media/products/) and [desktop-engine instructions](https://docs.acestream.media/developers/running-engine-desktop/) do not list a macOS engine. The initial native Mac client connects to a user-configured, reachable Windows/Linux engine, plays its output and saves recordings directly to Mac storage. Installation must explain this dependency before the user expects playback. The `.pkg` alone cannot be described as a self-contained Ace Stream solution. A local container/helper or another Mac engine route must be proved and explicitly chosen before inclusion.

Engine connections use trusted endpoints. A later remote service needs authenticated access and protected transport; public releases do not expose an unauthenticated engine API on DizyServer. Metadata service deployment and optional server recording remain separate milestones.

## Signing and build hosts

- Windows: build and package on a Windows-capable build host; sign the application and installer with an appropriate code-signing certificate and verify the signatures. A signature does not guarantee immediate SmartScreen reputation.
- Android: generate a release APK and sign with the project's retained release key. Keep the key backed up securely outside source control so future versions can update existing installations.
- macOS: build on a Mac/Xcode-capable host; sign the `.app` and bundled native components using Developer ID Application, sign the `.pkg` using Developer ID Installer, then notarize and staple it. Release distribution requires access to the developer account and its signing certificates.

The project does not currently have configured signing credentials or a build pipeline. Credentials, keystores, private keys, generated installers and recordings are excluded from source control. Development artifacts are labelled as such and are not presented as validated public releases.

## Public downloads

The current GitHub repository is private. Its release files require repository access. Downloads intended for everyone therefore need a public release repository or public download hosting when the release is ready. Source visibility and binary distribution are separate decisions; repository setup does not change visibility or publish anything.

Each published version includes:

- Platform and architecture-specific installers and SHA-256 checksums.
- Supported OS and engine versions, setup instructions and known limitations.
- A tested update path that preserves favourites, guide mappings and future timers.
- Third-party licence notices and any required source distribution.
- Notes on local storage permissions and when unattended recording can run.

Direct downloads are the initial distribution target. Google Play would add an Android App Bundle and store submission work; the Mac App Store is also separate. Neither store listing is implied by creating the APK or PKG.

## Release acceptance

Validate fresh installation and upgrade on every advertised platform/architecture. Exercise catalogue import, guide matching, playback, instant recording, a scheduled recording and permission/connection failures. Confirm signature verification and Mac notarization before describing the artifacts as public releases.

macOS initially requires an awake Mac and signed-in user for scheduled recording. Windows sleep/wake support and Android screen-off, reboot and battery restrictions are demonstrated on supported devices. Recordings must continue independently of the main UI where that platform's validated background mechanism permits it.

## Primary references

- [Apple Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates)
- [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
- [Android app signing](https://developer.android.com/studio/publish/app-signing)
- [Microsoft SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
