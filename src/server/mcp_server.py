import sys
from pathlib import Path

# Add repository root to sys.path — Claude Desktop starts the server from any folder
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer
from src import settings
from src.adhoc import vocab_candidate_finder
from src.adhoc.log_utils import get_logger
from src.db import db
from src.pronunciation_of_words import client as tts

logger = get_logger(__name__)

mcp = MCPServer("langhelper")


@mcp.tool()
def prepare_words(path: str, lang: str = "en") -> str:
    """
    Reads the transcript, lemmatizes it and filters out high-frequency and already known words.
     Returns a list of candidates in the following format: lemma | context window
    """
    try:
        return vocab_candidate_finder.prepare_text(vocab_candidate_finder.read_transcript(path), lang)
    except Exception as e:
        logger.error("prepare_words error: %s", e, exc_info=True)
        return f"Error: {e}"


@mcp.tool()
def add_words(entries: list, lang: str = "en", source_url: str = "") -> str:
    """
    Save a batch of vocabulary entries to db and generate TTS audio for each.

    Each entry in ``entries`` must contain:
      - ``lemma`` (str): the base form of the word.
      - ``translation`` (str): the target-language translation.
      - ``examples`` (list[dict], optional): example sentences, each a dict
        ``{"sentence": "<English sentence>", "translation": "<its translation>"}``.

    Entries with an empty lemma or empty translation are recorded as invalid and skipped.
    Entries whose lemma already exists in the database are recorded as duplicates and skipped.
    For every successfully inserted word, TTS audio is generated and its path is stored.
    All valid inserts are committed in a single transaction.

    Args:
        entries: list of dicts, each describing one vocabulary item.
        lang: language code used to select the target database (default ``"en"``).
        source_url: optional string identifying the source — a YouTube video URL,
            ``"conversation"`` for conversation-practice sessions, ``"grammar"``
            for grammar sessions, or empty string when the source is unknown.

    Returns:
        A human-readable summary string reporting the number of words added, duplicates
        skipped, invalid entries and whether a source URL was recorded.
    """
    added = []
    duplicates = []
    invalid = []

    logger.info("add_words: entries=%d, lang=%s, source_url=%r", len(entries), lang, source_url)

    conn = db.connect(lang)
    try:
        for entry in entries:
            lemma_raw = entry.get("lemma", "")
            lemma = " ".join(lemma_raw.strip().lower().split())
            translation = (entry.get("translation") or "").strip()

            if not lemma or not translation:
                reason = "empty lemma" if not lemma else "empty translation"
                invalid.append(f"{lemma_raw!r} — {reason}")
                logger.warning("Invalid entry skipped: %s", reason)
                continue

            examples = entry.get("examples", [])

            try:
                word_id = db.add_word(conn, lemma, translation, examples, source_url)
                if word_id:
                    added.append(lemma)
                    try:
                        audio_path = tts.save(lemma, voice=settings.TTS_VOICE)
                        db.set_audio_path(conn, word_id, str(audio_path))
                    except Exception as e:
                        logger.warning("TTS failed for '%s': %s", lemma, e)
                else:
                    duplicates.append(lemma)
            except Exception as e:
                logger.error("add_word failed for '%s': %s", lemma, e, exc_info=True)
                invalid.append(f"{lemma!r} - record error: {e}")

        conn.commit()
    finally:
        conn.close()

    parts = [f"Added: {len(added)}"]
    if duplicates:
        parts.append(f"Duplicates have been omitted ({len(duplicates)}): {', '.join(duplicates)}")
    if invalid:
        parts.append(f"Invalid ({len(invalid)}): {'; '.join(invalid)}")
    if source_url.strip():
        parts.append(f"Source saved: {source_url}")
    else:
        parts.append("Source not provided")

    result = ". ".join(parts) + "."
    logger.info(result)
    return result

@mcp.tool()
def prepare_text(text: str, lang: str = "en") -> str:
    """
    Lemmatize a session transcript and return vocabulary candidates for review.
    Each surviving lemma is paired with its surrounding context window to give
    enough context for translation.

    Args:
        text: plain English text of the session. May contain punctuation and mixed case.
        lang: language code used to select the target database (default ``"en"``).

    Returns:
        A string in the following format:
            Candidates: <n> (words are already in db: <skipped>)
            ---
            <lemma> | <context window>
            <lemma> | <context window>
            ...

        If ``text`` is empty or blank, returns ``"Error: no text was added"``.
        On unexpected error, returns a string starting with ``"Error: "``.
    """
    if not text or not text.strip():
        return "Error: no text was added"
    try:
        return vocab_candidate_finder.prepare_text(text, lang)
    except Exception as e:
        logger.error("prepare_text error: %s", e, exc_info=True)
        return f"Error: {e}"


@mcp.tool()
def start_conversation_topic(lang: str = "en") -> str:
    """
    Return the next conversation topic and a set of words due for review.

    Fetches the first topic from that has not yet been marked done,
    together with up to words selected for review

    Args:
        lang: language code used to select the target database (default ``"en"``).

    Returns:
        A newline-separated string in the following format:

            TOPIC_ID: <int>
            TOPIC: <title>
            PRACTICE_WORDS (<n>):
            - <lemma> | <translation>
            ...

        If no undone topics remain, returns the string ``"NO_TOPICS_LEFT"``.
        On unexpected error, returns a string starting with ``"Error: "``.
    """
    try:
        conn = db.connect(lang)
        try:
            topic = db.next_topic(conn, "topics")
            if topic is None:
                return "NO_TOPICS_LEFT"
            topic_id, title = topic
            words = db.practice_words(conn, settings.PRACTICE_WORDS_N)
        finally:
            conn.close()

        logger.info("start_conversation_topic: id=%d, title=%r", topic_id, title)

        lines = [f"TOPIC_ID: {topic_id}", f"TOPIC: {title}"]
        if words:
            lines.append(f"PRACTICE_WORDS ({len(words)}):")
            for lemma, translation in words:
                lines.append(f"- {lemma} | {translation}")
        else:
            lines.append("PRACTICE_WORDS (0): none")

        return "\n".join(lines)
    except Exception as e:
        logger.error("start_conversation_topic error: %s", e, exc_info=True)
        return f"Error: {e}"


@mcp.tool()
def finish_conversation_topic(topic_id: int, lang: str = "en") -> str:
    """
    Mark a conversation topic as completed.

    Sets ``done = 1`` for the given topic in the ``topics`` table.
    Should only be called after all session steps are successfully finished
    (vocabulary saved, practice complete).

    Args:
        topic_id: the integer ID returned by ``start_conversation_topic``.
        lang: language code used to select the target database (default ``"en"``).

    Returns:
        ``"OK: topic <id> marked done"`` on success,
        ``"ERROR: topic <id> not found"`` if the ID does not exist in the database.
        On unexpected error, returns a string starting with ``"Error: "``.
    """
    try:
        conn = db.connect(lang)
        try:
            found = db.mark_topic_done(conn, "topics", topic_id)
        finally:
            conn.close()
        if found:
            return f"OK: topic {topic_id} marked done"
        return f"ERROR: topic {topic_id} not found"
    except Exception as e:
        logger.error("finish_conversation_topic error: %s", e, exc_info=True)
        return f"Error: {e}"


@mcp.tool()
def start_grammar_topic(lang: str = "en") -> str:
    """
    Return the next grammar unit and a set of words due for review.

    Fetches the first topic from that has not yet been marked done,
    together with up to words selected for review

    Args:
        lang: language code used to select the target database (default ``"en"``).

    Returns:
        A newline-separated string in the following format::

            TOPIC_ID: <int>
            TOPIC: <title>
            PRACTICE_WORDS (<n>):
            - <lemma> | <translation>
            ...

        If no undone grammar units remain, returns the string ``"NO_TOPICS_LEFT"``.
        On unexpected error, returns a string starting with ``"Error: "``.
    """
    try:
        conn = db.connect(lang)
        try:
            topic = db.next_topic(conn, "grammar_topics")
            if topic is None:
                return "NO_TOPICS_LEFT"
            topic_id, title = topic
            words = db.practice_words(conn, settings.PRACTICE_WORDS_N)
        finally:
            conn.close()

        logger.info("start_grammar_topic: id=%d, title=%r", topic_id, title)

        lines = [f"TOPIC_ID: {topic_id}", f"TOPIC: {title}"]
        if words:
            lines.append(f"PRACTICE_WORDS ({len(words)}):")
            for lemma, translation in words:
                lines.append(f"- {lemma} | {translation}")
        else:
            lines.append("PRACTICE_WORDS (0): none")

        return "\n".join(lines)
    except Exception as e:
        logger.error("start_grammar_topic error: %s", e, exc_info=True)
        return f"Error: {e}"


@mcp.tool()
def finish_grammar_topic(topic_id: int, lang: str = "en") -> str:
    """
    Mark a grammar topic as completed.

    Sets ``done = 1`` for the given topic in the ``grammar_topics`` table.
    Should only be called after all session steps are successfully finished
    (vocabulary saved, practice complete).

    Args:
        topic_id: the integer ID returned by ``start_grammar_topic``.
        lang: language code used to select the target database (default ``"en"``).

    Returns:
        ``"OK: topic <id> marked done"`` on success,
        ``"ERROR: topic <id> not found"`` if the ID does not exist in the database.
        On unexpected error, returns a string starting with ``"Error: "``.
    """
    try:
        conn = db.connect(lang)
        try:
            found = db.mark_topic_done(conn, "grammar_topics", topic_id)
        finally:
            conn.close()
        if found:
            return f"OK: topic {topic_id} marked done"
        return f"ERROR: topic {topic_id} not found"
    except Exception as e:
        logger.error("finish_grammar_topic error: %s", e, exc_info=True)
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")