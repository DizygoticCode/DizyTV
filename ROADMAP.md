# DizyTV roadmap

All application milestones below are planned. They are not claims of implemented functionality.

## 1. Prove the integrations

- Import the site's documented playlist and inspect its actual identifiers, metadata and duplicates.
- Play a small selection of permitted streams on Windows through an installed Ace Stream engine and embedded libVLC.
- Save and replay a short recording in original quality.
- Import one XMLTV feed and measure how many selected channels can be matched correctly.
- Run an early Android playback and recording probe, including selected-folder access and any engine access restrictions.
- Run an early native macOS playback and local recording probe using a reachable Windows/Linux engine. Establish the engine setup required for Mac users before advertising a self-contained Mac download.
- Record the selected client UI frameworks and exact dependency versions before implementing the applications.
- Record the supported OS versions and CPU architectures from actual dependency builds and device tests.

## 2. Build the Windows application and metadata backend

- Create the DizyTV interface, channel browser, favourites and playback controls.
- Implement the DizyServer catalogue and guide service, with cached data and feed refresh status.
- Add multiple XMLTV sources, manual mapping and local-time guide display.
- Package a Windows development build and validate it on the intended Windows machine.

## 3. Deliver local recording

- Add Record now, timed stop and end-of-programme recording.
- Add EPG timers, configurable padding, selected-folder storage and a recordings screen.
- Persist jobs, handle schedule conflicts and keep recording independent of the main window.
- Validate low disk space, network interruption, unavailable streams, restart and supported wake-from-sleep behaviour.

## 4. Deliver the Android application

- Integrate native engine startup, playback, storage access and the shared backend contracts.
- Implement recording notifications, native timers and background recording with the appropriate permissions.
- Restore eligible future timers after reboot and clearly report jobs that could not run.
- Validate on the intended Android devices; include Huawei P30/Android 10 if it remains a target.
- Produce a signed development APK after the Android validation criteria pass.

## 5. Deliver the native Mac application

- Build a native DizyTV `.app` with embedded playback, the shared catalogue and guide contracts, and selected-folder recordings.
- Add explicit engine endpoint setup and clear connection errors; no native macOS Ace Stream binary is assumed to exist.
- Implement and validate a per-user background recorder. Initially document that scheduled recording requires an awake Mac and a signed-in user.
- Validate Apple Silicon and Intel separately before listing either as supported; a universal build requires all bundled native dependencies to support both.
- Package the app as a development `.pkg` after the Mac integration and storage checks pass.

## 6. Produce downloads for public use

- Build the Windows `.exe` installer, release-signed Android `.apk` and Mac `.pkg` on appropriate build hosts.
- Sign the Windows application and installer; use a retained Android signing key for future updates.
- Sign the Mac app with Developer ID Application, sign its package with Developer ID Installer, notarize it and staple the ticket.
- Test fresh installation, upgrade, guide import, playback and recording on every advertised platform and architecture.
- Publish versioned downloads, checksums, release notes, dependency setup and third-party notices at a public release location.
- Keep the existing private repository private during this setup; public artifact publishing is a separate release action.

## 7. Add optional server recording

- Add an explicit Record on DizyServer destination and a separate server recording worker.
- Keep recordings on the server until the user downloads or deletes them.
- Add authenticated access, recording quotas and visible job status.
- Deploy only when requested; keep the existing DizyServer applications and storage separate.

Multi-channel simultaneous recording, series recording, timeshift and catch-up/VOD are outside the first release. They require separate capability and resource validation.
