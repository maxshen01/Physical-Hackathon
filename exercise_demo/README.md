# Exercise recognition: phone-camera MVP

Input: live RGB camera frames from a phone browser. Output: **Squat, Push-up, Lateral raise, or Unknown**. Inference runs on the laptop, not on the phone. No frames are saved by the app.

## Run

The workspace `.venv` already contains the dependencies and `.cache/model` contains downloaded weights. For a fresh checkout, use Python 3.11:

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r exercise_demo/requirements.txt
.venv/bin/python exercise_demo/download_data.py
```

Laptop preview:

```sh
.venv/bin/python -m uvicorn server:app --app-dir exercise_demo --host 127.0.0.1 --port 8000
```

Open http://localhost:8000. For the actual phone demo, follow [PHONE_SETUP.md](PHONE_SETUP.md) to enable trusted HTTPS on the same Wi-Fi. No public hosting or tunnel is required.

## What was tested

See [experiment.ipynb](experiment.ipynb), [results/summary.json](results/summary.json), and the per-sample CSV files. Model: https://huggingface.co/prithivMLmods/Gym-Workout-Classifier-SigLIP2.

Fixed acceptance rule: the highest of all 22 class scores must be a target class, at least 0.65, and exceed the second-highest by 0.15. Otherwise return Unknown. Phone UI requires three consecutive matching accepted predictions. Scores are not calibrated probabilities of correctness.

### Image smoke test

Dataset: https://huggingface.co/datasets/averrous/workout, test split; 20 deterministic random images each for squat, push-up, lateral raise, plank, and shoulder press (seed 42). No training or threshold tuning on this sample.

| True class | Correct raw top-1 | Correct app output |
| --- | ---: | ---: |
| Squat | 20/20 | 19/20 |
| Push-up | 20/20 | 20/20 |
| Lateral raise | 19/20 | 17/20 |
| Plank | 20/20 | 20/20 Unknown |
| Shoulder press | 18/20 | 20/20 Unknown |

97/100 exact raw labels; 96/100 correct target-or-Unknown outputs. Median model inference about 53 ms on this run, excluding network, browser capture, and smoothing latency. Not an end-to-end FPS guarantee.

### Video smoke test: significant failure

Dataset: https://huggingface.co/datasets/ambarishnarayan/UFC101_Subset_Workout. Five lexicographically first validation clips each of PushUps and JumpingJack, eight evenly spaced frames per clip, majority vote after acceptance rules.

- Push-ups: **0/5** clips recognised; all majority outputs Unknown.
- Jumping jacks: **5/5** rejected as Unknown.

This is evidence of domain/viewpoint sensitivity. The good image numbers do not establish that this model is reliable for live phone exercise recognition. The app is a working integration prototype; the classifier needs testing on your actual phone footage and may need replacement or fine-tuning. Smoothing does not establish movement or a completed repetition.

Training-data overlap with the image dataset cannot be excluded because the model card does not identify its training dataset. The video sample is tiny and contains no squat/lateral-raise clips. Idle/walking, phone permissions, real-world phone recognition, and simulator appearance remain unvalidated. Dataset files stay local and are not committed; check original data permissions before redistribution.

## Reproduce

```sh
.venv/bin/python exercise_demo/download_data.py
HF_HUB_OFFLINE=1 .venv/bin/python exercise_demo/evaluate.py
.venv/bin/python -m unittest discover -s exercise_demo -p 'test_*.py'
```

`results/assets.json` records checksums; `requirements-lock.txt` records the installed environment. `results/image_predictions.csv` and `video_predictions.csv` allow inspection of individual outcomes. Notebook shows the saved real results and includes an optional full re-run cell.

## Files and adapters

- `classifier.py`: shared model and RGB/PIL prediction function; `EXERCISE_MODEL_PATH` overrides local weights.
- `server.py`: multipart POST `/predict` returns only `{"exercise":"squat"}` (or `pushup`, `lateral_raise`, `unknown`). `/health` is a separate readiness check.
- `demo.html`: mobile camera UI with start/stop and permission/connection handling.
- `video.py`: optional video-file, webcam-index, or MJPEG/RTSP adapter for offline development; writes JSONL only, no frames.
- `evaluate.py`: reproducible image and video smoke tests.

A future simulator can supply its rendered RGB array directly to `ExerciseClassifier.predict(rgb)` or upload a rendered JPEG to the same `/predict` API. No simulator is included; synthetic-to-real generalisation is untested. The recogniser does not accept skeleton coordinates as image input.

## Optional OpenAI fallback after 20 seconds

The native app can use a bounded OpenAI vision cross-check for unresolved sessions for the same three supported exercises. Put the key in the workspace's ignored `.env.local`; see [OPENAI_FALLBACK.md](OPENAI_FALLBACK.md). This path sends selected in-memory frames to OpenAI when configured, uses at most two calls per session, and requires two matching fresh-sequence results before the app locks a supported name. Its live recognition quality remains to be evaluated with your key.
