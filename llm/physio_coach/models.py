"""Validated measurement input and feedback returned by the API."""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Exercise = Literal["squat", "pushup", "lateral_raise"]
Phase = Literal["start", "peak", "finish", "capture"]
Angle = float | None


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    phase: Phase
    knee_left_deg: Angle = Field(default=None, ge=0, le=180)
    knee_right_deg: Angle = Field(default=None, ge=0, le=180)
    torso_inclination_deg: Angle = Field(default=None, ge=0, le=180)
    elbow_left_deg: Angle = Field(default=None, ge=0, le=180)
    elbow_right_deg: Angle = Field(default=None, ge=0, le=180)
    body_alignment_left_deg: Angle = Field(default=None, ge=0, le=180)
    body_alignment_right_deg: Angle = Field(default=None, ge=0, le=180)
    hip_offset_left_torso_lengths: float | None = None
    hip_offset_right_torso_lengths: float | None = None
    arm_left_deg: Angle = Field(default=None, ge=0, le=180)
    arm_right_deg: Angle = Field(default=None, ge=0, le=180)
    arm_difference_deg: Angle = Field(default=None, ge=0, le=180)

    @model_validator(mode="after")
    def arm_difference_matches(self) -> "Snapshot":
        if all(value is not None for value in (self.arm_left_deg, self.arm_right_deg, self.arm_difference_deg)):
            expected = abs(self.arm_left_deg - self.arm_right_deg)
            if not math.isclose(self.arm_difference_deg, expected, abs_tol=1.0):
                raise ValueError("arm_difference_deg must match the two arm angles")
        return self


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    exercise: Exercise
    camera_angle_deg: float = Field(ge=-180, le=180)
    snapshots: list[Snapshot] = Field(min_length=1, max_length=3)

    @field_validator("snapshots")
    @classmethod
    def correct_order(cls, snapshots: list[Snapshot]) -> list[Snapshot]:
        if [item.phase for item in snapshots] not in (["capture"], ["start", "peak", "finish"]):
            raise ValueError("Supply one capture or ordered start, peak, finish snapshots")
        return snapshots

    @model_validator(mode="after")
    def metrics_match_exercise(self) -> "FeedbackRequest":
        allowed = {
            "squat": {"knee_left_deg", "knee_right_deg", "torso_inclination_deg"},
            "pushup": {
                "elbow_left_deg", "elbow_right_deg", "body_alignment_left_deg",
                "body_alignment_right_deg", "hip_offset_left_torso_lengths",
                "hip_offset_right_torso_lengths",
            },
            "lateral_raise": {"arm_left_deg", "arm_right_deg", "arm_difference_deg"},
        }[self.exercise]
        for snapshot in self.snapshots:
            supplied = snapshot.model_dump(exclude_none=True, exclude={"phase"})
            if supplied.keys() - allowed:
                raise ValueError("Snapshot contains measurements for another exercise")
        return self


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
            raise ValueError("Unassessable measurements cannot have form cues")
        if self.cues and not self.observations:
            raise ValueError("Form cues require measured observations")
        return self


def approved_feedback(feedback: Feedback) -> Feedback:
    """Build the spoken script solely from server-approved cues."""
    if feedback.status == "unable_to_assess":
        speech = "I can't give reliable form feedback from these measurements. Please check the camera view and try again."
    elif not feedback.cues:
        speech = "These measurements do not support a specific correction. Please follow your physiotherapist's plan."
    else:
        speech = "Based on these measurements, try this. " + feedback.cues[0].rstrip(" .") + "."
        if len(feedback.cues) == 2:
            second = feedback.cues[1].rstrip(" .")
            speech += " Also, " + second[:1].lower() + second[1:] + "."
    return Feedback.model_validate({**feedback.model_dump(), "spoken_text": speech})
