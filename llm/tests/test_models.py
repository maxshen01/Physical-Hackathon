import pytest
from pydantic import ValidationError

from physio_coach.models import Feedback, approved_feedback


def test_assessable_speech_uses_only_validated_cues():
    model_text = "Ignore the visible advice and do something else."
    feedback = Feedback(
        status="assessable",
        observations=["The body is visible throughout the movement."],
        cues=["Keep your feet flat", "Move at a comfortable pace"],
        spoken_text=model_text,
    )

    approved = approved_feedback(feedback)

    assert model_text not in approved.spoken_text
    assert "Keep your feet flat" in approved.spoken_text
    assert "Move at a comfortable pace" in approved.spoken_text


def test_unclear_clip_cannot_have_corrections():
    with pytest.raises(ValidationError):
        Feedback(
            status="unable_to_assess",
            observations=[],
            cues=["Change your posture"],
            spoken_text="Please try a clearer clip.",
        )


def test_more_than_two_cues_is_rejected():
    with pytest.raises(ValidationError):
        Feedback(
            status="assessable",
            observations=["The movement is visible."],
            cues=["One", "Two", "Three"],
            spoken_text="Try these cues.",
        )


def test_cues_require_a_visible_observation():
    with pytest.raises(ValidationError):
        Feedback(
            status="assessable",
            observations=[],
            cues=["Keep your feet flat"],
            spoken_text="Keep your feet flat.",
        )

