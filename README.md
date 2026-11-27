# LangHelper

An app for learning English together with Claude

## Installation

```bash
python -m venv .venv
source .venv/bin/activate    
pip install -r requirements.txt
python -m spacy download en_core_web_md
python -m src.pronunciation_of_words.local_tts   # word pronunciation model, ~120 MB, once
```

### Linux (Ubuntu) notes

Python 3.10+ is required (`sudo apt install python3-venv` if `python -m venv` fails). To play word audio in `browse.py` one of these players must be installed: `paplay` (`pulseaudio-utils`), `pw-play` (`pipewire-bin`), `aplay` (`alsa-utils`) or `ffplay` (`ffmpeg`). On Ubuntu desktop `paplay` is usually already there.

## Database initialization

```bash
python -m src.db.db init [lang]
```

This creates `data/<lang>.db` and loads the conversation and grammar topics from `data/topics_names.md` and `data/grammar_topics_names.md`. Running it again is safe: existing words are kept and duplicate topics are skipped. To load your own topic list:

```bash
python -m src.adhoc.load_topics path/to/topics.md                          # conversation topics
python -m src.adhoc.load_topics path/to/grammar.md --table grammar_topics  # grammar units
```

## Connecting to Claude Code

```bash
claude mcp add langhelper -- /absolute/path/to/project/.venv/bin/python /absolute/path/to/project/src/server/mcp_server.py
```

## Connecting to Claude Desktop

Add the following block to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "langhelper": {
      "command": "/absolute/path/to/project/.venv/bin/python",
      "args": ["/absolute/path/to/project/src/server/mcp_server.py"]
    }
  }
}
```

## Helper scripts

In the terminal you can browse words with audio, translations, and usage examples using browse.py, and run a spaced-repetition session using review.py:

```bash
python -m src.adhoc.browse --last 20
python -m src.adhoc.review
```

Each word has two cards: English → translation (shown right away) and translation → English (unlocked 24 hours after the first correct answer).

## TTS

Words are automatically voiced when added, with the [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model. The backend is chosen by `TTS_BACKEND` in `src/settings.py`:

- `"local"` (default) — the model runs on the CPU inside the app through [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx): no Docker, PyTorch or GPU. A word takes about half a second.
- `"server"` — a separate TTS server in Docker, e.g. on a machine with a GPU (see below).
- `"off"` — no audio.

### Local TTS (default)

Download the model once (~120 MB, saved to `models/kokoro/`), optionally voicing a test word into `data/audio/`:

```bash
python -m src.pronunciation_of_words.local_tts
python -m src.pronunciation_of_words.local_tts "look forward to"
```

If the model is missing or TTS fails, words are still saved, just without audio. To voice such words later, or to re-voice everything after changing `TTS_VOICE` (e.g. `af_heart`, `am_michael`, `bf_emma`):

```bash
python -m src.adhoc.voice_words          # only words without audio
python -m src.adhoc.voice_words --all    # every word
```

### Starting TTS server

Only needed with `TTS_BACKEND = "server"`.

```bash
cd src/pronunciation_of_words
docker compose up --build
```

The server listens on the port defined in `src/pronunciation_of_words/.env` (`TTS_PORT`). Model weights are mounted from `weights/`. If the server runs on another machine or port, update the `TTS_URL` variable in `src/settings.py` (default `http://127.0.0.1:9091`).

If the server is not running, words are still saved, just without audio.
