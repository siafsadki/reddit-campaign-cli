"""post timing Optimization.

By subreddit optimal post hour + day of the week judgment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum


class TimingGrade(Enum):
    OPTIMAL = "optimal"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    AVOID = "avoid"


@dataclass
class TimingAdvice:
    grade: TimingGrade
    reason: str
    next_optimal: datetime | None = None
    wait_seconds: int = 0


# EST = UTC-5 (USA eastern)
EST_OFFSET = timedelta(hours=-5)

# By subreddit optimal hour (EST standard, hour range)
# (start_hour, end_hour, weekday_only)
PEAK_WINDOWS: dict[str, list[tuple[int, int, bool]]] = {
    "commandline": [(9, 12, True), (18, 21, True)],
    "programming": [(9, 11, True)],
    "rust": [(10, 13, True)],
    "ClaudeAI": [(9, 12, True), (14, 17, True)],
    "webdev": [(9, 12, True)],
    "SideProject": [(9, 12, True), (17, 20, True)],
    "macapps": [(10, 13, True)],
    "tauri": [(10, 13, True)],
    "neovim": [(10, 13, True), (19, 22, True)],
    "devops": [(9, 12, True)],
    "coolgithubprojects": [(9, 12, True)],
    "selfhosted": [(9, 12, True), (19, 22, True)],
}

# basic (registration not done serve)
DEFAULT_PEAK = [(9, 12, True)]

# avoid will do slot
AVOID_HOURS = list(range(0, 6))  # 0-6 AM EST

# avoid will do day of the week (friday afternoon, Saturday)
AVOID_DAYS = {
    4: [(14, 24)],  # friday afternoon
    5: [(0, 24)],   # Saturday entire
}


def check_timing(subreddit: str, now: datetime | None = None) -> TimingAdvice:
    """today time In the post Is it suitable? judgment."""
    if now is None:
        now = datetime.now(timezone.utc)

    # ESTas conversion
    est_now = now + EST_OFFSET
    hour = est_now.hour
    weekday = est_now.weekday()  # 0=month ~ 6=Day

    sub = subreddit.replace("r/", "").lower()

    # avoid will do hour
    if hour in AVOID_HOURS:
        next_opt = _next_optimal_time(sub, est_now)
        return TimingAdvice(
            grade=TimingGrade.AVOID,
            reason=f"dawn slot (EST {hour}city) — traffic lowest",
            next_optimal=next_opt,
            wait_seconds=_seconds_until(est_now, next_opt) if next_opt else 0,
        )

    # avoid will do day of the week
    if weekday in AVOID_DAYS:
        for start, end in AVOID_DAYS[weekday]:
            if start <= hour < end:
                next_opt = _next_optimal_time(sub, est_now)
                day_name = ["month", "fury", "number", "neck", "gold", "saturday", "Day"][weekday]
                return TimingAdvice(
                    grade=TimingGrade.POOR,
                    reason=f"{day_name}day of the week — weekend traffic low tone",
                    next_optimal=next_opt,
                    wait_seconds=_seconds_until(est_now, next_opt) if next_opt else 0,
                )

    # By subreddit optimal hour
    windows = PEAK_WINDOWS.get(sub, DEFAULT_PEAK)
    for start, end, weekday_only in windows:
        if weekday_only and weekday >= 5:
            continue
        if start <= hour < end:
            return TimingAdvice(
                grade=TimingGrade.OPTIMAL,
                reason=f"optimal slot (EST {hour}city, {sub})",
            )

    # work If it's time GOOD
    if 7 <= hour <= 22 and weekday < 5:
        return TimingAdvice(
            grade=TimingGrade.GOOD,
            reason=f"work slot (EST {hour}city)",
        )

    # that except
    if 7 <= hour <= 22:
        return TimingAdvice(
            grade=TimingGrade.ACCEPTABLE,
            reason=f"weekend afternoon hour (EST {hour}city)",
        )

    next_opt = _next_optimal_time(sub, est_now)
    return TimingAdvice(
        grade=TimingGrade.POOR,
        reason=f"inactivity slot (EST {hour}city)",
        next_optimal=next_opt,
        wait_seconds=_seconds_until(est_now, next_opt) if next_opt else 0,
    )


def _next_optimal_time(sub: str, est_now: datetime) -> datetime | None:
    """next optimal hour calculate."""
    windows = PEAK_WINDOWS.get(sub, DEFAULT_PEAK)
    hour = est_now.hour
    weekday = est_now.weekday()

    # today remainder windows
    for start, end, weekday_only in windows:
        if weekday_only and weekday >= 5:
            continue
        if hour < start:
            return est_now.replace(hour=start, minute=0, second=0, microsecond=0)

    # next weekdays first windows
    days_ahead = 1
    while days_ahead <= 3:
        next_day = est_now + timedelta(days=days_ahead)
        next_weekday = next_day.weekday()
        if next_weekday < 5:  # weekdays
            first_start = windows[0][0] if windows else 9
            return next_day.replace(hour=first_start, minute=0, second=0, microsecond=0)
        days_ahead += 1

    return None


def _seconds_until(now: datetime, target: datetime) -> int:
    delta = target - now
    return max(0, int(delta.total_seconds()))
