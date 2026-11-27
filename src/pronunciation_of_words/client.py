import re
from pathlib import Path
from src import settings
from src.adhoc.log_utils import get_logger

logger = get_logger(__name__)


def generate(text: str, lang: str = settings.DEFAULT_LANG, speed: float = 1.0) -> bytes:
    """Return WAV bytes for text using the backend chosen in settings.TTS_BACKEND"""
    if settings.TTS_BACKEND == "local":
        from src.pronunciation_of_words import local_tts

        return local_tts.generate(text, lang=lang, speed=speed)

    if settings.TTS_BACKEND == "server":
        if lang != "en":
            raise RuntimeError("The TTS server only speaks English; use TTS_BACKEND = 'local' for other languages")
        import requests

        response = requests.post(
            f"{settings.TTS_URL}/tts",
            json={"text": text, "voice": settings.LANGUAGES["en"]["tts"]["voice"], "speed": speed},
            timeout=30,
        )
        response.raise_for_status()
        return response.content

    if settings.TTS_BACKEND == "off":
        raise RuntimeError("TTS is turned off (TTS_BACKEND = 'off')")

    raise ValueError(f"Unknown TTS_BACKEND {settings.TTS_BACKEND!r}: use 'local', 'server' or 'off'")


def safe_filename(text: str) -> str:
    """Turn a word or phrase into a file name: keep letters, digits, - and ', replace the rest with _"""
    name = re.sub(r"[^\w\-']+", "_", text.strip()).strip("_")
    return name or "word"


def save(text: str, lang: str = settings.DEFAULT_LANG, speed: float = 1.0) -> Path:
    """Voice text and save it as data/audio/<lang>/<text>_<voice>.wav"""
    from src.pronunciation_of_words.local_tts import voice_tag

    audio = generate(text, lang=lang, speed=speed)
    folder = settings.AUDIO_DIR / lang
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{safe_filename(text)}_{voice_tag(lang)}.wav"
    path.write_bytes(audio)
    logger.info("Saved audio to %s", path)
    return path
