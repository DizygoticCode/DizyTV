# DizyTV design

Date: 2026-10-11

Status: product scope approved in conversation; native alpha implementation underway. Automated core and desktop checks are running; platform builds and device validation remain separate gates.

## Intent

Build native DizyTV applications for Windows, Android and macOS that make an imported Ace Stream channel catalogue usable through a television-style interface, an XMLTV guide, and instant or scheduled recordings saved directly to storage selected on the viewing device. Deliver downloadable Windows `.exe`, Android `.apk` and Mac `.pkg` installers for public use after platform validation.

The application is a separate project. DizyServer hosts the metadata backend; DizyTrades and DizyChat are not modified by the initial work. Server recording is optional and follows the local recording milestones.

## Architecture

The catalogue service fetches the documented playlist export and stores a last-known-good snapshot. Each source item retains its source identifier, original name and available metadata. A canonical channel record groups only verified equivalent variants; uncertain matches stay separate. Refreshes preserve favourites and manual guide mappings. The service reports its last successful refresh and failures instead of silently returning an empty catalogue.

The EPG service accepts multiple configured XMLTV sources, normalises timestamps to UTC and maps programme channel IDs to canonical channel records. Clients display times in the selected local timezone. Exact identifiers take precedence; automatic name matching proposes candidates but does not silently choose between regional variants. Manual mappings override automatic suggestions. Unmatched channels remain playable with an explicit absence of programme information.

The native applications use the Ace Stream engine's supported session APIs and an embedded libVLC player. Windows and Android initially use an installed engine and supported startup mechanisms. The application owns session startup, buffering feedback and shutdown. A recorder consumes the stream independently of whether the main window or player screen is open. Actual simultaneous-session capabilities must be validated before enabling recording while viewing a different channel.

The official Ace Stream product and desktop-engine documentation does not list a native macOS engine. The initial Mac client therefore uses an explicitly configured, reachable Windows/Linux engine through the session API. The Mac application and video playback are native, and its recorder saves the received stream to the selected Mac storage. A remote engine does not make the recording a server recording. Engine hosting on DizyServer is not added or deployed by this repository setup. A self-contained Mac engine, including any container/helper approach, needs a separate feasibility and distribution decision before inclusion.

The alpha uses Python 3.12 / PySide6 6.11.2 for native Windows and macOS interfaces and Kotlin / libVLC for Android. Desktop packaging uses PyInstaller; VLC 3 and the Ace engine are separate installations. Native playback and recording still require platform device verification. Native means an installed application with embedded playback and native storage/lifecycle integration; no browser-only client or renamed Ace Player is assumed. The Mac build must execute natively for each advertised CPU architecture. This is an explicit sequencing decision: no client framework is required to create the documentation repository.

The shared data contracts cover channels, stream candidates, guide sources, channel mappings and programme listings. Recording jobs and storage permissions are owned by the device performing the recording. A later server worker owns jobs explicitly assigned to DizyServer.

## Playback and catalogue behaviour

- The documented playlist is the initial import source; HTML scraping is not required unless the export proves unsuitable and a permitted replacement is selected.
- Imported entries are candidates, not a guarantee of current availability or of all broadcasts in the network.
- Search, categories and favourites use the cached catalogue.
- Stream and engine errors are shown clearly, including unavailable content or required access options.
- A failed refresh retains usable cached catalogue and guide data, marked with their age.
- The apps can play a channel without an EPG match.

## Recording behaviour

Instant recording begins with the stream available from the time recording starts. It supports manual stop, a selected duration or the current programme's EPG end. It does not imply retrospective recording or catch-up access.

Selecting a future programme creates a persistent recording job containing the canonical channel, selected stream, programme title, scheduled UTC start/end, padding and destination. Proposed defaults are two minutes before and five minutes after, adjustable per job. Tuning begins early enough to allow buffering. A programme selected after it has started offers recording of the remaining broadcast.

The first release permits one recording job at a time per device. Overlapping timers are reported when scheduled and require the user to choose which job to keep; jobs are not silently discarded. Recording and same-channel viewing may share a session where supported. Switching to another channel must not silently interrupt an active recording; conflicting engine behaviour is detected and explained before changing the session.

Jobs use queued, starting, recording, completed, partial, failed and cancelled states. They survive app restarts. On resume or reboot, a job whose end is still in the future may start late and is marked partial if its beginning was missed; an expired job is marked missed/failed rather than claiming success. An EPG refresh that changes a saved programme's times flags the change for review and retains the accepted timer until edited.

The initial file strategy saves the original stream without re-encoding where supported, using MPEG-TS output first. Alternative containers are enabled only after compatibility validation. A recording receives a safe filename from its channel, programme and date, without allowing title text to escape the selected folder. In-progress files are distinguishable from final recordings. Interrupted recordings are preserved when playable and identified as partial.

## Storage

Windows and macOS use a selected writable folder on an internal or connected drive, with platform permission handling appropriate to the selected native framework. The app checks destination availability and write access before starting. Android uses a selected accessible local directory through the system storage picker and retains its permission where supported; removable storage is offered only when the device exposes it as a writable destination.

Local recording writes to the selected device storage. It does not upload recordings to the metadata backend. Before recording, the app checks free space where the storage provider supports it. During recording it monitors write errors and available space, reserves a configurable minimum (initial default 1 GiB), and stops cleanly before exhausting that reserve where measurable. Unknown free space is shown as unknown. Existing recordings are not deleted automatically.

The recordings screen provides title, channel, time, duration when known, size, status, playback and user-initiated deletion. A disconnected destination or revoked storage permission creates a visible failure; the app does not silently write somewhere else.

## Scheduling and device lifecycle

Windows scheduling uses an OS-integrated background mechanism. Closing the main window does not cancel a job. Optional wake-from-sleep is offered only where system settings and hardware permit it; recording cannot start while the machine is powered off.

Android scheduling uses native alarms and an appropriate foreground recording service, with a visible notification and stop control. Exact-alarm access is requested where required. Battery restrictions, service limits and manufacturer behaviour are part of device validation. Swiping the UI away must be tested separately from force-stopping the app; force-stop or loss of permission must never be represented as a reliable unattended state.

macOS uses a per-user background recorder whose registration, storage access and lifetime are validated on the supported OS versions. Closing the main window must not silently stop an active job. Initial scheduled recording requires the Mac to be awake and the user signed in; lid closure, sleep, logout and power-off can prevent a timer from running. Wake-from-sleep is not promised until separately implemented and demonstrated. Future jobs are restored on resume and missed recordings remain visible.

Connectivity loss and insufficient peers can cause gaps. Retries are bounded, preserve the recording's scheduled end and report partial outcomes. Buffered live delay and EPG inaccuracies are handled with padding rather than a promise of frame-accurate recording.

## Optional DizyServer recording

A later, explicitly selected destination runs the engine and recorder on DizyServer and saves to a configured server volume. Device power is not required for that job. The server provides authenticated recording status and downloads; transfer to device storage happens afterwards. This mode does not claim to write directly into an offline phone or PC. It has independent quotas and storage, and is deployed separately from the metadata service.

## Integration and distribution boundaries

Public release targets are a Windows executable installer, a release-signed Android APK and a macOS installer package containing the native application. Versioned artifacts include platform/architecture names, checksums, supported OS versions, engine setup instructions and recording limitations. Signing credentials are kept outside the repository. Mac distribution uses Developer ID Application for the app, Developer ID Installer for the package and Apple notarization. Android retains its release key so users can install future updates. The Windows application and installer are signed for public releases. See the [distribution plan](../../DISTRIBUTION.md).

Apple Silicon and Intel Mac support are validated independently; a universal Mac build is advertised only after every native dependency supports both architectures. The initial repository is private. Public downloads require a public release location; this setup does not change repository visibility, publish binaries or enroll in an app store. Google Play and the Mac App Store are separate distribution decisions.

VLC/libVLC and Ace Stream components have different licences. The exact source components, binary distribution permissions, notices and any engine access requirements must be documented before bundling them. The project does not rename proprietary Ace Stream binaries or remove their notices. Public distribution of bundled channels or guide data requires appropriate source permissions. Feasibility tests use permitted streams and synthetic fixtures where possible.

Feed parsing limits file size and programme count, disables external XML entity resolution, and validates configured remote URLs and redirects. Playback engine addresses are explicitly configured local/trusted endpoints, separate from public feed fetches. Secrets, recordings, downloaded binary dependencies and runtime databases are not committed to source control.

## Acceptance criteria

1. A current playlist can be imported, cached and refreshed without losing favourites or manual mappings; duplicate and unavailable candidates are visible.
2. A selected permitted channel plays on Windows, Android and macOS with clear errors and clean session shutdown. Windows/Android installed-engine startup and the Mac's documented engine connection are each demonstrated.
3. XMLTV listings match the correct channel and region; UTC offsets and UK daylight-saving transitions display correctly.
4. Record now creates a playable original-quality file in the selected storage location and stops at the requested time.
5. An EPG timer starts and stops with its saved padding, persists across app restart, and reports missed or partial recordings accurately.
6. Closing the player UI does not silently cancel an active recording; schedule and stream-session conflicts are handled explicitly.
7. Low space, unavailable storage, revoked permission and interrupted connectivity produce visible states and preserve usable partial files.
8. Windows background/wake behaviour, Android screen-off/reboot/battery restrictions and macOS background/sleep/logout behaviour are demonstrated on the intended devices before reliability claims.
9. The initial application work does not deploy to DizyServer or alter DizyTrades/DizyChat without a separate deployment request.
10. Windows `.exe`, Android `.apk` and Mac `.pkg` artifacts install, launch and upgrade on their advertised platforms. Public builds pass their signing checks, including Mac notarization, and document any separate engine requirement.

## Evidence and remaining validation

The [directory documentation](https://search-ace.stream/doc) describes its playlist export. The [Ace Stream playback API](https://docs.acestream.media/developers/start-playback/) describes HTTP stream output and session control, and its [Android guide](https://docs.acestream.media/developers/running-engine-android/) describes service startup. [libVLC](https://www.videolan.org/vlc/libvlc.html) provides an embeddable player; [VLC stream output](https://docs.videolan.me/vlc-user/desktop/3.0/en/advanced/streaming/standard_introduction.html) documents file output and remuxing.

The [XMLTV specification](https://github.com/XMLTV/xmltv/blob/master/xmltv.dtd) defines programme times and channel IDs. Android documents [selected-folder access](https://developer.android.com/training/data-storage/shared/documents-files), [alarms](https://developer.android.com/develop/background-work/services/alarms) and [foreground services](https://developer.android.com/develop/background-work/services/fgs/service-types). Windows documents [scheduled wake](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-waketorun).

The [Ace Stream product list](https://docs.acestream.media/products/) and [desktop-engine guide](https://docs.acestream.media/developers/running-engine-desktop/) list Windows, Android and Linux routes without a native Mac engine. Apple documents [Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates) and [notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution); Android documents [release signing](https://developer.android.com/studio/publish/app-signing), and Microsoft documents [SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool).

These references establish an integration route, not a completed prototype. Actual playlist contents, guide-source coverage, exact dependency builds, Mac engine connectivity, Android recording compatibility and unattended recording behaviour remain validation work in milestone 1. Supported OS versions and CPU architectures are recorded from that evidence before application implementation and public packaging.

## Favourites, backups and timezone additions

Each client has a persistent favourites list and a favourites-only channel filter. Catalogue refreshes preserve saved favourites by stable stream identifier. Local versioned JSON backups cover channel listings, favourites, settings, manual XMLTV mappings and timers. Video files and device storage permissions are excluded. Restore validates the whole file before replacing state, resets recording storage, marks expired timers missed and pauses other restored timers until rearmed. See [backup format](../../BACKUP-FORMAT.md).

Automatic device timezone is the default, with manual IANA timezone selection. An EPG offset in minutes corrects newly imported listings. Programme and timer instants remain UTC; DST, travel and display changes do not shift accepted recordings. Guide labels include the local timezone abbreviation so repeated clock-change hours are distinguishable.

The desktop alpha uses a detached recording worker: closing the UI leaves it running. After a reboot users must reopen the app to restart it. Per-user auto-start/wake integration is a later validation gate. Android uses native exact-alarm permission and a visible foreground recording service; reboot recovery rechecks destination grants.

## EPG country, genre and stream categories

The channel browser and guide expose shared country, genre and stream-type filters. Country uses explicit playlist country metadata or recognized country tags in source groups; missing data stays Unspecified. Genre uses playlist groups/genre fields plus XMLTV programme categories. TV/radio and Ace Stream/HTTP are independent stream classifications. Channel names and languages are not treated as proof of country. Filters never alter saved timers or favourites.
