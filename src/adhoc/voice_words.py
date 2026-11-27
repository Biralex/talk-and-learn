import argparse
from pathlib import Path

from src import settings
from src.db import db
from src.pronunciation_of_words import client as tts


def needs_audio(row) -> bool:
    return not row["audio_path"] or not Path(row["audio_path"]).exists()


def run(lang: str, redo_all: bool) -> None:
    conn = db.connect(lang)
    try:
        rows = conn.execute("SELECT id, lemma, audio_path FROM words ORDER BY id").fetchall()
        todo = rows if redo_all else [row for row in rows if needs_audio(row)]
        if not todo:
            print("All words already have audio")
            return

        print(f"Words to voice: {len(todo)}")
        done = failed = 0
        for i, row in enumerate(todo, 1):
            try:
                path = tts.save(row["lemma"], lang=lang)
                db.set_audio_path(conn, row["id"], str(path))
                done += 1
                print(f"  [{i}/{len(todo)}] {row['lemma']}")
            except Exception as e:
                failed += 1
                print(f"  [{i}/{len(todo)}] {row['lemma']}: FAILED ({e})")
    finally:
        conn.close()

    print(f"Done: {done}, failed: {failed}")


if __name__ == "__main__":
    # python -m src.adhoc.voice_words [--all]
    parser = argparse.ArgumentParser(description="Generate pronunciation audio for words that have none")
    parser.add_argument("--all", action="store_true", help="re-voice every word, e.g. after changing the voice in settings")
    parser.add_argument("--lang", default=settings.DEFAULT_LANG, choices=list(settings.LANGUAGES))
    args = parser.parse_args()
    run(args.lang, args.all)
