# DizyTV native dependency release gates — unreleased development

This checklist governs the next release after **v0.1.17-alpha**. Do not overwrite
that published release or trigger a new public build until the applicable
acceptance criteria are met. Work branches #34, #35 and
`wip/complete-dependency-gates` are **not shipped binaries**.

## One-install delivery status

| Platform | VLC | FFmpeg | English Vosk | Ace engine |
|---|---|---|---|---|
| Windows | Private upstream VideoLAN staged | Existing pinned 8.1.2 | Existing pinned model | Unchecked opt-in bootstrap of original signed publisher installer, validation pending |
| Mac Intel | Private VLC DMG staged | Original native wheel executable staged | Model staged | Pin/build Outpace v0.2.0 native helper under AGPL, source/real swarm verification pending |
| Mac Apple Silicon | Same native arm64 process | Same native arm64 process | Model staged | Same on-demand Outpace |
| Linux amd64 | APT libvlc5/plugins | APT ffmpeg dependency | Model staged | Pinned native AGPL Outpace helper plus explicit opt-in original Ace downloader (vendor original only supports Ubuntu 22.04); real swarm testing pending |
| Android | Existing bundled libVLC | Android speech integration not implemented | Native offline Vosk not implemented | Original vendor engine remains a separate third-party Android installation and cannot be silently installed by a debug APK |

Linux Ace uses the original exact publisher URL and recorded SHA-256
`9b6bbd76a55e5a434641afae3b9cf8e6154ce1cf392152ec3aed5ac265432b2e`
for version 3.2.11 Ubuntu 22.04 amd64/Python 3.10. DizyTV never redistributes
this tarball, automatically runs `start-engine` during installation,
changes system services, overwrites pre-existing installations, or accepts
an off-publisher redirect. The checksum is independently recorded in public
third-party manifests, **not a publisher signature**; vendor EULA, user
consent, runtime compatibility and permitted use still apply. Unsupported
distributions fail safely and can use a trusted separately installed engine.

The .deb additionally bundles original Outpace 0.2.0 on Linux x64, built from upstream pinned commit under AGPL. It is a public-swarm reimplementation, not the original proprietary engine.

The .deb bootstrap lives in `dizytv/linux_ace_bootstrap.py`, included
by the main application's **Tools → Set up Ace Stream engine** action.
It is not a Debian `postinst` hook: unattended APT installs and upgrades
must never trigger a third-party network download or P2P executable.

## Mandatory before merge/public release

1. Inspect exact first-party archive formats, cryptographic provenance,
   FFmpeg/VLC LGPL/GPL fulfilment, Outpace AGPL source offer, licence texts,
   and platform code-signing. No unsigned downloaded installer auto-execution.
2. Test real Windows EXE install on a machine without VLC, including intact
   video+audio, subtitle Off, Vosk, 80% UI layout, upgrade and active
   recorder protection. Reproduce/diagnose existing #32 UI hangs.
3. Test **both** installed macOS PKGs without system VLC; FFmpeg/Vosk
   transcription; original Outpace local API, public peer playback and
   code-signing. P2P feed availability remains conditional.
4. Test clean Ubuntu 24.04 .deb, libvlc/ffmpeg resolution, real video,
   caption recognition, and determine a **verified Ubuntu 24.04 Ace engine
   compatibility solution**, or explicitly exclude the unsupported engine
   and keep #28 open.
5. Exercise opt-in Ace downloads only with user approval. In CI use mocked
   TLS, redirects, hashes, archive traversal, cancellations and offline
   failures; never execute vendor engines on CI runners.
6. Review #30 source diagnostics and explicit saved-channel alternate logic
   using authorised HTTP/HLS streams. An EPG match never proves decoding.
7. Document Android feature gaps honestly; do not label it desktop parity.
8. **Only after code review and cross-platform tests**, use one consolidated
   version bump/build/release; keep operator physical-device tests separate.

Issue acceptance: #27 and #28 remain **partially complete**, #30 requires
live-source checks, #32 requires Windows hang confirmation. Do not close issues
just because the code compiles.
