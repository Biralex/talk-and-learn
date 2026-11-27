"""
Piper TTS (https://github.com/OHF-Voice/piper1-gpl): small voices for many languages,
including Serbian, run on CPU through ONNX Runtime. Each voice is a separate ~60-80 MB
download from Hugging Face (rhasspy/piper-voices).
"""
import io
import threading
import wave
from pathlib import Path

from src import settings
from src.adhoc.log_utils import get_logger
from src.pronunciation_of_words.common import download

logger = get_logger(__name__)

_voices: dict = {}
_lock = threading.Lock()


def voice_paths(voice: str) -> tuple[Path, Path]:
    model = settings.PIPER_DIR / f"{voice}.onnx"
    return model, model.with_name(model.name + ".json")


def models_present(voice: str) -> bool:
    return all(path.exists() for path in voice_paths(voice))


def voice_url(voice: str, filename: str) -> str:
    # sr_RS-serbski_institut-medium -> sr/sr_RS/serbski_institut/medium/<file>
    locale, name, quality = voice.split("-", 2)
    family = locale.split("_")[0]
    return f"{settings.PIPER_VOICES_URL}/{family}/{locale}/{name}/{quality}/{filename}?download=true"


def download_models(voice: str) -> None:
    for path in voice_paths(voice):
        if path.exists():
            logger.info("%s is already downloaded", path.name)
        else:
            download(voice_url(voice, path.name), path, settings.PIPER_SHA256.get(path.name))
    logger.info("Piper voice %s is ready in %s", voice, settings.PIPER_DIR)


def _get_voice(voice: str):
    with _lock:
        if voice not in _voices:
            if not models_present(voice):
                raise FileNotFoundError(f"Piper voice {voice} not found in {settings.PIPER_DIR}")
            from piper import PiperVoice  # heavy import, only when TTS is actually used

            model_path, config_path = voice_paths(voice)
            _voices[voice] = PiperVoice.load(model_path, config_path=config_path)
            logger.info("Piper voice %s loaded", voice)
        return _voices[voice]


def generate(text: str, voice: str, speaker: int | None = None, speed: float = 1.0) -> bytes:
    """Voice text and return WAV bytes"""
    from piper.config import SynthesisConfig

    piper_voice = _get_voice(voice)
    # A full stop makes Piper finish the word with a natural falling intonation
    if text and text[-1].isalnum():
        text += "."
    config = SynthesisConfig(speaker_id=speaker, length_scale=1.0 / speed)
    buf = io.BytesIO()
    with _lock, wave.open(buf, "wb") as wav:
        piper_voice.synthesize_wav(text, wav, syn_config=config)
    return buf.getvalue()
