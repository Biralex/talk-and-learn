from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIO_DIR = DATA_DIR / "audio"
# Languages that can be learned. Each has its own database (data/<lang>.db) and topics.
#   spacy        - spaCy model used to find the base form of words (lemmas)
#   wordfreq     - language code for word frequencies (wordfreq package)
#   zipf_min/max - only words with a frequency in this range become vocabulary candidates
#                  (Zipf scale: ~7 = "and", ~5 = "house", ~3 = rare words)
#   topics       - conversation topics and grammar units loaded by `python -m src.db.db init <lang>`
#   tts          - how words are voiced with TTS_BACKEND = "local":
#                  {"engine": "kokoro", "voice": ..., "espeak": ...} - Kokoro-82M; "espeak" is the
#                      pronunciation language. Kokoro has no Serbian voice, but it can read Serbian
#                      pronunciation with e.g. the Italian voice "im_nicola"
#                  {"engine": "piper", "voice": ..., "speaker": ...} - a Piper voice (rhasspy/piper-voices)
LANGUAGES = {
    "en": {
        "name": "English",
        "spacy": "en_core_web_md",
        "wordfreq": "en",
        "zipf_min": 2.0,
        "zipf_max": 5.0,
        "topics": DATA_DIR / "topics_names.md",
        "grammar_topics": DATA_DIR / "grammar_topics_names.md",
        "tts": {"engine": "kokoro", "voice": "af_sky", "espeak": "en-us"},
    },
    "sr": {
        "name": "Serbian",
        # Croatian model: there is no Serbian one, and Serbian in Latin script is lemmatized well
        "spacy": "hr_core_news_md",
        "wordfreq": "sh",  # Serbo-Croatian
        # for a beginner: keep everyday words like "biti", "dan", drop only "i", "u", "je", "da", "se"
        "zipf_min": 3.0,
        "zipf_max": 7.0,
        "min_word_len": 2,  # ja, ti, on, mi, vi are worth learning
        "topics": DATA_DIR / "sr" / "topics_names.md",
        "grammar_topics": DATA_DIR / "sr" / "grammar_topics_names.md",
        "tts": {"engine": "piper", "voice": "sr_RS-serbski_institut-medium", "speaker": 0},
        # alternative: "tts": {"engine": "kokoro", "voice": "im_nicola", "espeak": "sr"},
    },
}

# How Serbian words are shown: "both" (kuća / кућа), "latin" or "cyrillic".
# Stored always in Latin; answers are accepted in either alphabet.
SERBIAN_SCRIPT = "both"

# Word pronunciation:
#   "local"  - voiced on the CPU inside the app, as set in LANGUAGES[...]["tts"]
#              (download the model with: python -m src.pronunciation_of_words.local_tts --lang <lang>)
#   "server" - the Docker/GPU Kokoro server at TTS_URL, English only
#              (see src/pronunciation_of_words/docker-compose.yml)
#   "off"    - no audio
TTS_BACKEND = "local"
TTS_URL = "http://127.0.0.1:9091"

MODELS_DIR = ROOT / "models"

KOKORO_DIR = MODELS_DIR / "kokoro"
_KOKORO_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_MODEL_FILE = "kokoro-v1.0.int8.onnx"
KOKORO_MODEL_URL = f"{_KOKORO_RELEASE}/{KOKORO_MODEL_FILE}"
KOKORO_MODEL_SHA256 = "6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb"
KOKORO_VOICES_FILE = "voices-v1.0.bin"
KOKORO_VOICES_URL = f"{_KOKORO_RELEASE}/{KOKORO_VOICES_FILE}"
KOKORO_VOICES_SHA256 = "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"

PIPER_DIR = MODELS_DIR / "piper"
PIPER_VOICES_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
# SHA-256 of the voice files that were tested; other voices are downloaded without a check
PIPER_SHA256 = {
    "sr_RS-serbski_institut-medium.onnx": "d7003890cf596e653f660a4fd97fd17f57f1eceb6d9727abad9cd76d2fda0d80",
    "sr_RS-serbski_institut-medium.onnx.json": "39ad6531b46ac629c0bed10aa9205dd2431e2dab3808b8535808711db87c2bc0",
}

DEFAULT_LANG = "en"
LOG_LEVEL = "INFO"
LOG_FILE = DATA_DIR / "app.log"
SEPARATOR = "─" * 40

WINDOW = 10

PRACTICE_WORDS_N = 20
REV_UNLOCK_DELAY_HOURS = 24
DESIRED_RETENTION = 0.9

FUZZY_RATIO = 0.85
FUZZY_MIN_LEN = 5
TYPING_MS_PER_CHAR = 400
BASELINE_N = 50
BASELINE_MIN = 20
FIXED_FAST_S = 4
FIXED_OK_S = 10
REL_FAST = 0.7
REL_OK = 1.5