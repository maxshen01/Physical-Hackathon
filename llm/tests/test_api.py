from pathlib import Path

from fastapi.testclient import TestClient

from physio_coach import main
from physio_coach.analysis import AnalysisError
from physio_coach.models import Feedback, approved_feedback
from physio_coach.speech import SpeechError
from physio_coach.video import VideoError


client = TestClient(main.app)
FEEDBACK = approved_feedback(
    Feedback(
        status="assessable",
        observations=["The movement is visible."],
        cues=["Keep your feet flat"],
        spoken_text="Model draft",
    )
)


def configure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-elevenlabs-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test-voice")
    monkeypatch.setenv("ELEVENLABS_MODEL_ID", "test-speech-model")


def post_video(name="Sit to stand", filename="clip.mp4", content=b"fake-video"):
    return client.post(
        "/api/analyse",
        data={"exercise_name": name},
        files={"video": (filename, content, "video/mp4")},
    )


def test_local_page_and_assets_are_served():
    assert client.get("/").status_code == 200
    assert "Review your movement" in client.get("/").text
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200


def test_clear_clip_returns_text_and_audio_and_removes_video(monkeypatch):
    configure(monkeypatch)
    paths: list[Path] = []

    def fake_extract(video_path, _work_dir):
        paths.append(video_path)
        assert video_path.read_bytes() == b"fake-video"
        return []

    monkeypatch.setattr(main, "extract_frames", fake_extract)
    monkeypatch.setattr(main, "analyse_frames", lambda *_args: FEEDBACK)
    monkeypatch.setattr(main, "synthesize_speech", lambda *_args: b"fake-mp3")

    response = post_video()

    assert response.status_code == 200
    body = response.json()
    assert body["feedback"]["cues"] == ["Keep your feet flat"]
    assert body["audio_base64"] == "ZmFrZS1tcDM="
    assert body["audio_error"] is None
    assert paths and not paths[0].exists()


def test_unclear_clip_has_no_cues(monkeypatch):
    configure(monkeypatch)
    unclear = approved_feedback(
        Feedback(
            status="unable_to_assess",
            observations=["The legs are outside the frame."],
            cues=[],
            spoken_text="Model draft",
        )
    )
    monkeypatch.setattr(main, "extract_frames", lambda *_args: [])
    monkeypatch.setattr(main, "analyse_frames", lambda *_args: unclear)
    monkeypatch.setattr(main, "synthesize_speech", lambda *_args: b"fake-mp3")

    response = post_video()

    assert response.status_code == 200
    assert response.json()["feedback"]["status"] == "unable_to_assess"
    assert response.json()["feedback"]["cues"] == []


def test_speech_failure_keeps_validated_text(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(main, "extract_frames", lambda *_args: [])
    monkeypatch.setattr(main, "analyse_frames", lambda *_args: FEEDBACK)

    def fail_speech(*_args):
        raise SpeechError("Provider failed")

    monkeypatch.setattr(main, "synthesize_speech", fail_speech)
    response = post_video()

    assert response.status_code == 200
    assert response.json()["feedback"]["cues"] == ["Keep your feet flat"]
    assert response.json()["audio_base64"] is None
    assert response.json()["audio_error"]


def test_invalid_uploads_do_not_call_model(monkeypatch):
    configure(monkeypatch)

    def should_not_analyse(*_args):
        raise AssertionError("Analysis should not run")

    monkeypatch.setattr(main, "analyse_frames", should_not_analyse)
    assert post_video(filename="clip.txt").status_code == 400
    assert post_video(content=b"").status_code == 400

    def corrupt_video(*_args):
        raise VideoError("The video could not be opened")

    monkeypatch.setattr(main, "extract_frames", corrupt_video)
    assert post_video().status_code == 400


def test_upload_size_limit_is_checked_while_streaming(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 4)
    monkeypatch.setattr(
        main,
        "extract_frames",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Video should not run")),
    )

    response = post_video(content=b"12345")

    assert response.status_code == 413


def test_model_failure_removes_temporary_video_and_skips_speech(monkeypatch):
    configure(monkeypatch)
    paths: list[Path] = []
    monkeypatch.setattr(
        main,
        "extract_frames",
        lambda video_path, _work_dir: paths.append(video_path) or [],
    )

    def fail_analysis(*_args):
        raise AnalysisError("Invalid feedback")

    monkeypatch.setattr(main, "analyse_frames", fail_analysis)
    monkeypatch.setattr(
        main,
        "synthesize_speech",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Speech should not run")),
    )

    response = post_video()

    assert response.status_code == 502
    assert paths and not paths[0].exists()


def test_missing_speech_configuration_keeps_text(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "")
    monkeypatch.setattr(main, "extract_frames", lambda *_args: [])
    monkeypatch.setattr(main, "analyse_frames", lambda *_args: FEEDBACK)

    response = post_video()

    assert response.status_code == 200
    assert response.json()["feedback"]["cues"] == ["Keep your feet flat"]
    assert response.json()["audio_base64"] is None
    assert "ELEVENLABS_VOICE_ID" in response.json()["audio_error"]

