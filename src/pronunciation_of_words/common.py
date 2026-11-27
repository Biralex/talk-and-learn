"""Helpers shared by the TTS engines: downloading model files and encoding WAV"""
import hashlib
import io
import sys
import urllib.request
import wave
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dest: Path, expected_sha256: str | None = None) -> None:
    """Download url to dest via a temporary .part file, check its SHA-256 if known, then move into place.
    Progress goes to stderr: stdout is the MCP protocol channel."""
    dest.parent.mkdir(parents=True, exist_ok=True)
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
    if expected_sha256:
        actual = sha256(tmp)
        if actual != expected_sha256:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"Checksum mismatch for {dest.name}: expected {expected_sha256}, got {actual}")
    tmp.replace(dest)


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
