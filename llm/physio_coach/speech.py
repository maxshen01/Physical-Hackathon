"""ElevenLabs text-to-speech integration."""

from urllib.parse import quote

import httpx


class SpeechError(Exception):
    """Speech could not be generated."""


MAX_AUDIO_BYTES = 5 * 1024 * 1024


def synthesize_speech(
    text: str, api_key: str, voice_id: str, model_id: str
) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{quote(voice_id, safe='')}/stream"
    chunks: list[bytes] = []
    size = 0
    try:
        with httpx.Client(timeout=45.0) as client:
            with client.stream(
                "POST",
                url,
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json={"text": text, "model_id": model_id},
            ) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    detail = response.read().decode("utf-8", errors="replace")
                    raise SpeechError(
                        f"ElevenLabs returned HTTP {response.status_code}: {detail}"
                    ) from exc
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_AUDIO_BYTES:
                        raise SpeechError("The speech response was too large")
                    chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise SpeechError("The speech service is unavailable") from exc
    audio = b"".join(chunks)
    if not audio:
        raise SpeechError("The speech service returned no audio")
    return audio
