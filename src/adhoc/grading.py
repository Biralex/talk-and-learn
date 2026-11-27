import re
import statistics
from difflib import SequenceMatcher

from src import settings
from src.lang import answer_forms


def normalize(text: str) -> str:
    """
    Normalize text for comparison: lowercase, collapse whitespace,
    replace ё→е, strip punctuation except hyphens and apostrophes.
    """
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("ё", "е")
    # strip punctuation except hyphens and apostrophes
    text = re.sub(r"[^\w\s\-']", "", text)
    return text


def grade(expected: list[str], user_input: str, elapsed_ms: int,
          recent_think_ms: list[int], answer_lang: str | None = None) -> tuple[bool, int, bool, int]:
    """Check user answer and compute FSRS rating

    Args:
        expected: list of accepted correct answers (e.g. ["cat", "kitty"])
        user_input: raw text typed by user
        elapsed_ms: total time from card shown to Enter pressed, in milliseconds
        recent_think_ms: think times from previous correct answers, used to
                         compute a personal speed baseline for the rating
        answer_lang: set when the answer is in the language being learned (e.g. "sr"):
                     a Serbian answer is accepted in Cyrillic or Latin, and without
                     diacritics (kuca for kuća) as a typo

    Returns:
        (correct, rating, fuzzy, think_ms) where correct is whether the answer
        was accepted, rating is 1-4 for FSRS, fuzzy is True if accepted as a
        typo and think_ms is elapsed time minus estimated typing time
    """
    think_ms = max(0, elapsed_ms - len(user_input) * settings.TYPING_MS_PER_CHAR)

    if not user_input.strip():
        return False, 1, False, think_ms

    if answer_lang:
        exact_input, loose_input = (normalize(f) for f in answer_forms(answer_lang, user_input))
        exact_expected, loose_expected = [], []
        for e in expected:
            exact, loose = answer_forms(answer_lang, e)
            exact_expected.append(normalize(exact))
            loose_expected.append(normalize(loose))
    else:
        exact_input = loose_input = normalize(user_input)
        exact_expected = loose_expected = [normalize(e) for e in expected]

    # exact match
    if exact_input in exact_expected:
        rating = compute_rating(think_ms, recent_think_ms, fuzzy=False)
        return True, rating, False, think_ms

    # the same word typed without diacritics (kuca for kuća): counts as a typo
    if loose_input in loose_expected:
        rating = compute_rating(think_ms, recent_think_ms, fuzzy=True)
        return True, rating, True, think_ms

    # typo
    norm_input = loose_input
    for exp in loose_expected:
        if len(exp) >= settings.FUZZY_MIN_LEN:
            ratio = SequenceMatcher(None, norm_input, exp).ratio()
            if ratio >= settings.FUZZY_RATIO:
                rating = compute_rating(think_ms, recent_think_ms, fuzzy=True)
                return True, rating, True, think_ms

    return False, 1, False, think_ms


def compute_rating(think_ms: int, recent: list[int], fuzzy: bool) -> int:
    think_s = think_ms / 1000

    if len(recent) < settings.BASELINE_MIN:
        if think_s <= settings.FIXED_FAST_S:
            rating = 4
        elif think_s <= settings.FIXED_OK_S:
            rating = 3
        else:
            rating = 2
    else:
        median = statistics.median(recent[-settings.BASELINE_N:])
        median_s = median / 1000
        if think_s <= settings.REL_FAST * median_s:
            rating = 4
        elif think_s <= settings.REL_OK * median_s:
            rating = 3
        else:
            rating = 2

    # Typo: grade no higher than 3
    return min(rating, 3) if fuzzy else rating
