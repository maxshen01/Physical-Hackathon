from fastapi.testclient import TestClient

from llm.physio_coach import main
from llm.physio_coach.analysis import AnalysisError
from llm.physio_coach.speech import SpeechError


client = TestClient(main.app)


def payload(peak=None, exercise="squat", angle=90):
    return {
        "exercise": exercise, "camera_angle_deg": angle,
        "snapshots": [
            {"phase": "start"},
            {"phase": "peak", **(peak if peak is not None else {"knee_left_deg": 120})},
            {"phase": "finish"},
        ],
    }


def configure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-elevenlabs-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")
    monkeypatch.setenv("ELEVENLABS_MODEL_ID", "test-speech-model")


def test_health_and_feedback_with_audio(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(main, "choose_cues", lambda *_args: ["squat_depth"])
    spoken = []
    monkeypatch.setattr(main, "synthesize_speech", lambda text, *_args: spoken.append(text) or b"fake-mp3")
    assert client.get("/health").json() == {"status": "ok"}
    response = client.post("/api/feedback", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["feedback"]["cues"] == ["Go deeper"]
    assert body["audio_base64"] == "ZmFrZS1tcDM="
    assert spoken == [body["feedback"]["spoken_text"]]


def test_unsuitable_view_skips_model_and_returns_no_cue(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(main, "choose_cues", lambda *_args: (_ for _ in ()).throw(AssertionError("No model call")))
    monkeypatch.setattr(main, "synthesize_speech", lambda *_args: b"audio")
    response = client.post("/api/feedback", json=payload(angle=0))
    assert response.status_code == 200
    assert response.json()["feedback"]["status"] == "unable_to_assess"
    assert response.json()["feedback"]["cues"] == []


def test_missing_peak_skips_model(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(main, "choose_cues", lambda *_args: (_ for _ in ()).throw(AssertionError("No model call")))
    response = client.post("/api/feedback", json=payload(peak={}))
    assert response.json()["feedback"]["status"] == "unable_to_assess"


def test_in_range_uses_no_model(monkeypatch, caplog):
    configure(monkeypatch)
    monkeypatch.setattr(main, "choose_cues", lambda *_args: (_ for _ in ()).throw(AssertionError("No model call")))
    monkeypatch.setattr(main, "synthesize_speech", lambda *_args: b"audio")
    with caplog.at_level("INFO", logger="uvicorn.error"):
        response = client.post("/api/feedback", json=payload(peak={"knee_left_deg": 90}))
    assert response.status_code == 200
    assert response.json()["feedback"]["status"] == "assessable"
    assert response.json()["feedback"]["cues"] == []
    assert "No eligible correction cues" in caplog.text


def test_invalid_request_is_rejected(monkeypatch):
    configure(monkeypatch)
    assert client.post("/api/feedback", json=payload(peak={"knee_left_deg": 200})).status_code == 422
    assert client.post("/api/feedback", json=payload(exercise="unknown")).status_code == 422
    assert client.post("/api/analyse").status_code == 404


def test_model_failure_never_reaches_speech(monkeypatch):
    configure(monkeypatch)
    def fail(*_args):
        raise AnalysisError("Unsupported cue")
    monkeypatch.setattr(main, "choose_cues", fail)
    monkeypatch.setattr(main, "synthesize_speech", lambda *_args: (_ for _ in ()).throw(AssertionError("No speech call")))
    assert client.post("/api/feedback", json=payload()).status_code == 502


def test_speech_failure_keeps_text(monkeypatch, caplog):
    configure(monkeypatch)
    monkeypatch.setattr(main, "choose_cues", lambda *_args: ["squat_depth"])
    def fail(*_args):
        raise SpeechError("Provider unavailable")
    monkeypatch.setattr(main, "synthesize_speech", fail)
    response = client.post("/api/feedback", json=payload())
    assert response.status_code == 200
    assert response.json()["feedback"]["cues"] == ["Go deeper"]
    assert response.json()["audio_base64"] is None
    assert response.json()["audio_error"]
    assert "Speech synthesis failed" in caplog.text
    assert "Provider unavailable" in caplog.text


def test_missing_provider_settings(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert client.post("/api/feedback", json=payload()).status_code == 503
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "")
    monkeypatch.setattr(main, "choose_cues", lambda *_args: ["squat_depth"])
    response = client.post("/api/feedback", json=payload())
    assert response.status_code == 200
    assert response.json()["audio_base64"] is None
    assert "ELEVENLABS_VOICE_ID" in response.json()["audio_error"]
