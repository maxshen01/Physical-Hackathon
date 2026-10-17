# Classifier module

An installable Python package independent of the iOS source tree. Run the commands below from the repository root.

```sh
.venv/bin/pip install -e './classifier[evaluation,test]'
.venv/bin/python classifier/tools/download_data.py
.venv/bin/python -m kinevoa_classifier --host 127.0.0.1 --port 8000
```

Alternatively, use the installed `kinevoa-classifier` command or `uvicorn kinevoa_classifier.api:app`. The packaged browser client is served at `/`; see the [HTTP contract](../contracts/classifier-api.md) for other clients.

## Package boundaries

- `src/kinevoa_classifier/image.py`: RGB/PIL image classification; model weights can be selected with `EXERCISE_MODEL_PATH`.
- `movement.py`: pose features and temporal movement recognition.
- `hybrid.py`: local image, crop and movement policy; `HybridClassifier.predict(image, session_id=...)` is the reusable inference interface.
- `vision_fallback.py`: optional bounded server-side vision provider.
- `preview.py`: restricts display vocabulary and exposes live model estimates.
- `api.py`: HTTP adapter; `create_app(classifier_factory=..., vision_factory=...)` allows independent adapters and provider-free tests.
- `web/`: bundled browser client and required app icons.
- `tools/`, `tests/`, `notebooks/`, `results/`: development tools, checks and historical evaluation evidence; not imported by the runtime package.

The only accepted exercises are `squat`, `pushup`, `lateral_raise`, and `unknown`. Other raw classes still compete internally, but are discarded for display and acceptance. The image acceptance rule requires top-1 score ≥0.65 and margin ≥0.15. Temporal fallback requires a session ID. Optional cloud checks require two agreeing fresh frame sequences after 20 unresolved seconds.

## Runtime configuration

By default, `.cache/` and `.env.local` are resolved from the working directory. Run from the repository root to use the existing local setup. For a different deployment, set `KINEVOA_PROJECT_ROOT`, or override `KINEVOA_CACHE_DIR` and `KINEVOA_ENV_FILE` separately. Paths do not depend on `ios/`. Model weights, datasets, credentials and build artifacts are not committed.

See [HTTPS phone setup](docs/PHONE_SETUP.md) and [OpenAI fallback](docs/OPENAI_FALLBACK.md). Inference currently runs on the server, including the movement recogniser. Camera frames are not persisted by the application; configured cloud checks send selected frames to OpenAI.

## Evaluation

```sh
.venv/bin/python -m unittest discover -s classifier/tests -p 'test_*.py'
HF_HUB_OFFLINE=1 .venv/bin/python classifier/tools/evaluate.py
```

Install the `evaluation` extra to run data tools and the notebook. See [movement report](results/MOVEMENT_REPORT.md), [combined test report](results/KINEVOA_TEST_REPORT.md), and [notebook](notebooks/experiment.ipynb). Historical reports describe their specific model versions and samples. Dataset overlap, small samples and viewpoint differences limit generalisation; these results do not establish real-world or clinical accuracy.

`requirements-lock.txt` is the recorded development environment. `pyproject.toml` defines runtime dependencies and optional development extras.

## Capture movement features

The browser now includes **Capture** for a known exercise: six seconds of timestamped camera frames → local MediaPipe → per-frame feature JSON and up to three review images. Coaching and speech are deferred. See the [complete feature contract](../contracts/movement-features.md) for names, geometry, quality fields, limits and integration details. Camera-angle selection and readiness are outside this module.
