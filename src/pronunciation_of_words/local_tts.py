"""
Local text-to-speech on the CPU: picks the engine and voice configured for each
language in settings.LANGUAGES[lang]["tts"]. Download the model once:

    python -m src.pronunciation_of_words.local_tts                     # English (Kokoro)
    python -m src.pronunciation_of_words.local_tts --lang sr           # Serbian
    python -m src.pronunciation_of_words.local_tts --lang sr "kuća"    # also voice a test word
"""
import argparse

from src import settings
from src.lang import config
from src.pronunciation_of_words import kokoro_tts, piper_tts


def tts_config(lang: str) -> dict:
    return config(lang)["tts"]


def models_present(lang: str) -> bool:
    tts = tts_config(lang)
    if tts["engine"] == "kokoro":
        return kokoro_tts.models_present()
    return piper_tts.models_present(tts["voice"])


def download_models(lang: str) -> None:
    tts = tts_config(lang)
    if tts["engine"] == "kokoro":
        kokoro_tts.download_models()
    elif tts["engine"] == "piper":
        piper_tts.download_models(tts["voice"])
    else:
        raise ValueError(f"Unknown TTS engine {tts['engine']!r} for {lang!r}: use 'kokoro' or 'piper'")


def voice_tag(lang: str) -> str:
    """Short name of the configured voice, used in audio file names"""
    tts = tts_config(lang)
    return tts["voice"] if tts.get("speaker") is None else f"{tts['voice']}-{tts['speaker']}"


def generate(text: str, lang: str, speed: float = 1.0) -> bytes:
    """Voice text in the given language and return WAV bytes"""
    tts = tts_config(lang)
    if not models_present(lang):
        raise FileNotFoundError(
            f"TTS model for {lang!r} is not downloaded. "
            f"Download it with: python -m src.pronunciation_of_words.local_tts --lang {lang}"
        )
    if tts["engine"] == "kokoro":
        return kokoro_tts.generate(text, voice=tts["voice"], espeak=tts.get("espeak", "en-us"), speed=speed)
    if tts["engine"] == "piper":
        return piper_tts.generate(text, voice=tts["voice"], speaker=tts.get("speaker"), speed=speed)
    raise ValueError(f"Unknown TTS engine {tts['engine']!r} for {lang!r}: use 'kokoro' or 'piper'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download the TTS model for a language and optionally voice a test text")
    parser.add_argument("text", nargs="*", help="text to voice into data/audio/<lang>/")
    parser.add_argument("--lang", default=settings.DEFAULT_LANG, choices=list(settings.LANGUAGES))
    args = parser.parse_args()

    download_models(args.lang)
    if args.text:
        from src.pronunciation_of_words import client

        path = client.save(" ".join(args.text), lang=args.lang)
        print(f"Saved {path}")
