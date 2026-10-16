# Desktop stability and recording consolidation

Baseline: `e360f91` on main, after PR #37 and the published 0.1.18-alpha.
This is an unreleased feature branch. Release metadata and assets stay unchanged.

The owner's 16 October task is the specification: eliminate confirmed GUI
blocking paths, make compatible cached replay usable, record clear HLS/TS,
repair independent broadcast/Vosk subtitle lifecycle defects, and preserve
working source diagnostics and detached recordings. Physical-device success
is not inferred from source tests or native CI.

## Implementation and verification

- [ ] Reproduce blocking native-player calls with slow fakes and a Qt heartbeat.
  Serialize native calls on one worker, expose cached snapshots, coalesce stale
  channel requests, and close without joining on Qt. Test rapid switches,
  errors, subtitle commands, and late completions.
- [ ] Reproduce replay selection and cache teardown with local HLS/TS fixtures.
  Anchor replay away from the live edge; preserve capture while replaying and
  pausing; move disk setup and snapshots off blocking GUI paths. Display
  actual seconds/bytes separately from configured maximums.
- [ ] Record bounded, clear HLS with MPEG-TS segments while retaining direct
  TS and detached timers. Reject encryption/unsupported formats honestly.
  Test cancellation, partial files, storage reserve/limits and worker survival.
  Show complete failure details in Recordings.
- [ ] Reproduce broadcast track restoration after surface changes separately
  from Vosk overlay/restart lifecycle. Test Off, resize, dock/popout/fullscreen
  ownership and stale callbacks; native rendering remains a device gate.
- [ ] Audit catalogue/guide/state/worker callbacks for GUI IO and unsafe signal
  delivery. Batch expensive UI rebuilding and persist refresh data off Qt.
  Add slow-operation and large-catalogue regressions.
- [ ] Correct the exact official signer subject and machine-wide Ace engine
  detection with mocked installer tests; preserve active recording protection.
- [ ] Run all source suites, metadata/syntax/startup checks; review the complete
  branch independently and resolve actionable findings before native CI.
- [ ] Open one consolidated PR, run Windows, both Mac architectures, Linux and
  Android builds once ready, and update issues with verified evidence and
  remaining physical checks. No merge/tag/release without owner approval.

## Review focus

Slow or hung native calls must not retain an unbounded command queue. Old
callbacks must not tune a new channel or resurrect captions after Off/close.
Disk stalls/recorder locks must not hold Qt or stop active detached recordings.
Replay eviction and stream discontinuities must fail visibly. HLS encryption,
oversized manifests/fragments, interrupted downloads and exhausted storage
must preserve partial recordings and produce honest, private diagnostics.

No new package dependency, user-data migration/deletion, proprietary Ace
bundling, source/rights bypass or Android desktop-feature parity is intended.
