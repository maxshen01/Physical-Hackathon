# Classifier HTTP contract

The classifier owns inference; clients own capture, display and session locking. Neither module imports the other. [classifier.openapi.json](classifier.openapi.json) records the server schema; `/openapi.json` serves it at runtime.

## Frame prediction

`POST /predict`: multipart field `file`, one JPEG or PNG, ≤8 MB and ≤20 million pixels. The iPhone scales frames to ≤640 px on the longest edge and keeps at most one request in flight.

Optional header `X-Movement-Session`: an opaque UUID, regenerated on each start or Re-classify. The server namespaces temporal state by client and this ID. Without the header, predictions are stateless and the response contains only `exercise`.

```json
{"exercise":"squat"}
```

`exercise` is exactly `squat`, `pushup`, `lateral_raise` or `unknown`. Unsupported classes are discarded, including cloud results. No forced nearest-target choice or score renormalisation occurs.

Session-aware responses may also contain:

| Field | Meaning |
| --- | --- |
| `source` | Decision path, e.g. image, person_crop, movement or openai_vision |
| `preview_label` | Squat, Push-up, Lateral raise or Unknown |
| `preview_score` | Model estimate from 0–1, or null when unavailable/unsupported |
| `preview_source` | Origin of that estimate |
| `display_name` | Supported exercise display name, if supplied |
| `cloud_status` | Current optional provider-check status |
| `cloud_checks` | Number of agreeing fresh-sequence checks |
| `cloud_confirmed` | True only after validated provider confirmation |

Model estimates are not calibrated correctness probabilities. Unknown preview has no score. Invalid frames return 400, oversized frames 413, missing multipart fields 422, and invalid session IDs 400.

## Native session policy

The app shows the live preview estimate separately from agreement over a full ten-response window. At least nine matching accepted labels, including the current response, lock the exercise. Validated cloud confirmation uses two agreeing disjoint six-frame sequences and displays 2/2 rather than a fabricated percentage. Only the three supported labels can lock.

At lock, uploads pause while the camera preview continues. Re-classify clears votes and the session ID and resumes. Stop or backgrounding cancels requests and ends capture. Native regression checks live in `ios/Tests/SessionLockTests.swift`.

## Transport and other endpoints

The native app uses HTTPS with hostname validation and the bundled public CA certificate. Redirects are rejected. Configure the server URL in the app's gear menu. If the CA changes, update `ios/MoveCamera/move-demo-ca.cer` and rebuild; never bundle private keys.

`GET /health` reports readiness, model device and whether cloud configuration is enabled. `GET /diagnostics` is loopback-only and returns bounded decision metadata. `/` and `/static/` serve the optional browser client.

The service does not persist uploaded frames. Provider keys stay on the server. Configured cloud fallback sends selected in-memory frames to OpenAI; see [provider setup](../classifier/docs/OPENAI_FALLBACK.md).

## Single-image capture

`POST /capture/image`: multipart `exercise` (`squat`, `pushup`, `lateral_raise`) and `file` (one JPEG/PNG, ≤1 MB, ≤2 million pixels). The entire image is validated before pose extraction. Errors: 400 for empty/corrupt/unsupported images or exercise IDs, 413 for size/resolution limits, 503 for extraction failure. Image objects and uploaded files are closed on success and failure; no application media files are written.

The response uses the movement-feature envelope with exactly one `frames` entry at `timestamp_ms: 0`, `measurement_space: "2d_image_plane"`, and `complete_repetition_verified: false`. Feature values include landmark quality and missing-value reasons. One image does not imply a movement peak. Orbit sends quality-checked values as one `capture` snapshot to `POST /api/feedback`; it never invents three stages.

The root `demo:app` combines classifier routes and feedback routes on the same HTTPS origin. The standalone classifier's OpenAPI snapshot excludes feedback routes; the combined server exposes its complete schema at `/openapi.json`.
