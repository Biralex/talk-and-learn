import re
from pathlib import Path
import sys
import spacy
from wordfreq import zipf_frequency

from src import settings
from src.db import db

spacy_model = None


def load_model(lang: str) -> spacy.Language:
    """It converts each word to its base form: running → run, cities → city.
    We need to make sure that a single word isn't counted multiple times"""
    global spacy_model
    if spacy_model is None:
        model = settings.SPACY_MODELS[lang]
        spacy_model = spacy.load(model, disable=["ner", "senter"])
    return spacy_model


def read_transcript(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def clean_transcript(text: str) -> str:
    text = re.sub(r"\[.*?\]", "", text)       # [Music] and so on
    text = re.sub(r">>", "", text)             # markers >>
    text = re.sub(r"https?://\S+", "", text)   # links
    text = re.sub(r"\s+", " ", text)           # spaces
    return text.strip()


def find_candidates(
    text: str, lang: str, known: set[str]
) -> tuple[list[tuple[str, str]], int]:
    """Return (candidates, skipped_count) where candidates are unique lemmas
    within Zipf frequency range that are not in known,
    each paired with surrounding context window
    """
    spacy_model = load_model(lang)
    tokens = list(spacy_model(text))

    seen_freq: set[str] = set()   # unique lemmas that have passed through a frequency filter
    seen_new: set[str] = set()    # of which some have not yet been encountered and are not in known
    result: list[tuple[str, str]] = []

    for i, token in enumerate(tokens):
        if not token.is_alpha or len(token.text) < 3:
            continue

        lemma = token.lemma_.lower()

        freq = zipf_frequency(lemma, lang)
        if freq == 0 or freq < settings.ZIPF_MIN or freq > settings.ZIPF_MAX:
            continue

        if lemma in seen_freq:
            continue
        seen_freq.add(lemma)

        if lemma in known:
            continue

        seen_new.add(lemma)

        start = max(0, i - settings.WINDOW)
        end = min(len(tokens), i + settings.WINDOW + 1)
        window_text = "".join(t.text_with_ws for t in tokens[start:end]).strip()

        result.append((lemma, window_text))

    skipped = len(seen_freq) - len(seen_new)
    return result, skipped


def prepare_text(text: str, lang: str = settings.DEFAULT_LANG) -> str:
    text = clean_transcript(text)
    known = db.known_lemmas(lang)
    candidates, skipped = find_candidates(text, lang, known)
    lines = [f"Candidates: {len(candidates)} (words are already in db: {skipped})", "---"]
    for lemma, window in candidates:
        lines.append(f"{lemma} | {window}")
    return "\n".join(lines)


if __name__ == "__main__":
    # python -m src.adhoc.vocab_candidate_finder <file_to_path> [lang]
    path = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else settings.DEFAULT_LANG
    print(prepare_text(read_transcript(path), lang))
