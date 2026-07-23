"""Tagged lexicons + the weak-phrase replacement map.

Pure data + lookup helpers, no external deps, so this is offline/test-safe and shared
by every text-analysis module. Tags: ``filler | hedge | weasel | intensifier | weak``.

Context-sensitive words (``like, so, well, right, okay``) are NOT counted by raw
membership; callers use :func:`is_context_filler` with positional info to avoid
flagging legitimate content uses ("I feel *like* running", "*So*, the result is...").
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a runtime import cycle; only needed for type hints
    from .schema import Transcript

# --------------------------------------------------------------------------- #
# Single-token lexicons
# --------------------------------------------------------------------------- #

# Non-lexical filled pauses: almost always fillers regardless of context.
FILLED_PAUSES: set[str] = {
    "um", "umm", "uh", "uhh", "uhm", "er", "err", "erm", "ah", "ahh",
    "hmm", "hm", "mm", "mmm", "mhm", "uh-huh", "huh",
}

# Discourse-marker fillers whose "filler-ness" depends on context.
CONTEXT_FILLERS: set[str] = {
    "like", "so", "well", "right", "okay", "ok", "anyway", "anyways", "see",
}

# Always-treated discourse fillers (low severity but counted).
DISCOURSE_FILLERS: set[str] = {
    "basically", "actually", "literally", "honestly",
}

FILLERS: set[str] = FILLED_PAUSES | CONTEXT_FILLERS | DISCOURSE_FILLERS

HEDGES: set[str] = {
    "maybe", "perhaps", "possibly", "probably", "might", "could", "may",
    "seems", "seemingly", "apparently", "somewhat", "fairly", "quite",
    "rather", "arguably", "presumably", "supposedly", "allegedly",
    "essentially", "kinda", "sorta",
}

# Vague quantifiers / placeholder nouns.
WEASEL: set[str] = {
    "many", "some", "several", "various", "most", "few", "numerous",
    "stuff", "things", "thing", "something", "someone", "somewhere",
}

INTENSIFIERS: set[str] = {
    "very", "really", "extremely", "totally", "absolutely", "completely",
    "super", "definitely", "incredibly", "highly", "just", "simply",
    "truly", "surprisingly", "particularly", "utterly", "deeply",
}

# Wordy / weak single tokens (union members folded into WEAK below).
_WEAK_EXTRA: set[str] = {"utilize", "leverage", "synergy", "impactful", "nice", "good", "bad"}

WEAK: set[str] = HEDGES | WEASEL | INTENSIFIERS | _WEAK_EXTRA

# --------------------------------------------------------------------------- #
# Multi-word phrases (tagged). Matched by scanning normalized n-grams.
# --------------------------------------------------------------------------- #

PHRASE_TAGS: dict[str, set[str]] = {
    "you know": {"filler"},
    "i mean": {"filler"},
    "you see": {"filler"},
    "let me see": {"filler"},
    "let's see": {"filler"},
    "you know what i mean": {"filler"},
    "sort of": {"filler", "hedge"},
    "kind of": {"filler", "hedge"},
    "i think": {"hedge"},
    "i guess": {"hedge", "filler"},
    "i suppose": {"hedge"},
    "i believe": {"hedge"},
    "i feel like": {"hedge"},
    "a bit": {"hedge"},
    "a little": {"hedge"},
    "more or less": {"hedge"},
    "to some extent": {"hedge"},
    "a number of": {"weasel"},
    "a lot of": {"weasel"},
    "a couple of": {"weasel"},
    "in order to": {"weak"},
    "due to the fact that": {"weak"},
    "at this point in time": {"weak"},
    "for all intents and purposes": {"weak"},
}

# Longest phrase length to scan for (in tokens).
MAX_PHRASE_LEN: int = max(len(p.split()) for p in PHRASE_TAGS)

# --------------------------------------------------------------------------- #
# Replacement suggestions: weak word/phrase -> stronger or "" (cut it).
# An empty string means "delete this word; it adds nothing."
# --------------------------------------------------------------------------- #

REPLACEMENTS: dict[str, str] = {
    "utilize": "use",
    "leverage": "use",
    "in order to": "to",
    "due to the fact that": "because",
    "at this point in time": "now",
    "for all intents and purposes": "effectively",
    "a lot of": "many",
    "a number of": "several",
    "really": "",
    "very": "",
    "just": "",
    "actually": "",
    "basically": "",
    "literally": "",
    "honestly": "",
    "simply": "",
    "kind of": "",
    "sort of": "",
    "kinda": "",
    "sorta": "",
    "maybe": "",
    "perhaps": "",
    "i think": "",
    "i guess": "",
    "i mean": "",
    "you know": "",
    "things": "(name them)",
    "thing": "(be specific)",
    "stuff": "(be specific)",
    "nice": "(use a precise adjective)",
    "good": "(use a precise adjective)",
    "bad": "(use a precise adjective)",
    "impactful": "(say the actual effect)",
}


def classify_token(tok: str) -> set[str]:
    """Return the set of tags for a single normalized token (may be empty)."""
    tags: set[str] = set()
    if tok in FILLED_PAUSES or tok in DISCOURSE_FILLERS:
        tags.add("filler")
    if tok in HEDGES:
        tags.add("hedge")
    if tok in WEASEL:
        tags.add("weasel")
    if tok in INTENSIFIERS:
        tags.add("intensifier")
    if tok in WEAK:
        tags.add("weak")
    return tags


def is_context_filler(t: "Transcript", i: int) -> bool:
    """Decide whether a context-sensitive token (like/so/well/right/okay) at index
    ``i`` is being used as a filler rather than as content.

    Heuristics (offline best-effort, no POS tagger required):
      * ``so``/``well``/``okay``/``ok``/``anyway`` -> filler when sentence-initial.
      * ``right`` -> filler when sentence-final (tag-question / verbal tic).
      * ``like`` -> filler unless it follows a comparison/verb cue
        (feel/feels/look/looks/sound/sounds/seem/be/was/were/just/more/'s) or precedes
        a determiner suggesting a real comparison.
      * ``see`` -> filler only in "you see" (handled as a phrase) -> here returns False.
    """
    from .schema import is_sentence_final, is_sentence_initial  # local import avoids cycle

    words = t.words
    if i < 0 or i >= len(words):
        return False
    tok = words[i].normalized
    prev = words[i - 1].normalized if i > 0 else ""

    if tok in {"so", "well", "okay", "ok", "anyway", "anyways"}:
        return is_sentence_initial(t, i)
    if tok == "right":
        return is_sentence_final(t, i)
    if tok == "like":
        # 'like' is usually content (main verb "I like X", comparison/preposition
        # "looks like a", "cities like Paris"). Default to NOT a filler and only
        # treat it as a discourse filler with positive evidence.
        nxt = words[i + 1].normalized if i + 1 < len(words) else ""
        # Verb / comparison senses immediately before 'like'.
        content_prev = {
            "feel", "feels", "felt", "look", "looks", "looked", "sound", "sounds",
            "sounded", "seem", "seems", "seemed", "be", "is", "are", "was", "were",
            "act", "acts", "acted", "treat", "treats", "'s", "more", "just",
            "would", "want", "wants", "wanted", "love", "loves", "loved",
            "like", "likes", "liked", "enjoy", "enjoys", "dislike",
        }
        # A determiner/pronoun after 'like' marks the preposition (comparison) use.
        object_next = {
            "a", "an", "the", "this", "that", "these", "those", "my", "your",
            "his", "her", "our", "their", "him", "them", "it", "us", "you", "me",
        }
        # A determiner/pronoun right after 'like' is the preposition (comparison)
        # use ("like a dream", "like the others") -> always content.
        if nxt in object_next:
            return False
        # Strong positive evidence overrides a verb cue ("it was, like, huge").
        if is_sentence_initial(t, i):
            return True
        if prev in FILLED_PAUSES or (i > 0 and words[i - 1].is_filled_pause):
            return True
        gap = t.gap_before(i)
        if gap > t.speaker_median_gap + 0.25 or gap > 0.45:
            return True  # bracketed by a hesitation pause -> discourse filler
        # Otherwise a verb/comparison cue before 'like' marks content use.
        if prev in content_prev:
            return False
        return False
    if tok == "see":
        return False
    return False
