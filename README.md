# LangHelper

An app for learning English together with Claude

## Installation

```bash
python -m venv .venv
source .venv/bin/activate    
pip install -r requirements.txt
python -m spacy download en_core_web_md
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

Words are automatically voiced when added. Uses the [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model, deployed on a separate GPU server, but can also be run locally without a GPU.

### Starting TTS server

```bash
cd src/pronunciation_of_words
docker compose up --build
```

The server listens on the port defined in `src/pronunciation_of_words/.env` (`TTS_PORT`). Model weights are mounted from `weights/`. If the server runs on another machine or port, update the `TTS_URL` variable in `src/settings.py` (default `http://127.0.0.1:9091`).

The TTS server is optional: if it is not running, words are still saved, just without audio.
