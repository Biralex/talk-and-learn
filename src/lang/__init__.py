"""
Language-specific text handling. Everything that differs between the languages
being learned goes through these functions, so the rest of the code stays generic.
"""
from src import settings
from src.lang import serbian


def config(lang: str) -> dict:
    try:
        return settings.LANGUAGES[lang]
    except KeyError:
        raise ValueError(f"Unknown language {lang!r}. Configured: {', '.join(settings.LANGUAGES)}") from None


def to_storage(lang: str, text: str) -> str:
    """Text in the form it is stored in the database and fed to the lemmatizer"""
    if lang == "sr":
        return serbian.to_latin(text)
    return text


def normalize_lemma(lang: str, lemma: str) -> str:
    return " ".join(to_storage(lang, lemma).strip().lower().split())


def display(lang: str, text: str) -> str:
    """Text as it is shown to the learner: Serbian in both alphabets"""
    if lang == "sr" and settings.SERBIAN_SCRIPT == "both":
        return serbian.both_scripts(text)
    if lang == "sr" and settings.SERBIAN_SCRIPT == "cyrillic":
        return serbian.to_cyrillic(text)
    return text


def display_sentence(lang: str, sentence: str, indent: str = "     ") -> str:
    """Like display(), but a Serbian sentence in both alphabets goes on two lines"""
    if lang == "sr" and settings.SERBIAN_SCRIPT == "both":
        latin = serbian.to_latin(sentence)
        return f"{latin}\n{indent}{serbian.to_cyrillic(latin)}"
    return display(lang, sentence)


def answer_forms(lang: str, text: str) -> tuple[str, str]:
    """(exact, loose) forms of an answer typed in the language being learned.
    Exact: Serbian in Latin whatever alphabet was typed. Loose: also without diacritics
    (kuca for kuća), which counts as a typo rather than a mistake"""
    if lang == "sr":
        return serbian.to_latin(text), serbian.ascii_fold(text)
    return text, text
