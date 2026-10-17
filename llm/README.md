# Physio video coach

A local demo that takes a short video and exercise name, analyses sampled frames with an OpenAI vision model, and returns brief written feedback and ElevenLabs speech. It is a prototype for patient self-practice, not a clinically validated assessment or treatment plan.

## Install and run on Windows

1. Install [Python 3.11 or newer](https://www.python.org/downloads/) and [FFmpeg](https://ffmpeg.org/download.html). Make sure `python`, `ffmpeg`, and `ffprobe` are on PATH. Open a new PowerShell terminal and check:

   ```powershell
   python --version
   ffmpeg -version
   ffprobe -version
   ```

2. From the repository root, set up the Python environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   Copy-Item .env.example .env
   ```

3. Edit `.env` with your `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, and `ELEVENLABS_VOICE_ID`. `OPENAI_MODEL` defaults to `gpt-6-astra`; the model must support image input and Structured Outputs. The ElevenLabs model ID is also configurable. A ChatGPT subscription does not supply an OpenAI API key.

4. Start the local server:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn physio_coach.main:app --reload
   ```

   Open <http://127.0.0.1:8000>. To run automated tests:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest -q
   ```

## How the demo works

`POST /api/analyse` accepts multipart fields `video` and `exercise_name`. Videos must be MP4, MOV, or WebM, no longer than 30 seconds or larger than 50 MB. The server checks that the video decodes, extracts 12 timestamped JPEG frames, and sends only the exercise name and frames to the OpenAI Responses API. The first version makes qualitative observations; it does not count repetitions or calculate joint angles.

The API returns `feedback` with `status`, `observations`, `cues`, and `spoken_text`, plus base64 encoded MP3 in `audio_base64` when speech succeeds. `status` is `assessable` or `unable_to_assess`; the latter has no form cues. If ElevenLabs fails or is not configured, the validated written feedback remains available with an `audio_error`. Video, frames, and audio are not kept as a local history.

The GPT model has no callable tools in this version. The Python service invokes FFmpeg, OpenAI, and ElevenLabs in sequence. The spoken script is assembled from validated cues, so a separate unvalidated model script cannot be sent to ElevenLabs.

## Safety and data handling

The UI tells patients to stop and consult their physiotherapist if exercise causes pain or if advice conflicts with their prescribed plan. An exercise name alone may not identify the prescribed variation; unclear clips receive a request for a clearer video. A physiotherapist must review representative clips and feedback before the demo is presented as reliable patient guidance.

The app sends sampled video frames to OpenAI and feedback text to ElevenLabs. Temporary local files are removed after each request, including failures. OpenAI requests use `store: false`, which does not itself guarantee zero provider retention; see [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data). ElevenLabs has its own [logging and retention controls](https://elevenlabs.io/docs/api-reference/text-to-speech/stream); its zero retention option is subject to account eligibility. Review both providers' current terms and settings before using real patient footage. Do not use identifiable patient clips in a demo without appropriate permission.

## Current validation state

- [x] Python API, upload page, video processing, structured feedback, and speech integration implemented.
- [x] Automated tests pass with mocked provider calls.
- [ ] Install Python and FFmpeg on the demo machine and test a real short clip.
- [ ] Configure live OpenAI and ElevenLabs credentials and verify browser audio playback.
- [ ] Have a physiotherapist review representative clips and feedback.

The live checks are pending because this environment has no configured provider credentials or FFmpeg on PATH. A temporary Python installation was used to run the automated tests.
