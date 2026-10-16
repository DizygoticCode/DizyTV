# Recovery checkpoint: Windows field-test fixes

Baseline: main `e360f91`, published 0.1.18-alpha unchanged.
This checkpoint preserves unfinished engineering after an interrupted session;
it is not a release candidate and the new regressions are intentionally red.

## Findings preserved

* Qt invokes native VLC stop/play/state/stat/track calls synchronously. A local
  slow-native regression measured `play_url()` blocking its Qt caller for
  0.252 seconds when native stop took 0.25 seconds. An unintegrated serialized
  worker prototype is in `dizytv/player_worker.py`; it still needs integration,
  completion/error handling review and rapid-switch/shutdown regressions.
* Timeshift `snapshot()` takes the same lock as disk writes and performs
  eviction/disk checks itself. Qt timers and seek controls call it. Constructor
  filesystem work also occurs on Qt. These paths need isolation.
* `replay.m3u8` remains a live playlist. `EXT-X-START:TIME-OFFSET=0` does not
  force VLC 3 to start at the oldest fragment; VLC may choose the live edge.
  Finite anchored replay and explicit continuation are under investigation.
  `starting_seq()` passes variable-duration boundary tests. Direct TS duration
  uses arrival time instead of PCR media time; signed HLS URLs are used as
  identity instead of media sequence. Late capture writes can race cache close.
* Cache UI rounds duration to whole minutes and bytes to GiB, hiding short
  buffers. Configured capacity is not actual cached footage.
* Recorder explicitly rejects mpegurl. Clear MPEG-TS HLS can be saved without
  transcoding or a new dependency. Tests cover encryption/session-key/fMP4/
  byte-range rejection, partial files, cancellation, reserve and byte caps.
  Existing direct TS and detached scheduling must remain intact.
* Broadcast `sync_subtitles()` returns for a manually selected track without
  restoring it after output recreation; auto-selection also short-circuits
  unchanged track lists. Vosk overlay recreation requeues already visible text
  through the configured delay. A queued restart can outlive CC Off. FFmpeg
  process management in `stop()` also needs to move off Qt.
* Catalogue rendering rereads locked state and creates every list item on each
  filter change. EPG refresh completion writes/fsyncs guide JSON on Qt. Even
  `Store.try_read()` only avoids lock waiting, not slow disk/JSON processing.
* PR #37 outstanding findings confirmed in source: optional Ace signer regex
  excludes the exact legal `INNOVATIVE DIGITAL TECHNOLOGIES LLC` name; setup
  detection misses both Program Files roots. Signature validity and strict
  vendor matching must remain mandatory. Upgrade protection needs additional
  inspection for workers using a nondefault `--data-dir`.

## Current evidence and constraints

Python syntax check passes for recovered files. The clean baseline full suite
was launched separately in `/workspace/work/dizytv-baseline`; its log is kept
outside the repository. No physical Windows/Mac/Linux/Android tests performed.
No confirmed cause from a real Windows hang dump is claimed.

Use `/workspace/work/dizytv-venv/bin/python`, with `QT_QPA_PLATFORM=offscreen`.
The worktree is `/workspace/work/dizytv-stability`; do not replace it with the
older `/workspace/DizyTV` checkout. Updated owner instruction: no native builds
or merge without approval. Preserve user data, detached active recordings and
all published release assets. Continue from the regressions and findings here.
