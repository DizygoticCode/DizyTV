# DizyTV — how to use it

[← Back to README](../README.md) · [Native downloads](https://github.com/DizygoticCode/DizyTV/releases) · [Build checks](BUILD-VERIFICATION.md)

This guide covers the published **0.1.15-alpha** desktop release. Some improvements noted below are in [PR #23](https://github.com/DizygoticCode/DizyTV/pull/23) and **are not yet in the release installers**.

## 1. Install and start

- **Windows:** Download the native Windows `.exe` installer from [the GitHub release](https://github.com/DizygoticCode/DizyTV/releases/tag/v0.1.15-alpha), close DizyTV, finish any active recording and install. VLC **3 x64** and an independently installed Ace Stream engine are used for Ace playback; direct HTTP/HLS does not need Ace.
- **Android:** Download the APK and install using Android's permitted app installation flow. Use the matching engine app for Ace streams if needed. These test APKs have CI debug signing and are not guaranteed to update in place over previous builds; make a backup before changing them.
- **macOS:** Use the `.pkg` for your Mac CPU architecture (Apple Silicon or Intel), install VLC 3 and configure a reachable Ace Stream engine separately. The Mac app does not include its own engine.
- **Linux (unreleased):** Native Debian `.deb` packaging and the separately installed Linux Ace `start-engine` launcher are being tested in PR #23. See [Linux setup](https://github.com/DizygoticCode/DizyTV/blob/feat/progressive-health-buffering-linux-0116/docs/LINUX.md). Do not treat PR build artifacts as a verified final release.

DizyTV does not bundle channels or an IPTV subscription. It imports playlists you choose. A listed channel is **not a promise of playback**, local availability, programme rights, or supported encryption.

## 2. Add channels

1. Open **Settings**. Under **Channel playlists**, keep or add M3U URL lines. Select **Add built-in free playlists** to add the app's presets without losing existing URLs.
2. For show marathons and loops, choose **Add 24/7 show / sitcom channels**. Optional UK retransmission and US FAST sources have separate opt-in buttons. Some lists have regional or DRM restrictions.
3. Save settings and click **Refresh channels**. Importing playlists may take a little time and always depends on the source.
4. Use sidebar **Playlist**, **Country**, **Category**, **EPG genre**, and **TV / Radio / stream** filters. Select **24/7 Shows & Loops** from **Category**. In 0.1.15 there is also a 24/7 shortcut button; PR #23 removes the redundant button while keeping the category.
5. Use **Ctrl+K** (or the large search near the top) to find channels **and programme names** across the full imported catalogue, even when sidebar filters are active.

**UK FAST programme listings:** Plex UK, Samsung TV Plus UK and Pluto TV UK M3U sources have matching XMLTV guides. In 0.1.15 use **Add built-in free playlists** followed by **Add matching UK FAST programme guides** before saving. In PR #23 there is a simpler **Add UK FAST playlists + matching guides** button that adds both sets together. If there are already 32 playlists or 20 guides, remove an unused entry first.

## 3. Import and view the programme guide

1. In Settings, keep or add XMLTV source URLs and save.
2. Choose **Refresh guide** on the main toolbar.
3. Open **TV Guide**. It shows **all channels matching the current filters**, including those without an EPG match. Scroll through the selected channels.
4. If a programme is missing, select its channel and click **Map EPG** to choose the correct guide identity. Don't guess regional variants.
5. Leave **Timezone** on **Automatic** or choose your preferred timezone. You can adjust **EPG time correction** if a source uses the wrong offset.

## 4. Watch TV and adjust playback

- Select a channel and press **Play** or double-click it. Direct HTTP/HLS should play without Ace. Ace content requires a working engine and peers.
- Use **CC Subtitles** for the tracks carried by the broadcaster. You can disable captions or load a local subtitle file; there is also opt-in offline Vosk transcription on desktop.
- **Cinema** uses the app window; **Screen** uses fullscreen; **Pop out** opens a separate TV window while keeping the guide accessible.
- **LIVE**, **Pause**, and the 30-second controls depend on available DVR/seekability. Experimental local timeshift is optional in Settings and works only for supported clear stream formats.
- If a channel stalls, try direct playback without timeshift, note whether sound continues and whether **LIVE** restarts it. A 200/OK HTTP check is not proof that video frames can decode.
- **In progress in PR #23:** Settings → adjustable direct HTTP/HLS buffering; Tools → System usage shows CPU, RAM and VLC decoder counters. These are not in the published 0.1.15 installer.

## 5. Favourites, hidden channels, and health checks

- Select a channel, then click **★ Add / remove favourite**; use **Favourites only** to narrow the list and guide.
- Click **Hide / restore selected** to hide a channel from the normal catalogue and searches. Tick **Show disabled** to see and restore hidden entries.
- In **Tools → Check channel health**, you can test a selected stream or the next 40 HTTP streams. HTTP 403, timeouts and Ace streams are **not** treated as proven missing. A missing endpoint needs **two consecutive HTTP 404/410 checks** before optional hiding; nothing gets deleted.
- **In PR #23:** a progressive all-channel scan with progress/stop controls and **Tools → Find duplicate channels** with manual hide/restore and a local last-health-result column. No automatic deletion or merge of duplicates.

## 6. Record programmes

1. In **Settings**, choose a **Local recording folder** and leave enough free space.
2. To start saving the current stream, select a channel and click **Record**.
3. To schedule a broadcast, open **TV Guide**, right-click a programme and choose the recording action.
4. Check **Recordings** for queued, active, completed, partial, or missed files.

One recording runs at a time per device. Desktop recording can continue after closing the DizyTV window **while the computer remains awake**; it cannot wake a sleeping PC. After reboot, open the desktop app to resume timer handling. Android scheduling also depends on alarm permissions, storage and background execution policies.

## 7. Back up and troubleshoot

Use **Tools → Save local backup** before changing test builds. **Restore local backup** restores preferences, playlists, favourites and timer definitions but does not restore video files or storage permissions. After restoring, select your recording location and rearm any paused timers.

If importing or playback fails:

- Try another legitimate channel from the same playlist. HTTP/HLS endpoints can expire or have inaccessible media segments even when the manifest responds.
- Use **Source status** to see which playlist imported and which failed.
- Inspect **Tools → Check channel health** for an HTTP hint, not a conclusive codec test.
- Check VLC 3 installation and your active stream subtitles/video decoder settings. Direct HLS performance is different from Ace engine peer health.
- For Windows updater errors, close the visible app and finish recordings first. The installer protects an active recorder worker rather than indiscriminately killing it.

More details: [Linux](https://github.com/DizygoticCode/DizyTV/blob/feat/progressive-health-buffering-linux-0116/docs/LINUX.md) · [Distribution](DISTRIBUTION.md) · [Backup format](BACKUP-FORMAT.md) · [Older release notes](RELEASE-NOTES.md).
