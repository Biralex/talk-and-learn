# LangHelper

An app for learning English together with Claude

## Installation

```bash
python -m venv .venv
source .venv/bin/activate    
pip install -r requirements.txt
python -m spacy download en_core_web_md
```

## Database initialization

```bash
python -m src.db.db init [lang]
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
python -m src.adhoc.browse
python -m src.adhoc.review
```

## TTS

Words are automatically voiced when added. Uses the [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model, deployed on a separate GPU server, but can also be run locally without a GPU.

### Starting TTS server

```bash
cd src/pronunciation_of_words
docker compose up --build
```

The server listens on the port defined in `src/pronunciation_of_words/.env` (`TTS_PORT`). Model weights are mounted from `weights/`. You also need to update `TTS_URL` variable in `src/settings.py`.
