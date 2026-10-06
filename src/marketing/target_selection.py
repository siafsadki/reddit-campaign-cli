"""sow seeds target post screening."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..state import StateDB


@dataclass
class TargetScore:
    url: str
    title: str
    score: int
    num_comments: int
    age_hours: float
    relevance: float     # 0-1
    final_score: float   # synthesis score
    skip_reason: str | None = None


# target selected standard
MAX_AGE_HOURS = 48         # 48hour within Post only
MIN_SCORE = 1              # minimum Upvote
MIN_COMMENTS = 0           # minimum comment
MAX_COMMENTS = 50          # too If there are many buried
SKIP_AUTHORS = {"[deleted]", "AutoModerator"}


def score_target(
    title: str,
    score: int,
    num_comments: int,
    created_utc: float,
    author: str,
    topic_keywords: list[str],
) -> TargetScore:
    """of the post sow seeds fitness score calculate."""
    now = datetime.now(timezone.utc).timestamp()
    age_hours = (now - created_utc) / 3600

    skip_reason = None

    # filtering
    if age_hours > MAX_AGE_HOURS:
        skip_reason = f"too old ({age_hours:.0f}h)"
    elif score < MIN_SCORE:
        skip_reason = f"Upvote shortage ({score})"
    elif num_comments > MAX_COMMENTS:
        skip_reason = f"comment too plenty ({num_comments}) — to be buried possibility"
    elif author in SKIP_AUTHORS:
        skip_reason = f"Author exception ({author})"

    # relevance score (0-1)
    title_lower = title.lower()
    if topic_keywords:
        matches = sum(1 for kw in topic_keywords if kw.lower() in title_lower)
        relevance = min(1.0, matches / max(1, len(topic_keywords) * 0.3))
    else:
        relevance = 0.5

    # freshness score (The more recent it is height)
    freshness = max(0, 1.0 - age_hours / MAX_AGE_HOURS)

    # Participation score (suitable comment medical charge optimal)
    if num_comments <= 5:
        engagement = 0.8  # beginning — in the eyes well It's hot
    elif num_comments <= 20:
        engagement = 1.0  # activity — well
    elif num_comments <= MAX_COMMENTS:
        engagement = 0.5  # plenty — to be buried number Yes
    else:
        engagement = 0.2

    # Upvote score
    if score >= 50:
        upvote_score = 1.0
    elif score >= 10:
        upvote_score = 0.8
    elif score >= 3:
        upvote_score = 0.6
    else:
        upvote_score = 0.3

    # synthesis score
    final = (
        relevance * 0.35
        + freshness * 0.25
        + engagement * 0.25
        + upvote_score * 0.15
    )

    return TargetScore(
        url="",
        title=title,
        score=score,
        num_comments=num_comments,
        age_hours=age_hours,
        relevance=relevance,
        final_score=round(final, 3),
        skip_reason=skip_reason,
    )


def filter_already_commented(targets: list[TargetScore], db: StateDB) -> list[TargetScore]:
    """already comment step post exception."""
    commented_urls = set()
    rows = db.conn.execute(
        "SELECT DISTINCT subreddit || ':' || body_hash FROM activity_log "
        "WHERE action_type IN ('comment', 'seeding')"
    ).fetchall()
    for r in rows:
        commented_urls.add(r[0])

    return [t for t in targets if t.url not in commented_urls]


def rank_targets(targets: list[TargetScore], limit: int = 3) -> list[TargetScore]:
    """Not skipped not target By score array."""
    valid = [t for t in targets if t.skip_reason is None]
    valid.sort(key=lambda x: x.final_score, reverse=True)
    return valid[:limit]
