"""content strain engine — Comment like a template I can't see it without."""

from __future__ import annotations

import hashlib
import random


# synonym substitution map
SYNONYMS = {
    "really": ["actually", "honestly", "genuinely"],
    "cool": ["neat", "solid", "nice", "interesting"],
    "great": ["solid", "nice", "good", "decent"],
    "I think": ["imo", "from what I've seen", "in my experience"],
    "a lot": ["quite a bit", "a ton", "plenty"],
    "pretty": ["fairly", "reasonably", "quite"],
    "awesome": ["solid", "really good", "impressive"],
    "use": ["run", "try", "work with"],
    "check out": ["look into", "take a look at", "have a look at"],
    "but": ["though", "although", "but then again"],
    "honestly": ["tbh", "real talk", "genuinely"],
    "I've been": ["been", "I started", "I've started"],
}

# filler expression (random insertion)
FILLERS = [
    "tbh", "honestly", "fwiw", "imo", "ngl",
    "interestingly", "funny enough", "worth noting",
]

# sentence end strain
ENDINGS = {
    ".": [".", ".", ".", ""],  # 75% full stop, 25% omission
    "!": ["!", ".", ""],
}


def vary(body: str, level: float = 0.3) -> str:
    """in text natural strain apply.

    level: 0.0 = strain doesn't exist, 1.0 = strong strain
    """
    if level <= 0 or not body:
        return body

    result = body

    # 1. synonym substitution
    for original, replacements in SYNONYMS.items():
        if original.lower() in result.lower() and random.random() < level:
            replacement = random.choice(replacements)
            # uppercase and lowercase letters preservation
            if original[0].isupper():
                replacement = replacement.capitalize()
            result = result.replace(original, replacement, 1)

    # 2. uppercase and lowercase letters strain (first letter)
    if random.random() < level * 0.5:
        if result[0].isupper():
            result = result[0].lower() + result[1:]

    # 3. full stop strain
    if random.random() < level * 0.3:
        if result.endswith("."):
            result = result[:-1]

    return result


def generate_variants(body: str, count: int = 3) -> list[str]:
    """several strain generation."""
    variants = [body]  # text include
    for i in range(count - 1):
        level = 0.2 + (i * 0.15)
        v = vary(body, level=min(level, 0.6))
        if v != body and v not in variants:
            variants.append(v)
    return variants


def is_too_similar(body: str, recent_comments: list[str], threshold: float = 0.6) -> bool:
    """existing comments and too Is it similar? check (Jaccard Similarity)."""
    body_words = set(body.lower().split())
    if not body_words:
        return False

    for existing in recent_comments:
        existing_words = set(existing.lower().split())
        if not existing_words:
            continue

        intersection = body_words & existing_words
        union = body_words | existing_words
        similarity = len(intersection) / len(union) if union else 0

        if similarity > threshold:
            return True

    return False


def get_recent_comment_bodies(db, limit: int = 20) -> list[str]:
    """recent comment detail check."""
    rows = db.conn.execute(
        "SELECT body FROM comments ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [r["body"] for r in rows if r["body"]]
