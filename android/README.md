# Native Android alpha

Build with JDK 17, Android SDK 36 and Gradle 8.13:

```bash
gradle -p android testDebugUnitTest lintDebug assembleDebug
```

The native Kotlin app uses libVLC for embedded playback. Install/start Ace Stream separately and configure the engine URL (normally `http://127.0.0.1:6878`). Select storage with Android's folder picker; the app retains the granted URI permission. Grant exact-alarm access for scheduled recording and notification access for recording status.

The APK is a debug development build, not a retained-key public release. Device testing must cover screen-off, reboot, battery restrictions, unavailable engine, SD-card removal and revoked storage permission. Force-stopping the app prevents reliable unattended recording until reopened. Android's foreground-service `specialUse` subtype is declared for user-requested local DVR recording; any future Play distribution requires Google's review of that use.
