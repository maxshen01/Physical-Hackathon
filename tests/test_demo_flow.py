"""The actual image-feature → validated LLM selection → speech boundary."""
import io
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from demo import create_demo_app
from llm.physio_coach import analysis, main
from llm.physio_coach.speech import SpeechError


@pytest.fixture
def pipeline(monkeypatch):
    for key, value in {
        "OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model",
        "ELEVENLABS_API_KEY": "test-key", "ELEVENLABS_VOICE_ID": "test-voice",
    }.items():
        monkeypatch.setenv(key, value)
    model = Mock(device="test")
    points = [NS(x=.5, y=.5, visibility=1., presence=1.) for _ in range(33)]
    # Front-view lateral raise with visible asymmetric arms, not a measured peak.
    for index, xy in {23:(.4,.7), 11:(.4,.4), 13:(.2,.4),
                      24:(.6,.7), 12:(.6,.4), 14:(.8,.6)}.items():
        points[index].x, points[index].y = xy
    model.pose.landmarks.return_value = [points]
    model.predict.return_value = {"exercise": "lateral_raise"}
    cloud = Mock()
    cloud.update.return_value = {}
    spoken, requests = [], []
    def choose(**kwargs):
        requests.append(kwargs)
        return NS(status="completed", output_text='{"cue_ids":["capture_uneven_arms"]}')
    monkeypatch.setattr(analysis, "OpenAI", lambda **kwargs: NS(responses=NS(create=choose)))
    monkeypatch.setattr(main, "synthesize_speech", lambda text, *_: spoken.append(text) or b"mp3")
    with TestClient(create_demo_app(classifier_factory=lambda:model, vision_factory=lambda:cloud)) as client:
        yield client, model, spoken, requests


def image_bytes(format="JPEG"):
    output = io.BytesIO()
    Image.new("RGB", (640, 480)).save(output, format=format)
    return output.getvalue()


def extract(client):
    response = client.post("/capture/image", data={"exercise":"lateral_raise"},
                           files={"file":("capture.jpg",image_bytes(),"image/jpeg")})
    assert response.status_code == 200
    features = response.json()
    assert features["complete_repetition_verified"] is False
    assert len(features["frames"]) == 1
    metrics = {key: item["value"] for key,item in features["frames"][0]["features"].items()}
    return {"exercise":"lateral_raise", "camera_angle_deg":0,
            "snapshots":[{"phase":"capture", **metrics}]}


def test_recognise_image_features_llm_and_voice(pipeline):
    client, model, spoken, requests = pipeline
    predicted = client.post("/predict", files={"file":("frame.jpg",image_bytes(),"image/jpeg")})
    assert predicted.json()["exercise"] == "lateral_raise"
    response = client.post("/api/feedback", json=extract(client))
    assert response.status_code == 200
    body = response.json()
    assert body["feedback"]["status"] == "assessable"
    assert body["audio_base64"] == "bXAz"
    assert spoken == [body["feedback"]["spoken_text"]]
    assert "prescribed" in spoken[0]
    assert requests[0]["store"] is False
    llm_input = json.loads(requests[0]["input"][0]["content"][0]["text"])
    assert [x["phase"] for x in llm_input["snapshots"]] == ["capture"]
    assert len(llm_input["eligible_cues"]) == 1
    assert "input_image" not in str(requests)


@pytest.mark.parametrize("payload,status", [(b"",400),(b"corrupt",400),(image_bytes("GIF"),400),(b"x"*(1024*1024+1),413)])
def test_invalid_capture_never_reaches_pose_llm_or_speech(pipeline,payload,status):
    client, model, spoken, requests = pipeline
    response = client.post("/capture/image",data={"exercise":"squat"},files={"file":("bad.jpg",payload,"image/jpeg")})
    assert response.status_code == status
    model.pose.landmarks.assert_not_called()
    assert not spoken and not requests


def test_unclear_image_produces_clear_spoken_retry(pipeline):
    client, model, spoken, requests = pipeline
    model.pose.landmarks.return_value=[]
    response=client.post("/api/feedback",json=extract(client))
    assert response.json()["feedback"]["status"] == "unable_to_assess"
    assert response.json()["feedback"]["cues"] == []
    assert "try again" in spoken[0]
    assert not requests


@pytest.mark.parametrize("status,output", [("completed","not json"),("completed",'{"cue_ids":["squat_depth"]}'),("incomplete",'{"cue_ids":[]}'),("completed","")])
def test_invalid_llm_output_never_reaches_voice(pipeline,monkeypatch,status,output):
    client, _, spoken, _ = pipeline
    monkeypatch.setattr(analysis,"OpenAI",lambda **_:NS(responses=NS(create=lambda **_:NS(status=status,output_text=output))))
    response=client.post("/api/feedback",json=extract(client))
    assert response.status_code == 502
    assert not spoken


def test_refusal_is_explicit_and_not_spoken(pipeline,monkeypatch):
    client, _, spoken, _ = pipeline
    monkeypatch.setattr(analysis,"OpenAI",lambda **_:NS(responses=NS(create=lambda **_:NS(
        status="completed",output_text="",output=[NS(content=[NS(type="refusal")])]))))
    response=client.post("/api/feedback",json=extract(client))
    assert response.status_code == 502 and "declined" in response.json()["detail"]
    assert not spoken


def test_timeout_is_explicit_and_not_spoken(pipeline,monkeypatch):
    client, _, spoken, _ = pipeline
    def timeout(**_):
        raise analysis.APITimeoutError(request=httpx.Request("POST","https://api.openai.com"))
    monkeypatch.setattr(analysis,"OpenAI",lambda **_:NS(responses=NS(create=timeout)))
    response=client.post("/api/feedback",json=extract(client))
    assert response.status_code == 502 and "timed out" in response.json()["detail"]
    assert not spoken


def test_speech_failure_preserves_validated_transcript(pipeline,monkeypatch):
    client, _, _, _ = pipeline
    def fail(*_): raise SpeechError("Unavailable")
    monkeypatch.setattr(main,"synthesize_speech",fail)
    body=client.post("/api/feedback",json=extract(client)).json()
    assert body["feedback"]["spoken_text"]
    assert body["audio_base64"] is None and body["audio_error"]


def test_single_image_cannot_trigger_depth_corrections(pipeline,monkeypatch):
    client, _, spoken, requests = pipeline
    monkeypatch.setattr(analysis,"OpenAI",lambda **_:NS(responses=NS(create=lambda **_:NS(status="completed",output_text='{"cue_ids":[]}'))))
    body=client.post("/api/feedback",json={"exercise":"squat","camera_angle_deg":90,
        "snapshots":[{"phase":"capture","knee_left_deg":175}]}).json()
    assert body["feedback"]["cues"] == []
    assert "one position" in body["feedback"]["observations"][0]
    assert "deeper" not in spoken[0]


def test_fake_stages_and_wrong_view_rejected(pipeline):
    client, _, spoken, requests = pipeline
    payload=extract(client)
    payload["snapshots"] *= 3
    assert client.post("/api/feedback",json=payload).status_code == 422
    assert not spoken and not requests
    payload["snapshots"] = payload["snapshots"][:1]
    payload["camera_angle_deg"]=90
    body=client.post("/api/feedback",json=payload).json()
    assert body["feedback"]["status"] == "unable_to_assess"
    assert not requests


@pytest.mark.parametrize("outcome", ["success", "corrupt", "pose_failure"])
def test_image_upload_is_closed_on_success_and_failure(pipeline,outcome):
    from fastapi import HTTPException, UploadFile
    client, model, _, _ = pipeline
    endpoint = next(route.endpoint for route in client.app.routes if getattr(route,"path",None)=="/capture/image")
    upload = UploadFile(filename="capture.jpg",file=io.BytesIO(b"bad" if outcome=="corrupt" else image_bytes()))
    if outcome=="pose_failure":
        model.pose.landmarks.side_effect=RuntimeError("pose unavailable")
    if outcome=="success":
        endpoint(exercise="squat",file=upload)
    else:
        with pytest.raises(HTTPException):
            endpoint(exercise="squat",file=upload)
    assert upload.file.closed
