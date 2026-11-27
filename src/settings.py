from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIO_DIR = DATA_DIR / "audio"
# Word pronunciation:
#   "local"  - Kokoro-82M on CPU inside the app (python -m src.pronunciation_of_words.local_tts to download)
#   "server" - the Docker/GPU TTS server at TTS_URL (see src/pronunciation_of_words/docker-compose.yml)
#   "off"    - no audio
TTS_BACKEND = "local"
TTS_URL = "http://127.0.0.1:9091"
TTS_VOICE = "af_sky"
TTS_LANG = "en-us"

KOKORO_DIR = ROOT / "models" / "kokoro"
_KOKORO_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_MODEL_FILE = "kokoro-v1.0.int8.onnx"
KOKORO_MODEL_URL = f"{_KOKORO_RELEASE}/{KOKORO_MODEL_FILE}"
KOKORO_MODEL_SHA256 = "6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb"
KOKORO_VOICES_FILE = "voices-v1.0.bin"
KOKORO_VOICES_URL = f"{_KOKORO_RELEASE}/{KOKORO_VOICES_FILE}"
KOKORO_VOICES_SHA256 = "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"

DEFAULT_LANG = "en"
SPACY_MODELS = {"en": "en_core_web_md"}
LOG_LEVEL = "INFO"
LOG_FILE = DATA_DIR / "app.log"
SEPARATOR = "─" * 40

ZIPF_MIN = 2.0
ZIPF_MAX = 5.0
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