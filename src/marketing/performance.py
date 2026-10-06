"""By subreddit result tracking + strategy adjustment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..state import StateDB


@dataclass
class SubredditPerformance:
    subreddit: str
    total_posts: int
    total_comments: int
    avg_score: float
    avg_comments: float
    positive_ratio: float
    effort_score: float    # we invested effort
    roi_score: float       # result/effort
    trend: str             # "improving", "stable", "declining"


def get_subreddit_rankings(db: StateDB) -> list[SubredditPerformance]:
    """By subreddit result ranking."""
    # submissionsat By subreddit statistics
    subs = db.conn.execute(
        "SELECT subreddit, COUNT(*) as cnt FROM submissions "
        "WHERE subreddit IS NOT NULL GROUP BY subreddit"
    ).fetchall()

    results = []
    for row in subs:
        sub = row["subreddit"]

        # metric average
        metrics = db.conn.execute(
            "SELECT AVG(m.upvotes) as avg_up, AVG(m.comment_count) as avg_cm "
            "FROM metrics m JOIN submissions s ON m.submission_id = s.reddit_id "
            "WHERE s.subreddit = ?",
            (sub,),
        ).fetchone()

        avg_score = metrics["avg_up"] or 0 if metrics else 0
        avg_comments = metrics["avg_cm"] or 0 if metrics else 0

        # we written comment number (effort characteristic)
        effort = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM comments WHERE subreddit = ?",
            (sub,),
        ).fetchone()["cnt"]

        # ROI (result/effort)
        roi = (avg_score + avg_comments * 2) / max(1, effort)

        results.append(SubredditPerformance(
            subreddit=sub,
            total_posts=row["cnt"],
            total_comments=effort,
            avg_score=round(avg_score, 1),
            avg_comments=round(avg_comments, 1),
            positive_ratio=0,  # TODO: emotion analyze data peristalsis
            effort_score=effort,
            roi_score=round(roi, 2),
            trend="stable",
        ))

    results.sort(key=lambda x: x.roi_score, reverse=True)
    return results


def suggest_effort_reallocation(rankings: list[SubredditPerformance]) -> dict[str, str]:
    """effort redistribution proposal."""
    suggestions = {}
    for r in rankings:
        if r.roi_score >= 5:
            suggestions[r.subreddit] = "increase"  # effort increase
        elif r.roi_score >= 2:
            suggestions[r.subreddit] = "maintain"   # maintain
        elif r.roi_score >= 0.5:
            suggestions[r.subreddit] = "reduce"     # reduction
        else:
            suggestions[r.subreddit] = "stop"       # interruption examine
    return suggestions
