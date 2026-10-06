"""ROI analyze — GitHub star/download vs Reddit activity correlation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

from ..state import StateDB

def _get_github_repo() -> str:
    """campaign.tomlat GitHub repo channel extraction."""
    try:
        from ..campaign_config import load_campaign, campaign_exists
        if campaign_exists():
            cfg = load_campaign()
            url = cfg.product_url
            # https://github.com/user/repo → user/repo
            if "github.com/" in url:
                return url.split("github.com/")[-1].rstrip("/")
    except Exception:
        pass
    return ""


@dataclass
class GitHubSnapshot:
    stars: int
    forks: int
    watchers: int
    total_downloads: int
    recorded_at: str


@dataclass
class ROISummary:
    total_reddit_score: int
    total_reddit_comments: int
    github_stars: int
    github_downloads: int
    stars_delta: int       # campaign period change
    downloads_delta: int
    best_day: str | None   # most effective me
    cost_per_star: float   # post number / star increase
    snapshots: list[dict]


def fetch_github_stats() -> GitHubSnapshot | None:
    """GitHub APIat today statistics import (certification otiosity)."""
    repo = _get_github_repo()
    if not repo:
        return None

    github_api = f"https://api.github.com/repos/{repo}"
    user_agent = f"RedditCampaign/1.0"

    try:
        req = Request(github_api, headers={"User-Agent": user_agent})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        stars = data.get("stargazers_count", 0)
        forks = data.get("forks_count", 0)
        watchers = data.get("subscribers_count", 0)

        # release download number
        total_downloads = 0
        try:
            releases_req = Request(
                f"{github_api}/releases",
                headers={"User-Agent": user_agent},
            )
            with urlopen(releases_req, timeout=10) as resp:
                releases = json.loads(resp.read())
            for release in releases:
                for asset in release.get("assets", []):
                    total_downloads += asset.get("download_count", 0)
        except Exception:
            pass

        return GitHubSnapshot(
            stars=stars,
            forks=forks,
            watchers=watchers,
            total_downloads=total_downloads,
            recorded_at=datetime.now().isoformat(),
        )
    except Exception:
        return None


def save_snapshot(db: StateDB, snapshot: GitHubSnapshot):
    """snapshot DB save."""
    db.conn.execute(
        "INSERT INTO github_metrics (stars, forks, watchers, total_downloads, recorded_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (snapshot.stars, snapshot.forks, snapshot.watchers,
         snapshot.total_downloads, snapshot.recorded_at),
    )
    db.conn.commit()


def get_roi_summary(db: StateDB) -> ROISummary:
    """ROI synthesis analyze."""
    # Reddit gun result
    reddit_scores = db.conn.execute(
        "SELECT COALESCE(SUM(upvotes), 0) as total FROM metrics"
    ).fetchone()["total"]
    reddit_comments = db.conn.execute(
        "SELECT COALESCE(SUM(comment_count), 0) as total FROM metrics"
    ).fetchone()["total"]

    # GitHub snapshot
    snapshots = db.conn.execute(
        "SELECT * FROM github_metrics ORDER BY recorded_at"
    ).fetchall()
    snapshots = [dict(r) for r in snapshots]

    github_stars = 0
    github_downloads = 0
    stars_delta = 0
    downloads_delta = 0

    if snapshots:
        latest = snapshots[-1]
        first = snapshots[0]
        github_stars = latest.get("stars", 0)
        github_downloads = latest.get("total_downloads", 0)
        stars_delta = github_stars - first.get("stars", 0)
        downloads_delta = github_downloads - first.get("total_downloads", 0)

    # post number
    post_count = db.conn.execute(
        "SELECT COUNT(*) as cnt FROM submissions"
    ).fetchone()["cnt"]

    cost_per_star = post_count / max(1, stars_delta) if stars_delta > 0 else 0

    return ROISummary(
        total_reddit_score=reddit_scores,
        total_reddit_comments=reddit_comments,
        github_stars=github_stars,
        github_downloads=github_downloads,
        stars_delta=stars_delta,
        downloads_delta=downloads_delta,
        best_day=None,
        cost_per_star=round(cost_per_star, 2),
        snapshots=snapshots,
    )
