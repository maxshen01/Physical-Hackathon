"""Provider selection tests; imports keep the existing local llm package path."""

import json
from types import SimpleNamespace

import pytest

from llm.physio_coach import analysis
from llm.physio_coach.rules import evaluate
from llm.physio_coach.models import FeedbackRequest


def sample():
    request = FeedbackRequest.model_validate({
        "exercise": "squat", "camera_angle_deg": 90,
        "snapshots": [
            {"phase": "start", "knee_left_deg": 170},
            {"phase": "peak", "knee_left_deg": 120},
            {"phase": "finish", "knee_left_deg": 175},
        ],
    })
    return request, evaluate(request).candidates


def test_selection_sends_stages_candidates_and_nonstored_request(monkeypatch):
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(status="completed", output_text='{"cue_ids":["squat_depth"]}')

    monkeypatch.setattr(analysis, "OpenAI", lambda **_kwargs: SimpleNamespace(responses=FakeResponses()))
    request, candidates = sample()
    assert analysis.choose_cues(request, candidates, "key", "model") == ["squat_depth"]
    assert captured["store"] is False
    payload = json.loads(captured["input"][0]["content"][0]["text"])
    assert [item["phase"] for item in payload["snapshots"]] == ["start", "peak", "finish"]
    assert payload["eligible_cues"][0]["id"] == "squat_depth"
    assert "image_url" not in str(captured)


def test_empty_model_selection_is_visible_in_logs(monkeypatch, caplog):
    monkeypatch.setattr(analysis, "OpenAI", lambda **_kwargs: SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_params: SimpleNamespace(
            id="resp_test", status="completed", output_text='{"cue_ids":[]}'))))
    request, candidates = sample()
    with caplog.at_level("INFO", logger="uvicorn.error"):
        assert analysis.choose_cues(request, candidates, "secret-key", "model") == []
    assert "response_id=resp_test" in caplog.text
    assert 'output_text=\'{"cue_ids":[]}\'' in caplog.text
    assert "cue_ids=[]" in caplog.text
    assert "secret-key" not in caplog.text


@pytest.mark.parametrize("status,output", [
    ("incomplete", '{"cue_ids":[]}'),
    ("completed", ""),
    ("completed", '{"cue_ids":["made_up"]}'),
    ("completed", '{"cue_ids":["squat_depth","squat_depth"]}'),
    ("completed", '{"cue_ids":["squat_depth","x","y"]}'),
    ("completed", '{"cue_ids":"squat_depth"}'),
])
def test_invalid_selection_is_rejected(monkeypatch, status, output):
    monkeypatch.setattr(analysis, "OpenAI", lambda **_kwargs: SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_params: SimpleNamespace(status=status, output_text=output))))
    request, candidates = sample()
    with pytest.raises(analysis.AnalysisError):
        analysis.choose_cues(request, candidates, "key", "model")
