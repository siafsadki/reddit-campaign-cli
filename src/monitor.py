"""comment monitoring + Q&A automatic response + continue monitoring + log documentation."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from .config import Config
from .display import confirm_action, show_info, show_success, show_warning
from .parser import QAPair
from .reddit_client import RedditClient
from .state import StateDB

# comment emotion/category classification keyword
SENTIMENT_KEYWORDS = {
    "positive": [
        "cool", "awesome", "nice", "great", "love", "amazing", "thanks",
        "useful", "helpful", "impressive", "solid", "clean", "beautiful",
    ],
    "negative": [
        "bloat", "waste", "bad", "slow", "ugly", "useless", "garbage",
        "sucks", "hate", "terrible", "awful", "pointless", "spam",
    ],
    "question": [
        "how", "why", "what", "does it", "can it", "is there", "when",
        "where", "support", "compatible", "work with",
    ],
    "feature_request": [
        "would be nice", "please add", "wish", "feature request",
        "it would be great", "any plans", "roadmap",
    ],
    "comparison": [
        "vs", "compared to", "better than", "worse than", "instead of",
        "alternative", "switch from", "tmux", "alacritty", "wezterm",
        "warp", "iterm", "kitty",
    ],
}

# importance topic detect
TOPIC_KEYWORDS = {
    "linux": ["linux", "ubuntu", "fedora", "arch", "debian", "wayland", "x11"],
    "open_source": ["open source", "closed source", "license", "foss", "gpl", "mit license"],
    "pricing": ["price", "free", "paid", "cost", "subscription", "pro tier"],
    "performance": ["slow", "fast", "memory", "ram", "cpu", "lag", "performance"],
    "security": ["security", "trust", "privacy", "data", "telemetry", "safe"],
}


def check_new_comments(
    client: RedditClient,
    db: StateDB,
    qa_pairs: list[QAPair] | None = None,
    dry_run: bool = False,
    auto_confirm: bool = False,
) -> list[dict]:
    """every existing of the post bird comment check + Q&A matching."""
    results = []
    submissions = db.get_submissions()
    replied_ids = db.get_replied_comment_ids()
    my_username = client.config.reddit.username.lower()

    if not submissions:
        show_info("No submissions to monitor.")
        return results

    for sub in submissions:
        reddit_id = sub.get("reddit_id")
        if not reddit_id:
            continue

        show_info(f"Checking {sub.get('subreddit', '?')} - {sub.get('title', '?')[:40]}...")

        try:
            comments = client.get_new_comments(reddit_id)
        except Exception as e:
            show_warning(f"  Error fetching comments: {e}")
            continue

        new_comments = []
        for c in comments:
            # self comment skip
            if hasattr(c, "author") and c.author and c.author.name.lower() == my_username:
                continue
            # already answered comment skip
            if c.id in replied_ids:
                continue

            # comment analyze
            sentiment = _classify_sentiment(c.body)
            topics = _detect_topics(c.body)
            priority = _calculate_priority(sentiment, topics, c)

            comment_data = {
                "id": c.id,
                "author": c.author.name if c.author else "[deleted]",
                "body": c.body,
                "score": getattr(c, "score", 0),
                "created_utc": getattr(c, "created_utc", 0),
                "sentiment": sentiment,
                "topics": topics,
                "priority": priority,
                "suggested_reply": None,
            }

            # Q&A matching
            if qa_pairs:
                match = _match_qa(c.body, qa_pairs)
                if match:
                    comment_data["suggested_reply"] = match.answer
                    comment_data["matched_question"] = match.question

            new_comments.append(comment_data)

        # priority array: high From things
        new_comments.sort(key=lambda x: x["priority"], reverse=True)

        if new_comments:
            results.append({
                "submission_id": reddit_id,
                "subreddit": sub.get("subreddit", ""),
                "title": sub.get("title", ""),
                "day_id": sub.get("day_id", ""),
                "new_comments": new_comments,
                "total_comments": len(comments),
            })

        db.update_comment_check(reddit_id)

    # automatic response treatment
    if not dry_run and results:
        _handle_auto_replies(client, db, results, auto_confirm)

    return results


def run_continuous_monitor(
    client: RedditClient,
    db: StateDB,
    qa_pairs: list[QAPair] | None = None,
    interval: int = 300,
    log_dir: str = "data/monitor-logs",
    auto_confirm: bool = False,
):
    """continue monitoring loop. intervalevery second bird comment check + log record."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    show_info(f"Starting continuous monitor (interval: {interval}s)")
    show_info(f"Logs: {log_dir}/")
    show_info("Press Ctrl+C to stop.\n")

    cycle = 0
    while True:
        cycle += 1
        now = datetime.now()
        show_info(f"--- Cycle {cycle} at {now.strftime('%H:%M:%S')} ---")

        try:
            results = check_new_comments(
                client, db, qa_pairs=qa_pairs,
                auto_confirm=auto_confirm,
            )

            # result log record
            if results:
                _write_monitor_log(results, log_dir, now)
                _update_monitor_report(results, log_dir, now)

            total_new = sum(len(r.get("new_comments", [])) for r in results)
            show_info(f"  Found {total_new} new comments across {len(results)} posts.\n")

        except KeyboardInterrupt:
            show_info("\nMonitor stopped by user.")
            break
        except Exception as e:
            show_warning(f"  Error in monitor cycle: {e}")

        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            show_info("\nMonitor stopped by user.")
            break


def _classify_sentiment(body: str) -> str:
    """comment emotion classification."""
    body_lower = body.lower()
    scores = {}
    for sentiment, keywords in SENTIMENT_KEYWORDS.items():
        scores[sentiment] = sum(1 for kw in keywords if kw in body_lower)

    if not any(scores.values()):
        return "neutral"

    return max(scores, key=scores.get)


def _detect_topics(body: str) -> list[str]:
    """In the comments importance topic detect."""
    body_lower = body.lower()
    detected = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in body_lower for kw in keywords):
            detected.append(topic)
    return detected


def _calculate_priority(sentiment: str, topics: list[str], comment) -> int:
    """comment response priority calculate (The higher it is hourly rate)."""
    score = 0

    # The question is answer essential
    if sentiment == "question":
        score += 30
    # negative The comment is fast react necessary
    elif sentiment == "negative":
        score += 25
    # function The request is importance
    elif sentiment == "feature_request":
        score += 20
    # comparison The question is opportunity
    elif sentiment == "comparison":
        score += 15
    # Positivity is thanks mark
    elif sentiment == "positive":
        score += 5

    # hot topic Extra points
    if "linux" in topics:
        score += 10  # often coming out question
    if "security" in topics:
        score += 10  # fast react necessary
    if "open_source" in topics:
        score += 5

    # Upvote high comment first of all
    comment_score = getattr(comment, "score", 0)
    if comment_score >= 10:
        score += 15
    elif comment_score >= 5:
        score += 10
    elif comment_score >= 2:
        score += 5

    return score


def _match_qa(comment_body: str, qa_pairs: list[QAPair]) -> QAPair | None:
    """comment content and Q&A keyword matching."""
    body_lower = comment_body.lower()
    best_match = None
    best_score = 0

    for qa in qa_pairs:
        keywords = qa.question.lower().split()
        # stop words eliminate
        stopwords = {"a", "the", "is", "it", "not", "just", "i", "you", "do", "does"}
        meaningful = [kw for kw in keywords if kw not in stopwords and len(kw) > 2]
        score = sum(1 for kw in meaningful if kw in body_lower)
        # minimum 2dog meaningful keyword matching necessary
        if score >= 2 and score > best_score:
            best_score = score
            best_match = qa

    return best_match


def _handle_auto_replies(
    client: RedditClient,
    db: StateDB,
    results: list[dict],
    auto_confirm: bool,
):
    """matched Q&Ato about automatic response."""
    for r in results:
        for c in r.get("new_comments", []):
            if not c.get("suggested_reply"):
                continue

            priority_label = "HIGH" if c["priority"] >= 25 else "MED" if c["priority"] >= 10 else "LOW"

            show_info(f"\n  [{r['subreddit']}] [{priority_label}] {c['author']}: {c['body'][:80]}")
            show_info(f"  Sentiment: {c['sentiment']} | Topics: {', '.join(c['topics']) or 'none'}")
            show_info(f"  -> Reply: {c['suggested_reply'][:80]}...")

            if not auto_confirm and not confirm_action("Post this reply?"):
                show_info("  Skipped.")
                continue

            try:
                reply = client.reply_to_comment(c["id"], c["suggested_reply"])
                db.save_comment(
                    reddit_id=reply.id,
                    submission_id=r["submission_id"],
                    subreddit=r["subreddit"],
                    body=c["suggested_reply"],
                    comment_type="auto_reply",
                )
                show_success(f"  Replied to {c['author']}")
            except Exception as e:
                show_warning(f"  Error replying: {e}")


def _write_monitor_log(results: list[dict], log_dir: str, now: datetime):
    """each monitoring cycle farsighted log JSONLas record."""
    log_path = Path(log_dir) / f"raw-{now.strftime('%Y-%m-%d')}.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        for r in results:
            for c in r.get("new_comments", []):
                entry = {
                    "timestamp": now.isoformat(),
                    "subreddit": r["subreddit"],
                    "submission_title": r["title"],
                    "comment_id": c["id"],
                    "author": c["author"],
                    "body": c["body"][:500],
                    "score": c.get("score", 0),
                    "sentiment": c["sentiment"],
                    "topics": c["topics"],
                    "priority": c["priority"],
                    "matched_question": c.get("matched_question"),
                    "had_suggested_reply": bool(c.get("suggested_reply")),
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _update_monitor_report(results: list[dict], log_dir: str, now: datetime):
    """glance monitoring report markdown file update."""
    report_path = Path(log_dir) / f"report-{now.strftime('%Y-%m-%d')}.md"

    # existing report loading or new generation
    if report_path.exists():
        existing = report_path.read_text(encoding="utf-8")
    else:
        existing = f"# Monitor Report — {now.strftime('%Y-%m-%d')}\n\n"

    # bird section addition
    section = f"\n## {now.strftime('%H:%M:%S')} Check\n\n"

    for r in results:
        new_comments = r.get("new_comments", [])
        if not new_comments:
            continue

        section += f"### {r['subreddit']} — {r['title'][:50]}\n\n"
        section += f"New comments: {len(new_comments)} | Total: {r.get('total_comments', '?')}\n\n"

        # emotion distribution
        sentiments = {}
        for c in new_comments:
            s = c["sentiment"]
            sentiments[s] = sentiments.get(s, 0) + 1
        section += f"Sentiment: {', '.join(f'{k}={v}' for k, v in sorted(sentiments.items()))}\n\n"

        # detected topic
        all_topics = set()
        for c in new_comments:
            all_topics.update(c["topics"])
        if all_topics:
            section += f"Topics: {', '.join(sorted(all_topics))}\n\n"

        # main comment (priority difference)
        section += "| Priority | Author | Sentiment | Comment |\n"
        section += "|----------|--------|-----------|---------|\n"
        for c in new_comments[:10]:  # difference 10Just a dog
            body_short = c["body"][:60].replace("|", "/").replace("\n", " ")
            section += f"| {c['priority']} | u/{c['author']} | {c['sentiment']} | {body_short} |\n"
        section += "\n"

    # In the report addition
    report_path.write_text(existing + section, encoding="utf-8")


def generate_daily_summary(log_dir: str = "data/monitor-logs", date_str: str | None = None):
    """glance monitoring from log synthesis Summary generation."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    log_path = Path(log_dir) / f"raw-{date_str}.jsonl"
    if not log_path.exists():
        show_info(f"No log found for {date_str}")
        return

    entries = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    if not entries:
        show_info(f"No entries for {date_str}")
        return

    # statistics tally
    total = len(entries)
    by_subreddit = {}
    by_sentiment = {}
    by_topic = {}
    high_priority = []

    for e in entries:
        sub = e["subreddit"]
        by_subreddit[sub] = by_subreddit.get(sub, 0) + 1

        sent = e["sentiment"]
        by_sentiment[sent] = by_sentiment.get(sent, 0) + 1

        for t in e.get("topics", []):
            by_topic[t] = by_topic.get(t, 0) + 1

        if e.get("priority", 0) >= 25:
            high_priority.append(e)

    # summation markdown generation
    summary_path = Path(log_dir) / f"summary-{date_str}.md"
    lines = [
        f"# Daily Summary — {date_str}\n",
        f"\nTotal new comments: **{total}**\n",
        "\n## By Subreddit\n",
        "| Subreddit | Count |",
        "|-----------|-------|",
    ]
    for sub, count in sorted(by_subreddit.items(), key=lambda x: -x[1]):
        lines.append(f"| {sub} | {count} |")

    lines.extend([
        "\n## Sentiment Distribution\n",
        "| Sentiment | Count | Pct |",
        "|-----------|-------|-----|",
    ])
    for sent, count in sorted(by_sentiment.items(), key=lambda x: -x[1]):
        pct = round(count / total * 100)
        lines.append(f"| {sent} | {count} | {pct}% |")

    if by_topic:
        lines.extend([
            "\n## Hot Topics\n",
            "| Topic | Mentions |",
            "|-------|----------|",
        ])
        for topic, count in sorted(by_topic.items(), key=lambda x: -x[1]):
            lines.append(f"| {topic} | {count} |")

    if high_priority:
        lines.extend([
            f"\n## High Priority Comments ({len(high_priority)})\n",
        ])
        for e in high_priority[:15]:
            body_short = e["body"][:80].replace("\n", " ")
            lines.append(f"- **[{e['subreddit']}]** u/{e['author']}: {body_short}")

    lines.append(f"\n---\n*Generated at {datetime.now().strftime('%H:%M:%S')}*\n")

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    show_success(f"Daily summary written to {summary_path}")
