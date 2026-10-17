# Kinevoa native iOS app

Open `MoveCamera.xcodeproj` in Xcode. Scheme: **MoveCamera**. Minimum iOS: **17**. Signing is set to Sonia's existing personal team and `com.soniakoszut.moveexercise`.

The rear camera samples JPEG frames (longest edge ≤640 px) and posts multipart `file` to the configured HTTPS server's `/predict`. Only one request is in flight; the UI shows agreement across the last ten readings. At 90% agreement, the exercise name locks for the session and further classification uploads pause. Tap **Re-classify** to reset the votes and start a new movement session, or **Stop** to end it. The percentage is consistency, not measured accuracy. The visible result is Squat, Push-up, Lateral raise, or Unknown. No exercise classifier runs in this app.

Default backend: `https://172.20.10.3:8443`. Tap the gear to change it. See the [shared HTTP contract](../contracts/classifier-api.md). Minimal server response:

```json
{"exercise":"squat"}
```

Other supported labels: `pushup`, `lateral_raise`, `unknown`. Model improvements can happen independently of the iOS app.

The public `MoveCamera/move-demo-ca.cer` is bundled as a resource. URLSession accepts only HTTPS and evaluates server trust against this CA, using the exact configured hostname/IP. Redirects are rejected. There is no ATS bypass and no unconditional certificate acceptance. The phone does not need a Settings certificate profile for this app. If the server CA changes, replace this public certificate and rebuild. Never bundle the CA or server private keys.

Camera frames are not written to disk by the app. Stop or backgrounding the app stops the capture session and cancels in-flight requests. Camera permission and local-network access must be allowed on the phone.

## Three-stage voice feedback handoff

The feedback service is separate from the laptop classifier. Set its hosted HTTPS base URL in **Connection → Hosted feedback service**. The app uses normal system certificate trust for that URL; OpenAI and ElevenLabs keys stay on the server. See [the feedback API](../llm/README.md) for the JSON contract and provisional form thresholds.

The measurement team calls `CameraModel.prepareFeedback(exercise:cameraAngleDeg:snapshots:)` with the canonical exercise ID, signed horizontal camera angle (0° front, ±90° side, ±180° back), and three `FeedbackSnapshot` values ordered `.start`, `.peak`, `.finish`. Use the exact metric properties in `FeedbackProtocol.swift`; leave unavailable values as `nil`. Supplying this input opens the review screen. The user taps **Review** to request written feedback and ElevenLabs audio. No sample readings are built into the app, and the current classifier does not yet supply these measurements.

On a Mac, run the contract check and unsigned build:

```sh
mkdir -p .cache/swift-module-cache
xcrun swiftc -parse-as-library -module-cache-path .cache/swift-module-cache \
  ios/MoveCamera/FeedbackProtocol.swift ios/Tests/FeedbackContractTests.swift \
  -o .cache/feedback-contract-tests
.cache/feedback-contract-tests
xcodebuild -project ios/MoveCamera.xcodeproj -scheme MoveCamera \
  -sdk iphonesimulator -configuration Debug -derivedDataPath .cache/ios-build \
  CODE_SIGNING_ALLOWED=NO build
```

A physical phone is needed to check the hosted connection and audio playback after the measurement pipeline is connected.

Unsigned build check:

```sh
xcodebuild -project ios/MoveCamera.xcodeproj \
  -scheme MoveCamera -sdk iphonesimulator -configuration Debug \
  -derivedDataPath .cache/ios-build CODE_SIGNING_ALLOWED=NO build
```

Run this check on a Mac after adding the feedback files. A physical phone is required to validate camera capture, permissions, server reachability, exercise results, and feedback playback. The backend classifier is experimental and may return Unknown on real-world footage.
