# Orbit native iOS app

Open `MoveCamera.xcodeproj` in Xcode. Scheme: **MoveCamera**. Minimum iOS: **17**. Signing is set to Sonia's existing personal team and `com.soniakoszut.moveexercise`.

The rear camera samples JPEG frames (longest edge ≤640 px) and posts multipart `file` to the configured HTTPS server's `/predict`. Only one request is in flight; the UI shows agreement across the last ten readings. At 90% agreement, the exercise name locks for the session and further classification uploads pause. Tap **Re-classify** to reset the votes and start a new movement session, or **Stop** to end it. The percentage is consistency, not measured accuracy. The visible result is Squat, Push-up, Lateral raise, or Unknown. No exercise classifier runs in this app.

Default backend: `https://172.20.10.3:8443`. Tap the gear to change it. See the [shared HTTP contract](../contracts/classifier-api.md). Minimal server response:

```json
{"exercise":"squat"}
```

Other supported labels: `pushup`, `lateral_raise`, `unknown`. Model improvements can happen independently of the iOS app.

The public `MoveCamera/move-demo-ca.cer` is bundled as a resource. URLSession accepts only HTTPS and evaluates server trust against this CA, using the exact configured hostname/IP. Redirects are rejected. There is no ATS bypass and no unconditional certificate acceptance. The phone does not need a Settings certificate profile for this app. If the server CA changes, replace this public certificate and rebuild. Never bundle the CA or server private keys.

Camera frames are not written to disk by the app. Stop or backgrounding the app stops the capture session and cancels in-flight requests. Camera permission and local-network access must be allowed on the phone.

Unsigned build check:

```sh
xcodebuild -project ios/MoveCamera.xcodeproj \
  -scheme MoveCamera -sdk iphonesimulator -configuration Debug \
  -derivedDataPath .cache/ios-build CODE_SIGNING_ALLOWED=NO build
```

This check passed. A physical phone is required to validate camera capture, permissions, server reachability, and exercise results. The backend classifier is experimental and may return Unknown on real-world footage.

## Native movement capture

After an exercise locks, tap **Capture** to collect six seconds from the existing rear-camera feed (target 10 fps, longest edge 640 px). The native app sends ordered JPEG frames and monotonic capture timestamps to the same Python server at `/capture/features`, using the existing pinned HTTPS session. Tap **Features** to view review images, per-frame values, landmark quality, unavailable reasons and full JSON. No coaching/speech is generated. Camera-angle readiness is handled elsewhere; this button does not verify it.

Capture sampling and network state live on the camera queue. Stop, Re-classify and app backgrounding cancel capture, invalidate stale responses, and clear temporary results. Raw sequence frames are released after processing; review images and feature results remain in memory until cleared or the session ends. `MovementCapture.swift` contains the isolated multipart request and typed response contract; see [feature definitions](../contracts/movement-features.md). Physical-device camera/network testing is still required.
