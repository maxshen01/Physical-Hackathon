# Kinevoa — Physical AI Hackathon

Exercise-recognition prototype with a native iPhone camera app and a Python backend.

- Image classification across 22 workout classes, with Squat, Push-up and Lateral raise accepted by the local app.
- Pose-based movement recognition and a person-crop retry for uncertain images.
- Live leading-label/model-confidence display, with a separate session-agreement lock.
- Optional GPT-5.4 nano vision fallback after 20 unresolved seconds; two fresh-sequence checks must agree before locking an unfamiliar exercise.
- Re-classify starts a fresh session. Camera frames are not saved; the optional cloud fallback sends selected in-memory frames to OpenAI.

## Start here

- [Backend setup, datasets and evaluation](exercise_demo/README.md)
- [Native iOS app](exercise_demo/ios/README.md)
- [OpenAI fallback and environment setup](exercise_demo/OPENAI_FALLBACK.md)
- [Phone HTTPS setup](exercise_demo/PHONE_SETUP.md)
- [Classifier results and limitations](exercise_demo/results/MOVEMENT_REPORT.md)
- [Brand assets](branding/BRAND_GUIDE.md)
- [Demo guide](demo_materials/output/kinevoa-demo-guide.md)

## Local setup

Use Python 3.11. From the repository root:

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r exercise_demo/requirements.txt
.venv/bin/python exercise_demo/download_data.py
mkdir -p .cache/pose
curl -fL https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task -o .cache/pose/pose_landmarker_full.task
cp .env.example .env.local
.venv/bin/python -m uvicorn server:app --app-dir exercise_demo --host 127.0.0.1 --port 8000
```

Add your key to `.env.local` to enable the optional OpenAI fallback. The local classifiers run without it. Model weights, datasets, credentials and machine-specific build products are excluded from git. The supplied iOS demo CA certificate is public; private certificate keys are excluded. Configure signing and HTTPS for your own device using the linked guides.

## Checks

```sh
.venv/bin/python -m unittest discover -s exercise_demo -p 'test_*.py'
xcrun swiftc -parse-as-library -module-cache-path .cache/swift-module-cache exercise_demo/ios/MoveCamera/RecognitionProtocol.swift exercise_demo/ios/SessionLockTests.swift -o .cache/session-lock-tests
.cache/session-lock-tests
```

Model confidence is not measured accuracy. The saved results document convenience-sample tests and remaining misses; this prototype does not provide validated clinical assessment or live form coaching.
