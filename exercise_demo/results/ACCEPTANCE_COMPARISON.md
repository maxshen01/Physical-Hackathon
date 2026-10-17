# Acceptance-policy comparison

Same 15 real-person clips / 266 sampled frames as the Kinevoa replay test. No training or weight changes. Policies compared after the app’s three-consecutive-result rule. These are exploratory tuning results on a tiny reused sample, not held-out validation.

| Policy | Squat | Push-up | Lateral raise | Unrelated rejected (majority) |
|---|---:|---:|---:|---:|
| current | 0/3 | 1/3 | 3/3 | 6/6 |
| relaxed | 0/3 | 1/3 | 3/3 | 6/6 |
| guarded_three | 0/3 | 3/3 | 3/3 | 6/6 |
| three_only | 0/3 | 3/3 | 3/3 | 1/6 |

- current: top of all 22 classes, minimum 0.65 score, minimum 0.15 margin.
- relaxed: top of all 22, minimum 0.25 score, minimum 0.03 margin.
- guarded_three: choose among target labels only; top absolute score ≥0.10, ≥60% of target score mass and ≥0.15 relative margin. Conditional score is not calibrated confidence.
- three_only: force whichever target has highest score, with no rejection.

Why squat still fails: on all three squat clips, squat was never even the best of the three target scores. Most full-model winners were unrelated labels, including tricep dips, Russian twist, and barbell curl. Lowering acceptance cannot repair that ordering.

Guarded_three also produced 8 wrong displayed frames on squat clips and 11 on unrelated clips. Majority rejection alone hides brief false positives. Therefore no lower-threshold/three-way policy was enabled by this session.

Integration fix: iOS now sends X-Movement-Session with a fresh UUID per camera start. The existing hybrid server source from the classifier session required this header to enable pose, person crop and temporal fallback. The deployed server was previously the old image-only process; it has now been restarted with HybridClassifier. App request/response format remains exercise-name-only.

## Live integration smoke test

After deploying the session-enabled app and hybrid service, replayed one clip each at approximately 2 Hz through the shared native client. Squat was displayed correctly on 7/20 frames, push-up 11/20, lateral raise 10/12; shoulder press remained Unknown on 18/18. Squat majority remained Unknown because detection starts after movement evidence and does not label every phase. This is a four-clip integration smoke test, not an accuracy benchmark. Full outcomes: `kinevoa-hybrid-live-test.json`.
