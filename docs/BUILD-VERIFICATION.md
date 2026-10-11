# Native alpha build verification

Date: **11 October 2026**. Application version: **0.1.0-alpha**.

Verified application source: [`ba30a3966a16fe64e48a98e73f2dd222dae734fb`](https://github.com/DizygoticCode/DizyTV/commit/ba30a3966a16fe64e48a98e73f2dd222dae734fb).

All four jobs in [native build run 38148508455](https://github.com/DizygoticCode/DizyTV/actions/runs/38148508455) completed successfully. Later documentation updates do not alter the packaged application source.

## Checks that passed

| Area | Evidence |
| --- | --- |
| Desktop/core | 25 Python tests: catalogue IDs/deduplication, country tags/categories, favourites, UTC/DST, backup validation, atomic state writes, cancellation, timer conflicts, recorder recovery and native UI filters |
| Android domain | 13 Kotlin/JUnit tests: equivalent playlist/time/backup contracts, preserved segments, atomic guide-cache failure and queued adjacent jobs |
| Windows x64 | Source startup, packaged EXE startup and Inno Setup installer build on Windows 2022 |
| Apple Silicon Mac | Source/packaged app startup, PKG payload inspection and strict ad-hoc app signature verification on macOS 15 arm64 |
| Intel Mac | Equivalent app startup, package inspection and signature verification on macOS 15 Intel |
| Android APK | `testDebugUnitTest`, `lintDebug`, `assembleDebug` and `apksigner verify` on Ubuntu 24.04; minimum SDK 26, target 35, compile 36 |
| HTTP recording | Local FFmpeg-generated MPEG-TS saved to the chosen folder; `ffprobe` confirmed playable MPEG-2 video at 160×90 |
| Live catalogue import | The configured search-ace.stream playlist imported successfully; exact channel counts vary with the feed |
| Download verification | Archive digests and contained installer SHA-256 files are checked before delivery; APK contents include libVLC and licence assets |

Tests exercise failure effects, including keeping the prior state after an oversized write, preserving earlier footage if a resume fails, respecting cancellation before a recording is claimed and retaining guide cache after a failed write. Country tags are recognised only from supported metadata/tags; quality tags do not become countries. Saved category edits survive refresh and backup, and filter both channels and guide rows.

## Review and fixes

A fresh-context whole-branch review identified four important issues and a guide-cache issue initially graded minor. The cache issue was treated as important because a failed write could lose the user's working guide. All were fixed with regression checks:

1. Bound state size before replacing the existing file.
2. Preserve recording segments and their file/URI references after interruption or a failed resume.
3. Atomically recheck cancellation/deadline before claiming a recording.
4. Queue adjacent Android requests so completion of one service task cannot stop its successor.
5. Atomically publish Android guide cache, retaining the previous file if writing fails.

No review findings were deferred. Android's compile SDK was raised to 36 because libVLC 3.7.5 declares that minimum compile requirement; minimum device API stays 26 and target stays 35.

## What these checks do not prove

- Live P2P engine playback and representative channels on physical devices.
- Fresh installer execution, upgrades, SmartScreen/Gatekeeper trust or Apple notarization.
- Huawei P30/Android 10 folder-provider behaviour, exact-alarm access, vendor battery limits, screen-off recording and reboot recovery.
- Recording while a desktop sleeps. The desktop alpha does not wake a machine or start its worker automatically after reboot.
- Whole-catalogue XMLTV coverage. Users supply feed URLs and map missing channels; there is no preselected universal guide.
- Concurrent multi-channel recording, catch-up, series recording or server recording.

The Windows installer and Mac PKGs are unsigned development packages; the Mac app uses an ad-hoc signature. Android's debug signature verifies the build, rather than establishing a retained release/update identity. Licence notices/texts are packaged, but public redistribution/source-offer work and the owner-selected DizyTV source licence remain release tasks.

## 0.1.2-alpha upgrade validation (pending CI and device confirmation)

The 0.1.2 Windows upgrade preflight adds an isolated native Windows CI scenario: start the packaged detached worker, check that an active job blocks the upgrade helper without killing the worker, clear the job, and verify that the helper terminates the now-idle worker before installer creation. The existing 0.1.0 checks above are historical, not evidence for 0.1.2. Native CI and real install-over-0.1.1 still need confirmation. Mac and Android installers continue to be versioned independently; Windows and Android package signing limitations remain.

## 0.1.3-alpha Windows upgrade regression (CI pending)

A real 0.1.2 upgrade failed when background DizyTV.exe and libcrypto-3.dll remained loaded. The previous CI tested a PowerShell helper in isolation but did not bundle it in the compiled installer. 0.1.3 adds an explicit Inno Setup [Files] dontcopy entry to embed the preflight helper, normalizes installer path delimiters, and adds a Windows end-to-end regression: create existing installation, start detached worker, launch compiled Setup over it, confirm files were replaced, DLL exists, worker exited, and packaged app launches. Real-device upgrade still must be confirmed.
