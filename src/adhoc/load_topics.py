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

    titles = db.read_topic_titles(Path(args.path))

    db.init(args.lang)
    conn = db.connect(args.lang)
    added, skipped = db.add_topics(conn, titles, args.table)
    conn.close()
    print(f"Added: {added}, omitted as duplicates: {skipped}")


if __name__ == "__main__":
    main()