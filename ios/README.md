# Orbit native iOS app

Open `MoveCamera.xcodeproj`, scheme **MoveCamera**, iOS 17+. The app includes recognition networking, on-device camera placement, photo capture and voice feedback in one flow. Orbit's dark background, lime actions, native text and floor-mark diagram remain consistent throughout.

**Start recording → recognise exercise → choose facing / recommend position → Continue → move phone → Capture image → extract features → LLM → automatic speech.**

No saved video is created. Recognition streams bounded frames to the HTTPS server until the exercise locks. Apple Vision then estimates facing locally. Position confirmation freezes the recommendation before moving the phone. A real photo is captured, resized to ≤1280 px, uploaded for image-plane features, and discarded after review. The signed camera angle comes from the frozen floor-mark recommendation, not the phone's current preview. Moving to the recommended mark is a manual step.

One image is encoded as **one `capture` snapshot**, never duplicated into fake start/peak/finish stages. The app drops unavailable, low-quality and nonfinite measurements. The server validates the payload and cue selection. The voice screen starts its request automatically, plays the returned MP3, and offers replay/stop. An audio failure preserves the transcript. Closing the screen cancels requests and releases audio. Stopping/backgrounding clears the capture and resets the flow.

The combined HTTPS demo address is configured in `ContentView.swift` (currently
`https://172.20.10.3:8443`). Set it to the demo laptop's address before building.
The local connection uses the bundled public CA with hostname validation and
rejects redirects. Provider credentials are never entered in the app.

See the root [README](../README.md) for server setup, public certificate copy, build and test commands. Camera permission and local-network permission are required; no microphone or Photos-library permission is requested. **Position setup** shows persistent labels for height, the phone's starting mark and the person's facing direction. Controls are disabled while a photo is being processed, while Stop remains available to cancel.

If Automatic cannot resolve the direction, the bottom action becomes **Choose
facing direction** and opens a labelled list of the eight directions. Select
the mark the person is looking towards. This computes a placement without
requiring another pose detection. The floor diagram also accepts taps to set
facing. The action then becomes **Continue · camera mark N**, stays visible
while scrolling, and advances to **Capture image**. **Change camera position**
returns to setup without repeating recognition. Invalid height and expired
automatic estimates produce explanations. Temporary inactive states caused
by system prompts do not cancel the flow; backgrounding still stops it.

Test recognition, Apple Vision orientation for all eight headings, actual movement to the selected mark, capture and audible playback on a physical iPhone. Simulator build and mocked API tests cannot verify these physical steps.

Orientation uses Apple Vision 2D and 3D pose detection, plus local torso/profile
geometry, rather than an LLM. The placement card shows the evidence source.
To retest a sideways squat, start at mark 5, leave **Which way is the person facing?** on
**Automatic**, and face mark 7 or 3 with the torso and face in profile. A clear
profile should recommend mark 5; the evidence label should say **Apple Vision
2D torso + face profile**. Turn the entire body, not only the head. Hold each
direction for several samples. If the direction remains unclear, the marker
should disappear after two seconds. These heuristics still need device testing.

The real camera-model transitions can also be tested without a camera or
server. With an iPhone simulator already booted, from the repository root:

```sh
xcrun --sdk iphonesimulator swiftc -D PLACEMENT_FLOW_TESTS -parse-as-library \
  -sdk /Applications/Xcode.app/Contents/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator.sdk \
  -target arm64-apple-ios17.0-simulator -module-cache-path .cache/swift-module-cache-ios \
  camera_placement/ios/PlacementEngine.swift camera_placement/ios/OnDevicePoseHeading.swift \
  ios/MoveCamera/RecognitionProtocol.swift ios/MoveCamera/MovementCapture.swift \
  ios/MoveCamera/FeedbackProtocol.swift ios/MoveCamera/CameraModel.swift \
  ios/Tests/PlacementFlowTests.swift -o .cache/placement-flow-tests
xcrun simctl spawn booted "$PWD/.cache/placement-flow-tests"
```

These checks cover manual recovery from blocked automatic detection,
position-to-capture, changing position, height validation, and expired estimate
recovery. The test fixture is excluded from the application build. These are
state-transition tests; they do not verify touch interaction or camera accuracy.
