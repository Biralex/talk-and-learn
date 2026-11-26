import argparse
import re
import subprocess
import sys
import termios
import tty
from src import settings
from src.db import db

SEPARATOR = settings.SEPARATOR


def extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def get_character() -> str:
    """
    Read a single keypress without waiting for Enter
    Arrow keys are returned as 3-byte escape sequences (e.g. '\\x1b[C' for →)
    """
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def render_word(word: dict, idx: int, total: int) -> None:
    """
    Clear the screen and display a word card with translation, examples, and navigation hint
    """
    print("\033[2J\033[H", end="") # сlear the screen
    print(SEPARATOR)
    translations = " / ".join(v.strip() for v in word["translation"].split(";"))
    print(f"  {word['lemma']}  —  {translations}")
    print(SEPARATOR)
    for i, ex in enumerate(word["examples"], 1):
        print(f"  {i}. {ex['sentence']}")
        print(f"     {ex['translation']}")
    print()
    audio_hint = "  [Space] play audio" if word["audio_path"] else ""
    print(f"  [{idx + 1}/{total}]{audio_hint}    [← →] navigation    [q] quit")


def browse(words: list) -> None:
    if not words:
        print("No words were found in the database")
        return

    idx = 0
    audio_proc = None

    render_word(words[idx], idx, len(words))

    while True:
        ch = get_character()
        if ch in ('q', 'Q', '\x03'):
            print("\033[2J\033[H", end="")
            break
        elif ch == '\x1b[C':  # →
            idx = (idx + 1) % len(words)
            render_word(words[idx], idx, len(words))
        elif ch == '\x1b[D':  # ←
            idx = (idx - 1) % len(words)
            render_word(words[idx], idx, len(words))
        elif ch == ' ' and words[idx]["audio_path"]:
            if audio_proc and audio_proc.poll() is None:
                audio_proc.terminate()
            audio_proc = subprocess.Popen(["afplay", words[idx]["audio_path"]])


def run(lang: str, source: str, last: int | None, part_of_word: str) -> None:
    conn = db.connect(lang)

    if source:
        video_id = extract_video_id(source)
        if not video_id:
            print(f"Unable to extract video_id from URL: {source}")
            conn.close()
            return
        rows = db.words_by_source(conn, video_id)
    elif last is not None:
        rows = db.last_words(conn, last)
    else:
        rows = db.words_by_part(conn, part_of_word)

    words = [
        {**dict(row), "examples": db.get_examples(conn, row["id"])}
        for row in rows
    ]
    conn.close()

    browse(words)


if __name__ == "__main__":
    # python -m src.adhoc.browse --source "youtube_url"
    parser = argparse.ArgumentParser(description="View words and examples with audio")
    group = parser.add_mutually_exclusive_group(required=True) # you can pass one of the arguments below
    group.add_argument("--source", default="", help="YouTube video URL")
    group.add_argument("--last", type=int, metavar="N", help="last N words added")
    group.add_argument("--part-of-word", metavar="TEXT", help="A substring in lemma")
    args = parser.parse_args()

    run(settings.DEFAULT_LANG, args.source, args.last, args.part_of_word or "")