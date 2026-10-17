# Orbit

The iPhone app now gives **on-device camera placement** for Squat, Push-up, and
Lateral raise. It estimates the subject's direction from live camera frames,
then selects one of eight fixed floor marks and a lens height relative to the
subject's height. The Python classifier remains a separate exercise-recognition
experiment.

## Components

| Folder | Responsibility |
| --- | --- |
| [camera_placement/](camera_placement/) | On-device pose direction, fixed presets, eight-mark selector, tests and setup notes |
| [ios/](ios/) | iPhone camera app, live placement UI, and in-memory photo preview |
| [classifier/](classifier/) | Separate Python inference package, HTTP server, browser client, and evaluation tools |
| [contracts/](contracts/) | HTTP interface for the separate classifier experiment |

The iPhone app uses Apple Vision locally. It does not use the classifier server,
an OpenAI model, or an external provider for camera placement. See the
[placement setup](camera_placement/README.md) for the eight marks and presets.

## Run the classifier

From the repository root, using Python 3.11:

```sh
python3.11 -m venv .venv
.venv/bin/pip install -e './classifier[evaluation,test]'
.venv/bin/python classifier/tools/download_data.py
.venv/bin/python -m kinevoa_classifier --host 127.0.0.1 --port 8000
```

Open http://localhost:8000 for the classifier browser client. This server is
not used by the iPhone placement app. Optional server-side provider settings
for the classifier experiment are documented in [.env.example](.env.example)
and [fallback setup](classifier/docs/OPENAI_FALLBACK.md). Never put keys in the
iOS app.

## Verify

```sh
.venv/bin/python -m unittest discover -s classifier/tests -p 'test_*.py'
mkdir -p .cache/swift-module-cache
xcrun swiftc -module-cache-path .cache/swift-module-cache camera_placement/ios/PlacementEngine.swift camera_placement/ios/PlacementEngineTests.swift -o .cache/placement-engine-tests
.cache/placement-engine-tests
xcrun swiftc -parse-as-library -module-cache-path .cache/swift-module-cache ios/MoveCamera/RecognitionProtocol.swift ios/Tests/SessionLockTests.swift -o .cache/session-lock-tests
.cache/session-lock-tests
xcodebuild -quiet -project ios/MoveCamera.xcodeproj -scheme MoveCamera -sdk iphonesimulator -configuration Debug -derivedDataPath .cache/ios-placement-build CODE_SIGNING_ALLOWED=NO build
```

See [classifier evaluation](classifier/results/MOVEMENT_REPORT.md) for the
separate recognition experiment and its limitations. Camera placement needs
physical testing with a real iPhone and physiotherapist review before it is
used for patient guidance.
