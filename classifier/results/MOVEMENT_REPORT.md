# Exercise classifier: movement and person-crop fallback

The phone continues to send HTTPS JPEG frames to the Mac. The Mac now combines the original SigLIP2 image classifier, a person-centred crop retry, and pose-based movement evidence. This is an improvement to the prototype, not a validated general-purpose exercise recogniser.

## Pipeline

1. Classify the complete frame across all 22 model classes. Accept only a supported class with score ≥0.65 and margin ≥0.15.
2. Extract pose with Google's MediaPipe Pose Landmarker Full, CPU delegate. Use only visible in-frame joints and correct image aspect ratio before calculating angles.
3. If the image output is Unknown, retry the image model on a square crop around the detected person using the same acceptance rule.
4. If still Unknown, use a completed ordered movement cycle. Squats require standing, knee flexion with hip descent, then extension. Static standing/crouching is insufficient for this fallback. Push-ups and lateral raises have separate conservative cycle rules, but their pose-only recall is poor in these tests.
5. The native app displays a label after three identical responses. Movement labels persist briefly after a confirmed cycle to accommodate this display rule, then expire.

The pose model is learned; the movement decision rules are heuristic. Neither the image score nor a completed cycle is a calibrated probability of correctness. A high model score can still be wrong.

Each camera start creates an opaque `X-Movement-Session` UUID. Temporal histories are isolated by client and session, expire after inactivity, and have a bounded count. Missing pose suppresses the output; a short gap can preserve an incomplete cycle, while sustained gaps, timestamp reversals, abrupt translation and large scale changes reset it. Multiple detected people suppress pose evidence. Stateless clients keep the original image API.

## Real video results

Evaluation uses ideal 2 Hz sampling and the app's actual three-response display requirement. A target clip succeeds if the correct name is displayed at least once after three matching predictions. A negative clip succeeds if no target name is displayed. These are **clip detection results, not frame accuracy**; startup and Unknown intervals remain in the saved per-frame results.

| Evaluation class | Image alone | Image + crop + movement |
| --- | ---: | ---: |
| Squat | 0/5 | 4/5 |
| Push-up | 1/10 | 7/10 |
| Lateral raise | 11/11 | 11/11 |
| Non-target rejection | 30/30 | 30/30 |
| All clip decisions | 42/56 (75.0%) | 52/56 (92.9%) |

No accepted wrong exercise names were observed in these 56 clips. Four target clips remained Unknown. Zero observed false positives in a small sample does not establish a low false-positive rate in deployment.

The 30-clip selection combines 20 clips from the separate `similar_dataset` folder of RickyRiccio's dataset and the original ten UCF smoke-test clips. The additional 26 clips were selected from FitCenter before evaluation: the eleven remaining lateral-raise files after the first five development files, and five lexicographically first clips each of deadlift, bench press and chest fly. The additional selection had no squat or push-up clips. The 25 development clips scored 25/25 after iteration; that is a tuning result and must not be presented as held-out accuracy.

Folder separation does not establish participant-disjoint sources, and overlap with the pretrained image model's undisclosed training material cannot be ruled out. These are small convenience samples with no independent label audit. Idle, walking, sitting down, occlusions, live phone capture and diverse environments need separate evaluation.

The anatomical animation web demos are a separate failure case: all six target animation clips remained Unknown. Pose and image models both fail on this stylised rendering domain. Do not combine their results with the real-video headline or claim screen-content/animation support.

## Speed and integration

On this Mac, pose extraction median was about 16 ms; p95 was about 23 ms on the additional evaluation clips. A real-time HTTPS squat replay through the phone backend on port 8443 succeeded, with median round-trip time 64 ms and p95 86 ms after the first request. These local replay timings exclude phone capture and Wi-Fi latency. Detection also waits for a movement cycle and three matching responses; network inference time is not time to first recognition.

Seventeen backend behaviour/API/session tests pass. Native Swift session-lock tests also pass. The iOS simulator build passed after the session-header integration. The app session ID was reconciled with the app chat's shared request implementation; a fresh UUID is sent on every camera start.

## Reproduce

```sh
.venv/bin/python exercise_demo/download_motion_data.py
.venv/bin/python exercise_demo/evaluate_previous_video.py
.venv/bin/python exercise_demo/download_lateral_data.py
MPLCONFIGDIR=.cache/matplotlib HF_HUB_OFFLINE=1 .venv/bin/python exercise_demo/evaluate_movement.py --split development --image-baseline
MPLCONFIGDIR=.cache/matplotlib HF_HUB_OFFLINE=1 .venv/bin/python exercise_demo/evaluate_movement.py --split holdout --image-baseline
MPLCONFIGDIR=.cache/matplotlib HF_HUB_OFFLINE=1 .venv/bin/python exercise_demo/evaluate_movement.py --split final --image-baseline
.venv/bin/python -m unittest discover -s exercise_demo -p 'test_*.py'
.venv/bin/python exercise_demo/replay_hybrid_api.py --endpoint https://127.0.0.1:8443
```

Pose weights: `.cache/pose/pose_landmarker_full.task`. Model URL: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task. This Mac's MediaPipe initialisation needs a working graphics context even with CPU inference; the sandboxed process failed to initialise, while normal local execution worked.

Saved results: `movement_development.json`, `movement_holdout.json`, `movement_final.json`, `movement_web.json`, `movement_api_replay.json`. Local dataset manifests record per-file SHA-256 values. Files under `data/` remain local and are ignored by git. No phone camera frames are saved. An explicitly started live diagnostic check saves numeric results only in `movement_live.json`.

## Sources

- Google Pose Landmarker Python documentation: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python
- Real/synthetic exercise archive and dataset description: https://huggingface.co/datasets/RickyRiccio/Real_Time_Exercise_Recognition_Dataset
- Real lateral raises and confusable exercises: https://github.com/krishwin/FitCenter-1
- Original UCF subset: https://huggingface.co/datasets/ambarishnarayan/UFC101_Subset_Workout

The source archive describes a noncommercial share-alike licence; underlying media sources have their own terms. This workflow downloads selected clips locally for testing and does not redistribute them.

## Live phone trial and today’s session lock

The user confirmed the phone displayed Squat, then reported it was brief. Numeric live diagnostics contained two completed squat cycles attributed to the movement fallback while all image predictions were Unknown. Replaying the saved joint features exposed an early ankle-reference drift and an expiry between repetitions. The fix re-anchors feet during the standing phase and refreshes an already confirmed label during continuing motion. The same feature replay then retained Squat through subsequent repetitions and counted three completed cycles. The 56-clip metrics above were rechecked after that fix.

At the user’s request, the native demo UI now uses **Start classifying** / **Re-classify**, a live consistency percentage, and a green lock at ≥90% agreement over a full ten-reading window. Unknown readings count against agreement and can never lock. A current response must match the leading known label. Once locked, the name and percentage stay fixed and classification uploads pause; camera preview continues. Re-classify resets votes and UUID without restarting the camera. Stop/backgrounding clears the session. The percentage does not measure actual classification accuracy.

The 56-clip table uses the earlier three-consecutive-response detection metric to isolate classifier changes. It is not a benchmark of the newer ten-reading lock acquisition time. A short clip can be recognised under that metric and still be too short to reach the session lock.
