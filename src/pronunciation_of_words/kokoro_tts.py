"""
Kokoro-82M via ONNX Runtime: runs on CPU inside this process, no Docker, PyTorch or GPU.
The model files (~120 MB) are shared by all its voices and languages.
"""
import threading
from pathlib import Path

from src import settings
from src.adhoc.log_utils import get_logger
from src.pronunciation_of_words.common import download, to_wav

logger = get_logger(__name__)

_model = None
_lock = threading.Lock()


def model_paths() -> tuple[Path, Path]:
    return settings.KOKORO_DIR / settings.KOKORO_MODEL_FILE, settings.KOKORO_DIR / settings.KOKORO_VOICES_FILE


def models_present() -> bool:
    return all(path.exists() for path in model_paths())


def download_models() -> None:
    model_path, voices_path = model_paths()
    files = [
        (settings.KOKORO_MODEL_URL, model_path, settings.KOKORO_MODEL_SHA256),
        (settings.KOKORO_VOICES_URL, voices_path, settings.KOKORO_VOICES_SHA256),
    ]
    for url, path, sha256 in files:
        if path.exists():
            logger.info("%s is already downloaded", path.name)
        else:
            download(url, path, sha256)
    logger.info("Kokoro model is ready in %s", settings.KOKORO_DIR)


def _get_model():
    """Load the model on first use and keep it in memory"""
    global _model
    with _lock:
        if _model is None:
            if not models_present():
                raise FileNotFoundError(f"Kokoro model not found in {settings.KOKORO_DIR}")
            from kokoro_onnx import Kokoro  # heavy import, only when TTS is actually used

            model_path, voices_path = model_paths()
            _model = Kokoro(str(model_path), str(voices_path))
            logger.info("Kokoro model loaded")
        return _model


def generate(text: str, voice: str, espeak: str = "en-us", speed: float = 1.0) -> bytes:
    """Voice text and return WAV bytes. espeak is the pronunciation language: Kokoro's own
    (en-us, en-gb, es, fr-fr, it, pt-br, hi, ja, cmn) or any other espeak-ng language such as
    "sr", which is then read with the given voice"""
    model = _get_model()
    with _lock:  # one synthesis at a time: the ONNX session already uses all CPU cores
        samples, sample_rate = model.create(text, voice=voice, speed=speed, lang=espeak)
    return to_wav(samples, sample_rate)
