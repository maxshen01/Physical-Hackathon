# Movement feature capture contract

`POST /capture/features`, multipart: `exercise` (`squat`, `pushup`, `lateral_raise`), `timestamps` (JSON list of milliseconds relative to capture start), and repeated `files` (ordered JPEG/PNG frames). This endpoint does not classify exercises, call cloud services, or generate coaching/speech. Camera angle and readiness are supplied externally.

Browser: Start camera → known exercise (classifier prefill or manual selection) → Capture. Captures six seconds, targeting roughly 10 fps, with actual timestamps. Recognition pauses during capture. Results remain until cleared, stopped, hidden, or replaced; review images use temporary browser object URLs.

## Feature inventory

All angles are projected **2D image-plane estimates**, corrected for image aspect ratio, not anatomical joint measurements. Left/right are anatomical model labels; do not horizontally mirror image data. No clinical thresholds are applied.

| Exercise | Feature | Definition |
|---|---|---|
| squat | `knee_left_deg`, `knee_right_deg` | Hip–knee–ankle angle, 0–180° |
| squat | `torso_inclination_deg` | Shoulder midpoint–hip midpoint axis against image-up vertical, 0–180°; requires both shoulders and hips |
| pushup | `elbow_left_deg`, `elbow_right_deg` | Shoulder–elbow–wrist angle, 0–180° |
| pushup | `body_alignment_left_deg`, `body_alignment_right_deg` | Shoulder–hip–ankle angle, 0–180° |
| pushup | `hip_offset_left_torso_lengths`, `hip_offset_right_torso_lengths` | Signed perpendicular hip distance from shoulder–ankle line divided by shoulder–hip distance; positive toward image-up. Near-vertical body axes make this sign unhelpful; side-view positioning is an upstream responsibility. |
| lateral_raise | `arm_left_deg`, `arm_right_deg` | Hip–shoulder–elbow angle, 0–180° |
| lateral_raise | `arm_difference_deg` | Absolute left/right arm-angle difference in the same frame, 0–180° |

Each feature is `{value: number|null, landmark_quality: number|null, unavailable_reason: string|null}`. Quality is the minimum visibility/presence score across required landmarks, **not calibrated measurement accuracy**. Missing values are not zero or carried forward. Reasons: `no_person`, `multiple_people`, `low_landmark_confidence` (below 0.6), `joint_out_of_frame`, `degenerate_geometry`.

Response:

```json
{
  "exercise": "squat",
  "status": "features_available",
  "measurement_space": "2d_image_plane",
  "frames": [{"timestamp_ms": 100, "features": {"knee_left_deg": {"value": 92.1, "landmark_quality": 0.94, "unavailable_reason": null}}}],
  "review_frame_indices": [0, 24, 50],
  "complete_repetition_verified": false
}
```

The example abbreviates the frame series and feature set. Status means at least one feature was extracted; it does not certify sufficient tracking or form. Otherwise status is `unable_to_extract`. Review indices identify first usable, observed extreme, last usable (deduplicated, chronological). The extreme uses mean available knee/elbow/arm angles; changing side visibility can affect it. **These frames do not prove a complete repetition.** No smoothing, cycle validation, raw landmarks, or 3D measurements are included in this version.

Limits: 3–90 frames, strictly increasing finite nonnegative timestamps within 10 seconds; 1 MB per frame, 24 MB total decoded upload bytes, 2 million pixels per image. Invalid batches are rejected before model inference. HTTP 400: invalid input; 413: too large; local model exceptions produce HTTP 503 and a browser retry message. Configure deployment request-body limits as well: multipart parsing occurs before endpoint validation and framework UploadFile may spool large incoming files temporarily. The endpoint closes uploads and decoded images in `finally`; it does not create retained media or a capture history. Browser capture does not use localStorage or IndexedDB.

## Modules

- `web/static/capture.js`: capture sampling, cancellation, temporary review images, JSON presentation.
- `capture.py`: pure landmark-to-feature geometry and review-frame selection.
- `movement.py`: shared MediaPipe model adapter (`PoseEstimator.landmarks`); recognition rules remain separate.
- `api.py`: batch validation, serialized local inference, response adapter.

Current model adapter uses independent IMAGE-mode inference to reuse the existing locked model safely. VIDEO tracking and complete-repetition detection are follow-up work, not implemented claims. Test actual target-device capture and representative clips before relying on these measurements.

## Per-feature ranges

The response also includes `ranges`, keyed by the same feature names. Each entry contains `min`, `max`, `min_timestamp_ms`, `max_timestamp_ms`, `valid_frames`, and `total_frames`. Only non-null usable measurements contribute. If none are usable, both extrema and their timestamps are null. One usable reading produces equal min/max. Ties use the earliest timestamp. Units match the original feature: degrees or torso lengths. These are observed capture extrema, not verified anatomical range of motion; isolated tracking errors may still affect extrema. Full timestamped `frames` remain unchanged. The native Features screen displays ranges before individual readings.

```json
"ranges": {
  "knee_left_deg": {
    "min": 88.4,
    "max": 173.2,
    "min_timestamp_ms": 2400,
    "max_timestamp_ms": 500,
    "valid_frames": 48,
    "total_frames": 55
  }
}
```
