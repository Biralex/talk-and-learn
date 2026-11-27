import re
from pathlib import Path
import requests
from src import settings
from src.adhoc.log_utils import get_logger

logger = get_logger(__name__)


def generate(text: str, voice: str = 'af_sky', speed: float = 1.0) -> bytes:
    response = requests.post(
        f"{settings.TTS_URL}/tts",
        json={"text": text, "voice": voice, "speed": speed},
        timeout=30,
    )
    response.raise_for_status()
    return response.content


def safe_filename(text: str) -> str:
    """Turn a word or phrase into a file name: keep letters, digits, - and ', replace the rest with _"""
    name = re.sub(r"[^\w\-']+", "_", text.strip()).strip("_")
    return name or "word"


def save(text: str, voice: str = 'af_sky', speed: float = 1.0) -> Path:
    audio = generate(text, voice=voice, speed=speed)
    settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    path = settings.AUDIO_DIR / f"{safe_filename(text)}_{voice}.wav"
    path.write_bytes(audio)
    logger.info("Saved audio to %s", path)
    return path
