"""By subreddit rule management."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubredditProfile:
    name: str
    min_karma: int = 0
    min_account_age_days: int = 0
    self_promo_ratio: float = 0.1   # 10:1 rule (promotion 1 : contribution 10)
    self_promo_allowed: bool = True
    max_posts_per_week: int = 2
    requires_flair: bool = False
    allowed_types: list[str] = field(default_factory=lambda: ["text", "link"])
    banned_keywords: list[str] = field(default_factory=list)
    notes: str = ""


# campaign Target subreddit profile
PROFILES: dict[str, SubredditProfile] = {
    "commandline": SubredditProfile(
        name="commandline",
        min_karma=10,
        self_promo_ratio=0.1,
        notes="terminal equipment illusion. GUI app 'terminal'as When you call repulsion.",
    ),
    "programming": SubredditProfile(
        name="programming",
        min_karma=50,
        min_account_age_days=7,
        self_promo_ratio=0.1,
        notes="10:1 rule severity. self project Promotion is contribution 10dog after 1dog.",
    ),
    "rust": SubredditProfile(
        name="rust",
        min_karma=20,
        self_promo_ratio=0.2,
        notes="Rust cord/crate related only. common app promotion negative.",
    ),
    "ClaudeAI": SubredditProfile(
        name="ClaudeAI",
        min_karma=5,
        self_promo_ratio=0.3,
        notes="AI integration example illusion. use experience center.",
    ),
    "webdev": SubredditProfile(
        name="webdev",
        min_karma=20,
        self_promo_ratio=0.1,
        notes="Show-off Saturday conjugation. weekdays self promo caution.",
    ),
    "SideProject": SubredditProfile(
        name="SideProject",
        min_karma=5,
        self_promo_allowed=True,
        self_promo_ratio=0.5,
        notes="side project share exclusive. self promo OK.",
    ),
    "macapps": SubredditProfile(
        name="macapps",
        min_karma=10,
        allowed_types=["text", "link"],
        notes="macOS app exclusive. price/free express necessary.",
    ),
    "tauri": SubredditProfile(
        name="tauri",
        min_karma=5,
        self_promo_ratio=0.3,
        notes="Tauri framework community. technology detail importance.",
    ),
    "neovim": SubredditProfile(
        name="neovim",
        min_karma=10,
        notes="terminal purist plenty. Electron/Taurito skeptical.",
    ),
    "devops": SubredditProfile(
        name="devops",
        min_karma=20,
        self_promo_ratio=0.1,
        notes="practice equipment center. light project antipathy.",
    ),
    "coolgithubprojects": SubredditProfile(
        name="coolgithubprojects",
        min_karma=5,
        self_promo_allowed=True,
        self_promo_ratio=1.0,
        notes="GitHub project share exclusive. link essential.",
    ),
    "selfhosted": SubredditProfile(
        name="selfhosted",
        min_karma=10,
        notes="self hosting It should be possible. Docker/server distribution related.",
    ),
}


@dataclass
class RuleCheckResult:
    allowed: bool
    warnings: list[str]
    blocks: list[str]


def check_rules(subreddit: str, action_type: str, is_self_promo: bool = False) -> RuleCheckResult:
    """subreddit rule check."""
    sub = subreddit.replace("r/", "").lower()
    profile = PROFILES.get(sub)

    warnings = []
    blocks = []

    if not profile:
        warnings.append(f"r/{sub}: profile Not registered — basic rule apply")
        return RuleCheckResult(allowed=True, warnings=warnings, blocks=blocks)

    # self promo check
    if is_self_promo and not profile.self_promo_allowed:
        blocks.append(f"r/{sub}: self promotion prohibition subreddit")

    if is_self_promo and profile.self_promo_ratio < 0.2:
        warnings.append(
            f"r/{sub}: 10:1 rule — promotion jeon contribution comment {int(1/profile.self_promo_ratio)}dog necessary"
        )

    # post type
    if action_type == "post" and "text" not in profile.allowed_types:
        blocks.append(f"r/{sub}: text post not allowed")

    # Note
    if profile.notes:
        warnings.append(f"r/{sub} reference: {profile.notes}")

    allowed = len(blocks) == 0
    return RuleCheckResult(allowed=allowed, warnings=warnings, blocks=blocks)


def get_profile(subreddit: str) -> SubredditProfile | None:
    """subreddit profile check."""
    sub = subreddit.replace("r/", "").lower()
    return PROFILES.get(sub)
