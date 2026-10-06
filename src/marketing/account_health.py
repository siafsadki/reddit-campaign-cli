"""account health management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from ..state import StateDB


class RiskLevel(Enum):
    GREEN = "green"     # normal
    YELLOW = "yellow"   # caution
    RED = "red"         # danger — activity interruption


@dataclass
class HealthReport:
    risk_level: RiskLevel
    karma: int | None
    posts_today: int
    posts_this_week: int
    comments_today: int
    comments_this_week: int
    last_post_time: datetime | None
    cooldown_remaining_sec: int
    warnings: list[str]
    can_proceed: bool


# danger standard
RED_THRESHOLDS = {
    "posts_per_day": 3,
    "comments_per_day": 12,
    "posts_per_week": 10,
}

YELLOW_THRESHOLDS = {
    "posts_per_day": 2,
    "comments_per_day": 8,
    "posts_per_week": 7,
    "comments_per_sub_per_day": 3,
}

POST_COOLDOWN_HOURS = 4


def check_health(db: StateDB) -> HealthReport:
    """account health situation synthesis check."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    week_ago = (now - timedelta(days=7)).isoformat()

    warnings = []

    # today activity
    today_posts = _count_actions(db, "post", today_only=True)
    today_comments = _count_actions(db, "comment", today_only=True) + _count_actions(db, "seeding", today_only=True)

    # this time main activity
    week_posts = _count_actions_since(db, "post", week_ago)
    week_comments = _count_actions_since(db, "comment", week_ago) + _count_actions_since(db, "seeding", week_ago)

    # last post hour
    last_post = _last_action_time(db, "post")
    cooldown_sec = 0
    if last_post:
        elapsed = (now - last_post).total_seconds()
        remaining = POST_COOLDOWN_HOURS * 3600 - elapsed
        if remaining > 0:
            cooldown_sec = int(remaining)
            warnings.append(f"post cooldown: {int(remaining/60)}minute Remaining")

    # risk judgment
    risk = RiskLevel.GREEN

    # RED check
    if today_posts >= RED_THRESHOLDS["posts_per_day"]:
        risk = RiskLevel.RED
        warnings.append(f"daily post {today_posts}dog — limit over!")
    if today_comments >= RED_THRESHOLDS["comments_per_day"]:
        risk = RiskLevel.RED
        warnings.append(f"daily comment {today_comments}dog — limit over!")
    if week_posts >= RED_THRESHOLDS["posts_per_week"]:
        risk = RiskLevel.RED
        warnings.append(f"weekly post {week_posts}dog — spam danger!")

    # YELLOW check (REDgo Not only)
    if risk == RiskLevel.GREEN:
        if today_posts >= YELLOW_THRESHOLDS["posts_per_day"]:
            risk = RiskLevel.YELLOW
            warnings.append(f"daily post {today_posts}dog — caution")
        if today_comments >= YELLOW_THRESHOLDS["comments_per_day"]:
            risk = RiskLevel.YELLOW
            warnings.append(f"daily comment {today_comments}dog — caution")
        if week_posts >= YELLOW_THRESHOLDS["posts_per_week"]:
            risk = RiskLevel.YELLOW
            warnings.append(f"weekly post {week_posts}dog — reduce it box")

    can_proceed = risk != RiskLevel.RED

    return HealthReport(
        risk_level=risk,
        karma=None,  # by browser check necessary
        posts_today=today_posts,
        posts_this_week=week_posts,
        comments_today=today_comments,
        comments_this_week=week_comments,
        last_post_time=last_post,
        cooldown_remaining_sec=cooldown_sec,
        warnings=warnings,
        can_proceed=can_proceed,
    )


def _count_actions(db: StateDB, action_type: str, today_only: bool = False) -> int:
    if today_only:
        today = datetime.now().strftime("%Y-%m-%d")
        row = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM activity_log WHERE action_type = ? AND date(created_at) = ?",
            (action_type, today),
        ).fetchone()
    else:
        row = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM activity_log WHERE action_type = ?",
            (action_type,),
        ).fetchone()
    return row["cnt"] if row else 0


def _count_actions_since(db: StateDB, action_type: str, since: str) -> int:
    row = db.conn.execute(
        "SELECT COUNT(*) as cnt FROM activity_log WHERE action_type = ? AND created_at >= ?",
        (action_type, since),
    ).fetchone()
    return row["cnt"] if row else 0


def _last_action_time(db: StateDB, action_type: str) -> datetime | None:
    row = db.conn.execute(
        "SELECT created_at FROM activity_log WHERE action_type = ? ORDER BY created_at DESC LIMIT 1",
        (action_type,),
    ).fetchone()
    if row:
        return datetime.fromisoformat(row["created_at"])
    return None
