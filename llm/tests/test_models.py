import pytest
from pydantic import ValidationError

from llm.physio_coach.models import Feedback, approved_feedback


def test_spoken_text_is_built_from_approved_cues():
    draft = Feedback(status="assessable", observations=["Peak knee angle was 112°."],
                     cues=["Go deeper"], spoken_text="Untrusted model text")
    approved = approved_feedback(draft)
    assert "Go deeper" in approved.spoken_text
    assert "Untrusted" not in approved.spoken_text
    assert "see" not in approved.spoken_text


def test_unassessable_cannot_contain_cues():
    with pytest.raises(ValidationError):
        Feedback(status="unable_to_assess", observations=["Camera view is unsuitable."],
                 cues=["Go deeper"], spoken_text="draft")
