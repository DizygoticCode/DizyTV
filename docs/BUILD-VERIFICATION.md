# Native alpha build verification

## 0.1.16-alpha — 15 October 2026

The [five-platform PR CI run on `9136c93`](https://github.com/DizygoticCode/DizyTV/actions/runs/38815152069) completed successfully: Windows x64 EXE packaging/upgrade verification, macOS arm64 and Intel PKGs, Ubuntu 24.04 amd64 DEB with system libVLC, and Android universal debug APK tests/lint/signature. A local full Python/PySide6 run passed **223 tests, zero failures or skips**; macOS arm64 CI retained five expected skips for offscreen/other-platform-only cases. GitHub code re-review reported no major issues. The release publishing step runs after all native jobs succeed on `main`.

Native Linux X11 testing displayed an embedded synthetic HLS video pattern and exercised a stalled-video warning with continued audio. This does **not** establish live stream reliability, geo/DRM access, real-device Ace peer playback or acceptable performance for a 15,000–30,000-channel Windows catalogue. Those remain acceptance checks. See the [PR #23 investigation report](https://github.com/DizygoticCode/DizyTV/pull/23#issuecomment-6202945241) and [Linux instructions](LINUX.md).

---

## Historical 0.1.0-alpha baseline

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

## 0.1.4-alpha candidate (native CI pending)

- Added conservatively verified Free-TV UK vs Freeview XMLTV channel aliases (BBC Two, BBC Four and 5). BBC One/ITV1 remain region-specific: the correct region must be chosen using Map EPG. The public M3U list includes circled stream metadata symbols; the guide matcher removes these and selects only unique results. Explicit user mappings override matching.
- Playback now differentiates HTTP/HLS from Ace streams, reports failed/timed-out streams instead of hanging indefinitely, and starts an existing Windows Ace engine in the background for default loopback configuration. No external engine or VLC binary is bundled with the native installer.
- Android engine availability is checked on a background worker, never the UI thread; if installed but stopped, it offers to open it.
- The 0.1.3 Windows installer preflight and end-to-end upgrade CI are retained; 0.1.4 gets new direct native assets and distinct checksums.

These entries describe intended code coverage only. A real Windows/Android playback test and signed shipping workflow are still outstanding.

## 0.1.5-alpha candidate: source naming and hierarchical browser

- Preserve every original playlist channel name, stream URI, `tvg_id`, favourite/recording identity and manually assigned category/mapping. Use `display_channel_name` / `Domain.displayName` only for user-facing labels, removing provider circle glyphs and trailing technical `@HD/@UK` badges while retaining legitimate brand punctuation such as AT&T and Great! Movies.
- Countries > categories > channels navigator in Windows/macOS and Android. Category fallback derives from genre or safe channel-name/group hints; nothing is silently relabelled in original metadata.
- Optional (unchecked) Windows setup task opens the **official** Ace Stream download site. We do **not** redistribute, download or execute their installer, and normal HLS/HTTP playback never depends on Ace Stream. Installed Windows engine auto-launch is retained; users accept third-party terms themselves.
- CI coverage: Qt country tree, EPG and identity preservation; Android domain naming and categories; explicit external provider setup link; Inno installer upgrade integration. Real video playback and provider engine setup still require device validation.

## 0.1.6-alpha TV player controls — build candidate

Native Windows/macOS: distinct **Cinema** (maximized player in window, with embedded controls) and **Screen** (a Qt fullscreen output window containing the same VLC video frame) modes. Double-click video enters/exits screen fullscreen. The fullscreen surface has dedicated Pause, 30-second rewind, Live, Quick Guide, Info and Exit buttons; the main player has a seek slider and a volume slider. Playing a channel briefly shows its current programme when XMLTV has a match. Searchable Quick Guide chooses another channel in-place. Fullscreen rebinds the existing libVLC video surface; it must not destroy the media player or a detached recorder.

Android: Cinema and immersive full-screen modes (Back exits), quick guide and programme info, video controls, scrub bar, volume. No streaming credentials or channel IDs change.

**Important functional restriction:** Pause/rewind/scrub use libVLC's actual `is_seekable` / `isSeekable` state. If a source exposes no DVR window they refuse to fake a pause/rewind. **This version does not yet implement a universal disk-based rolling live buffer.** The existing detached recording system only accepts direct MPEG-TS for recording; ordinary HLS channel playback works independently, but automatic multi-segment HLS timeshift is a separate future engineering task. No video stream is recorded covertly. Test one seekable and one nonseekable stream on Windows and Android before claiming the DVR functions are reliable.

## 0.1.7-alpha rolling timeshift test gate (experimental)

- Python: bounded ring timestamps, quotas/free-space reserve, packet alignment, direct MPEG-TS HTTP ingest, HLS/TS HTTP ingest and loopback manifest/fragment access, token check, crash cleanup and preservation of unrelated user files.
- Android: native rolling ring cleanup and validation, config migration/defaults, native build and lint; real-world player seek/pause still needs validation on a physical phone.
- Both: storage is opt-in, restricted to 1–240 minutes with up to 32 GiB disk quota; never starts recording in the background on Android when the Activity is paused.
- Windows: preserve 0.1.6 installer idle-recorder upgrade verification; timeshift buffer must not interfere with permanent recording workers.
- Release is an **experimental alpha** requiring device testing. Do not claim universal HLS DVR; VideoLAN live HLS clients may interpret EXT-X-START and sliding playlist windows differently.

## 0.1.8-alpha Windows regression matrix

- Resize main window to 710×480 logical pixels with scrollable toolbars; apply 80% interface scale and Compact/Normal/Large button settings.
- Open a separate windowed TV output while keeping main guide usable, enter/leave fullscreen, restore embedded player and verify the libVLC instance was not replaced.
- Verify mouse-idle popout controls reappear on movement and that volume/seek controls are accessible.
- Verify optional installed Windows engine path and working-directory startup. Confirm no foreign EXE can be selected.
- Distinguish source HTTP 403, 404, 429 and HTML/manifest responses without exposing stream URL query strings.
- Classify BBC Radio1/Radio Asian Network using actual UK Free-TV feed attributes while preserving original IDs, and retroactively organize existing cached state.
- Local rolling HLS playlist exposes sufficient recent fragments to avoid overly aggressive VLC segment expiry. Buffer recovery never overrides an explicit pause.
- Validate Windows in-place installer upgrade and active recorder exclusion on GitHub Actions. **Physical Windows/VLC playback remains mandatory** to confirm real streams/engine/variable-DPI behavior.

## 0.1.9-alpha Windows and guide checks

- Search 2,200+ imported Ace Stream channels via Ctrl+K globally even with HTTP-only filter selected. No 250-row rendering cap in the guide; no XMLTV match still displays the channel.
- Search an upcoming XMLTV title; jump to the correct channel and broadcast hour, or schedule a recording only after user approval.
- Verify programme result pagination (150/page) and all-source matching independent of favourites, category or selected playlist.
- Check transparent pop-out tool controls show/hide above native video without resizing the video or outer TV window; control size follows UI/button scaling.
- In a seekable stream or buffered timeshift: left/right 30s and timeline wheel scroll advance/rewind appropriately, clipped at LIVE or oldest cache. Unseekable streams keep controls unavailable.
- Exercise Windows Ace Engine startup, local API diagnostics, and colour status, then physically check at least one HTTP/HLS and Ace channel.
- Qt offscreen CI verifies layout/content and excludes unavailable native video reparenting. Only a real Windows GUI can validate HWND overlay layering.

## 0.1.9-alpha appearance and public-catalogue verification

- In Windows Settings switch **Green**, **Dark**, and **Light**; repeat with the toolbar theme picker beside DizyTV. Confirm guide text, selected rows, category filters, and pop-out controls remain legible and the video is unchanged; close/reopen to confirm persistence.
- Resize the main window to 480 × 360: **Live TV**, **TV Guide**, and **Recordings** rounded tabs must stay usable via overflow scroll buttons and not overlap the window border. Backup/Restore is under **Tools** in the toolbar. Restore should still require confirmation and leave recordings protected.
- Existing upgrades preserve configured M3U links. Click **Settings → Add built-in free playlists** to add Canada/Australia/New Zealand/South Africa/Singapore/Hong Kong and the Classic/Series/Movies/Comedy/Sports indexes. A fresh profile has the expanded preset set already.
- Filter by each new playlist and check source-status counts. If a stream is present in both a country feed and a Series/Movies feed it should appear in both source filters, **once** under All Playlists, and retain one favourite and guide mapping. Its playback/EPG is not guaranteed.
- Search a favourite 24/7-style programme channel. Channel existence, availability in the UK, and live/EPG continuity must be checked in VLC on Windows; avoid treating third-party M3U links as verified broadcasting rights.
- Recheck Codex fixes: a normally playing direct HTTP/HLS/Ace stream stays green past 18 seconds, and pop-out mouse hover does not hide the control panel on an off-origin secondary display. Do not automatically resume paused timeshift playback.

## Desktop subtitle and offline auto-caption acceptance

1. On an authorized UK/AU/US live channel known to carry subtitles/closed captions, choose **CC Subtitles** in Live TV. Confirm the broadcast tracks appear and change or disable them without restarting playback; allow several seconds after switching channels for VLC to discover HLS tracks. A no-caption channel should show an explicit unavailable status, not fabricated text.
2. Repeat inside the pop-out video player and after docking back into the main DizyTV window. Try an external SRT file, then change channel; the custom captions must not persist across unrelated streams or affect recordings.
3. Change subtitle font, size (12–64 px), colour (especially Black) and vertical position (Bottom/Raised/High) in Settings, restart DizyTV, and check legibility at 80% UI scale and at 480×360 main window size. VLC bitmap captions may not honour text-specific styles.
4. For optional speech-generated captions, install FFmpeg separately and obtain an extracted Vosk model from https://alphacephei.com/vosk/models, then select the model and FFmpeg location in Settings. Do not test until you have a permitted direct stream: a second audio-only connection is created for transcription.
5. Start **CC Subtitles → Generate live subtitles**. Verify spoken words appear as a readable overlay on the playing video (not inside the player-control layout); expect some lag and transcription mistakes. Confirm the overlay stays above native Windows VLC video in both embedded and pop-out modes, and does not intercept mouse clicks. Test on a second monitor away from the desktop origin.
6. Stop captions, change channel, dock/pop out and close DizyTV. Confirm the FFmpeg child process exits promptly, no microphone permission is requested, no audio or transcripts are saved, recordings/timers remain unaffected, and the caption engine is **off by default** after restart. Test the expected graceful message if FFmpeg/model are missing, the source is protected, or timeshift is enabled.
7. Android APK does not gain native speech recognition in this desktop patch; ensure Android CI still passes. Mac must be validated on both Intel and Apple Silicon with actual VLC and packaged Vosk native libraries.


## v0.1.10 native test requirements

Android local timeshift uses short-lived, quota-bounded loopback HLS. CI now exercises deterministic clear HTTP MPEG-TS and HLS fixtures, a replay playlist, local file cleanup and encrypted-HLS fallback; actual libVLC playback on the Huawei device remains an independent human acceptance check. Verify pause/30-second rewind/scrub/return to live on real nonseekable streams, that switching channels and backgrounding erase the temporary fragments, and that programme recordings are undisturbed. Check protected/unavailable HLS sources fall back to ordinary live playback with a useful error. Do not treat successful CI as completed physical-device validation.

## 0.1.11-alpha Windows bundled speech installer tests

On Windows CI, `scripts/stage_windows_speech.py` downloads fixed versioned FFmpeg 8.1.2 and the Vosk Small English US 0.15 model, verifies immutable SHA-256 hashes, stages only the selected executable and expected model tree, then bundles both inside the native PyInstaller/Inno Setup output. The Windows packaged smoke job fails if the executable is missing or fails `-version`, or if the model lacks `am` and `conf` folders. A new unit test covers automatic model/binary discovery and explicit override; another checks safe archive staging. Verify real live-caption legibility and audio sync on a Windows device before a stable release. FFmpeg licensing/source fulfilment still requires review.
