# Optional OpenAI vision fallback

Put your API key in the workspace `.env.local`:

```dotenv
OPENAI_API_KEY=your-key-here
EXERCISE_OPENAI_FALLBACK_ENABLED=true
EXERCISE_OPENAI_MODEL=gpt-5.4-nano
EXERCISE_OPENAI_AFTER_SECONDS=20
EXERCISE_OPENAI_MAX_CALLS=30
```

`.env.local` is ignored by git and is never included in the iOS app or sent to the phone. Configuration is read by the Mac backend on new requests, so adding the key does not need a backend restart. Tap **Re-classify** to start a fresh session after configuring it. Process environment values take priority over the file.

## Behaviour

- The local image/pose pipeline runs first. A label that reaches 90% agreement locally locks as before, with no paid request.
- If the session is still unresolved after 20 seconds, a background worker sends six recent frames to the OpenAI Responses API. Images are reduced to at most 512 pixels on their longest edge. Only one frame per approximately second is buffered.
- A clear exercise result gets a second check only after six fresh frames have arrived. The two sets do not overlap. At most two requests are made per camera session.
- Two matching clear results, both reporting visible exercise motion, produce an AI-confirmed name. The native app can display exercises outside Squat, Push-up and Lateral raise, such as Lunge or Biceps curl. The UI shows **AI cross-check 2/2**, turns green and locks until Re-classify/Stop.
- The AI result is not counted as nine independent local predictions. No model self-reported confidence is used or presented as measured accuracy.
- If the result is uncertain, static, ordinary walking/standing, an API refusal/error, or the checks disagree, the AI path does not lock a name. Local classification continues. Tap Re-classify for another attempt.
- A camera restart/Re-classify creates a new session ID. A late response from the old session cannot affect the new session.

Frames are buffered in RAM, not saved to disk. With the fallback configured, these selected frames leave the Mac and go to OpenAI; the app's Connection settings describe this. Requests use `store: false`; this setting is not a claim of zero data retention under all account policies.

Defaults bound memory to eight sessions with six JPEGs each, use two network workers, and cap the server process at 30 paid requests (15 fully checked fallback sessions). The maximum per-process setting is 100 calls. API calls have a bounded timeout and no automatic retries. A failed API call cannot crash or block the local model's prediction path. The model is configurable; there is no automatic upgrade to a larger, more expensive model.

## Testing and diagnostics

The Python tests mock OpenAI requests; they do not spend tokens or test live model accuracy. Swift tests verify the existing local 90% lock, unmapped names, two-check confirmation, rejection of unconfirmed/invalid names, and reset behaviour. Key validity, model access, latency and recognition quality require a live test after adding your key.

```sh
.venv/bin/python -m unittest discover -s exercise_demo -p 'test_*.py'
xcrun swiftc -parse-as-library -module-cache-path .cache/swift-module-cache \
  exercise_demo/ios/MoveCamera/RecognitionProtocol.swift \
  exercise_demo/ios/SessionLockTests.swift -o .cache/session-lock-tests
.cache/session-lock-tests
```

`GET /health` reports `cloud_configured` as a boolean without exposing credentials. Loopback-only `GET /diagnostics` reports `cloud_status`, completed check count and sanitised error category. It does not contain API keys, image bytes, request payloads or provider response bodies. Cloud states include waiting, checking, awaiting_fresh_frames, checking_again, confirmed, uncertain, disagreement, error and budget_reached.

## Official API sources

- [GPT-5.4 nano model and pricing](https://developers.openai.com/api/docs/models/gpt-5.4-nano): image input and structured outputs; designed for inexpensive, fast classification and extraction.
- [Image inputs](https://developers.openai.com/api/docs/guides/images-vision): ordered image inputs using base64 JPEG data URLs.
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs): strict JSON Schema in the Responses API `text.format` field.

Two agreeing model judgments can still be wrong. This fallback has not established a new accuracy figure for the exercise classifier; use labelled recordings to evaluate it.
