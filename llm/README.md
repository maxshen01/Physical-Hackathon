# Three-stage exercise feedback

This hosted FastAPI service accepts **measurements**, not images or video. The iOS measurement pipeline supplies an exercise ID, the signed horizontal camera angle, and start/peak/finish snapshots. The server compares peak values with provisional form thresholds, asks an OpenAI model to choose up to two eligible cues, then uses ElevenLabs to speak the approved text. It is a prototype, not clinically validated guidance.

## Run

From the repository root (`Physical Hackathon`), install Python 3.11+ and run in Git Bash:

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r llm/requirements-dev.txt
cp -n llm/.env.example llm/.env
# Fill OPENAI_API_KEY, ELEVENLABS_API_KEY, and ELEVENLABS_VOICE_ID in llm/.env.
./.venv/Scripts/python.exe -m uvicorn llm.physio_coach.main:app --reload
./.venv/Scripts/python.exe -m pytest -q llm/tests
```

Run the commands from the repository root so Python can import `llm.physio_coach`. The service loads `llm/.env`, not the root `.env`; environment variables already set in the server process take precedence. The root `.env.example` is for the separate classifier. After changing credentials, stop and restart the API; you do not need to repeat installation.

Deploy the same ASGI app behind HTTPS for the iPhone. Configure its base URL in the app's **Hosted feedback service** setting. Provider keys remain on the server. `OPENAI_MODEL` and `ELEVENLABS_MODEL_ID` are configurable.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Returns `{"status":"ok"}` when the API process is running. It does not check provider credentials. |
| `POST` | `/api/feedback` | Accepts three measurement snapshots and returns written feedback plus optional MP3 audio. |

Send `POST /api/feedback` with `Content-Type: application/json`. For example, from the repository root:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/feedback \
  -H 'Content-Type: application/json' \
  --data '{"exercise":"squat","camera_angle_deg":90,"snapshots":[{"phase":"start","knee_left_deg":171},{"phase":"peak","knee_left_deg":112,"torso_inclination_deg":49},{"phase":"finish","knee_left_deg":173}]}'
```

### Request body

`POST /api/feedback` takes JSON. The three snapshots must be ordered and labelled `start`, `peak`, `finish`. `peak` means deepest squat, lowest push-up, or highest lateral raise. The camera angle is horizontal relative to the exerciser: 0° front, ±90° side, ±180° back. All `*_deg` values are finite numbers from 0 to 180; unavailable measurements may be `null` or omitted. Hip offsets are finite signed torso lengths, positive toward image-up.

```json
{
  "exercise": "squat",
  "camera_angle_deg": 90,
  "snapshots": [
    {"phase": "start", "knee_left_deg": 171},
    {"phase": "peak", "knee_left_deg": 112, "torso_inclination_deg": 49},
    {"phase": "finish", "knee_left_deg": 173}
  ]
}
```

| Field | Type | Requirements |
| --- | --- | --- |
| `exercise` | string | One of `squat`, `pushup`, `lateral_raise`. |
| `camera_angle_deg` | number | Finite, from -180 to 180 degrees. |
| `snapshots` | array | Exactly three objects, ordered `start`, `peak`, `finish`. |
| `snapshots[].phase` | string | The snapshot's stage: `start`, `peak`, or `finish`. |
| Exercise measurement fields | number or `null` | Use only fields listed for that exercise below. Omit unavailable values or send `null`. |

Supported exercise-specific fields:

| Exercise | Snapshot fields |
| --- | --- |
| `squat` | `knee_left_deg`, `knee_right_deg`, `torso_inclination_deg` |
| `pushup` | `elbow_left_deg`, `elbow_right_deg`, `body_alignment_left_deg`, `body_alignment_right_deg`, `hip_offset_left_torso_lengths`, `hip_offset_right_torso_lengths` |
| `lateral_raise` | `arm_left_deg`, `arm_right_deg`, `arm_difference_deg` |

If both arm angles and their difference are supplied, the difference must match within 1°. Unknown fields, measurements for another exercise, invalid numbers, and wrong stage counts/order return 422. Other camera views or missing peak measurements return `unable_to_assess` with no form cues.

### Response body

Successful analysis returns HTTP 200. The model may choose zero, one, or two eligible cues, so the exact observations and cues can vary. This example shows a response when it selects the squat depth cue; the MP3 value is shortened for readability:

```json
{
  "feedback": {
    "status": "assessable",
    "observations": ["At the deepest squat, the measured knee angle stayed above 100° on each available side."],
    "cues": ["Go deeper"],
    "spoken_text": "Based on these measurements, try this. Go deeper."
  },
  "audio_base64": "SUQz...",
  "audio_mime_type": "audio/mpeg",
  "audio_error": null
}
```

`feedback.status` is `assessable` when the view and peak measurements permit review; it does not mean a correction was found. It is `unable_to_assess` when the camera view or peak measurements are insufficient. In that case, `cues` is empty and `observations` explains why. `spoken_text` is the approved script sent to ElevenLabs. `audio_base64` contains a base64-encoded MP3 when speech succeeds; decode it before playback.

Speech failure still returns HTTP 200 with written feedback. For example:

```json
{
  "feedback": {
    "status": "assessable",
    "observations": ["Peak-stage measurements were available for review."],
    "cues": [],
    "spoken_text": "These measurements do not support a specific correction. Please follow your physiotherapist's plan."
  },
  "audio_base64": null,
  "audio_mime_type": null,
  "audio_error": "Speech could not be generated. The written feedback is available."
}
```

If speech settings are missing, `audio_error` instead names the missing environment variables. Provider failure details are logged on the server and are not included in the API response.

| HTTP status | Meaning |
| --- | --- |
| `200` | Feedback returned, with or without audio. Inspect `feedback.status` and `audio_error`. |
| `422` | Request body failed validation. FastAPI returns a `detail` array describing the invalid fields. |
| `502` | The OpenAI cue selection failed or returned unusable feedback. |
| `503` | Required OpenAI settings are missing when cue selection is needed. |

## Rule policy

Only peak measurements trigger cues. Start and finish values are context, not averaged with peak. The provisional targets are: squat knee ≤100° and torso inclination ≤45°; push-up elbow ≤90°, body alignment 165–180°, with hip offset beyond ±0.1 torso lengths for a directional hip cue; lateral raise arm 80–100° and arm difference ≤10°. A shared left/right cue requires every available side to cross the same boundary. Squat and push-up cues require a camera angle within 30° of side view; lateral-raise cues require within 30° of front view. The 30° and ±0.1 cutoffs need validation with the measurement team.

The LLM receives measurements and eligible cue IDs, never media. It may select zero to two eligible IDs. The server checks the selection and builds speech from approved cue text; no model-written script reaches ElevenLabs. OpenAI requests use `store: false`. This does not itself guarantee zero provider retention. Do not use identifiable patient data without appropriate permission; have a physiotherapist review representative feedback before presenting it as reliable guidance.

## Integrated Orbit image flow

The integrated app now uses **one captured image**, following the revised product flow. The original three-stage contract above remains supported for existing clients. `POST /api/feedback` additionally accepts:

```json
{
  "exercise": "lateral_raise",
  "camera_angle_deg": 0,
  "snapshots": [
    {"phase": "capture", "arm_left_deg": 90, "arm_right_deg": 65, "arm_difference_deg": 25}
  ]
}
```

A single capture is never labelled a movement peak or a full repetition, but it always gets spoken feedback. The rules build priority-ordered candidates from whatever measurements are present: corrections first (depth and range targets worded conditionally, e.g. "If this is the lowest point of your squat…"), then positive confirmations, then a general form tip for the exercise. An unsuitable camera view or missing landmarks leaves only the general tip. The LLM is asked to pick one or two; if it picks none, the server uses the top-priority candidate. Numeric features remain image-plane research values and are not presented as clinical joint angles.

For the simplest setup, use the combined `demo:app` server described in the root README. Both `/capture/image` and `/api/feedback` share the same HTTPS origin; a separate hosted service is optional. Voice feedback plays automatically in the app and can be replayed or stopped. Audio errors preserve the validated transcript. Local image and audio history is not stored.

The LLM client bounds its request to 45 seconds without automatic retries; ElevenLabs has a 45-second HTTP timeout. Refusals, incomplete output, unsupported cue IDs, malformed JSON and timeouts return explicit analysis errors; unvalidated model text is never sent to speech. Requests use the [Responses API structured output format](https://developers.openai.com/api/docs/guides/structured-outputs).

## Logging

At the default Uvicorn `info` log level, the server logs each feedback request's measurements, the rules decision with eligible cue IDs, and the final cues and spoken text; `/capture/image` logs each extracted feature's value, landmark quality and whether the app keeps it (quality ≥ 0.6). It also logs when the rules find no eligible cue. When OpenAI is called, it logs the response ID, status, incomplete reason, returned `output_text`, and validated cue IDs. Provider request failures log the error type and request ID. These logs do not include API keys or images, but measurements and model output are logged, so restrict access to server logs.
