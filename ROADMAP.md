# DizyTV roadmap

## Native alpha — implemented

- Native Qt apps for Windows/macOS and Kotlin Android app with embedded libVLC.
- Playlist import/cache, stable IDs, search, favourites and country/genre/type filters.
- Saved category edits preserved through refresh and portable backup/restore.
- XMLTV sources, now/next, programme grid and manual channel mappings.
- Automatic/manual timezone, daylight-saving display and guide correction; fixed UTC timers.
- Record now, padded EPG timers, overlap checks and one recorder per device.
- Selected local folders, persistent jobs, preserved partial segments and recording playback/deletion.
- Detached desktop recorder; Android exact alarms, foreground notification and reboot recovery.
- Local JSON backup/restore with destination reset and explicit timer rearming.
- Windows EXE, Apple Silicon/Intel Mac PKGs and universal Android debug APK built in CI, with checksums and licence notices.

See [build verification](docs/BUILD-VERIFICATION.md) for actual evidence. Successful builds do not establish physical-device acceptance.

## Next — device acceptance

- Fresh install and upgrade on Windows x64, Intel Mac, Apple Silicon Mac and Android; include Huawei P30/Android 10.
- Live playback through separately installed engines; Mac connects to a reachable Windows/Linux engine.
- Record/replay permitted live streams, including scheduled recording with the main UI closed.
- Measure XMLTV coverage and mapping across representative countries and genres.
- Test storage removal, low space, engine/stream loss, Android screen-off/reboot/permissions and vendor battery restrictions.
- Confirm upgrades preserve favourites, category edits, mappings, timers and recording history.

Desktop sleep/wake and automatic recorder startup after reboot are not implemented. Android background behaviour needs device evidence before reliability claims.

## Next — public distribution

- Make the source repository public and set About text/topics. These owner settings cannot be changed through the connected file tools.
- Select the DizyTV source licence and finish third-party source/relinking requirements.
- Configure Windows signing, a retained Android release key, and Apple Developer ID signing/notarization.
- Publish durable versioned downloads and release notes after device acceptance. Current CI artifacts expire after 30 days and require GitHub access.

## Later — DizyServer integration

- Optional cached catalogue/EPG service.
- Explicit **Record on DizyServer** destination, separate worker, authenticated access, quotas and downloads.
- Deploy only when requested; retain local recording and keep existing Dizy services separate.

Simultaneous multi-channel recording, series recording, timeshift and catch-up/VOD are later work. A self-contained Mac Ace Stream engine also requires a separate feasibility and redistribution check.
