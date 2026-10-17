# Native app ↔ classifier

The iOS app is a camera client. Classifier implementation can change independently.

- Default base URL: `https://172.20.10.3:8443` (editable in app gear menu).
- Request: `POST /predict`, multipart field `file`, JPEG RGB camera frame, maximum longest dimension 640 px. At most one request in flight, sampled no faster than 2 Hz.
- Response HTTP 200 JSON: `{"exercise":"squat"}`. Supported values: `squat`, `pushup` (or `push-up`), `lateral_raise`, `unknown`.
- Today’s demo mode shows a provisional candidate and live consistency: votes for the leading known exercise divided by 10, counting Unknown among the last 10 readings. After a full window, ≥9/10 matching readings with a matching current response locks the name.
- The percentage is agreement, not a calibrated probability or measured accuracy. At lock, further classification uploads pause while the camera preview continues.
- Re-classify clears the result, all votes, and the movement-session UUID, then resumes classification without restarting the camera. Stop or backgrounding ends the session and clears the lock.
- Transport: HTTPS, trust anchored to bundled `MoveCamera/move-demo-ca.cer`, with hostname validation and redirects rejected. Backend must use a certificate signed by that CA. Existing server cert/key: workspace `.cache/tls/phone.pem` and `.cache/tls/phone-key.pem`. Do not replace the CA without updating/rebuilding the app.
- Each camera start sends a new opaque UUID in `X-Movement-Session` on every request. The backend namespaces temporal state by client and this ID; clients without it get image-only predictions.
- Backend now combines the original image prediction (all 22 classes, score ≥0.65 and margin ≥0.15), a square person crop retry, and a completed-movement-cycle fallback. These operate on the Mac; no on-device exercise classifier is included.
- `/diagnostics` is loopback-only and reports the decision source, tracking features, cycle phases and timings; frames are never stored.
- No frame storage is included. Camera stops when app leaves foreground.

The classifier session can replace server inference while preserving this request/response contract. No native rebuild is needed for classifier weight or inference changes.

## Movement fallback integration (build 3)

The camera client sends `X-Movement-Session: <UUID>` on each frame. The UUID is regenerated on every camera start. The hybrid backend uses it to isolate temporal histories; without it, callers only get stateless image recognition. Preserve this header in client and backend changes. Real-time replay can be enabled with `REPLAY_REALTIME=1` for motion-based testing; fast offline replay is unsuitable for wall-clock motion timing.

## Optional OpenAI fallback

After 20 unresolved seconds, the server may run two non-overlapping six-frame vision checks if the Mac's `.env.local` supplies a key. Local predictions remain available while the worker runs. Successful cross-checks extend the response with `source: "openai_vision"`, `display_name`, `cloud_confirmed: true`, `cloud_checks: 2`, and `cloud_status: "confirmed"`; `exercise` can be a new canonical snake_case name. The native app validates these fields before locking a previously unmapped exercise. It displays AI cross-check 2/2 rather than inventing a 90% accuracy score. Clients that decode only exercise remain compatible for the original vocabulary. Other cloud_status values describe pending, unavailable or inconclusive checks.

The key stays on the Mac. Selected frames go to OpenAI only when configured. See `../OPENAI_FALLBACK.md`.

## Live preview before locking

For session-aware clients, each response also contains `preview_label`, `preview_score` (0–1, or null), and `preview_source`. Rejected full-frame top-1 predictions remain visible across all 22 image-model classes without changing `exercise` or counting toward locking. An accepted crop supplies its own score. Movement and AI-confirmed labels have no fabricated image probability. The native screen shows MOST LIKELY and live model confidence per response (at most about 2 Hz), separately from session agreement. The label and score freeze at lock and reset on Re-classify/Stop. These are model scores, not measured correctness.

## Current vocabulary restriction

The latest demo accepts and displays only Squat, Push-up, Lateral raise, or Unknown. This supersedes earlier open-vocabulary preview and cloud-fallback descriptions above. Other raw image classes still compete internally, but their names and confidence are discarded from the app preview. Other cloud exercise names are rejected by the request schema, backend validation and native display/lock validation. No renormalisation or forced nearest-target choice is used.
