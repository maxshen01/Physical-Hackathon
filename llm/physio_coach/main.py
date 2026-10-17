"""Local FastAPI app for completed exercise clips."""

import base64
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from physio_coach.analysis import AnalysisError, analyse_frames
from physio_coach.config import Settings
from physio_coach.models import Feedback
from physio_coach.speech import SpeechError, synthesize_speech
from physio_coach.video import VideoError, VideoToolsMissing, extract_frames


MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm"}
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Physio video coach")


class AnalyseResponse(BaseModel):
    feedback: Feedback
    audio_base64: str | None
    audio_mime_type: str | None
    audio_error: str | None


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/app.js", include_in_schema=False)
def javascript() -> FileResponse:
    return FileResponse(STATIC_DIR / "app.js", media_type="text/javascript")


@app.get("/style.css", include_in_schema=False)
def stylesheet() -> FileResponse:
    return FileResponse(STATIC_DIR / "style.css", media_type="text/css")


@app.post("/api/analyse", response_model=AnalyseResponse)
async def analyse(
    video: UploadFile = File(...), exercise_name: str = Form(...)
) -> AnalyseResponse:
    try:
        name = exercise_name.strip()
        if not name or len(name) > 100:
            raise HTTPException(400, "Enter an exercise name of up to 100 characters")
        suffix = Path(video.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, "Upload an MP4, MOV, or WebM video")

        settings = Settings.from_env()
        missing = settings.missing_analysis()
        if missing:
            raise HTTPException(503, "Server setup is missing: " + ", ".join(missing))

        with TemporaryDirectory(prefix="physio-coach-") as temporary:
            work_dir = Path(temporary)
            video_path = work_dir / f"upload{suffix}"
            size = 0
            with video_path.open("wb") as target:
                while chunk := await video.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, "The video must be 50 MB or smaller")
                    target.write(chunk)
            if not size:
                raise HTTPException(400, "The video is empty")

            try:
                frames = await run_in_threadpool(extract_frames, video_path, work_dir)
                feedback = await run_in_threadpool(
                    analyse_frames,
                    name,
                    frames,
                    settings.openai_api_key,
                    settings.openai_model,
                )
            except VideoToolsMissing as exc:
                raise HTTPException(503, str(exc)) from exc
            except VideoError as exc:
                raise HTTPException(400, str(exc)) from exc
            except AnalysisError as exc:
                raise HTTPException(502, str(exc)) from exc

            missing_speech = settings.missing_speech()
            if missing_speech:
                return AnalyseResponse(
                    feedback=feedback,
                    audio_base64=None,
                    audio_mime_type=None,
                    audio_error="Speech is not configured: " + ", ".join(missing_speech),
                )
            try:
                audio = await run_in_threadpool(
                    synthesize_speech,
                    feedback.spoken_text,
                    settings.elevenlabs_api_key,
                    settings.elevenlabs_voice_id,
                    settings.elevenlabs_model_id,
                )
            except SpeechError:
                return AnalyseResponse(
                    feedback=feedback,
                    audio_base64=None,
                    audio_mime_type=None,
                    audio_error="Speech could not be generated. The written feedback is available.",
                )
            return AnalyseResponse(
                feedback=feedback,
                audio_base64=base64.b64encode(audio).decode("ascii"),
                audio_mime_type="audio/mpeg",
                audio_error=None,
            )
    finally:
        await video.close()

