# Kinevoa

Live exercise recognition for **Squat, Push-up, Lateral raise, or Unknown**, plus a separate three-stage voice-feedback service.

## Components

| Folder | Responsibility |
| --- | --- |
| [classifier/](classifier/) | Installable Python inference package, HTTP server, browser client, tests and evaluation tools |
| [ios/](ios/) | Standalone iPhone camera app and native session-lock tests |
| [llm/](llm/) | Hosted measurement-based feedback API with OpenAI cue selection and ElevenLabs speech |
| [contracts/](contracts/) | Shared HTTP interface and generated OpenAPI schema |

The iPhone app uses HTTP contracts for recognition and feedback. It has no Python, model-weight or provider-key dependency. The feedback screen becomes available when the measurement team supplies three stage snapshots. Branding kits and presentation materials are excluded.

## Run the classifier

From the repository root, using Python 3.11:

```sh
python3.11 -m venv .venv
.venv/bin/pip install -e './classifier[evaluation,test]'
.venv/bin/python classifier/tools/download_data.py
.venv/bin/python -m kinevoa_classifier --host 127.0.0.1 --port 8000
```

Open http://localhost:8000 for the browser client. For iPhone HTTPS setup, see [phone setup](classifier/docs/PHONE_SETUP.md) and [iOS setup](ios/README.md). Optional server-side provider settings are documented in [.env.example](.env.example) and [fallback setup](classifier/docs/OPENAI_FALLBACK.md). Never put keys in the iOS app.

## Verify

```sh
.venv/bin/python -m unittest discover -s classifier/tests -p 'test_*.py'
mkdir -p .cache/swift-module-cache
xcrun swiftc -parse-as-library -module-cache-path .cache/swift-module-cache ios/MoveCamera/RecognitionProtocol.swift ios/Tests/SessionLockTests.swift -o .cache/session-lock-tests
.cache/session-lock-tests
```

See [classifier evaluation](classifier/results/MOVEMENT_REPORT.md) for recorded experiments and limitations. Live scores and session agreement are not measured accuracy. This is an experimental classifier, not clinically validated guidance.
