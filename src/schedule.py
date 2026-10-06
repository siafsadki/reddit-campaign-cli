"""30Day strategy schedule — karma building first of all, gradual activity enlargement.

existing markdown file dependence without programming in a way strategy management.
Phase 1: karma building (app mention without)
Phase 2: karma + light sow seeds
Phase 3: sow seeds + first post
Phase 4: authentic campaign

campaign.tomlthis If there is config based, If there is no basic hard coding subreddit use.
DBto custom schedule If there is automatic created than schedule first of all apply.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class Phase(Enum):
    KARMA_BUILD = "karma_build"       # pure karma building
    LIGHT_SEED = "light_seed"         # karma + light sow seeds
    SEED_AND_POST = "seed_and_post"   # sow seeds + post
    FULL_CAMPAIGN = "full_campaign"   # entire campaign


class TaskType(Enum):
    KARMA_COMMENT = "karma_comment"   # app military officer help comment
    SEED_COMMENT = "seed_comment"     # natural app mention comment
    POST = "post"                     # subreddit post
    MONITOR = "monitor"              # existing post monitoring
    REST = "rest"                     # rest
    REVIEW = "review"                # result analyze


@dataclass
class DayTask:
    task_type: TaskType
    subreddits: list[str] = field(default_factory=list)
    search_keywords: list[str] = field(default_factory=list)
    max_comments: int = 0
    post_subreddit: str = ""
    notes: str = ""


@dataclass
class DaySchedule:
    day: int
    phase: Phase
    tasks: list[DayTask] = field(default_factory=list)
    description: str = ""


# karma For buildings subreddit + keyword
KARMA_SUBS = {
    "commandline": ["terminal workflow", "cli tools", "shell productivity", "zsh fish bash"],
    "programming": ["developer tools", "code editor", "productivity tips", "IDE setup"],
    "webdev": ["frontend tools", "developer experience", "web tooling"],
    "linux": ["terminal emulator", "desktop linux", "window manager"],
    "vim": ["terminal multiplexer", "vim workflow", "neovim setup"],
    "neovim": ["terminal integration", "plugin", "lua config"],
    "rust": ["tauri app", "cross-platform", "wasm"],
    "devops": ["monitoring", "deployment tools", "CI/CD"],
    "python": ["cli framework", "automation", "scripting"],
    "golang": ["developer tools", "cli apps"],
    "opensource": ["new project", "side project", "open source tools"],
    "selfhosted": ["self-hosted tools", "server dashboard"],
}

# sow seeds target (app and relevant subreddit)
SEED_SUBS = {
    "commandline": ["terminal multiplexer", "terminal tabs", "tmux alternative"],
    "webdev": ["developer terminal", "web dev tools", "terminal setup"],
    "programming": ["terminal tools", "developer workflow", "multi-language IDE"],
    "rust": ["tauri desktop app", "rust gui", "cross-platform"],
    "SideProject": ["weekend project", "indie dev", "show my project"],
    "macapps": ["mac terminal", "mac developer tools"],
    "coolgithubprojects": ["github project", "open source tool"],
    "opensource": ["terminal emulator", "developer tools"],
}

# post subreddit order (gradually)
POST_ORDER = [
    # Phase 3: small From the serve
    {"sub": "SideProject", "title_hint": "Show: terminal app share"},
    {"sub": "coolgithubprojects", "title_hint": "GitHub project share"},
    # Phase 4: middle scale
    {"sub": "commandline", "title_hint": "CLI Workflow elevation"},
    {"sub": "rust", "title_hint": "Tauri based terminal"},
    {"sub": "macapps", "title_hint": "Mac terminal app"},
    {"sub": "webdev", "title_hint": "developer terminal equipment"},
    {"sub": "programming", "title_hint": "development equipment introduction"},
    {"sub": "linux", "title_hint": "cross platform terminal"},
    {"sub": "opensource", "title_hint": "open source terminal"},
    {"sub": "selfhosted", "title_hint": "self host terminal"},
    {"sub": "devops", "title_hint": "DevOps terminal equipment"},
    {"sub": "neovim", "title_hint": "Neovim integration terminal"},
    {"sub": "vim", "title_hint": "Vim Workflow"},
]


# campaign entire date order (share constant)
DAY_ORDER = [
    "prep-d3", "prep-d2", "prep-d1",
    *[f"day-{i:02d}" for i in range(1, 31)],
]


def build_schedule() -> list[DaySchedule]:
    """30Day entire schedule generation."""
    schedule = []

    # ═══ Phase 1: Days 1-7 — pure karma building ═══
    karma_subs_list = list(KARMA_SUBS.keys())

    for day in range(1, 8):
        if day == 7:
            # Day 7: rest + review
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.KARMA_BUILD,
                tasks=[DayTask(task_type=TaskType.REVIEW, notes="1parking karma building result analyze")],
                description="1parking review — karma current situation check",
            ))
        else:
            # day 2-3dog On the subreddit help comment
            subs_for_day = karma_subs_list[(day - 1) * 2: (day - 1) * 2 + 3]
            if not subs_for_day:
                subs_for_day = karma_subs_list[:2]

            tasks = []
            for sub in subs_for_day:
                keywords = KARMA_SUBS.get(sub, ["developer tools"])
                tasks.append(DayTask(
                    task_type=TaskType.KARMA_COMMENT,
                    subreddits=[sub],
                    search_keywords=keywords,
                    max_comments=2,
                    notes=f"r/{sub}at help comment (app mention prohibition)",
                ))
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.KARMA_BUILD,
                tasks=tasks,
                description=f"karma building: {', '.join(subs_for_day)}",
            ))

    # ═══ Phase 2: Days 8-14 — karma + light sow seeds ═══
    seed_subs_list = list(SEED_SUBS.keys())

    for day in range(8, 15):
        if day == 13:
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.LIGHT_SEED,
                tasks=[DayTask(task_type=TaskType.REST, notes="rest")],
                description="rest day",
            ))
        elif day == 14:
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.LIGHT_SEED,
                tasks=[
                    DayTask(task_type=TaskType.REVIEW, notes="2parking result analyze"),
                    DayTask(task_type=TaskType.MONITOR, notes="existing activity reaction check"),
                ],
                description="2parking review",
            ))
        else:
            tasks = []
            # karma building 1-2dog
            karma_idx = (day - 8) % len(karma_subs_list)
            karma_sub = karma_subs_list[karma_idx]
            tasks.append(DayTask(
                task_type=TaskType.KARMA_COMMENT,
                subreddits=[karma_sub],
                search_keywords=KARMA_SUBS[karma_sub],
                max_comments=2,
                notes=f"karma: r/{karma_sub}",
            ))

            # sow seeds 1dog (naturally)
            seed_idx = (day - 8) % len(seed_subs_list)
            seed_sub = seed_subs_list[seed_idx]
            tasks.append(DayTask(
                task_type=TaskType.SEED_COMMENT,
                subreddits=[seed_sub],
                search_keywords=SEED_SUBS[seed_sub],
                max_comments=1,
                notes=f"sow seeds: r/{seed_sub} (natural mention)",
            ))

            schedule.append(DaySchedule(
                day=day,
                phase=Phase.LIGHT_SEED,
                tasks=tasks,
                description=f"karma({karma_sub}) + sow seeds({seed_sub})",
            ))

    # ═══ Phase 3: Days 15-21 — sow seeds + first post ═══
    post_idx = 0

    for day in range(15, 22):
        if day == 20:
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.SEED_AND_POST,
                tasks=[DayTask(task_type=TaskType.REST, notes="rest")],
                description="rest day",
            ))
        elif day == 21:
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.SEED_AND_POST,
                tasks=[
                    DayTask(task_type=TaskType.REVIEW, notes="3parking result analyze + post reaction"),
                    DayTask(task_type=TaskType.MONITOR, notes="post monitoring"),
                ],
                description="3parking review",
            ))
        elif day in (16, 19):
            # post me — small From the serve
            tasks = []
            if post_idx < len(POST_ORDER):
                post_info = POST_ORDER[post_idx]
                tasks.append(DayTask(
                    task_type=TaskType.POST,
                    post_subreddit=post_info["sub"],
                    notes=post_info["title_hint"],
                ))
                post_idx += 1

            # Sowing seeds parallelism
            seed_idx = (day - 15) % len(seed_subs_list)
            seed_sub = seed_subs_list[seed_idx]
            tasks.append(DayTask(
                task_type=TaskType.SEED_COMMENT,
                subreddits=[seed_sub],
                search_keywords=SEED_SUBS[seed_sub],
                max_comments=2,
                notes=f"sow seeds: r/{seed_sub}",
            ))

            schedule.append(DaySchedule(
                day=day,
                phase=Phase.SEED_AND_POST,
                tasks=tasks,
                description=f"post({post_info['sub']}) + sow seeds",
            ))
        else:
            # sow seeds + karma
            tasks = []
            seed_idx = (day - 15) % len(seed_subs_list)
            seed_sub = seed_subs_list[seed_idx]
            tasks.append(DayTask(
                task_type=TaskType.SEED_COMMENT,
                subreddits=[seed_sub],
                search_keywords=SEED_SUBS[seed_sub],
                max_comments=2,
            ))
            tasks.append(DayTask(
                task_type=TaskType.MONITOR,
                notes="existing post reaction check",
            ))
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.SEED_AND_POST,
                tasks=tasks,
                description=f"sow seeds({seed_sub}) + monitoring",
            ))

    # ═══ Phase 4: Days 22-30 — authentic campaign ═══
    for day in range(22, 31):
        if day == 27:
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.FULL_CAMPAIGN,
                tasks=[DayTask(task_type=TaskType.REST, notes="rest")],
                description="rest day",
            ))
        elif day == 28:
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.FULL_CAMPAIGN,
                tasks=[
                    DayTask(task_type=TaskType.REVIEW, notes="4parking + entire result analyze"),
                    DayTask(task_type=TaskType.MONITOR, notes="every post monitoring"),
                ],
                description="4parking review",
            ))
        elif day == 30:
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.FULL_CAMPAIGN,
                tasks=[
                    DayTask(task_type=TaskType.REVIEW, notes="final result analyze + ROI report"),
                    DayTask(task_type=TaskType.MONITOR, notes="entire post final monitoring"),
                ],
                description="final review + ROI",
            ))
        elif day in (22, 24, 26, 29):
            # post me
            tasks = []
            if post_idx < len(POST_ORDER):
                post_info = POST_ORDER[post_idx]
                tasks.append(DayTask(
                    task_type=TaskType.POST,
                    post_subreddit=post_info["sub"],
                    notes=post_info["title_hint"],
                ))
                post_idx += 1

            # sow seeds 2dog
            for i in range(2):
                s_idx = ((day - 22) * 2 + i) % len(seed_subs_list)
                s_sub = seed_subs_list[s_idx]
                tasks.append(DayTask(
                    task_type=TaskType.SEED_COMMENT,
                    subreddits=[s_sub],
                    search_keywords=SEED_SUBS[s_sub],
                    max_comments=2,
                ))

            schedule.append(DaySchedule(
                day=day,
                phase=Phase.FULL_CAMPAIGN,
                tasks=tasks,
                description=f"post + sow seeds",
            ))
        else:
            # comment management + sow seeds
            tasks = []
            tasks.append(DayTask(
                task_type=TaskType.MONITOR,
                notes="post comment response",
            ))
            s_idx = (day - 22) % len(seed_subs_list)
            s_sub = seed_subs_list[s_idx]
            tasks.append(DayTask(
                task_type=TaskType.SEED_COMMENT,
                subreddits=[s_sub],
                search_keywords=SEED_SUBS[s_sub],
                max_comments=2,
            ))
            tasks.append(DayTask(
                task_type=TaskType.KARMA_COMMENT,
                subreddits=[karma_subs_list[(day - 22) % len(karma_subs_list)]],
                search_keywords=KARMA_SUBS[karma_subs_list[(day - 22) % len(karma_subs_list)]],
                max_comments=1,
            ))
            schedule.append(DaySchedule(
                day=day,
                phase=Phase.FULL_CAMPAIGN,
                tasks=tasks,
                description=f"monitoring + sow seeds + karma",
            ))

    return schedule


def build_schedule_from_config(config) -> list[DaySchedule]:
    """CampaignConfig based 30Day schedule generation."""
    schedule = []

    karma_subs = {st.sub: st.keywords for st in config.karma_subs} if config.karma_subs else KARMA_SUBS
    seed_subs = {st.sub: st.keywords for st in config.seed_subs} if config.seed_subs else SEED_SUBS
    post_order = (
        [{"sub": pt.sub, "title_hint": pt.title_hint} for pt in config.post_subs]
        if config.post_subs else POST_ORDER
    )

    karma_subs_list = list(karma_subs.keys())
    seed_subs_list = list(seed_subs.keys())

    # Phase 1: Days 1-7 — karma building
    for day in range(1, 8):
        if day == 7:
            schedule.append(DaySchedule(
                day=day, phase=Phase.KARMA_BUILD,
                tasks=[DayTask(task_type=TaskType.REVIEW, notes="1parking karma building result analyze")],
                description="1parking review — karma current situation check",
            ))
        else:
            subs_for_day = karma_subs_list[(day - 1) * 2: (day - 1) * 2 + 3]
            if not subs_for_day:
                subs_for_day = karma_subs_list[:2]
            tasks = []
            for sub in subs_for_day:
                keywords = karma_subs.get(sub, ["developer tools"])
                if isinstance(keywords, list):
                    kw = keywords
                else:
                    kw = [keywords]
                tasks.append(DayTask(
                    task_type=TaskType.KARMA_COMMENT,
                    subreddits=[sub], search_keywords=kw, max_comments=2,
                    notes=f"r/{sub}at help comment (app mention prohibition)",
                ))
            schedule.append(DaySchedule(
                day=day, phase=Phase.KARMA_BUILD, tasks=tasks,
                description=f"karma building: {', '.join(subs_for_day)}",
            ))

    # Phase 2: Days 8-14 — karma + sow seeds
    for day in range(8, 15):
        if day == 13:
            schedule.append(DaySchedule(
                day=day, phase=Phase.LIGHT_SEED,
                tasks=[DayTask(task_type=TaskType.REST, notes="rest")],
                description="rest day",
            ))
        elif day == 14:
            schedule.append(DaySchedule(
                day=day, phase=Phase.LIGHT_SEED,
                tasks=[
                    DayTask(task_type=TaskType.REVIEW, notes="2parking result analyze"),
                    DayTask(task_type=TaskType.MONITOR, notes="existing activity reaction check"),
                ],
                description="2parking review",
            ))
        else:
            tasks = []
            karma_idx = (day - 8) % len(karma_subs_list)
            karma_sub = karma_subs_list[karma_idx]
            tasks.append(DayTask(
                task_type=TaskType.KARMA_COMMENT,
                subreddits=[karma_sub],
                search_keywords=karma_subs.get(karma_sub, ["developer tools"]),
                max_comments=2,
                notes=f"karma: r/{karma_sub}",
            ))
            seed_idx = (day - 8) % len(seed_subs_list)
            seed_sub = seed_subs_list[seed_idx]
            tasks.append(DayTask(
                task_type=TaskType.SEED_COMMENT,
                subreddits=[seed_sub],
                search_keywords=seed_subs.get(seed_sub, ["tool"]),
                max_comments=1,
                notes=f"sow seeds: r/{seed_sub} (natural mention)",
            ))
            schedule.append(DaySchedule(
                day=day, phase=Phase.LIGHT_SEED, tasks=tasks,
                description=f"karma({karma_sub}) + sow seeds({seed_sub})",
            ))

    # Phase 3: Days 15-21 — sow seeds + post
    post_idx = 0
    for day in range(15, 22):
        if day == 20:
            schedule.append(DaySchedule(
                day=day, phase=Phase.SEED_AND_POST,
                tasks=[DayTask(task_type=TaskType.REST, notes="rest")],
                description="rest day",
            ))
        elif day == 21:
            schedule.append(DaySchedule(
                day=day, phase=Phase.SEED_AND_POST,
                tasks=[
                    DayTask(task_type=TaskType.REVIEW, notes="3parking result analyze + post reaction"),
                    DayTask(task_type=TaskType.MONITOR, notes="post monitoring"),
                ],
                description="3parking review",
            ))
        elif day in (16, 19):
            tasks = []
            if post_idx < len(post_order):
                post_info = post_order[post_idx]
                tasks.append(DayTask(
                    task_type=TaskType.POST,
                    post_subreddit=post_info["sub"],
                    notes=post_info.get("title_hint", ""),
                ))
                post_idx += 1
            seed_idx = (day - 15) % len(seed_subs_list)
            seed_sub = seed_subs_list[seed_idx]
            tasks.append(DayTask(
                task_type=TaskType.SEED_COMMENT,
                subreddits=[seed_sub],
                search_keywords=seed_subs.get(seed_sub, ["tool"]),
                max_comments=2,
                notes=f"sow seeds: r/{seed_sub}",
            ))
            schedule.append(DaySchedule(
                day=day, phase=Phase.SEED_AND_POST, tasks=tasks,
                description=f"post({post_order[post_idx-1]['sub'] if post_idx > 0 else '?'}) + sow seeds",
            ))
        else:
            tasks = []
            seed_idx = (day - 15) % len(seed_subs_list)
            seed_sub = seed_subs_list[seed_idx]
            tasks.append(DayTask(
                task_type=TaskType.SEED_COMMENT,
                subreddits=[seed_sub],
                search_keywords=seed_subs.get(seed_sub, ["tool"]),
                max_comments=2,
            ))
            tasks.append(DayTask(
                task_type=TaskType.MONITOR, notes="existing post reaction check",
            ))
            schedule.append(DaySchedule(
                day=day, phase=Phase.SEED_AND_POST, tasks=tasks,
                description=f"sow seeds({seed_sub}) + monitoring",
            ))

    # Phase 4: Days 22-30 — authentic campaign
    for day in range(22, 31):
        if day == 27:
            schedule.append(DaySchedule(
                day=day, phase=Phase.FULL_CAMPAIGN,
                tasks=[DayTask(task_type=TaskType.REST, notes="rest")],
                description="rest day",
            ))
        elif day == 28:
            schedule.append(DaySchedule(
                day=day, phase=Phase.FULL_CAMPAIGN,
                tasks=[
                    DayTask(task_type=TaskType.REVIEW, notes="4parking + entire result analyze"),
                    DayTask(task_type=TaskType.MONITOR, notes="every post monitoring"),
                ],
                description="4parking review",
            ))
        elif day == 30:
            schedule.append(DaySchedule(
                day=day, phase=Phase.FULL_CAMPAIGN,
                tasks=[
                    DayTask(task_type=TaskType.REVIEW, notes="final result analyze + ROI report"),
                    DayTask(task_type=TaskType.MONITOR, notes="entire post final monitoring"),
                ],
                description="final review + ROI",
            ))
        elif day in (22, 24, 26, 29):
            tasks = []
            if post_idx < len(post_order):
                post_info = post_order[post_idx]
                tasks.append(DayTask(
                    task_type=TaskType.POST,
                    post_subreddit=post_info["sub"],
                    notes=post_info.get("title_hint", ""),
                ))
                post_idx += 1
            for i in range(2):
                s_idx = ((day - 22) * 2 + i) % len(seed_subs_list)
                s_sub = seed_subs_list[s_idx]
                tasks.append(DayTask(
                    task_type=TaskType.SEED_COMMENT,
                    subreddits=[s_sub],
                    search_keywords=seed_subs.get(s_sub, ["tool"]),
                    max_comments=2,
                ))
            schedule.append(DaySchedule(
                day=day, phase=Phase.FULL_CAMPAIGN, tasks=tasks,
                description="post + sow seeds",
            ))
        else:
            tasks = []
            tasks.append(DayTask(
                task_type=TaskType.MONITOR, notes="post comment response",
            ))
            s_idx = (day - 22) % len(seed_subs_list)
            s_sub = seed_subs_list[s_idx]
            tasks.append(DayTask(
                task_type=TaskType.SEED_COMMENT,
                subreddits=[s_sub],
                search_keywords=seed_subs.get(s_sub, ["tool"]),
                max_comments=2,
            ))
            tasks.append(DayTask(
                task_type=TaskType.KARMA_COMMENT,
                subreddits=[karma_subs_list[(day - 22) % len(karma_subs_list)]],
                search_keywords=karma_subs.get(
                    karma_subs_list[(day - 22) % len(karma_subs_list)],
                    ["developer tools"]
                ),
                max_comments=1,
            ))
            schedule.append(DaySchedule(
                day=day, phase=Phase.FULL_CAMPAIGN, tasks=tasks,
                description="monitoring + sow seeds + karma",
            ))

    return schedule


def get_day_schedule(day: int, config=None) -> DaySchedule | None:
    """specific of the day schedule return."""
    sched = build_schedule_from_config(config) if config else build_schedule()
    for s in sched:
        if s.day == day:
            return s
    return None


def format_schedule_overview(config=None) -> str:
    """30Day entire schedule outline."""
    schedule = build_schedule_from_config(config) if config else build_schedule()
    lines = ["═══ 30-Day Campaign Schedule ═══", ""]

    if config:
        lines.append(f"  Product: {config.product_name}")
        lines.append(f"  URL: {config.product_url}")
        lines.append("")

    current_phase = None
    for s in schedule:
        if s.phase != current_phase:
            current_phase = s.phase
            phase_names = {
                Phase.KARMA_BUILD: "Phase 1: karma building (app mention without)",
                Phase.LIGHT_SEED: "Phase 2: karma + light sow seeds",
                Phase.SEED_AND_POST: "Phase 3: sow seeds + first post",
                Phase.FULL_CAMPAIGN: "Phase 4: authentic campaign",
            }
            lines.append(f"\n── {phase_names[current_phase]} ──")

        task_icons = {
            TaskType.KARMA_COMMENT: "K",
            TaskType.SEED_COMMENT: "S",
            TaskType.POST: "P",
            TaskType.MONITOR: "M",
            TaskType.REST: "R",
            TaskType.REVIEW: "V",
        }
        task_types = [t.task_type for t in s.tasks]
        icons = " ".join(task_icons.get(t, "?") for t in task_types)
        lines.append(f"  Day {s.day:2d} | {icons} | {s.description}")

    return "\n".join(lines)


# ═══ custom schedule: DBto saved user edit schedule ═══

def _task_to_dict(task: DayTask) -> dict:
    return {
        "type": task.task_type.value,
        "subreddits": task.subreddits,
        "keywords": task.search_keywords,
        "max_comments": task.max_comments,
        "post_subreddit": task.post_subreddit,
        "notes": task.notes,
    }


def _dict_to_task(d: dict) -> DayTask:
    type_val = d.get("type") or d.get("task_type")
    keywords = d.get("keywords") or d.get("search_keywords", [])
    return DayTask(
        task_type=TaskType(type_val),
        subreddits=d.get("subreddits", []),
        search_keywords=keywords,
        max_comments=d.get("max_comments", 0),
        post_subreddit=d.get("post_subreddit", ""),
        notes=d.get("notes", ""),
    )


def day_schedule_to_dict(s: DaySchedule) -> dict:
    return {
        "day": s.day,
        "phase": s.phase.value,
        "description": s.description,
        "tasks": [_task_to_dict(t) for t in s.tasks],
    }


def dict_to_day_schedule(d: dict) -> DaySchedule:
    return DaySchedule(
        day=d["day"],
        phase=Phase(d["phase"]),
        tasks=[_dict_to_task(t) for t in d.get("tasks", [])],
        description=d.get("description", ""),
    )


def save_schedule_to_db(db, schedule: list[DaySchedule]):
    """entire schedule DBto save."""
    for s in schedule:
        tasks_json = json.dumps([_task_to_dict(t) for t in s.tasks], ensure_ascii=False)
        db.save_custom_schedule(s.day, s.phase.value, s.description, tasks_json)


def load_schedule_from_db(db) -> list[DaySchedule]:
    """DBat custom schedule load."""
    rows = db.get_all_custom_schedules()
    result = []
    for row in rows:
        tasks = json.loads(row["tasks_json"]) if row.get("tasks_json") else []
        result.append(DaySchedule(
            day=row["day"],
            phase=Phase(row["phase"]),
            tasks=[_dict_to_task(t) for t in tasks],
            description=row.get("description", ""),
        ))
    return result


def get_effective_schedule(config=None, db=None) -> list[DaySchedule]:
    """final schedule: DB custom > config based > basic.

    DBto saved The day is custom use, no The day is automatic generation.
    """
    # automatic generation schedule
    if config:
        auto = build_schedule_from_config(config)
    else:
        auto = build_schedule()

    if not db:
        return auto

    # DB custom schedule load
    custom_rows = db.get_all_custom_schedules()
    if not custom_rows:
        return auto

    custom_map = {}
    for row in custom_rows:
        tasks = json.loads(row["tasks_json"]) if row.get("tasks_json") else []
        custom_map[row["day"]] = DaySchedule(
            day=row["day"],
            phase=Phase(row["phase"]),
            tasks=[_dict_to_task(t) for t in tasks],
            description=row.get("description", ""),
        )

    # synthesis: Custom If there is custom, If there is no automatic
    result = []
    for s in auto:
        if s.day in custom_map:
            result.append(custom_map[s.day])
        else:
            result.append(s)
    return result
