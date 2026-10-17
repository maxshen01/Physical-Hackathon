# Orbit

An iPhone demo with one guided flow:

1. Tap **Start recording** and perform a squat, push-up or lateral raise. Recognition locks after sufficient agreement; frame uploads then pause.
2. The phone estimates the facing direction and recommends one of eight camera marks and a lens height. If automatic detection is stuck, tap **Choose facing direction** and select the mark the person is looking towards. Tap **Continue · camera mark N**, then move the phone there.
3. Tap **Capture image**. The server extracts image-plane pose features from that one image.
4. Validated features go to the LLM service, followed by ElevenLabs. **Voice feedback plays automatically**; replay and stop controls are available. A transcript remains available if speech fails.

The live camera is used for recognition and placement; no video recording is saved. A captured image is one pose, not a start/peak/finish sequence or a verified repetition. The app never fabricates those stages. Single-image feedback avoids depth/range targets and clinical joint-angle claims.

## Video
[Watch the demo video](../demo-video/orbit-demo.mp4)

## Start the demo

Use Python 3.11 and Xcode 26 (iOS 17+):

```sh
python3.11 -m venv .venv
.venv/bin/pip install -e './classifier[evaluation,test]' -r llm/requirements-dev.txt
.venv/bin/python classifier/tools/download_data.py
cp llm/.env.example llm/.env
```

Fill in `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` in **llm/.env**. Model and voice settings stay on the server. Never bundle keys in the app. The optional recognition fallback uses the separate root [.env.example](.env.example) / `.env.local` settings.

Start the combined HTTPS server with the laptop's Wi-Fi IPv4 address:

```sh
./classifier/tools/run_phone.sh 192.168.1.42
```

This runs `demo:app`, serving recognition, feature extraction and feedback from one address. On first use, or after regenerating the demo CA, copy its **public certificate** and build the app:

```sh
cp .cache/tls/move-demo-ca.cer ios/MoveCamera/move-demo-ca.cer
open ios/MoveCamera.xcodeproj
```

Set `address` in `ios/MoveCamera/ContentView.swift` to `https://192.168.1.42:8443`
(replace the IP), then build/run scheme **MoveCamera** on a physical iPhone.
The current demo uses this fixed address rather than a settings page. Keep both
devices on the same Wi-Fi. The app validates the exact hostname against its
bundled demo CA; redirects are rejected.

Under **Position setup**, set the person's height and starting floor mark (default: mark 5). Choose the person's facing direction if the estimate is wrong, using the labelled control or the tappable diagram. The phone does not verify that you moved to the suggested mark, so keep the subject's direction unchanged and place the phone as instructed. The shown camera angle is an estimate based on that position.

## Components and API

| Component | Purpose |
| --- | --- |
| `ios/` | Guided recognition → placement → image capture → automatic voice feedback |
| `camera_placement/` | On-device heading estimator, eight floor marks and placement presets |
| `classifier/` | Recognition and image-plane feature extraction |
| `llm/` | Validated measurement input, constrained LLM cue selection, ElevenLabs speech |
| `demo.py` | Combines both Python APIs on one HTTPS origin |
| `contracts/` | Recognition and capture HTTP contracts |

`POST /predict` recognises a frame. `POST /capture/image` takes `exercise` and one multipart `file` (JPEG/PNG, ≤1 MB, ≤2 million pixels). `POST /api/feedback` takes the exercise, signed horizontal camera angle and **one snapshot with `phase: "capture"`**. Only quality-checked measurements are included. The original three-stage measurement API and six-second `/capture/features` experiment remain available for compatibility; the patient flow does not use them.

See [LLM API details](llm/README.md), [native setup](ios/README.md), [placement presets](camera_placement/README.md) and [classifier setup](classifier/README.md).

## Verify

```sh
.venv/bin/python -m pytest -q tests llm/tests
.venv/bin/python -m unittest discover -s classifier/tests -p 'test_*.py'
mkdir -p .cache/swift-module-cache
xcrun swiftc -module-cache-path .cache/swift-module-cache camera_placement/ios/PlacementEngine.swift camera_placement/ios/PlacementEngineTests.swift -o .cache/placement-engine-tests
.cache/placement-engine-tests
xcrun swiftc -parse-as-library -module-cache-path .cache/swift-module-cache ios/MoveCamera/RecognitionProtocol.swift ios/Tests/SessionLockTests.swift -o .cache/session-lock-tests
.cache/session-lock-tests
xcrun swiftc -parse-as-library -module-cache-path .cache/swift-module-cache camera_placement/ios/PlacementEngine.swift ios/MoveCamera/MovementCapture.swift ios/MoveCamera/FeedbackProtocol.swift ios/Tests/FeedbackContractTests.swift -o .cache/feedback-contract-tests
.cache/feedback-contract-tests
xcodebuild -quiet -project ios/MoveCamera.xcodeproj -scheme MoveCamera -sdk iphonesimulator -configuration Debug -derivedDataPath .cache/ios-integrated-build CODE_SIGNING_ALLOWED=NO build
```

Provider tests use mocks; they do not send patient media or spend API credits. Physical camera capture, pose orientation, final camera position and audio playback still need a real-iPhone run. Have a physiotherapist review representative captures and feedback before using this as reliable patient guidance.

## Privacy and limitations

Photos and audio remain in memory and are cleared on dismissal, restart, stopping or backgrounding. There is no patient media history. Uploaded images are processed and closed without writing application media files. OpenAI sees measurements and eligible cues for feedback; if the optional recognition fallback is enabled, it also sees selected recognition frames. ElevenLabs receives only the validated `spoken_text`.

OpenAI requests set `store: false`. This disables response storage but does not promise zero provider retention; consult [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data) and confirm the actual organisation's settings. ElevenLabs retention depends on account settings and terms; verify those settings before release. Provider account settings have not been audited by this integration. Feedback is a prototype, not clinically validated. If exercise causes pain or feedback conflicts with the prescribed plan, stop and consult your physiotherapist.
