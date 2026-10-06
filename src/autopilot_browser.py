"""Pi Browser + marketing engine + bird schedule integration fully automatic campaign.

every Action is marketing of the engine pre_flight_checkcast coarseness.
campaign.toml based universal campaign execution.
Phase 1->4 order: karma building -> sow seeds -> post.
"""

from __future__ import annotations

import random
import re
import time
from datetime import datetime
from pathlib import Path

from .display import console, show_error, show_info, show_success, show_warning
from .marketing.engine import MarketingEngine, Action, ActionType
from .schedule import (
    DaySchedule, DayTask, Phase, TaskType,
    build_schedule, build_schedule_from_config,
    get_day_schedule, format_schedule_overview,
)
from .pi_browser import RedditBrowser
from .state import StateDB

REPORT_DIR = "data/reports"


def _load_campaign_config():
    """campaign.toml load (If there is no None)."""
    try:
        from .campaign_config import load_campaign, campaign_exists
        if campaign_exists():
            return load_campaign()
    except Exception as e:
        show_warning(f"campaign.toml load failure: {e}")
    return None


def run_browser_campaign(
    db_path: str = "data/campaign.db",
    run_all: bool = False,
    dry_run: bool = False,
    delay: int = 30,
    comment_delay: int = 10,
    start_day: int | None = None,
    campaign_path: str | None = None,
    **kwargs,
):
    """bird schedule based fully automatic campaign."""
    db = StateDB(db_path)
    engine = MarketingEngine(db)

    # campaign setting load
    campaign = None
    if campaign_path:
        from .campaign_config import load_campaign
        campaign = load_campaign(campaign_path)
    else:
        campaign = _load_campaign_config()

    if campaign:
        show_info(f"campaign: {campaign.product_name} ({campaign.category})")
        if campaign.product_url:
            show_info(f"URL: {campaign.product_url}")

    # situation mark
    console.print()
    console.print(engine.format_status())
    console.print()

    # health check
    health = engine.get_health()
    if not health.can_proceed and not dry_run:
        show_error("account danger situation - activity interruption")
        for w in health.warnings:
            show_error(f"  {w}")
        db.close()
        return

    # browser connection
    browser = None
    if not dry_run:
        show_info("Reddit Browser connection middle...")
        browser = RedditBrowser()
        if not browser.connect():
            show_error("Reddit Browser connection failure - Chromeat Reddit Browser expansion check")
            db.close()
            return

        show_info("Reddit log in check...")
        login = browser.check_login()
        if login.get("logged_in"):
            show_success("Reddit log in Confirmed")
        else:
            show_warning("Reddit Not logged in - Chromeat first Please log in")
            db.close()
            return

    # schedule generation (config based or basic)
    if campaign:
        schedule = build_schedule_from_config(campaign)
    else:
        schedule = build_schedule()

    # start date decision
    if start_day:
        schedule = [s for s in schedule if s.day >= start_day]
    else:
        for s in schedule:
            day_id = f"day-{s.day:02d}"
            status = db.get_day_status(day_id)
            if status not in ("completed",):
                schedule = [x for x in schedule if x.day >= s.day]
                break

    for day_schedule in schedule:
        day_id = f"day-{day_schedule.day:02d}"

        if db.get_day_status(day_id) == "completed":
            continue

        budget = engine.get_budget()
        console.print()
        console.print(f"  [bold]=== Day {day_schedule.day} - {day_schedule.phase.value} ===[/bold]")
        console.print(f"  {day_schedule.description}")
        console.print(f"  Posts: {budget.posts_used}/{budget.posts_limit} | "
                      f"Comments: {budget.comments_used}/{budget.comments_limit}")

        if dry_run:
            _dry_run_day(day_schedule, engine)
            db.set_day_status(day_id, "completed")
        else:
            _execute_day(browser, db, engine, day_schedule, campaign)

        _write_report(db, engine, day_schedule, campaign)

        if not run_all:
            break

        next_days = [s for s in schedule if s.day > day_schedule.day]
        if next_days and run_all:
            show_info(f"Next: Day {next_days[0].day} (after {delay} seconds)...")
            time.sleep(delay)

    if not dry_run:
        _final_report(db, engine)

    db.close()
    if browser:
        browser.stop()


def _dry_run_day(day_schedule: DaySchedule, engine: MarketingEngine):
    """Preview."""
    for task in day_schedule.tasks:
        icon = {
            TaskType.KARMA_COMMENT: "[cyan]KARMA[/cyan]",
            TaskType.SEED_COMMENT: "[green]SEED[/green]",
            TaskType.POST: "[yellow]POST[/yellow]",
            TaskType.MONITOR: "[blue]MONITOR[/blue]",
            TaskType.REST: "[dim]REST[/dim]",
            TaskType.REVIEW: "[magenta]REVIEW[/magenta]",
        }.get(task.task_type, "?")

        console.print(f"  {icon} {task.notes or task.task_type.value}")

        if task.subreddits:
            for sub in task.subreddits:
                action_type = (ActionType.KARMA_BUILD if task.task_type == TaskType.KARMA_COMMENT
                              else ActionType.SEEDING)
                action = Action(
                    action_type=action_type,
                    subreddit=sub,
                    body="[dry-run]",
                )
                pf = engine.pre_flight_check(action)
                status = "[green]OK[/green]" if pf.allowed else f"[red]BLOCKED: {', '.join(pf.blocks)}[/red]"
                console.print(f"    r/{sub}: {status}")
                if pf.warnings:
                    for w in pf.warnings:
                        console.print(f"      [yellow]! {w}[/yellow]")

        if task.task_type == TaskType.POST and task.post_subreddit:
            action = Action(
                action_type=ActionType.POST,
                subreddit=task.post_subreddit,
                title="[dry-run title]",
                body="[dry-run body]",
                is_self_promo=True,
            )
            pf = engine.pre_flight_check(action)
            status = "[green]OK[/green]" if pf.allowed else f"[red]BLOCKED: {', '.join(pf.blocks)}[/red]"
            console.print(f"    r/{task.post_subreddit}: {status}")

    show_success(f"  [DRY RUN] Day {day_schedule.day} complete")


def _execute_day(browser: RedditBrowser, db: StateDB, engine: MarketingEngine,
                 day_schedule: DaySchedule, campaign=None):
    """actual execution."""
    day_id = f"day-{day_schedule.day:02d}"
    db.set_day_status(day_id, "in_progress")

    try:
        for i, task in enumerate(day_schedule.tasks):
            if task.task_type == TaskType.KARMA_COMMENT:
                _exec_karma(browser, db, engine, task, campaign)
            elif task.task_type == TaskType.SEED_COMMENT:
                _exec_seed(browser, db, engine, task, campaign)
            elif task.task_type == TaskType.POST:
                _exec_post(browser, db, engine, task, campaign)
            elif task.task_type == TaskType.MONITOR:
                _exec_monitor(browser, db, engine)
            elif task.task_type == TaskType.REVIEW:
                _exec_review(db, engine)
            elif task.task_type == TaskType.REST:
                show_info("  rest day - activity doesn't exist")

            # task between atmosphere (last task exception)
            if i < len(day_schedule.tasks) - 1:
                between_delay = random.uniform(30, 60)
                show_info(f"  next Until the task {int(between_delay)}candle atmosphere...")
                time.sleep(between_delay)

        db.set_day_status(day_id, "completed")
        show_success(f"  Day {day_schedule.day} complete!")

    except Exception as e:
        show_error(f"  error: {e}")
        db.set_day_status(day_id, "error")


def _get_random_delay(campaign=None) -> float:
    """bot detect For avoidance random delay — minimum 90candle, maximum 180candle.

    Redditsilver sequence Leave a comment to spam Because I sense it sufficient interval necessary.
    """
    base_min = 90
    base_max = 180
    if campaign:
        # config value Even if minimum 90candle guarantee
        cfg_min = max(base_min, campaign.limits.min_delay_seconds)
        cfg_max = max(base_max, campaign.limits.max_delay_seconds)
        return random.uniform(cfg_min, cfg_max)
    return random.uniform(base_min, base_max)


def _check_daily_limit(db: StateDB, action_type: str, campaign=None) -> bool:
    """daily limit check."""
    count = db.get_today_action_count(action_type)
    if campaign:
        if action_type == "karma_build":
            return count < campaign.limits.karma_comments_per_day
        elif action_type in ("seeding", "seed_comment"):
            return count < campaign.limits.seed_comments_per_day
    return count < 8  # basic limit


def _exec_karma(browser: RedditBrowser, db: StateDB, engine: MarketingEngine,
                task: DayTask, campaign=None):
    """karma building - app mention without help comment."""
    for sub in task.subreddits:
        # daily limit check
        if not _check_daily_limit(db, "karma_build", campaign):
            show_warning(f"  KARMA r/{sub}: daily limit arrival")
            continue

        action = Action(
            action_type=ActionType.KARMA_BUILD,
            subreddit=sub, body="", is_self_promo=False,
        )
        pf = engine.pre_flight_check(action)
        if not pf.allowed:
            # Timing only problem case Warning only do continue progress
            timing_only = all("timing" in b for b in pf.blocks)
            if timing_only:
                show_warning(f"  KARMA r/{sub}: timing warning — continue progress")
            else:
                show_warning(f"  KARMA r/{sub}: block - {', '.join(pf.blocks)}")
                continue

        show_info(f"  KARMA r/{sub}: post quest...")

        # HOT post read
        browser.browser.ext_navigate(f"https://www.reddit.com/r/{sub}/hot/")
        browser._wait_load(4)

        # post link collection
        links = browser.browser.ext_evaluate("""
            (() => {
                const posts = document.querySelectorAll('a[href*="/comments/"]');
                const results = [];
                const seen = new Set();
                for (const a of posts) {
                    const href = a.href;
                    if (href && href.includes('/comments/') && !seen.has(href)) {
                        seen.add(href);
                        const id = href.match(/\\/comments\\/([^/]+)/);
                        results.push({url: href, title: (a.textContent || '').substring(0, 100), id: id ? id[1] : ''});
                        if (results.length >= 8) break;
                    }
                }
                return results;
            })()
        """)

        if not links or not isinstance(links, list) or len(links) == 0:
            text = browser.browser.ext_get_text()
            show_info(f"  KARMA r/{sub}: text based on quest ({len(text or '')}ruler)")
            engine.log_executed(action)
            continue

        show_info(f"  KARMA r/{sub}: {len(links)}dog post find")

        # duplication check after target select
        commented_ids = db.get_commented_submission_ids()
        target = None
        for link in links:
            post_id = link.get("id", "")
            if post_id and post_id not in commented_ids:
                target = link
                break
        if not target:
            target = links[0]

        show_info(f"    target: {target.get('title', '?')[:60]}")

        # post detail read
        browser.browser.ext_navigate(target["url"])
        browser._wait_load(3)

        # like a person: post reading hour + scroll
        read_time = random.uniform(5, 15)
        show_info(f"    post reading middle... ({int(read_time)}candle)")
        time.sleep(read_time / 2)
        browser.browser.ext_scroll("down", random.randint(200, 600))
        time.sleep(read_time / 2)

        post_text = browser.browser.ext_get_text() or ""
        show_info(f"    post detail ({len(post_text)}ruler)")

        # existing comment collection (kimigo reference)
        existing_comments = browser.browser.reddit_get_comments(limit=10)
        if existing_comments:
            show_info(f"    existing comment {len(existing_comments)}dog reference")

        # scroll Put it up comment input field Make it visible
        browser.browser.ext_scroll("up", random.randint(300, 800))
        time.sleep(random.uniform(1, 3))

        # comment generation (existing comment reference)
        from .comment_generator import generate_karma_comment
        tone = campaign.karma_tone if campaign else "helpful_expert"
        keywords = task.search_keywords or []
        comment = generate_karma_comment(post_text, sub, tone, keywords,
                                         existing_comments=existing_comments)
        show_info(f"    created comment: {comment[:80]}...")

        # Write a comment
        max_comments = task.max_comments or 2
        result = browser.post_comment(target["url"], comment, comment_type="karma_build")

        # kimi based verification: page reload after comment existence check
        from .comment_generator import verify_comment_posted
        time.sleep(3)
        browser.browser.ext_navigate(target["url"])
        browser._wait_load(4)
        verify_text = browser.browser.ext_get_text() or ""
        verification = verify_comment_posted(verify_text, comment)

        if verification["verified"]:
            show_success(f"    KARMA comment verification complete! r/{sub} ({verification['reason']})")
            db.save_browsed_post(sub, target.get("id", ""), target.get("title", ""),
                               "", target["url"])
        else:
            show_warning(f"    KARMA comment Not verified: {verification['reason']}")

        engine.log_executed(action)

        # random delay (bot detect evasion)
        delay = _get_random_delay(campaign)
        show_info(f"    {int(delay)}candle atmosphere...")
        time.sleep(delay)


def _exec_seed(browser: RedditBrowser, db: StateDB, engine: MarketingEngine,
               task: DayTask, campaign=None):
    """sow seeds - related in the post natural app mention."""
    for sub in task.subreddits:
        # daily limit check
        if not _check_daily_limit(db, "seeding", campaign):
            show_warning(f"  SEED r/{sub}: daily limit arrival")
            continue

        action = Action(
            action_type=ActionType.SEEDING,
            subreddit=sub, body="", is_self_promo=False,
        )
        pf = engine.pre_flight_check(action)
        if not pf.allowed:
            timing_only = all("timing" in b for b in pf.blocks)
            if timing_only:
                show_warning(f"  SEED r/{sub}: timing warning — continue progress")
            else:
                show_warning(f"  SEED r/{sub}: block - {', '.join(pf.blocks)}")
                continue

        show_info(f"  SEED r/{sub}: related post search...")

        # keyword search
        keywords = task.search_keywords or ["tool"]
        query = keywords[0] if keywords else "tool"

        browser.browser.ext_navigate(
            f"https://www.reddit.com/r/{sub}/search/?q={query}&restrict_sr=1&sort=new&t=week"
        )
        browser._wait_load(4)

        # search result collection
        links = browser.browser.ext_evaluate("""
            (() => {
                const posts = document.querySelectorAll('a[href*="/comments/"]');
                const results = [];
                const seen = new Set();
                for (const a of posts) {
                    const href = a.href;
                    if (href && href.includes('/comments/') && !seen.has(href)) {
                        seen.add(href);
                        const id = href.match(/\\/comments\\/([^/]+)/);
                        results.push({url: href, title: (a.textContent || '').substring(0, 100), id: id ? id[1] : ''});
                        if (results.length >= 5) break;
                    }
                }
                return results;
            })()
        """)

        if not links or not isinstance(links, list) or len(links) == 0:
            text = browser.browser.ext_get_text()
            show_warning(f"  SEED r/{sub}: post undiscovered - Skip")
            continue

        # duplication check
        commented_ids = db.get_commented_submission_ids()
        target = None
        for link in links:
            post_id = link.get("id", "")
            if post_id and post_id not in commented_ids:
                target = link
                break
        if not target:
            target = links[0]

        show_info(f"  SEED r/{sub}: target '{target.get('title', '?')[:50]}'")

        # post detail read
        browser.browser.ext_navigate(target["url"])
        browser._wait_load(3)

        # like a person: post reading hour + scroll
        read_time = random.uniform(5, 15)
        show_info(f"    post reading middle... ({int(read_time)}candle)")
        time.sleep(read_time / 2)
        browser.browser.ext_scroll("down", random.randint(200, 600))
        time.sleep(read_time / 2)

        post_text = browser.browser.ext_get_text() or ""

        # existing comment collection (kimigo reference)
        existing_comments = browser.browser.reddit_get_comments(limit=10)
        if existing_comments:
            show_info(f"    existing comment {len(existing_comments)}dog reference")

        browser.browser.ext_scroll("up", random.randint(300, 800))
        time.sleep(random.uniform(1, 3))

        # sow seeds comment generation (existing comment reference)
        if campaign:
            from .comment_generator import generate_seed_comment
            tone = campaign.seed_tone
            comment = generate_seed_comment(post_text, campaign, tone, keywords,
                                            existing_comments=existing_comments)
        else:
            comment = f"I've been exploring similar tools. Worth checking out the options available."

        show_info(f"    created comment: {comment[:80]}...")

        # Write a comment
        result = browser.post_comment(target["url"], comment, comment_type="seeding")

        # kimi based verification
        from .comment_generator import verify_comment_posted
        time.sleep(3)
        browser.browser.ext_navigate(target["url"])
        browser._wait_load(4)
        verify_text = browser.browser.ext_get_text() or ""
        verification = verify_comment_posted(verify_text, comment)

        if verification["verified"]:
            show_success(f"    SEED comment verification complete! r/{sub} ({verification['reason']})")
            db.save_browsed_post(sub, target.get("id", ""), target.get("title", ""),
                               "", target["url"])
        else:
            show_warning(f"    SEED comment Not verified: {verification['reason']}")

        engine.log_executed(action)

        delay = _get_random_delay(campaign)
        show_info(f"    {int(delay)}candle atmosphere...")
        time.sleep(delay)


def _exec_post(browser: RedditBrowser, db: StateDB, engine: MarketingEngine,
               task: DayTask, campaign=None):
    """post publication - CDP based."""
    sub = task.post_subreddit
    if not sub:
        return

    # duplication post prevention
    if db.has_posted_to(sub, days=7):
        show_warning(f"  POST r/{sub}: recent 7Day my already Posted - Skip")
        return

    # daily limit
    if db.get_today_post_count() >= (campaign.limits.posts_per_day if campaign else 1):
        show_warning(f"  POST r/{sub}: daily post limit arrival")
        return

    action = Action(
        action_type=ActionType.POST,
        subreddit=sub,
        title=f"[preparation] {task.notes}",
        body="",
        is_self_promo=True,
    )
    pf = engine.pre_flight_check(action)
    _show_preflight(pf)

    if not pf.allowed:
        show_error(f"  POST r/{sub}: blocked")
        for b in pf.blocks:
            show_error(f"    - {b}")
        return

    # post detail generation
    if campaign:
        from .comment_generator import generate_post_title, generate_post_body
        title = generate_post_title(campaign, sub, task.notes)
        body = generate_post_body(campaign, sub, task.notes)
    else:
        title = task.notes or f"Sharing my project with r/{sub}"
        body = ""

    show_info(f"  POST r/{sub}: post page opening...")
    show_info(f"    title: {title}")

    # CDP based post publication
    result = browser.submit_post(sub, title, body)

    if result.get("status") == "ready":
        # CDP typeTextas publication
        show_info(f"  POST r/{sub}: detail input complete, publication trial...")
        submit_result = browser.confirm_submit()

        # URL change check (/comments/ include)
        time.sleep(3)
        current_text = browser.browser.ext_get_text() or ""
        page_info = browser.browser.ext_evaluate("({url: location.href, title: document.title})")

        current_url = ""
        if isinstance(page_info, dict):
            current_url = page_info.get("url", "")

        if "/comments/" in current_url:
            show_success(f"  POST r/{sub}: publication success! {current_url}")
            # DB save
            m = re.search(r'/comments/([^/]+)', current_url)
            reddit_id = m.group(1) if m else ""
            day_id = f"day-{task.post_subreddit}"
            db.save_submission(day_id, reddit_id, sub, title, current_url)
        else:
            show_warning(f"  POST r/{sub}: publication unconfirmed - passivity check necessary")
            console.print(f"    today URL: {current_url}")

    engine.log_executed(action)


def _exec_monitor(browser: RedditBrowser, db: StateDB, engine: MarketingEngine):
    """existing post monitoring."""
    submissions = db.get_submissions()
    if not submissions:
        show_info("  to monitor post doesn't exist")
        return

    show_info(f"  {len(submissions)}dog post monitoring")
    for sub in submissions:
        url = sub.get("url", "")
        if not url:
            continue
        stats = browser.get_post_stats(url)
        if stats:
            show_info(f"    r/{sub.get('subreddit', '?')}: "
                      f"score={stats.get('score', '?')}, "
                      f"comments={stats.get('comment_count', '?')}")
        time.sleep(2)


def _exec_review(db: StateDB, engine: MarketingEngine):
    """result review."""
    show_info("  result analyze...")
    console.print(engine.format_status())

    try:
        from .marketing.performance import get_subreddit_rankings, suggest_effort_reallocation
        rankings = get_subreddit_rankings(db)
        if rankings:
            show_info("  subreddit ROI ranking:")
            for r in rankings[:5]:
                console.print(f"    r/{r.subreddit}: ROI={r.roi_score}, "
                             f"posts={r.total_posts}, comments={r.total_comments}")
            suggestions = suggest_effort_reallocation(rankings)
            for sub_name, action_str in suggestions.items():
                console.print(f"    r/{sub_name}: {action_str}")
    except Exception:
        pass

    try:
        from .marketing.roi import fetch_github_stats, save_snapshot
        snapshot = fetch_github_stats()
        if snapshot:
            save_snapshot(db, snapshot)
            show_info(f"  GitHub: {snapshot.stars} stars, {snapshot.total_downloads} downloads")
    except Exception:
        pass


def _show_preflight(pf):
    """pre-flight result mark."""
    if pf.timing:
        grade_colors = {
            "optimal": "green", "good": "green",
            "acceptable": "yellow", "poor": "yellow", "avoid": "red",
        }
        color = grade_colors.get(pf.timing.grade.value, "white")
        console.print(f"  Timing: [{color}]{pf.timing.grade.value.upper()}[/{color}] - {pf.timing.reason}")

    if pf.health:
        risk_colors = {"green": "green", "yellow": "yellow", "red": "red"}
        color = risk_colors.get(pf.health.risk_level.value, "white")
        console.print(f"  Health: [{color}]{pf.health.risk_level.value.upper()}[/{color}]")

    for w in pf.warnings:
        show_warning(f"  {w}")
    for b in pf.blocks:
        show_error(f"  BLOCK: {b}")


def _write_report(db: StateDB, engine: MarketingEngine, day_schedule: DaySchedule, campaign=None):
    """execution report."""
    Path(REPORT_DIR).mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    filepath = Path(REPORT_DIR) / f"day-{day_schedule.day:02d}_{now.strftime('%Y-%m-%d_%H%M%S')}.md"

    health = engine.get_health()
    budget = engine.get_budget()

    task_summary = ", ".join(t.task_type.value for t in day_schedule.tasks)

    lines = [
        f"# Day {day_schedule.day} - {day_schedule.phase.value}",
        "",
    ]
    if campaign:
        lines.append(f"**Campaign**: {campaign.product_name}")
        lines.append(f"**URL**: {campaign.product_url}")
        lines.append("")

    lines.extend([
        f"**Phase**: {day_schedule.phase.value}",
        f"**Tasks**: {task_summary}",
        f"**Description**: {day_schedule.description}",
        "",
        "## Marketing Engine Status",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Risk Level | {health.risk_level.value} |",
        f"| Posts Today | {budget.posts_used}/{budget.posts_limit} |",
        f"| Comments Today | {budget.comments_used}/{budget.comments_limit} |",
        f"| Time | {now.strftime('%Y-%m-%d %H:%M:%S')} |",
        "",
    ])

    if health.warnings:
        lines.extend(["## Warnings", ""])
        for w in health.warnings:
            lines.append(f"- {w}")
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    show_info(f"  Report: {filepath}")


def _final_report(db: StateDB, engine: MarketingEngine):
    """final ROI report."""
    try:
        from .marketing.roi import fetch_github_stats, save_snapshot, get_roi_summary
        show_info("GitHub metric collection...")
        snapshot = fetch_github_stats()
        if snapshot:
            save_snapshot(db, snapshot)
            show_success(f"GitHub: {snapshot.stars} stars, {snapshot.total_downloads} downloads")

        roi = get_roi_summary(db)
        show_info(f"ROI: Reddit score={roi.total_reddit_score}, "
                  f"Stars delta={roi.stars_delta}, Downloads delta={roi.downloads_delta}")
    except Exception as e:
        show_warning(f"ROI report failure: {e}")


def show_schedule(campaign_path: str | None = None):
    """30Day entire schedule output of power."""
    campaign = None
    if campaign_path:
        from .campaign_config import load_campaign
        campaign = load_campaign(campaign_path)
    else:
        campaign = _load_campaign_config()

    console.print(format_schedule_overview(campaign))
