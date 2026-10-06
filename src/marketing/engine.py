"""marketing engine — every of judgment center.

Claude the code this the engine through every Reddit action control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..state import StateDB
from .account_health import HealthReport, RiskLevel, check_health
from .anti_spam import (
    DailyBudget, SpamCheckResult,
    check_spam, get_daily_budget, get_human_delay, log_activity,
)
from .content_variation import generate_variants, is_too_similar, get_recent_comment_bodies, vary
from .negative_response import NegativeAnalysis, analyze_negative, should_respond
from .subreddit_rules import RuleCheckResult, check_rules, get_profile
from .target_selection import TargetScore, score_target, rank_targets
from .timing import TimingAdvice, TimingGrade, check_timing


class ActionType(Enum):
    POST = "post"
    COMMENT = "comment"
    SEEDING = "seeding"
    REPLY = "reply"
    KARMA_BUILD = "karma_build"  # karma building (app mention without)


@dataclass
class Action:
    action_type: ActionType
    subreddit: str
    title: str = ""
    body: str = ""
    target_url: str = ""
    day_id: str = ""
    is_self_promo: bool = False


@dataclass
class PreFlightResult:
    allowed: bool
    action: Action
    timing: TimingAdvice | None = None
    health: HealthReport | None = None
    spam_check: SpamCheckResult | None = None
    rule_check: RuleCheckResult | None = None
    warnings: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    suggested_delay: float = 0
    varied_body: str = ""  # transformed text


# karma in the building good subreddit (app related + common)
KARMA_SUBS = [
    "commandline", "programming", "rust", "webdev",
    "vim", "neovim", "linux", "opensource",
    "python", "golang", "devops",
]

# karma building search keyword
KARMA_TOPICS = {
    "commandline": ["terminal workflow", "cli tools", "shell setup"],
    "programming": ["developer tools", "IDE setup", "productivity"],
    "rust": ["tauri", "portable-pty", "wasm"],
    "webdev": ["developer productivity", "web tooling"],
    "vim": ["terminal multiplexer", "neovim config"],
    "neovim": ["terminal setup", "plugin"],
    "linux": ["terminal emulator", "desktop linux"],
    "devops": ["monitoring tools", "deployment"],
}


class MarketingEngine:
    """marketing judgment engine."""

    def __init__(self, db: StateDB):
        self.db = db

    def pre_flight_check(self, action: Action) -> PreFlightResult:
        """action execution jeon entire check. Claude the code this the result report judgment."""
        warnings = []
        blocks = []

        # 1. account health
        health = check_health(self.db)
        if not health.can_proceed:
            blocks.append(f"account danger: {', '.join(health.warnings)}")
        elif health.warnings:
            warnings.extend(health.warnings)

        # 2. timing
        timing = check_timing(action.subreddit)
        if timing.grade == TimingGrade.AVOID:
            blocks.append(f"timing: {timing.reason}")
        elif timing.grade == TimingGrade.POOR:
            warnings.append(f"timing: {timing.reason}")

        # 3. spam check
        spam = check_spam(self.db, action.action_type.value, action.subreddit, action.body)
        if not spam.allowed:
            blocks.append(f"spam prevention: {spam.reason}")

        # 4. subreddit rule
        rules = check_rules(action.subreddit, action.action_type.value, action.is_self_promo)
        if not rules.allowed:
            blocks.extend(rules.blocks)
        warnings.extend(rules.warnings)

        # 5. content strain + duplication check
        varied_body = action.body
        if action.body and action.action_type in (ActionType.SEEDING, ActionType.COMMENT, ActionType.KARMA_BUILD):
            # existing comments and Similarity check
            recent = get_recent_comment_bodies(self.db)
            if is_too_similar(action.body, recent):
                warnings.append("existing comments and analogy — strain apply")
                varied_body = vary(action.body, level=0.4)

        # 6. delay calculate
        suggested_delay = 0
        if spam.suggested_delay > 0:
            suggested_delay = spam.suggested_delay
        elif action.action_type != ActionType.POST:
            suggested_delay = get_human_delay()

        allowed = len(blocks) == 0
        return PreFlightResult(
            allowed=allowed,
            action=action,
            timing=timing,
            health=health,
            spam_check=spam,
            rule_check=rules,
            warnings=warnings,
            blocks=blocks,
            suggested_delay=suggested_delay,
            varied_body=varied_body,
        )

    def log_executed(self, action: Action):
        """execution complete record."""
        log_activity(self.db, action.action_type.value, action.subreddit, action.body)

    def get_budget(self) -> DailyBudget:
        """today remainder activity budget."""
        return get_daily_budget(self.db)

    def get_health(self) -> HealthReport:
        """account health."""
        return check_health(self.db)

    def analyze_comment(self, body: str, score: int = 0, upvotes: int = 0) -> NegativeAnalysis:
        """comment emotion analyze."""
        return analyze_negative(body, score, upvotes)

    def get_karma_building_plan(self, count: int = 3) -> list[Action]:
        """karma building action generation.

        app mention without On the subreddit helpful felled Leave a comment moon plan.
        """
        budget = self.get_budget()
        available = budget.comments_limit - budget.comments_used
        count = min(count, available)

        if count <= 0:
            return []

        actions = []
        import random
        subs = random.sample(KARMA_SUBS, min(count, len(KARMA_SUBS)))

        for sub in subs[:count]:
            topics = KARMA_TOPICS.get(sub, ["developer tools"])
            topic = random.choice(topics)
            actions.append(Action(
                action_type=ActionType.KARMA_BUILD,
                subreddit=sub,
                body="",  # in your browser post read directly write
                target_url="",
                is_self_promo=False,
            ))

        return actions

    def score_seeding_targets(
        self,
        posts: list[dict],
        topic_keywords: list[str],
    ) -> list[TargetScore]:
        """sow seeds target score Ranking."""
        targets = []
        for p in posts:
            t = score_target(
                title=p.get("title", ""),
                score=p.get("score", 0),
                num_comments=p.get("num_comments", 0),
                created_utc=p.get("created_utc", 0),
                author=p.get("author", ""),
                topic_keywords=topic_keywords,
            )
            t.url = p.get("url", "")
            targets.append(t)
        return rank_targets(targets)

    def get_content_variants(self, body: str, count: int = 3) -> list[str]:
        """content strain candidate generation."""
        return generate_variants(body, count)

    def format_status(self) -> str:
        """today situation summation (Claude the code read number present text)."""
        health = self.get_health()
        budget = self.get_budget()

        lines = [
            "=== Marketing Engine Status ===",
            f"Risk Level: {health.risk_level.value.upper()}",
            f"Posts Today: {budget.posts_used}/{budget.posts_limit}",
            f"Comments Today: {budget.comments_used}/{budget.comments_limit}",
            f"Can Post: {'Yes' if budget.can_post else 'No'}",
            f"Can Comment: {'Yes' if budget.can_comment else 'No'}",
        ]

        if health.cooldown_remaining_sec > 0:
            lines.append(f"Post Cooldown: {health.cooldown_remaining_sec // 60}minute Remaining")

        if health.warnings:
            lines.append("Warnings:")
            for w in health.warnings:
                lines.append(f"  - {w}")

        return "\n".join(lines)
