# DizyTV — how to use it

[← Back to README](../README.md) · [Native downloads](https://github.com/DizygoticCode/DizyTV/releases) · [Build checks](BUILD-VERIFICATION.md)

This guide covers **0.1.16-alpha** desktop changes. The new release artifacts publish only after GitHub's gated five-platform build succeeds; real-device playback and large-catalogue performance are not guaranteed.

## 1. Install and start

- **Windows:** Download the native Windows `.exe` installer from [the GitHub release](https://github.com/DizygoticCode/DizyTV/releases/tag/v0.1.16-alpha), close DizyTV, finish any active recording and install. VLC **3 x64** and an independently installed Ace Stream engine are used for Ace playback; direct HTTP/HLS does not need Ace.
- **Android:** Download the APK and install using Android's permitted app installation flow. Use the matching engine app for Ace streams if needed. These test APKs have CI debug signing and are not guaranteed to update in place over previous builds; make a backup before changing them.
- **macOS:** Use the `.pkg` for your Mac CPU architecture (Apple Silicon or Intel), install VLC 3 and configure a reachable Ace Stream engine separately. The Mac app does not include its own engine.
- **Ubuntu Linux x64 (experimental):** Download the native `.deb` and run `sudo apt install ./DizyTV-0.1.16-alpha-linux-amd64.deb`. System VLC 3/libVLC is required; the optional Ace `start-engine` is installed separately. Other Debian-family distros, Wayland and native playback need field testing. See [Linux setup](LINUX.md).

DizyTV does not bundle channels or an IPTV subscription. It imports playlists you choose. A listed channel is **not a promise of playback**, local availability, programme rights, or supported encryption.

## 2. Add channels

1. Open **Settings**. Under **Channel playlists**, keep or add M3U URL lines. Select **Add built-in free playlists** to add the app's presets without losing existing URLs.
2. For show marathons and loops, choose **Add 24/7 show / sitcom channels**. Optional UK retransmission and US FAST sources have separate opt-in buttons. Some lists have regional or DRM restrictions.
3. Save settings and click **Refresh channels**. Importing playlists may take a little time and always depends on the source.
4. Use sidebar **Playlist**, **Country**, **Category**, **EPG genre**, and **TV / Radio / stream** filters. Select **24/7 Shows & Loops** from **Category**. The redundant separate 24/7 shortcut was removed in 0.1.16; the category remains.
5. Use **Ctrl+K** (or the large search near the top) to find channels **and programme names** across the full imported catalogue, even when sidebar filters are active.

**UK FAST programme listings:** Plex UK, Samsung TV Plus UK and Pluto TV UK M3U sources have matching XMLTV guides. Use **Add UK FAST playlists + matching guides** in Settings to add the matched playlists and EPG together without overwriting existing sources. If there are already 32 playlists or 20 guides, remove an unused entry first.

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
- **0.1.16 desktop:** Settings → adjustable direct HTTP/HLS buffering (1–12 seconds, 4 default); Tools → System usage displays local CPU, memory and available VLC counters. A stalled-picture warning helps distinguish video freezes from continuing audio.

## 5. Favourites, hidden channels, and health checks

- Select a channel, then click **★ Add / remove favourite**; use **Favourites only** to narrow the list and guide.
- Click **Hide / restore selected** to hide a channel from the normal catalogue and searches. Tick **Show disabled** to see and restore hidden entries.
- In **Tools → Check channel health**, you can test a selected stream or the next 40 HTTP streams. HTTP 403, timeouts and Ace streams are **not** treated as proven missing. A missing endpoint needs **two consecutive HTTP 404/410 checks** before optional hiding; nothing gets deleted.
- **0.1.16 desktop:** progressive scans have progress/stop controls and rate-limit handling. **Tools → Find duplicate channels** offers manual hide/restore and saved check history. No automatic deletion or merge of duplicates.

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

More details: [Linux](LINUX.md) · [Distribution](DISTRIBUTION.md) · [Backup format](BACKUP-FORMAT.md) · [Older release notes](RELEASE-NOTES.md).
