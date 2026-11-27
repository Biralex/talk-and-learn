"""
Local text-to-speech with Kokoro-82M via ONNX Runtime: runs on CPU inside this
process, no Docker, PyTorch or GPU needed. Model files (~120 MB) are downloaded
once into settings.KOKORO_DIR:

    python -m src.pronunciation_of_words.local_tts            # download the model
    python -m src.pronunciation_of_words.local_tts "hello"    # also voice a test word
"""
import hashlib
import io
import sys
import threading
import urllib.request
import wave
from pathlib import Path

import numpy as np

from src import settings
from src.adhoc.log_utils import get_logger

logger = get_logger(__name__)

_model = None
_lock = threading.Lock()


def model_paths() -> tuple[Path, Path]:
    return settings.KOKORO_DIR / settings.KOKORO_MODEL_FILE, settings.KOKORO_DIR / settings.KOKORO_VOICES_FILE


def models_present() -> bool:
    return all(path.exists() for path in model_paths())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, dest: Path, sha256: str) -> None:
    """Download url to dest via a temporary .part file, check its SHA-256, then move into place.
    Progress goes to stderr: stdout is the MCP protocol channel."""
    tmp = dest.with_name(dest.name + ".part")
    print(f"Downloading {dest.name} ...", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=60) as response, tmp.open("wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while chunk := response.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done >> 20} / {total >> 20} MB", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    actual = _sha256(tmp)
    if actual != sha256:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Checksum mismatch for {dest.name}: expected {sha256}, got {actual}")
    tmp.replace(dest)


def download_models() -> None:
    """Download the Kokoro model and voices if they are not there yet"""
    settings.KOKORO_DIR.mkdir(parents=True, exist_ok=True)
    model_path, voices_path = model_paths()
    files = [
        (settings.KOKORO_MODEL_URL, model_path, settings.KOKORO_MODEL_SHA256),
        (settings.KOKORO_VOICES_URL, voices_path, settings.KOKORO_VOICES_SHA256),
    ]
    for url, path, sha256 in files:
        if path.exists():
            logger.info("%s is already downloaded", path.name)
        else:
            _download(url, path, sha256)
    logger.info("Kokoro model is ready in %s", settings.KOKORO_DIR)


def _get_model():
    """Load the model on first use and keep it in memory"""
    global _model
    with _lock:
        if _model is None:
            if not models_present():
                raise FileNotFoundError(
                    f"Kokoro model not found in {settings.KOKORO_DIR}. "
                    "Download it with: python -m src.pronunciation_of_words.local_tts"
                )
            from kokoro_onnx import Kokoro  # heavy import, only when TTS is actually used

            model_path, voices_path = model_paths()
            _model = Kokoro(str(model_path), str(voices_path))
            logger.info("Kokoro model loaded")
        return _model


def to_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    """Encode float samples in [-1, 1] as 16-bit mono WAV"""
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def generate(text: str, voice: str = "af_sky", speed: float = 1.0) -> bytes:
    """Voice text and return it as WAV bytes"""
    model = _get_model()
    with _lock:  # one synthesis at a time: the ONNX session already uses all CPU cores
        samples, sample_rate = model.create(text, voice=voice, speed=speed, lang=settings.TTS_LANG)
    return to_wav(samples, sample_rate)


if __name__ == "__main__":
    download_models()
    if len(sys.argv) > 1:
        from src.pronunciation_of_words import client

        path = client.save(" ".join(sys.argv[1:]), voice=settings.TTS_VOICE)
        print(f"Saved {path}")
