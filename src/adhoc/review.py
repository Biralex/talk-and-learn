import argparse
import time
from datetime import datetime, timezone, timedelta

from fsrs import Card, Rating, Scheduler, State

from src import settings
from src.db import db
from src.adhoc import grading
from src.adhoc.browse import extract_video_id
from src.adhoc.log_utils import get_logger

logger = get_logger(__name__)

scheduler = Scheduler(desired_retention=settings.DESIRED_RETENTION)


def row_to_card(row) -> Card:
    card = Card()
    state_val = row["state"] if row["state"] in (1, 2, 3) else 1
    card.state = State(state_val)
    card.step = row["step"] if row["step"] is not None else 0
    card.stability = row["stability"]
    card.difficulty = row["difficulty"]
    if row["due"]:
        card.due = datetime.fromisoformat(row["due"])
    if row["last_review"]:
        card.last_review = datetime.fromisoformat(row["last_review"])
    return card


def card_to_dict(card: Card) -> dict:
    return {
        "state": card.state.value,
        "step": card.step,
        "stability": card.stability,
        "difficulty": card.difficulty,
        "due": card.due.isoformat() if card.due else None,
        "last_review": card.last_review.isoformat() if card.last_review else None,
    }


def apply_rating(row, rating: int) -> dict:
    card = row_to_card(row)
    updated_card, _ = scheduler.review_card(card, Rating(rating))
    return card_to_dict(updated_card)


def get_cards_to_review(conn, direction: str, include_new: bool = True, filter_word_ids: set[int] | None = None) -> list:
    """Return a list of cards to review. If filter_word_ids is given, returns all cards
    for those words; otherwise returns due cards plus all new fwd cards.
    """
    if filter_word_ids is not None:
        dirs = ["fwd", "rev"] if direction == "both" else [direction]
        queue = []
        for d in dirs:
            queue.extend(db.all_cards_for_word_ids(conn, filter_word_ids, d))
        return queue

    dirs = ["fwd", "rev"] if direction == "both" else [direction]

    queue = []
    for d in dirs:
        queue.extend(db.due_cards(conn, d))

    if "fwd" in dirs and include_new:
        queue.extend(db.new_fwd_cards(conn))

    return queue


def unlock_reverse_card(conn, card_id: int, word_id: int) -> None:
    """Schedule the reverse card for review after the first correct fwd answer"""
    already_logged = conn.execute(
        "SELECT COUNT(*) FROM review_log WHERE card_id = ? AND correct = 1",
        (card_id,),
    ).fetchone()[0]
    if already_logged > 0:
        return
    unlock_time = (
        datetime.now(timezone.utc) + timedelta(hours=settings.REV_UNLOCK_DELAY_HOURS)
    ).isoformat()
    conn.execute(
        "UPDATE cards SET due = ? WHERE word_id = ? AND direction = 'rev' AND due IS NULL",
        (unlock_time, word_id),
    )


def show_card(word, direction: str) -> None:
    print(settings.SEPARATOR)
    if direction == "fwd":
        print(f"  {word['lemma']}")
    else:
        variants = " / ".join(v.strip() for v in word["translation"].split(";"))
        print(f"  {variants}")
    print()


def show_result(examples, correct: bool, fuzzy: bool, expected: list[str]) -> None:
    if correct:
        status = "Correct (typo)" if fuzzy else "Correct"
    else:
        status = "Incorrect"
    print(f"  {status}")
    print(f"  Answer: {' / '.join(expected)}")
    print()
    for i, ex in enumerate(examples, 1):
        print(f"  {i}. {ex['sentence']}")
        print(f"     {ex['translation']}")


def run(lang: str, direction: str, include_new: bool = True, source_url: str = "") -> None:
    conn = db.connect(lang)

    filter_word_ids = None
    if source_url:
        source = extract_video_id(source_url) or source_url
        filter_word_ids = {row["id"] for row in db.words_by_source(conn, source)}
        print(f"Filter by source '{source}': {len(filter_word_ids)} words")

    queue = get_cards_to_review(conn, direction, include_new, filter_word_ids)

    if not queue:
        print("There are no flashcards for review (:")
        conn.close()
        return

    print(f"Cards in the queue: {len(queue)}")

    total = correct_count = 0
    think_times: list[int] = []

    try:
        for card in queue:
            word = db.get_word(conn, card["word_id"])
            examples = db.get_examples(conn, card["word_id"])
            if not word:
                continue

            card_dir = card["direction"]
            expected = (
                [v.strip() for v in word["translation"].split(";")]
                if card_dir == "fwd"
                else [word["lemma"]]
            )

            show_card(word, card_dir)

            recent = db.recent_think_ms(conn, card_dir, settings.BASELINE_N)
            start = time.perf_counter()
            try:
                user_input = input("  > ")
            except EOFError:
                raise KeyboardInterrupt
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            correct, rating, fuzzy, think_ms = grading.grade(
                expected, user_input, elapsed_ms, recent
            )

            show_result(examples, correct, fuzzy, expected)

            now = datetime.now(timezone.utc).isoformat()

            if correct and card_dir == "fwd":
                unlock_reverse_card(conn, card["id"], card["word_id"])

            updated = apply_rating(card, rating)
            conn.execute(
                """
                UPDATE cards
                SET due=?, state=?, step=?, stability=?, difficulty=?, last_review=?
                WHERE id=?
                """,
                (
                    updated["due"], updated["state"], updated["step"],
                    updated["stability"], updated["difficulty"], updated["last_review"],
                    card["id"],
                ),
            )
            conn.execute(
                "INSERT INTO review_log (card_id, reviewed_at, correct, rating, think_ms) VALUES (?,?,?,?,?)",
                (card["id"], now, int(correct), rating, think_ms),
            )
            conn.commit()

            total += 1
            if correct:
                correct_count += 1
                think_times.append(think_ms)

    except KeyboardInterrupt:
        print(f"\n{settings.SEPARATOR}")
        print("  The session has been suspended")

    finally:
        conn.close()

    print(settings.SEPARATOR)
    if total:
        pct = int(correct_count / total * 100)
        avg_s = round(sum(think_times) / len(think_times) / 1000, 1) if think_times else 0
        print(f"  Summary: {total} cards · {pct}% true · average time {avg_s}s")
    else:
        print("  There were no cards")


if __name__ == "__main__":
    # python -m src.adhoc.review --source "youtube_url"
    parser = argparse.ArgumentParser(description="Повторение слов")
    parser.add_argument(
        "--direction", choices=["fwd", "rev", "both"], default="both",
        help="Card direction (default: both)")
    parser.add_argument("--no-new", action="store_true", help="Do not show new cards")
    parser.add_argument("--source", default="", help="Filter by source: conversation, grammar or YouTube URL")
    args = parser.parse_args()

    run(settings.DEFAULT_LANG, args.direction, not args.no_new, args.source)
