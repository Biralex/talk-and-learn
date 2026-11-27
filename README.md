# LangHelper

An app for learning languages together with Claude: **English** and **Serbian** (see [Serbian](#serbian)).

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

If the model is missing or TTS fails, words are still saved, just without audio. To voice such words later, or to re-voice everything after changing the voice in `LANGUAGES[...]["tts"]` in `src/settings.py` (e.g. `af_heart`, `am_michael`, `bf_emma`):

```bash
python -m src.adhoc.voice_words                # only words without audio
python -m src.adhoc.voice_words --all          # every word
python -m src.adhoc.voice_words --lang sr      # Serbian words
```

### Starting TTS server

Only needed with `TTS_BACKEND = "server"`.

```bash
cd src/pronunciation_of_words
docker compose up --build
```

The server listens on the port defined in `src/pronunciation_of_words/.env` (`TTS_PORT`). Model weights are mounted from `weights/`. If the server runs on another machine or port, update the `TTS_URL` variable in `src/settings.py` (default `http://127.0.0.1:9091`).

If the server is not running, words are still saved, just without audio.

## Serbian

Serbian is set up for a Russian-speaking beginner (A1 → B1). It has its own database (`data/sr.db`), topics and Claude skills, and lives next to English: every tool and script takes `--lang sr` (or `lang="sr"` in MCP calls).

### Setup

```bash
python -m spacy download hr_core_news_md                 # lemmatizer, see below
python -m src.pronunciation_of_words.local_tts --lang sr # Serbian voice, ~77 MB, once
python -m src.db.db init sr                              # database + 40 conversation topics + 47 grammar units
```

Then add the skills from `skill/sr/` to Claude (next to the English ones in `skill/`):

- `CONVERSATION_SKILL.md` — conversation practice: ~12 simple questions with translation and hints, corrections explained in Russian, a short role-play, new words saved to the base;
- `GRAMMAR_SKILL.md` — grammar lessons from `data/sr/grammar_topics_names.md`, explained through Russian (what is the same, what is different), ~15 exercises;
- `VOCAB_SKILL.md` — vocabulary from Serbian (Croatian, Bosnian) YouTube videos.

Start a session by telling Claude something like «хочу попрактиковать сербский» or «следующий урок сербской грамматики».

### Repeating words

```bash
python -m src.adhoc.review --lang sr
python -m src.adhoc.browse --lang sr --last 20
python -m src.adhoc.browse --lang sr --part-of-word кућ   # search works in both alphabets
```

### How Serbian is handled

- **Two alphabets.** Words are stored in Latin and shown in both: `kuća / кућа`. Text in Cyrillic is converted automatically. Set `SERBIAN_SCRIPT` in `src/settings.py` to `"latin"` or `"cyrillic"` to show only one.
- **Answers** in the cards are accepted in Cyrillic or Latin; typed without diacritics (`kuca` for `kuća`, `djak` for `đak`) they count as a typo.
- **Ekavian standard** (`mleko`, `dete`), as spoken in Serbia; the skills tell Claude to use Serbian rather than Croatian words.
- **Lemmatizer.** spaCy has no Serbian model, so the Croatian one is used. It handles Serbian in Latin well but sometimes misses Serbian-only words or gives a Croatian or wrong base form; the candidates are only hints and the skills tell Claude to write the correct dictionary form itself.
- **Word frequencies** come from wordfreq's Serbo-Croatian list. For a beginner the range is wide (`zipf_min`/`zipf_max` in `LANGUAGES["sr"]`), so everyday words like `biti`, `dan`, `hvala` are offered too.
- **Voice.** Kokoro has no Serbian, so by default Serbian is voiced by [Piper](https://github.com/OHF-Voice/piper1-gpl) with the `sr_RS-serbski_institut-medium` voice. Despite its name it was trained on Sorbian (Lusatian) speakers and reads Serbian through Serbian pronunciation rules: phrases are clear, some single words are not. The alternative is Kokoro reading Serbian pronunciation with an Italian voice, set in `src/settings.py`:

  ```python
  "tts": {"engine": "kokoro", "voice": "im_nicola", "espeak": "sr"},
  ```

  After switching, re-voice the words with `python -m src.adhoc.voice_words --lang sr --all`.
