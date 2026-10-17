# Orbit native iOS app

Open `MoveCamera.xcodeproj` in Xcode. Scheme: **MoveCamera**. Minimum iOS: **17**.
The app now guides on-device camera placement for the branch's fixed exercise
set: Squat, Push-up, and Lateral raise. Choose the exercise, enter the subject's
height, select the physical setup mark, and start the rear camera. A stable
direction estimate highlights one of eight floor marks, gives a lens height,
and estimates the camera's angle clockwise from the subject's facing direction.
Lock the recommendation before moving the phone, then take a photo. The photo
is previewed in memory and is not saved by the app. The recommendation shows
its inferred facing direction. If it is wrong, select the actual direction in
**Subject faces (if estimate is wrong)**, or select **Automatic** to resume
live detection.

All live pose inference uses Apple Vision on the iPhone. The iOS target has no
HTTP client, server address, provider key, model download, or local network
permission. The older `CameraModel.swift`, `MovementCapture.swift`, and
`RecognitionProtocol.swift` remain in the repository for the separate
recognition experiment but are excluded from the app target. Sonia's Orbit
branding assets remain included in the app target.

See [camera placement](../camera_placement/README.md) for the mark numbering,
presets, assumptions, tests, and physical validation required. The Python
classifier remains a separate experiment and is not used by the iOS app.

Unsigned build check:

```sh
xcodebuild -quiet -project ios/MoveCamera.xcodeproj \
  -scheme MoveCamera -sdk iphonesimulator -configuration Debug \
  -derivedDataPath .cache/ios-placement-build CODE_SIGNING_ALLOWED=NO build
```

A physical iPhone is needed to validate camera permissions, frame orientation,
3D pose direction, photo capture, and all eight subject headings.
