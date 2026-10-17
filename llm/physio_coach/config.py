"""Server-side provider configuration."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    elevenlabs_model_id: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-6-astra").strip(),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", "").strip(),
            elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", "").strip(),
            elevenlabs_model_id=os.getenv(
                "ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"
            ).strip(),
        )

    def missing_analysis(self) -> list[str]:
        required = {
            "OPENAI_API_KEY": self.openai_api_key,
            "OPENAI_MODEL": self.openai_model,
        }
        return [name for name, value in required.items() if not value]

    def missing_speech(self) -> list[str]:
        required = {
            "ELEVENLABS_API_KEY": self.elevenlabs_api_key,
            "ELEVENLABS_VOICE_ID": self.elevenlabs_voice_id,
            "ELEVENLABS_MODEL_ID": self.elevenlabs_model_id,
        }
        return [name for name, value in required.items() if not value]

