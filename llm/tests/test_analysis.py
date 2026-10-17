import json
from types import SimpleNamespace

import pytest

from physio_coach import analysis
from physio_coach.video import Frame


def test_analysis_sends_timestamped_frames_and_nonstored_request(monkeypatch, tmp_path):
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"jpeg-image")
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                status="completed",
                output_text=json.dumps(
                    {
                        "status": "assessable",
                        "observations": ["The movement is visible."],
                        "cues": ["Keep your feet flat"],
                        "spoken_text": "A model-written script.",
                    }
                ),
            )

    monkeypatch.setattr(
        analysis,
        "OpenAI",
        lambda **_kwargs: SimpleNamespace(responses=FakeResponses()),
    )
    feedback = analysis.analyse_frames(
        "Sit to stand", [Frame(1.5, image)], "test-key", "test-model"
    )

    assert captured["model"] == "test-model"
    assert captured["store"] is False
    content = captured["input"][0]["content"]
    assert "Sit to stand" in content[0]["text"]
    assert "1.50 seconds" in content[1]["text"]
    assert content[2]["image_url"].startswith("data:image/jpeg;base64,")
    assert feedback.spoken_text != "A model-written script."


@pytest.mark.parametrize(
    "status,output",
    [
        ("completed", ""),
        ("incomplete", "{}"),
        ("completed", '{"status":"assessable","cues":"wrong"}'),
        (
            "completed",
            json.dumps(
                {
                    "status": "unable_to_assess",
                    "observations": [],
                    "cues": ["Invented correction"],
                    "spoken_text": "Bad advice",
                }
            ),
        ),
    ],
)
def test_analysis_rejects_refused_incomplete_or_invalid_output(
    monkeypatch, tmp_path, status, output
):
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"jpeg-image")
    monkeypatch.setattr(
        analysis,
        "OpenAI",
        lambda **_kwargs: SimpleNamespace(
            responses=SimpleNamespace(
                create=lambda **_params: SimpleNamespace(status=status, output_text=output)
            )
        ),
    )

    with pytest.raises(analysis.AnalysisError):
        analysis.analyse_frames("Sit to stand", [Frame(0.5, image)], "key", "model")

