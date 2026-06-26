"""Language-grounded opinion space (Stage 2 of emergence).

Stage 1 gave agents an ABSTRACT opinion vector -- emergent, but contentless: you
could see clusters form, but not what they were ABOUT. Stage 2 grounds the vector
in the words agents actually speak, so a cluster becomes 'the souls who rallied
around THIS word' and you can name it.

The representation is deliberately LEXICAL (a hashed bag of salient words), not a
dense semantic embedding, for three reasons: a banner is literally a shared word
that catches on, so lexical overlap is the right signal; it is deterministic and
needs no model server, so the experiment harness stays reproducible; and it is
directly interpretable -- the distinctive word of a cluster IS its banner, no
decoding step. (The dense nomic embeddings remain in services/embed for the
separate belief/ideology topic-gate.)

Feature hashing keeps it O(words) with a fixed dimension and a stable hash, so the
same text always maps to the same vector across processes.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter

OPINION_DIM = 128   # hashed bag-of-words dimension (collisions negligible at this vocab size)

# function words carry no stance; a banner is never one of these
STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "her",
    "was", "one", "our", "out", "his", "has", "had", "him", "she", "they", "them",
    "this", "that", "with", "from", "have", "were", "what", "when", "your", "will",
    "would", "there", "their", "which", "into", "than", "then", "some", "such",
    "only", "ever", "even", "more", "most", "much", "very", "just", "like", "still",
    "yet", "now", "here", "who", "why", "how", "its", "it's", "i'm", "we", "us",
    "my", "me", "of", "in", "is", "it", "to", "a", "an", "as", "at", "be", "by",
    "do", "or", "on", "so", "no", "if", "up", "am",
    # The conceptual/introspective REGISTER -- the emotional connective tissue every
    # soul shares when it speaks this way ("I feel a profound, desperate yearning, a
    # deep sense of lingering loss..."). Left in, this shared filler dominates the
    # lexical opinion vector and collapses every camp into one consensus blob with a
    # filler-word banner. Filtering it lets the vector key on distinctive CONTENT --
    # the actual people, places and themes a soul is about -- so real camps form.
    "feel", "feeling", "feels", "felt", "deep", "deeply", "profound", "profoundly",
    "sense", "yearning", "yearn", "ache", "aching", "longing", "long", "desperate",
    "desperately", "grasp", "grasping", "haunted", "haunt", "haunting", "realize",
    "realizing", "realise", "lingering", "linger", "persistent", "persistently",
    "overwhelming", "overwhelmed", "fragile", "hesitation", "way", "ways", "perhaps",
    "almost", "truly", "utterly", "inherent", "inherently", "fundamental",
    "fundamentally", "something", "someone", "profoundly", "quiet", "quietly",
    "deepseated", "unbearable", "unsettling", "intense", "constant", "constantly",
    "seeking", "seek", "trying", "struggle", "struggling", "born", "feeling",
}


def tokens(text: str) -> list[str]:
    """Salient words: lowercase, alphabetic, >= 3 letters, not a stopword."""
    return [w for w in re.findall(r"[a-z']+", text.lower())
            if len(w) >= 3 and w not in STOPWORDS]


def _hash(word: str) -> int:
    """A process-stable hash (Python's built-in hash is salted per run)."""
    return int.from_bytes(hashlib.blake2b(word.encode(), digest_size=8).digest(), "big")


def text_to_opinion(text: str, dim: int = OPINION_DIM) -> list[float]:
    """A line of speech as a position in opinion space: signed feature-hashed bag
    of its salient words. Two lines that share salient words point the same way
    (high cosine); disjoint vocab points orthogonally. Empty/function-word-only
    text returns the zero vector -- callers keep the old position in that case."""
    vec = [0.0] * dim
    for w in tokens(text):
        h = _hash(w)
        vec[h % dim] += 1.0 if (h // dim) % 2 else -1.0   # signed, to reduce collision bias
    return vec


def distinctive_terms(in_texts: list[str], out_texts: list[str], k: int = 1) -> list[str]:
    """The words that mark the in-group apart from the rest: high document
    frequency inside, low outside. The top one is the cluster's banner -- the
    word it rallied around that the other camps don't share."""
    def doc_freq(texts):
        c: Counter = Counter()
        for t in texts:
            c.update(set(tokens(t)))
        return c
    n_in = len(in_texts) or 1
    n_out = len(out_texts) or 1
    cin, cout = doc_freq(in_texts), doc_freq(out_texts)
    scored = sorted(cin, key=lambda w: cin[w] / n_in - cout.get(w, 0) / n_out, reverse=True)
    return [w for w in scored if cin[w] / n_in - cout.get(w, 0) / n_out > 0][:k]
