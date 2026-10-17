# On-device camera placement

The iPhone app uses the rear camera and Apple's Vision 3D body pose request to
estimate a person's direction every 0.45 seconds. All inference and photo
capture run on the phone; no setup frames, photos, or keys are sent to a server.
The photo stays in memory for preview and is discarded when dismissed or when
the camera stops. This feature suggests camera placement only; it does not
assess exercise form.

## Floor marks and setup

The eight line segments in the supplied sketch are the only allowed camera
positions. Number them clockwise from the top, with the subject in the centre:

```text
                 1 top
       8 top left       2 top right
   7 left      SUBJECT       3 right
    6 bottom left       4 bottom right
                5 bottom
```

Start with the phone at mark **5** (the sketch's CAMERA mark), or choose the
actual setup mark in the app. Aim the rear camera at one fully visible person,
holding it upright in portrait. The setup mark matters because body direction
from an image is relative to the camera. Keep the phone there until a stable
recommendation appears, then tap **Lock placement** before moving it. Put the
phone at the highlighted mark, set its **lens** to the shown height above the
floor, and tap **Take photo**. The app stores no photo history.

The recommendation shows the direction inferred from the setup image. If that
direction is wrong, choose the correct floor mark in **Subject faces (if
estimate is wrong)**. The recommendation is recalculated on the phone using
the same fixed preset. Select **Automatic** to try live detection again.

## Fixed presets

| Exercise | Desired view | Lens height above floor |
| --- | --- | --- |
| Squat | Side | 0.50 × subject height |
| Push-up | Side, relative to head-to-feet direction | 0.25 × subject height |
| Lateral raise | Front | 0.65 × subject height |

The app chooses the nearest available mark to the desired view. Both sides
are acceptable for a side view; if they tie, it chooses the side closest to
the setup mark. The exercise is selected from the fixed list already supported
by the branch. Height is entered in centimetres. These ratios are starting
presets, not measured optima. The distance of each floor mark and the phone's
field of view still need physical calibration so the whole person fits in the
final photo.

The recommendation also reports an **approximate camera angle** at that mark,
clockwise from the subject's facing direction on the floor map. Zero degrees
means the camera is in front; 180° means it is behind. For example, if the
subject faces the bottom of the sketch and the camera is at the left mark, the
angle is 90°. If the subject turns 20° toward the sketch's right, it is 110°.
The app rounds to the nearest 10° because the pose estimate and eight fixed
marks do not support a precise measurement. No angle is shown until a stable
direction estimate is available; it is not a body-joint angle.

The Vision estimate must be stable across at least three samples and requires
visible head, shoulders, hips, and ankles. If it is unclear, the app gives no
new mark and asks for a clearer view. The 3D estimate, camera-axis mapping,
and push-up direction require verification with a real iPhone and subjects
facing all eight directions before use with patients. A physiotherapist should
review the exercise presets and representative resulting photos.

## Verify

From the repository root:

```sh
mkdir -p .cache/swift-module-cache
xcrun swiftc -module-cache-path .cache/swift-module-cache \
  camera_placement/ios/PlacementEngine.swift \
  camera_placement/ios/PlacementEngineTests.swift \
  -o .cache/placement-engine-tests
.cache/placement-engine-tests
xcodebuild -quiet -project ios/MoveCamera.xcodeproj \
  -scheme MoveCamera -sdk iphonesimulator -configuration Debug \
  -derivedDataPath .cache/ios-placement-build CODE_SIGNING_ALLOWED=NO build
```

The iOS app target compiles only the new placement camera code and does not
include the older network recognition classes or the bundled server CA. The
Python classifier is retained in its own folder for separate experiments.
