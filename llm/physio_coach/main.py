"""Hosted API for exercise feedback from three measurement snapshots."""

import base64
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .analysis import AnalysisError, choose_cues
from .config import Settings
from .models import Feedback, FeedbackRequest, approved_feedback
from .rules import evaluate
from .speech import SpeechError, synthesize_speech


app = FastAPI(title="Physio measurement feedback")
logger = logging.getLogger("uvicorn.error")


class FeedbackResponse(BaseModel):
    feedback: Feedback
    audio_base64: str | None
    audio_mime_type: str | None
    audio_error: str | None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest) -> FeedbackResponse:
    logger.info(
        "Feedback request: exercise=%s camera_angle_deg=%s snapshots=%s",
        request.exercise, request.camera_angle_deg,
        [snapshot.model_dump(exclude_none=True) for snapshot in request.snapshots],
    )
    evaluation = evaluate(request)
    logger.info(
        "Feedback rules: assessable=%s reason=%r eligible_cue_ids=%s",
        evaluation.assessable, evaluation.reason, [item.id for item in evaluation.candidates],
    )
    if not evaluation.assessable:
        result = approved_feedback(Feedback(
            status="unable_to_assess", observations=[evaluation.reason], cues=[], spoken_text="placeholder"
        ))
    else:
        candidates = {item.id: item for item in evaluation.candidates}
        selected: list[str] = []
        if candidates or len(request.snapshots) == 1:
            settings = Settings.from_env()
            missing = settings.missing_analysis()
            if missing:
                raise HTTPException(503, "Server setup is missing: " + ", ".join(missing))
            try:
                selected = await run_in_threadpool(
                    choose_cues, request, evaluation.candidates,
                    settings.openai_api_key, settings.openai_model,
                )
            except AnalysisError as exc:
                logger.warning("Feedback analysis failed: %s", exc)
                raise HTTPException(502, str(exc)) from exc
            if not selected and len(request.snapshots) == 1 and evaluation.candidates:
                # Single captures always get feedback; candidates are priority-ordered.
                selected = [evaluation.candidates[0].id]
                logger.info("Model selected no cue for a capture; using top-priority cue_id=%s", selected[0])
        else:
            logger.info("No eligible correction cues from peak measurements: exercise=%s", request.exercise)
        result = approved_feedback(Feedback(
            status="assessable",
            observations=[candidates[item].observation for item in selected] or [evaluation.reason],
            cues=[candidates[item].cue for item in selected],
            spoken_text="placeholder",
        ))

    logger.info(
        "Feedback result: status=%s cues=%s spoken_text=%r",
        result.status, result.cues, result.spoken_text,
    )
    settings = Settings.from_env()
    missing_speech = settings.missing_speech()
    if missing_speech:
        return FeedbackResponse(
            feedback=result, audio_base64=None, audio_mime_type=None,
            audio_error="Speech is not configured: " + ", ".join(missing_speech),
        )
    try:
        audio = await run_in_threadpool(
            synthesize_speech, result.spoken_text, settings.elevenlabs_api_key,
            settings.elevenlabs_voice_id, settings.elevenlabs_model_id,
        )
    except SpeechError:
        logger.exception("Speech synthesis failed")
        return FeedbackResponse(
            feedback=result, audio_base64=None, audio_mime_type=None,
            audio_error="Speech could not be generated. The written feedback is available.",
        )
    return FeedbackResponse(
        feedback=result, audio_base64=base64.b64encode(audio).decode("ascii"),
        audio_mime_type="audio/mpeg", audio_error=None,
    )
