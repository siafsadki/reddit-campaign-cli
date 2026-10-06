"""fully automatic campaign execution engine.

python main.py auto          → next Incomplete date 1dog execution + monitoring + report
python main.py auto --all    → every Incomplete date sequential execution
python main.py auto --daemon → daemon mode (on schedule Guess what automatic execution)
python main.py auto --status → entire progress + next will do Day mark
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from .config import Config, load_config
from .display import console, show_error, show_info, show_success, show_warning
from .parser import DayPlan, DayType, parse_all_days, resolve_day_id
from .schedule import DAY_ORDER
from .state import StateDB

MONITOR_INTERVAL = 300  # 5minute


def _get_next_pending(db: StateDB) -> str | None:
    """next run date return."""
    for day_id in DAY_ORDER:
        status = db.get_day_status(day_id)
        if status not in ("completed",):
            return day_id
    return None


def _get_progress(db: StateDB) -> dict:
    """entire progress."""
    total = len(DAY_ORDER)
    completed = 0
    in_progress = 0
    errors = 0
    pending = 0

    for day_id in DAY_ORDER:
        status = db.get_day_status(day_id)
        if status == "completed":
            completed += 1
        elif status == "error":
            errors += 1
        elif status == "in_progress":
            in_progress += 1
        else:
            pending += 1

    return {
        "total": total,
        "completed": completed,
        "in_progress": in_progress,
        "errors": errors,
        "pending": pending,
        "pct": round(completed / total * 100, 1),
    }


def show_auto_status(config: Config):
    """automatic execution situation dashboard."""
    from rich.panel import Panel
    from rich.table import Table

    db = StateDB(config.campaign.db_path)
    plans = parse_all_days(config.campaign.docs_dir)
    progress = _get_progress(db)
    next_day = _get_next_pending(db)

    console.print()
    console.print(Panel("[bold]Autopilot Status[/bold]", style="blue", width=70))

    # progress
    bar_len = 40
    filled = int(bar_len * progress["completed"] / progress["total"])
    bar = "█" * filled + "░" * (bar_len - filled)
    console.print(f"  Progress: [{bar}] {progress['pct']}%")
    console.print(
        f"  Completed: {progress['completed']} | "
        f"Pending: {progress['pending']} | "
        f"Errors: {progress['errors']}"
    )
    console.print()

    if next_day:
        plan = plans.get(next_day)
        if plan:
            console.print(f"  [bold]Next:[/bold] {next_day} ({plan.day_type.value})")
            if plan.subreddit:
                console.print(f"  Subreddit: r/{plan.subreddit}")
            if plan.post:
                console.print(f"  Post: {plan.post.title[:60]}")
            if plan.seeding_comments:
                console.print(f"  Seeding: {len(plan.seeding_comments)} comments")
    else:
        console.print("  [green]All days completed![/green]")

    # By date situation table
    console.print()
    table = Table(title="Campaign Timeline", width=70)
    table.add_column("Day", style="cyan", width=12)
    table.add_column("Type", width=14)
    table.add_column("Subreddit", width=20)
    table.add_column("Status", width=12)

    status_styles = {
        "completed": "[green]done[/green]",
        "in_progress": "[yellow]running[/yellow]",
        "error": "[red]error[/red]",
    }

    for day_id in DAY_ORDER:
        status = db.get_day_status(day_id) or "pending"
        plan = plans.get(day_id)
        table.add_row(
            day_id,
            plan.day_type.value if plan else "?",
            plan.subreddit if plan and plan.subreddit else "-",
            status_styles.get(status, "[dim]pending[/dim]"),
        )

    console.print(table)
    console.print()
    db.close()


def run_auto_next(config: Config, dry_run: bool = False):
    """next Incomplete date 1dog execution + monitoring + influence report."""
    from .scheduler import run_day

    db = StateDB(config.campaign.db_path)
    next_day = _get_next_pending(db)
    db.close()

    if not next_day:
        show_success("All days completed! Campaign finished.")
        return False

    progress = _get_progress(StateDB(config.campaign.db_path))
    StateDB(config.campaign.db_path).close()

    console.print()
    console.print(f"  [bold]Autopilot: Executing {next_day}[/bold] "
                  f"({progress['completed']}/{progress['total']} done)")

    # 1. date execution
    run_day(config, next_day, dry_run=dry_run, auto_confirm=True)

    # 2. monitoring 1episode
    if not dry_run:
        _run_monitor_cycle(config)

    # 3. influence report (dry_runthis Not at the time)
    if not dry_run:
        _run_influence_report(config)

    return True


def run_auto_all(config: Config, dry_run: bool = False, delay: int = 30):
    """every Incomplete date sequential execution."""
    console.print()
    console.print("[bold]═══ Autopilot: Full Campaign Run ═══[/bold]")

    db = StateDB(config.campaign.db_path)
    progress = _get_progress(db)
    db.close()

    console.print(f"  Remaining: {progress['pending'] + progress['errors']} days")
    console.print(f"  Delay between days: {delay}s")
    console.print()

    count = 0
    while True:
        has_more = run_auto_next(config, dry_run=dry_run)
        if not has_more:
            break
        count += 1

        # next date check
        db = StateDB(config.campaign.db_path)
        next_day = _get_next_pending(db)
        db.close()

        if next_day:
            show_info(f"Next: {next_day} in {delay}s...")
            time.sleep(delay)

    console.print()
    console.print(f"[bold green]Autopilot complete. {count} days executed.[/bold green]")

    # final report
    _run_influence_report(config)


def run_auto_daemon(config: Config, day_interval: int = 86400, monitor_interval: int = 300):
    """daemon mode — day at intervals next date execution, that between monitoring."""
    console.print()
    console.print("[bold]═══ Autopilot Daemon Mode ═══[/bold]")
    console.print(f"  Day interval: {day_interval}s ({day_interval // 3600}h)")
    console.print(f"  Monitor interval: {monitor_interval}s ({monitor_interval // 60}m)")
    console.print("  Press Ctrl+C to stop")
    console.print()

    last_day_run = 0

    try:
        while True:
            now = time.time()

            # date execution timing
            if now - last_day_run >= day_interval:
                has_more = run_auto_next(config)
                last_day_run = now
                if not has_more:
                    show_success("All days completed. Switching to monitor-only mode.")
                    # monitor exclusive mode
                    from .monitor import run_continuous_monitor
                    from .parser import parse_all_days
                    from .reddit_client import RedditClient

                    client = RedditClient(config)
                    db = StateDB(config.campaign.db_path)
                    plans = parse_all_days(config.campaign.docs_dir)
                    all_qa = []
                    for p in plans.values():
                        all_qa.extend(p.qa_pairs)
                    run_continuous_monitor(
                        client, db, qa_pairs=all_qa,
                        interval=monitor_interval, auto_confirm=True,
                    )
                    return

            # monitoring cycle
            _run_monitor_cycle(config)
            show_info(f"Next monitor check in {monitor_interval}s...")
            time.sleep(monitor_interval)

    except KeyboardInterrupt:
        console.print("\n  [yellow]Daemon stopped.[/yellow]")
        _run_influence_report(config)


def _run_monitor_cycle(config: Config):
    """monitoring 1episode execution."""
    try:
        from .monitor import check_new_comments
        from .parser import parse_all_days
        from .reddit_client import RedditClient

        client = RedditClient(config)
        db = StateDB(config.campaign.db_path)
        plans = parse_all_days(config.campaign.docs_dir)

        all_qa = []
        for p in plans.values():
            all_qa.extend(p.qa_pairs)

        results = check_new_comments(client, db, qa_pairs=all_qa, auto_confirm=True)

        total_new = sum(len(r.get("new_comments", [])) for r in results)
        if total_new > 0:
            show_info(f"Monitor: {total_new} new comments found")
        db.close()
    except Exception as e:
        show_warning(f"Monitor cycle failed: {e}")


def _run_influence_report(config: Config):
    """influence report generation."""
    try:
        from .influence import fetch_influence_data, write_influence_report

        db = StateDB(config.campaign.db_path)
        submissions = db.get_submissions()
        if submissions:
            results = fetch_influence_data(db)
            if results:
                path = write_influence_report(results)
                show_success(f"Influence report: {path}")
        db.close()
    except Exception as e:
        show_warning(f"Influence report failed: {e}")
