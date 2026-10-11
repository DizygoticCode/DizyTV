# DizyTV native alpha implementation

**Goal:** Build installable native Windows, macOS and Android alpha clients with favourites, local backup/restore, a timezone-aware XMLTV guide and local recording.

**Architecture:** Python standard-library domain/storage/recorder core, native Qt desktop clients, and a Kotlin Android client with libVLC, Storage Access Framework, alarms and a foreground recorder. Both clients consume the same versioned JSON backup contract. Device timers store UTC seconds. No deployment to DizyServer is part of this work.

**Tech stack:** Python 3.12, PySide6 6.11.2, python-vlc 3.0.21203, PyInstaller 6.22.3, tzdata 2026.2; Kotlin/JDK 17, Android Gradle Plugin 8.11.1, Gradle 8.13, Android compile API 36 (target 35), native libVLC. Desktop VLC and the Ace Stream engine are separate installations. macOS initially connects to a configured compatible remote engine.

**Spec:** [Product design](../specs/2026-10-11-dizytv-design.md), extended by the user's requests for favourites, local backups and timezone detection/selection.

**Outcome:** Native alpha source is implemented. All four native build jobs passed for application commit `ba30a3966a16fe64e48a98e73f2dd222dae734fb`; see [build verification](../../BUILD-VERIFICATION.md) for checks and physical-device limits. Country/genre/type filters and persistent category edits were added to both clients following the user's extension.

## Global constraints

- One recording at a time; never interrupt an existing recording when a timer overlaps.
- UTC is authoritative for timers. Device timezone, DST and EPG correction affect presentation or new imports, not accepted timers.
- Backup restore validates before writing, resets destination permissions, and pauses restored timers until explicitly rearmed.
- Native alpha packages are development builds. Signing, notarization and hardware playback/background verification remain explicit release gates.
- Keep last-good data on feed failures; cap inputs; reject external XML entities.
- Never deploy or change other Dizy applications.

## Task 1 — core contracts and behaviour

Files: `dizytv/core.py`, `dizytv/storage.py`, `tests/test_core.py`, `tests/fixtures/`.

1. Write tests for stable catalogue IDs/deduplication, XMLTV offsets/DST, missing guide channels, favourite persistence, schema-invalid backups, paused restore, UTC timer conflicts and filename safety.
2. Run `python -m unittest discover -s tests -v`. Expected: missing core modules fail before implementation.
3. Implement parsing, validated configuration/state, atomic storage and backup import/export.
4. Run the same suite. Expected: all core cases pass.

Produces: JSON state/backup v1, channel/programme dictionaries and UTC scheduling helpers shared with Android fixtures.

## Task 2 — recorder and native desktop client

Files: `dizytv/recorder.py`, `dizytv/desktop.py`, `dizytv/__main__.py`, `tests/test_recorder.py`, `tests/test_desktop.py`.

1. Write recorder tests with a real local HTTP MPEG-TS fixture: completed, premature EOF, cancellation, low space, late/missed timers and duplicate-worker exclusion.
2. Run the recorder suite before implementation. Expected: missing recorder fails.
3. Implement an independent background process, persistent jobs and native Qt channel/guide/recording/settings screens, embedded libVLC, favourites and native file dialogs for backup/restore.
4. Verify with all Python tests, Qt offscreen smoke and a locally packaged executable launch. Expected: successful startup and honest dependency/engine errors.

## Task 3 — native Android client

Files: `android/`, matching JSON fixtures.

1. Write JVM tests for the shared backup/time/playlist/recording conflict contracts.
2. Implement native views and embedded libVLC; feed import, guide, favourites, timezone configuration, local backup documents and SAF recording destinations.
3. Add exact-alarm scheduling/reboot recovery, visible foreground recording and stop action. Preserve partial files and report inaccessible storage.
4. Run JVM tests, lint and assemble APK in platform CI. Expected: compiled, installable development APK; actual device behaviour remains a release gate.

## Task 4 — platform packaging and integration

Files: `scripts/`, `.github/workflows/native-builds.yml`, dependency manifests, notices and documentation.

1. Package Windows via PyInstaller + Inno Setup and macOS `.app` + `pkgbuild`; build Android APK. Generate checksums and upload versioned artifacts.
2. Publish source changes to the authorized repository and inspect actual CI results. Fix compilation failures before claiming artifacts exist.
3. Perform one fresh-context whole-branch review; fix important findings with regression tests and rerun affected suites.
4. Update README badges/buttons and precise implemented/build/device-validation status. Expected: links identify real results, never planning badges masquerading as downloads.

## Review focus

Deliberately inspect malicious and oversized backup/feed inputs, restored destination permissions, interprocess lost updates, timezone/DST transitions, foreground-service lifecycle and exact-alarm access, partial stream output, UI exceptions, macOS VLC architecture compatibility, native dependency packaging and honest CI/signing claims. Synthetic tests cannot prove P2P availability, OS wake, vendor battery management or installer upgrades on users' devices.
