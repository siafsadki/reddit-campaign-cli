"""negative comment react strategy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    TRIVIAL = "trivial"           # "not really" — ignore
    CONSTRUCTIVE = "constructive"  # "Xgo more It's better" — admit + roadmap
    HOSTILE = "hostile"            # "trash" — 1episode fact correction
    ATTACK = "attack"             # personal attack — ignore
    VIRAL_NEGATIVE = "viral"       # goupvote criticism — discretion react


class ResponseAction(Enum):
    IGNORE = "ignore"
    RESPOND_ONCE = "respond_once"
    ACKNOWLEDGE = "acknowledge"
    ESCALATE = "escalate"         # passivity examine necessary


@dataclass
class NegativeAnalysis:
    severity: Severity
    action: ResponseAction
    reason: str
    suggested_response: str | None = None


# keyword based classification
HOSTILE_KEYWORDS = [
    "garbage", "trash", "crap", "sucks", "terrible", "awful",
    "waste", "scam", "bloat", "bloated", "useless",
]

ATTACK_KEYWORDS = [
    "idiot", "stupid", "dumb", "moron", "shill", "spam",
    "bot", "fake", "liar",
]

CONSTRUCTIVE_PATTERNS = [
    "but", "however", "instead", "rather", "prefer",
    "better", "alternative", "compared to", "why not",
    "have you considered", "what about",
]

# react template
TEMPLATES = {
    Severity.CONSTRUCTIVE: [
        "that's a fair point. {topic} is something I've been thinking about — it's on the list but haven't gotten to it yet",
        "yeah I get that. {topic} is definitely a tradeoff. the way I see it is {reasoning}",
        "totally valid feedback. I'll look into {topic} — appreciate the honest take",
    ],
    Severity.HOSTILE: [
        "fair enough, it's not for everyone. happy to hear specific feedback if you have any",
        "I hear you. {topic} is a conscious tradeoff — {reasoning}. but I get it's not ideal for everyone",
    ],
}


def analyze_negative(
    body: str,
    score: int = 0,
    upvotes: int = 0,
) -> NegativeAnalysis:
    """negative comment analyze + react strategy decision."""
    body_lower = body.lower()

    # personal attack detect
    attack_count = sum(1 for kw in ATTACK_KEYWORDS if kw in body_lower)
    if attack_count >= 1:
        return NegativeAnalysis(
            severity=Severity.ATTACK,
            action=ResponseAction.IGNORE,
            reason=f"personal attack detect ({attack_count}dog keyword)",
        )

    # viral negative (goupvote criticism)
    hostile_count = sum(1 for kw in HOSTILE_KEYWORDS if kw in body_lower)
    if hostile_count >= 1 and upvotes >= 20:
        return NegativeAnalysis(
            severity=Severity.VIRAL_NEGATIVE,
            action=ResponseAction.ESCALATE,
            reason=f"goupvote({upvotes}) criticism — discretion react necessary",
        )

    # hostile
    if hostile_count >= 2:
        return NegativeAnalysis(
            severity=Severity.HOSTILE,
            action=ResponseAction.RESPOND_ONCE,
            reason=f"hostile expression {hostile_count}dog",
            suggested_response=TEMPLATES[Severity.HOSTILE][0],
        )

    # constructive criticism
    constructive_count = sum(1 for p in CONSTRUCTIVE_PATTERNS if p in body_lower)
    if constructive_count >= 1 or (hostile_count <= 1 and len(body) > 50):
        return NegativeAnalysis(
            severity=Severity.CONSTRUCTIVE,
            action=ResponseAction.ACKNOWLEDGE,
            reason="constructive criticism — admit + answer",
            suggested_response=TEMPLATES[Severity.CONSTRUCTIVE][0],
        )

    # minute negative
    return NegativeAnalysis(
        severity=Severity.TRIVIAL,
        action=ResponseAction.IGNORE,
        reason="minute negative — ignore",
    )


def should_respond(analysis: NegativeAnalysis) -> bool:
    """have to respond Do you do it?."""
    return analysis.action in (ResponseAction.RESPOND_ONCE, ResponseAction.ACKNOWLEDGE)


def get_escalation_status(negative_ratio: float, total_comments: int) -> str:
    """post entire negative ratio check."""
    if total_comments < 5:
        return "insufficient_data"
    if negative_ratio > 0.4:
        return "critical"  # 40% more negative — passivity examine
    if negative_ratio > 0.2:
        return "warning"   # 20% more — caution
    return "normal"
