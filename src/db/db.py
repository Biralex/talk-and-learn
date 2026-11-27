import sys
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src import settings
from src.adhoc.log_utils import get_logger

logger = get_logger(__name__)

SCHEMA = Path(__file__).resolve().parent / "schema.sql"
TOPIC_TABLES = frozenset({"topics", "grammar_topics"})


def db_path(lang: str) -> Path:
    if lang not in settings.LANGUAGES:  # also keeps a tool argument from pointing outside data/
        raise ValueError(f"Unknown language {lang!r}. Configured: {', '.join(settings.LANGUAGES)}")
    return settings.DATA_DIR / f"{lang}.db"


def connect(lang: str) -> sqlite3.Connection:
    """Open the language's database, creating the tables if they do not exist yet"""
    path = db_path(lang)
    settings.DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))  # CREATE TABLE IF NOT EXISTS: a no-op when present
    try:
        # databases created before the audio_path column existed
        conn.execute("ALTER TABLE words ADD COLUMN audio_path TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    return conn


def init(lang: str) -> None:
    conn = connect(lang)
    conn.close()
    logger.info("The %s database has been initialized", db_path(lang))


def read_topic_titles(path: Path) -> list[str]:
    """Read topic titles from a Markdown file with lines in the format '- Title'"""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line[2:].strip() for line in lines if line.startswith("- ")]


def load_default_topics(lang: str) -> None:
    """Load the language's conversation topics and grammar units from the files in
    settings.LANGUAGES (duplicates are skipped)"""
    cfg = settings.LANGUAGES[lang]
    conn = connect(lang)
    try:
        for table in ("topics", "grammar_topics"):
            path = cfg[table]
            if not path.exists():
                logger.warning("Topic file %s not found, %s left as is", path, table)
                continue
            added, skipped = add_topics(conn, read_topic_titles(path), table)
            logger.info("%s: added %d, already present %d", table, added, skipped)
    finally:
        conn.close()


def set_audio_path(conn: sqlite3.Connection, word_id: int, audio_path: str) -> None:
    conn.execute("UPDATE words SET audio_path = ? WHERE id = ?", (audio_path, word_id))
    conn.commit()


def known_lemmas(lang: str) -> set[str]:
    conn = connect(lang)
    rows = conn.execute("SELECT lemma FROM words").fetchall()
    conn.close()
    return {row["lemma"] for row in rows}


def add_word(
    conn: sqlite3.Connection,
    lemma: str,
    translation: str,
    examples: list[dict],
    source_url: str = "",
) -> int | None:
    """
    Creates a word, examples and two cards in a single transaction
    """
    existing = conn.execute(
        "SELECT id FROM words WHERE lemma = ?", (lemma,)
    ).fetchone()
    if existing:
        logger.info("DUPLICATE: '%s' already in db, skipped", lemma)
        return None

    now = datetime.now(timezone.utc).isoformat()
    conn.execute("SAVEPOINT add_entry")
    try:
        cursor = conn.execute(
            "INSERT INTO words (lemma, translation, created_at, source_url) VALUES (?, ?, ?, ?)",
            (lemma, translation, now, source_url or None),
        )
        word_id = cursor.lastrowid

        for example in examples:
            conn.execute(
                "INSERT INTO examples (word_id, sentence, translation) VALUES (?, ?, ?)",
                (word_id, example["sentence"], example["translation"]),
            )

        # fwd is opened (due = now), rev is blocked (due = NULL)
        conn.execute(
            "INSERT INTO cards (word_id, direction, due, state) VALUES (?, 'fwd', ?, 1)",
            (word_id, now),
        )
        conn.execute(
            "INSERT INTO cards (word_id, direction, due, state) VALUES (?, 'rev', NULL, 1)",
            (word_id,),
        )
    except Exception:
        conn.execute("ROLLBACK TO add_entry")
        conn.execute("RELEASE add_entry")
        raise

    conn.execute("RELEASE add_entry")
    return word_id


def add_topics(conn: sqlite3.Connection, titles: list[str], table: str) -> tuple[int, int]:
    """Insert topics into table, skipping duplicates"""
    assert table in TOPIC_TABLES
    added = 0
    skipped = 0
    for title in titles:
        title = title.strip()
        if not title:
            continue
        cur = conn.execute(f"INSERT OR IGNORE INTO {table} (title) VALUES (?)", (title,))
        if cur.rowcount:
            added += 1
        else:
            skipped += 1
    conn.commit()
    return added, skipped


def next_topic(conn: sqlite3.Connection, table: str) -> tuple[int, str] | None:
    assert table in TOPIC_TABLES
    row = conn.execute(
        f"SELECT id, title FROM {table} WHERE done = 0 ORDER BY id LIMIT 1"
    ).fetchone()
    return (row["id"], row["title"]) if row else None


def mark_topic_done(conn: sqlite3.Connection, table: str, topic_id: int) -> bool:
    assert table in TOPIC_TABLES
    cur = conn.execute(f"UPDATE {table} SET done = 1 WHERE id = ?", (topic_id,))
    conn.commit()
    found = cur.rowcount > 0
    if found:
        logger.info("%s DONE: %d", table.upper(), topic_id)
    return found


def practice_words(conn: sqlite3.Connection, n: int) -> list[tuple[str, str]]:
    """ Return up to n (lemma, translation) pairs for practice.
    First fills list with words that have at least one due card, ordered by
    oldest due date. If fewer than n are due, pads with never-reviewed words
    (newest additions first) until n is reached
    """
    now = datetime.now(timezone.utc).isoformat()

    due_rows = conn.execute(
        """
        SELECT w.id, w.lemma, w.translation, MIN(c.due) AS min_due
        FROM words w
        JOIN cards c ON c.word_id = w.id
        WHERE c.due IS NOT NULL AND c.due <= ?
        GROUP BY w.id
        ORDER BY min_due ASC
        LIMIT ?
        """,
        (now, n),
    ).fetchall()

    result = [(row["lemma"], row["translation"]) for row in due_rows]

    if len(result) < n:
        due_ids = {row["id"] for row in due_rows}
        new_rows = conn.execute(
            """
            SELECT w.id, w.lemma, w.translation
            FROM words w
            WHERE NOT EXISTS (
                SELECT 1 FROM review_log rl
                JOIN cards c ON c.id = rl.card_id
                WHERE c.word_id = w.id
            )
            ORDER BY w.created_at DESC
            """,
        ).fetchall()
        for row in new_rows:
            if row["id"] not in due_ids:
                result.append((row["lemma"], row["translation"]))
                if len(result) >= n:
                    break

    return result


def due_cards(conn: sqlite3.Connection, direction: str | None = None) -> list[sqlite3.Row]:
    """
    Return cards whose due date has passed. Includes reverse cards that were
    unlocked (due set) but never reviewed; new fwd cards come from new_fwd_cards()
    """
    now = datetime.now(timezone.utc).isoformat()
    query = (
        "SELECT * FROM cards WHERE due IS NOT NULL AND due <= ? "
        "AND (last_review IS NOT NULL OR direction = 'rev')"
    )
    params: list = [now]
    if direction:
        query += " AND direction = ?"
        params.append(direction)
    query += " ORDER BY due"
    return conn.execute(query, params).fetchall()


def new_fwd_cards(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM cards WHERE direction = 'fwd' AND last_review IS NULL ORDER BY id"
    ).fetchall()


def recent_think_ms(conn: sqlite3.Connection, direction: str, n: int) -> list[int]:
    rows = conn.execute(
        """
        SELECT rl.think_ms FROM review_log rl
        JOIN cards c ON c.id = rl.card_id
        WHERE rl.correct = 1 AND c.direction = ?
        ORDER BY rl.reviewed_at DESC
        LIMIT ?
        """,
        (direction, n),
    ).fetchall()
    return [row[0] for row in rows]


def all_cards_for_word_ids(
    conn: sqlite3.Connection, word_ids: set[int], direction: str | None = None
) -> list[sqlite3.Row]:
    """
    Return cards for the given word IDs, sorted by review priority
    """
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join("?" * len(word_ids))
    ids = list(word_ids)

    rows = conn.execute(
        f"""
        SELECT *,
            CASE
                WHEN last_review IS NOT NULL AND due <= ? THEN 0
                WHEN last_review IS NOT NULL AND due > ?  THEN 1
                WHEN last_review IS NULL AND direction = 'fwd' THEN 2
                -- unlocked reverse card that has never been reviewed yet
                WHEN last_review IS NULL AND direction = 'rev' AND due IS NOT NULL THEN 2
                ELSE 3
            END AS _priority
        FROM cards
        WHERE word_id IN ({placeholders})
          AND (due IS NOT NULL OR (direction = 'fwd' AND last_review IS NULL))
          {("AND direction = ?" if direction else "")}
        ORDER BY _priority, due ASC NULLS LAST, id ASC
        """,
        [now, now] + ids + ([direction] if direction else []),
    ).fetchall()
    return [r for r in rows if dict(r)["_priority"] < 3]


def words_by_source(conn: sqlite3.Connection, source: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM words WHERE source_url LIKE ? ORDER BY id",
        (f"%{source}%",),
    ).fetchall()


def last_words(conn: sqlite3.Connection, n: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM words ORDER BY created_at DESC LIMIT ?", (n,)
    ).fetchall()


def words_by_part(conn: sqlite3.Connection, part: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM words WHERE lemma LIKE ? ORDER BY lemma",
        (f"%{part}%",),
    ).fetchall()




def get_word(conn: sqlite3.Connection, word_id: int) -> sqlite3.Row:
    return conn.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()


def get_examples(conn: sqlite3.Connection, word_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM examples WHERE word_id = ?", (word_id,)
    ).fetchall()


if __name__ == "__main__":
    # python -m src.db.db init [lang]
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        lang = sys.argv[2] if len(sys.argv) > 2 else settings.DEFAULT_LANG
        init(lang)
        load_default_topics(lang)
    else:
        print("Usage: python -m src.db.db init [lang]")