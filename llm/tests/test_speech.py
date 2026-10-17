import httpx
import pytest

from llm.physio_coach import speech


def test_speech_sends_only_text_and_returns_mp3(monkeypatch):
    captured = {}
    real_client = httpx.Client

    def handle(request):
        captured["request"] = request
        return httpx.Response(200, content=b"mp3-bytes")

    monkeypatch.setattr(
        speech.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs),
    )

    audio = speech.synthesize_speech("Keep your feet flat.", "secret", "voice", "model")

    assert audio == b"mp3-bytes"
    request = captured["request"]
    assert request.url.path == "/v1/text-to-speech/voice/stream"
    assert request.url.params["output_format"] == "mp3_44100_128"
    assert request.headers["xi-api-key"] == "secret"
    assert request.read().decode() == '{"text":"Keep your feet flat.","model_id":"model"}'


def test_speech_http_failure_is_reported(monkeypatch):
    real_client = httpx.Client
    monkeypatch.setattr(
        speech.httpx,
        "Client",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(503, json={"detail": "quota exceeded"})
            ),
            **kwargs,
        ),
    )

    with pytest.raises(speech.SpeechError, match="ElevenLabs returned HTTP 503: .*quota exceeded"):
        speech.synthesize_speech("Try again.", "secret", "voice", "model")
