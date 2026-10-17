# Kinevoa app and web-video test

Native app renamed in header, Home Screen display name, and camera permission text; build 2 installed and launched on Sonia’s connected iPhone. Bundle ID retained so this updates the existing app.

The native camera app’s shared RecognitionRequest, PinnedTrust, RecognitionResponse and RecognitionHistory code was compiled as a Mac replay harness. It sent sampled JPEG frames through the real HTTPS `/predict` service and processed the actual responses. No classifier settings were changed.

| Expected | Majority-correct clips | Correct displayed frames |
|---|---:|---:|
| Squat | 0/3 | 0/50 |
| Push-up | 1/3 | 9/55 |
| Lateral raise | 3/3 | 37/43 |
| Unknown | 6/6 | 118/118 |

266 real-person frames; median HTTPS request duration 20 ms in this run (not camera-to-label latency). Three matching predictions are required for a visible target label, so initial frames normally display Unknown.

Conclusion: the transport/decoding/display path passes, and lateral raise worked on these clips. Squat and push-up recognition are not reliable enough to claim demo readiness. Six non-target clips were rejected correctly.

Sources:

- Squat, push-up, shoulder-press and curl: first three lexicographic clips per class in the existing `similar_dataset` source folder of https://huggingface.co/datasets/RickyRiccio/Real_Time_Exercise_Recognition_Dataset .
- Lateral raise: `lateral raise_10.mp4`, `_11.mp4`, `_12.mp4` from https://www.kaggle.com/datasets/hasyimabdillah/workoutfitness-video . Individual-file downloads are ZIPs and were extracted in memory.

An additional nine anatomical-animation videos from https://github.com/luisaraujoc/free-exercise-db-api were tested separately: all six target clips had Unknown as majority output; all three non-target clips were rejected. These are synthetic visuals, not real-person evidence.

Limitations:

- Tiny convenience sample, not a benchmark; no guarantee of subject independence or training-data independence.
- Shared native HTTPS request, CA validation, JSON decoding, and display stabilisation executed on Mac; not an optical phone-camera test.
- First 12 seconds maximum per clip; 2 Hz sampled frames replayed sequentially without real-time delays.
- Classifier weights and thresholds were not changed for this test.
- Synthetic anatomical animations were evaluated separately and not mixed with real-person results.

Full per-frame outcomes: `kinevoa-combined-video-test.json`. Source frames and URLs: `data/real_web_tests/replay.json`. Shared-client harness: `ios/ReplayWebVideos.swift`. Build log: `kinevoa-build.log`.

Reproduce from workspace root (requires downloaded local public clips and running HTTPS backend):

```sh
.venv/bin/python exercise_demo/prepare_real_replay.py
xcrun swiftc -parse-as-library -module-cache-path .cache/swift-module-cache exercise_demo/ios/MoveCamera/RecognitionProtocol.swift exercise_demo/ios/ReplayWebVideos.swift -o .cache/replay-web-videos
.cache/replay-web-videos exercise_demo/data/real_web_tests/replay.json https://172.20.10.3:8443/predict .cache/tls/move-demo-ca.cer exercise_demo/results/kinevoa-real-video-test.json
```
