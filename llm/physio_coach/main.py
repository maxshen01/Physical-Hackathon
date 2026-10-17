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
logger = logging.getLogger(__name__)


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
    evaluation = evaluate(request)
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
                raise HTTPException(502, str(exc)) from exc
        result = approved_feedback(Feedback(
            status="assessable",
            observations=[candidates[item].observation for item in selected] or [evaluation.reason],
            cues=[candidates[item].cue for item in selected],
            spoken_text="placeholder",
        ))

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
