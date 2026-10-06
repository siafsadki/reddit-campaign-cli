"""sow seeds engine — Search related posts → Write a comment."""

from __future__ import annotations

import time

from .config import Config
from .display import confirm_action, show_info, show_success, show_warning
from .parser import SeedingComment
from .reddit_client import RedditClient
from .state import StateDB


def execute_seeding(
    client: RedditClient,
    db: StateDB,
    seeding_comments: list[SeedingComment],
    day_id: str,
    dry_run: bool = False,
    auto_confirm: bool = False,
) -> list[dict]:
    """sow seeds comment execution."""
    results = []

    if not seeding_comments:
        show_info("No seeding comments for this day.")
        return results

    for sc in seeding_comments:
        if not sc.body:
            show_warning(f"  {sc.subreddit}: No comment body (template only), skipping.")
            continue

        show_info(f"  Seeding target: {sc.subreddit}")
        if sc.context:
            show_info(f"  Context: {sc.context}")

        if dry_run:
            show_info(f"  [DRY RUN] Would search {sc.subreddit} and post comment")
            show_info(f"  Comment: {sc.body[:80]}...")
            results.append({"subreddit": sc.subreddit, "status": "dry_run"})
            continue

        try:
            # On the subreddit Search related posts
            search_terms = _extract_search_terms(sc.context)
            posts = client.search_subreddit(
                sc.subreddit, search_terms, limit=client.config.settings.seeding_search_limit
            )

            if not posts:
                # If there are no search results, choose from hot posts
                posts = client.get_hot_posts(sc.subreddit, limit=5)

            if not posts:
                show_warning(f"  No posts found in {sc.subreddit}")
                continue

            # first th good in the post comment
            target_post = posts[0]
            show_info(f"  Target post: {target_post.title[:60]}")
            show_info(f"  Comment: {sc.body[:80]}...")

            if not auto_confirm and not confirm_action("Post this seeding comment?"):
                show_info("  Skipped.")
                continue

            comment = client.post_comment(target_post.id, sc.body)
            db.save_comment(
                reddit_id=comment.id,
                submission_id=target_post.id,
                subreddit=sc.subreddit,
                body=sc.body,
                comment_type="seeding",
            )
            show_success(f"  Seeding comment posted in {sc.subreddit}")
            results.append({
                "subreddit": sc.subreddit,
                "comment_id": comment.id,
                "post_title": target_post.title,
                "status": "posted",
            })

        except Exception as e:
            show_warning(f"  Error seeding {sc.subreddit}: {e}")
            results.append({"subreddit": sc.subreddit, "status": "error", "error": str(e)})

    return results


def _extract_search_terms(context: str) -> str:
    """in context search term extraction."""
    if not context:
        return "terminal CLI tool"
    # Try extracting text inside quotes
    import re
    quoted = re.findall(r'"([^"]+)"', context)
    if quoted:
        return " ".join(quoted)
    # just context as search term use
    return context[:50]
