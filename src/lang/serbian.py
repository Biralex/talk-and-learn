"""
Serbian has two official alphabets that map one-to-one: Cyrillic (кућа) and
Latin (kuća). The app stores Serbian text in Latin, because the lemmatizer
(spaCy's Croatian model) only understands Latin, and shows it in both.
"""
import re

_CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ђ": "đ", "е": "e", "ж": "ž",
    "з": "z", "и": "i", "ј": "j", "к": "k", "л": "l", "љ": "lj", "м": "m", "н": "n",
    "њ": "nj", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "ћ": "ć", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "č", "џ": "dž", "ш": "š",
}
# Upper case: a digraph is "Lj" at the start of a capitalised word, "LJ" inside an all-caps one
_CYR_TO_LAT.update({c.upper(): l.capitalize() for c, l in list(_CYR_TO_LAT.items())})

_LAT_DIGRAPHS = {"lj": "љ", "nj": "њ", "dž": "џ"}
_LAT_SINGLE = {l: c for c, l in _CYR_TO_LAT.items() if c.islower() and len(l) == 1}
_LAT_TOKEN = re.compile(r"(?i)dž|lj|nj|.", re.S)

# For lenient answer checking: letters with diacritics -> what people type without them
_ASCII_FOLD = str.maketrans({"č": "c", "ć": "c", "š": "s", "ž": "z", "đ": "dj"})

_CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def has_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC.search(text))


def to_latin(text: str) -> str:
    """кућа -> kuća. Characters outside the Serbian alphabet are kept as they are"""
    out = "".join(_CYR_TO_LAT.get(ch, ch) for ch in text)
    # "ЉУБАВ" -> "LjUBAV" -> "LJUBAV": fix digraph case inside all-caps words
    return re.sub(r"\b(Lj|Nj|Dž)(?=[A-ZČĆŠŽĐ])", lambda m: m.group(1).upper(), out)


def to_cyrillic(text: str) -> str:
    """kuća -> кућа. lj, nj and dž always become one letter (љ, њ, џ). That is right for
    almost every word; the rare exceptions such as nadživeti come out as над-џ-ивети."""
    out = []
    for tok in _LAT_TOKEN.findall(text):
        low = tok.lower()
        cyr = _LAT_DIGRAPHS.get(low) or _LAT_SINGLE.get(low)
        if cyr is None:
            out.append(tok)
        else:
            out.append(cyr.upper() if tok[0].isupper() else cyr)
    return "".join(out)


def ascii_fold(text: str) -> str:
    """kuća -> kuca, đak -> djak, džep -> dzep: how a word looks typed without Serbian letters"""
    return to_latin(text).lower().translate(_ASCII_FOLD)


def both_scripts(text: str) -> str:
    """kuća -> 'kuća / кућа'"""
    latin = to_latin(text)
    return f"{latin} / {to_cyrillic(latin)}"
