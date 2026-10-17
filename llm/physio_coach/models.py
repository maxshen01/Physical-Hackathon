"""Validated feedback shared by the API and provider integrations."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["assessable", "unable_to_assess"]
    observations: list[str] = Field(max_length=3)
    cues: list[str] = Field(max_length=2)
    spoken_text: str

    @field_validator("observations", "cues")
    @classmethod
    def nonempty_items(cls, items: list[str]) -> list[str]:
        cleaned = [item.strip() for item in items]
        if any(not item or len(item) > 240 for item in cleaned):
            raise ValueError("Feedback items must be concise and nonempty")
        return cleaned

    @field_validator("spoken_text")
    @classmethod
    def concise_speech(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 500:
            raise ValueError("Spoken feedback must be concise and nonempty")
        return value

    @model_validator(mode="after")
    def status_matches_cues(self) -> "Feedback":
        if self.status == "unable_to_assess" and self.cues:
            raise ValueError("Unassessable clips cannot have form cues")
        if self.cues and not self.observations:
            raise ValueError("Form cues require visible observations")
        return self


def approved_feedback(feedback: Feedback) -> Feedback:
    """Build speech from validated cues so it cannot contradict the displayed advice."""
    if feedback.status == "unable_to_assess":
        speech = (
            "I can't assess this movement clearly. Please try a new clip that shows "
            "your whole movement and the relevant body parts."
        )
    elif not feedback.cues:
        speech = (
            "I can see the movement, but I can't suggest a specific correction "
            "from this clip. Please check your form with your physiotherapist."
        )
    else:
        speech = "From what I can see, here is something to try. "
        speech += feedback.cues[0].rstrip(" .") + "."
        if len(feedback.cues) == 2:
            speech += " Also, " + feedback.cues[1].rstrip(" .") + "."
    return feedback.model_copy(update={"spoken_text": speech})

