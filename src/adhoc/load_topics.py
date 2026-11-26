import argparse
from pathlib import Path
from src import settings
from src.db import db


def main() -> None:
    # run as python -m src.adhoc.load_topics
    parser = argparse.ArgumentParser(description="Imports topics from Markdown file into db")
    parser.add_argument("path", help="Path to the theme file (lines in the format '- Name')")
    parser.add_argument("--lang", default=settings.DEFAULT_LANG)
    parser.add_argument("--table", default="topics", choices=["topics", "grammar_topics"])
    args = parser.parse_args()

    lines = Path(args.path).read_text(encoding="utf-8").splitlines()
    titles = [line[2:].strip() for line in lines if line.startswith("- ")]

    db.init(args.lang)
    conn = db.connect(args.lang)
    added, skipped = db.add_topics(conn, titles, args.table)
    conn.close()
    print(f"Added: {added}, omitted as duplicates: {skipped}")


if __name__ == "__main__":
    main()