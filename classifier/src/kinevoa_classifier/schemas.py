"""Public wire types shared by the HTTP adapter and generated API schema."""
from typing import Literal
from pydantic import BaseModel, Field


class PredictionResponse(BaseModel):
    exercise: Literal['squat', 'pushup', 'lateral_raise', 'unknown']
    display_name: Literal['Squat', 'Push-up', 'Lateral raise'] | None = None
    source: str | None = None
    preview_label: Literal['Squat', 'Push-up', 'Lateral raise', 'Unknown'] | None = None
    preview_score: float | None = Field(default=None, ge=0, le=1)
    preview_source: str | None = None
    cloud_status: str | None = None
    cloud_checks: int | None = Field(default=None, ge=0)
    cloud_confirmed: bool | None = None


class HealthResponse(BaseModel):
    ready: bool
    device: str
    cloud_configured: bool
