"""strategy advisor — DB data analyze → marketing strategy automatic establish.

everyday activity data analyze and:
1. karma trend grasp
2. By subreddit ROI analyze
3. activity pattern Optimization proposal
4. next me strategy establish
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .marketing.account_health import check_health
from .marketing.anti_spam import get_daily_budget
from .marketing.performance import get_subreddit_rankings, suggest_effort_reallocation
from .state import StateDB


def generate_daily_report(db: StateDB, karma: int = 0) -> dict:
    """everyday synthesis report generation + DB save."""
    today = datetime.now().strftime("%Y-%m-%d")
    summary = db.get_activity_summary(today)

    # karma amount of change
    prev_karma = db.get_latest_karma()
    karma_change = karma - prev_karma if karma > 0 and prev_karma > 0 else 0

    # karma record
    if karma > 0:
        db.save_karma(karma)

    # Most activity subreddit
    top_sub = ""
    if summary["comments_by_sub"]:
        top_sub = summary["comments_by_sub"][0]["subreddit"]

    # health
    health = check_health(db)

    # strategy notes generation
    notes = _build_strategy_notes(db, summary, karma, karma_change, health)

    # save
    db.save_daily_report(
        report_date=today,
        karma=karma,
        karma_change=karma_change,
        comments_count=summary["comments_total"],
        posts_count=summary["posts_total"],
        upvotes_count=summary["upvotes_total"],
        browsed_count=summary["browsed_total"],
        top_subreddit=top_sub,
        risk_level=health.risk_level.value,
        strategy_notes=notes,
    )

    return {
        "date": today,
        "karma": karma,
        "karma_change": karma_change,
        "comments": summary["comments_total"],
        "posts": summary["posts_total"],
        "upvotes": summary["upvotes_total"],
        "browsed": summary["browsed_total"],
        "top_subreddit": top_sub,
        "risk_level": health.risk_level.value,
        "strategy": notes,
    }


def _build_strategy_notes(db, summary, karma, karma_change, health) -> str:
    """today activity based strategy notes."""
    lines = []

    # karma trend
    if karma_change > 0:
        lines.append(f"karma +{karma_change} rising")
    elif karma_change < 0:
        lines.append(f"karma {karma_change} degradation — comment ton inspection necessary")

    # activity level analyze
    comments = summary["comments_total"]
    if comments == 0:
        lines.append("today comment 0 — minimum 3dog karma building necessary")
    elif comments < 3:
        lines.append(f"comment {comments}dog — target 5dog")
    elif comments >= 8:
        lines.append(f"comment {comments}dog — today sufficient, tomorrow Even if you reduce it being")

    # health
    if health.risk_level.value == "red":
        lines.append("account danger! 24hour rest recommended")
    elif health.risk_level.value == "yellow":
        lines.append("account caution — activity speed letdown")

    return " | ".join(lines) if lines else "normal activity"


def suggest_next_day_strategy(db: StateDB) -> list[dict]:
    """tomorrow marketing strategy proposal (DB analyze based)."""
    strategies = []
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. karma trend analyze
    karma_history = db.get_karma_history(7)
    if len(karma_history) >= 2:
        recent = karma_history[0]["karma"]
        older = karma_history[-1]["karma"]
        trend = recent - older

        if trend < 0:
            s = {
                "type": "karma_recovery",
                "recommendation": "karma recovery mode — help comment mainly",
                "reason": f"recent 7Day karma {trend} degradation",
                "priority": 10,
                "subreddits": ["commandline", "programming", "python"],
            }
            strategies.append(s)
            db.save_strategy("karma_recovery", "", s["recommendation"], s["reason"], 10)
        elif trend > 50:
            s = {
                "type": "expand",
                "recommendation": "karma sufficient — sow seeds enlargement possible",
                "reason": f"recent 7Day karma +{trend} rising",
                "priority": 5,
                "subreddits": [],
            }
            strategies.append(s)
            db.save_strategy("expand", "", s["recommendation"], s["reason"], 5)

    # 2. By subreddit ROI analyze
    rankings = get_subreddit_rankings(db)
    realloc = suggest_effort_reallocation(rankings)

    for sub, action in realloc.items():
        if action == "increase":
            s = {
                "type": "increase_effort",
                "recommendation": f"r/{sub} activity increase — ROI height",
                "reason": f"ROI score difference",
                "priority": 7,
                "subreddits": [sub],
            }
            strategies.append(s)
            db.save_strategy("increase_effort", sub, s["recommendation"], s["reason"], 7)
        elif action == "stop":
            s = {
                "type": "stop_effort",
                "recommendation": f"r/{sub} activity interruption examine — ROI lowness",
                "reason": f"effort contrast result shortage",
                "priority": 3,
                "subreddits": [sub],
            }
            strategies.append(s)
            db.save_strategy("stop_effort", sub, s["recommendation"], s["reason"], 3)

    # 3. activity pattern analyze
    reports = db.get_daily_reports(7)
    if reports:
        avg_comments = sum(r["comments_count"] for r in reports) / len(reports)
        if avg_comments < 2:
            s = {
                "type": "increase_activity",
                "recommendation": "daily comment number increase necessary (target: 5dog/Day)",
                "reason": f"recent 7Day average {avg_comments:.1f}dog/Day",
                "priority": 8,
                "subreddits": [],
            }
            strategies.append(s)
            db.save_strategy("increase_activity", "", s["recommendation"], s["reason"], 8)

    # 4. subreddit manifold check
    summary = db.get_activity_summary()
    if summary["comments_by_sub"]:
        total = sum(r["cnt"] for r in summary["comments_by_sub"])
        top = summary["comments_by_sub"][0]
        if total > 5 and top["cnt"] / total > 0.5:
            s = {
                "type": "diversify",
                "recommendation": f"subreddit diversification necessary — r/{top['subreddit']}to focused",
                "reason": f"entire of comments {top['cnt']*100//total}%go one place",
                "priority": 6,
                "subreddits": [],
            }
            strategies.append(s)
            db.save_strategy("diversify", top["subreddit"], s["recommendation"], s["reason"], 6)

    # 5. budget check
    budget = get_daily_budget(db)
    if not budget.can_post and not budget.can_comment:
        s = {
            "type": "rest",
            "recommendation": "today rest — budget exhaustion",
            "reason": "daily post/comment limit arrival",
            "priority": 10,
            "subreddits": [],
        }
        strategies.append(s)

    strategies.sort(key=lambda x: x["priority"], reverse=True)
    return strategies


def format_strategy_report(strategies: list[dict]) -> str:
    """strategy report text Format."""
    if not strategies:
        return "strategy proposal doesn't exist — today plan maintain"

    lines = ["=== marketing strategy proposal ===", ""]
    for i, s in enumerate(strategies, 1):
        priority_icon = "!!!" if s["priority"] >= 8 else "!!" if s["priority"] >= 5 else "!"
        lines.append(f"{i}. [{priority_icon}] {s['recommendation']}")
        lines.append(f"   reason: {s['reason']}")
        if s.get("subreddits"):
            lines.append(f"   Target: {', '.join('r/' + sub for sub in s['subreddits'])}")
        lines.append("")

    return "\n".join(lines)
