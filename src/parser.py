"""markdown → DayPlan data farthing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DayType(Enum):
    PREP = "prep"
    POST = "post"
    COMMENT_MGMT = "comment_mgmt"
    REST = "rest"
    REVIEW = "review"


@dataclass
class PostContent:
    title: str
    body: str
    placeholders: list[str] = field(default_factory=list)


@dataclass
class QAPair:
    question: str
    answer: str


@dataclass
class SeedingComment:
    subreddit: str
    context: str  # example situation
    body: str


@dataclass
class DayPlan:
    day_id: str
    day_type: DayType
    subreddit: str | None = None
    post: PostContent | None = None
    qa_pairs: list[QAPair] = field(default_factory=list)
    seeding_comments: list[SeedingComment] = field(default_factory=list)
    previous_days_to_monitor: list[str] = field(default_factory=list)
    raw_content: str = ""


# day_id -> day_type mapping
POST_DAYS = {1, 3, 5, 8, 10, 12, 15, 17, 19, 22, 24, 26, 29}
COMMENT_MGMT_DAYS = {2, 4, 9, 11, 16, 18, 23, 25}
REST_DAYS = {6, 13, 20, 27}
REVIEW_DAYS = {7, 14, 21, 28, 30}


def _classify_day(day_id: str) -> DayType:
    if day_id.startswith("prep"):
        return DayType.PREP

    m = re.match(r"day-(\d+)", day_id)
    if not m:
        return DayType.REST

    num = int(m.group(1))
    if num in POST_DAYS:
        return DayType.POST
    if num in COMMENT_MGMT_DAYS:
        return DayType.COMMENT_MGMT
    if num in REVIEW_DAYS:
        return DayType.REVIEW
    return DayType.REST


def _extract_subreddit(content: str) -> str | None:
    # basic information at the table subreddit extraction
    m = re.search(r"\|\s*subreddit\s*\|\s*(r/\w+)", content)
    return m.group(1) if m else None


def _extract_post(content: str) -> PostContent | None:
    # "## post" In section title + text extraction
    post_section = re.search(r"## post\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if not post_section:
        return None

    section = post_section.group(1)

    # title extraction
    title_match = re.search(r'\*\*title:\*\*\s*"([^"]+)"', section)
    if not title_match:
        title_match = re.search(r'\*\*title:\*\*\s*(.+)', section)
    if not title_match:
        return None
    title = title_match.group(1).strip().strip('"')

    # text extraction (```as wrapped block)
    body_match = re.search(r'\*\*text:\*\*\s*\n```\n(.*?)```', section, re.DOTALL)
    if not body_match:
        return None

    body = body_match.group(1).strip()

    # placeholder detection
    placeholders = re.findall(r'\[([^\]]*?(?:function|correction|based|today|number|reason|quotation)[^\]]*?)\]', body)
    post = PostContent(title=title, body=body)
    if placeholders:
        post.placeholders = placeholders
    return post


def _extract_qa_pairs(content: str) -> list[QAPair]:
    pairs = []
    # "## expectation question + ready answer" section Find
    qa_section = re.search(
        r"## expectation question.*?\n(.*?)(?=\n## (?!#)|\Z)", content, re.DOTALL
    )
    if not qa_section:
        return pairs

    section = qa_section.group(1)

    # ### "question" by pattern each Q&A extraction
    questions = re.finditer(
        r'### "([^"]+)"\s*\n```\n(.*?)```', section, re.DOTALL
    )
    for m in questions:
        pairs.append(QAPair(question=m.group(1).strip(), answer=m.group(2).strip()))

    return pairs


def _extract_seeding_comments(content: str, day_type: DayType) -> list[SeedingComment]:
    comments = []

    if day_type == DayType.PREP:
        # PREP file: ### N. r/subreddit comment Ndog pattern
        sections = re.finditer(
            r"### \d+\.\s+(r/\w+)\s+comment.*?\n(.*?)(?=### \d+\.|## |\Z)",
            content,
            re.DOTALL,
        )
        for section in sections:
            subreddit = section.group(1)
            section_text = section.group(2)
            # ```as wrapped comment extraction
            comment_blocks = re.finditer(
                r"\*\*example situation:\*\*\s*(.*?)\n```\n(.*?)```",
                section_text,
                re.DOTALL,
            )
            for cb in comment_blocks:
                comments.append(
                    SeedingComment(
                        subreddit=subreddit,
                        context=cb.group(1).strip(),
                        body=cb.group(2).strip(),
                    )
                )
    else:
        # POST/COMMENT_MGMT: "## comment activity" In section extraction
        comment_section = re.search(
            r"## (?:comment activity|different serve comment activity).*?\n(.*?)(?=\n## (?!#)|\Z)",
            content,
            re.DOTALL,
        )
        if not comment_section:
            # "### 2. different serve comment activity" pattern too trial
            comment_section = re.search(
                r"### \d+\.\s*different serve comment activity.*?\n(.*?)(?=### \d+\.|## |\Z)",
                content,
                re.DOTALL,
            )
        if comment_section:
            section_text = comment_section.group(1)
            # r/subreddit by pattern comment target extraction
            targets = re.finditer(
                r"(r/\w+).*?(?:comment|at)",
                section_text,
            )
            for t in targets:
                subreddit = t.group(1)
                comments.append(
                    SeedingComment(subreddit=subreddit, context="", body="")
                )

            # ```as wrapped comment template extraction
            comment_blocks = re.finditer(
                r"(r/\w+)\s*[—\-–]\s*(.*?)\n```\n(.*?)```",
                section_text,
                re.DOTALL,
            )
            for cb in comment_blocks:
                # already added bean comment shift
                subreddit = cb.group(1)
                for i, c in enumerate(comments):
                    if c.subreddit == subreddit and not c.body:
                        comments[i] = SeedingComment(
                            subreddit=subreddit,
                            context=cb.group(2).strip(),
                            body=cb.group(3).strip(),
                        )
                        break
                else:
                    comments.append(
                        SeedingComment(
                            subreddit=subreddit,
                            context=cb.group(2).strip(),
                            body=cb.group(3).strip(),
                        )
                    )

    return comments


def _extract_monitor_targets(content: str) -> list[str]:
    """to monitor before post day_id extraction."""
    targets = []
    # "Day N post" pattern Find
    for m in re.finditer(r"Day\s+(\d+)\s+(?:post|comment)", content):
        day_num = int(m.group(1))
        targets.append(f"day-{day_num:02d}")
    return list(set(targets))


def parse_day_file(filepath: Path) -> DayPlan:
    """markdown file one DayPlanby farthing."""
    content = filepath.read_text(encoding="utf-8")
    stem = filepath.stem  # "day-01", "prep-d3"

    # day_id normalization
    day_id = stem

    day_type = _classify_day(day_id)

    plan = DayPlan(
        day_id=day_id,
        day_type=day_type,
        raw_content=content,
    )

    plan.subreddit = _extract_subreddit(content)
    plan.post = _extract_post(content)
    plan.qa_pairs = _extract_qa_pairs(content)
    plan.seeding_comments = _extract_seeding_comments(content, day_type)
    plan.previous_days_to_monitor = _extract_monitor_targets(content)

    return plan


def parse_all_days(docs_dir: str = "docs/reddit-30day") -> dict[str, DayPlan]:
    """every markdown file By parsing day_id → DayPlan mapping return."""
    plans = {}
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        return plans

    for f in sorted(docs_path.glob("*.md")):
        if f.name == "README.md":
            continue
        plan = parse_day_file(f)
        plans[plan.day_id] = plan

    return plans


def resolve_day_id(day_input: str) -> str:
    """user input day_idas conversion. '1' -> 'day-01', 'prep-d3' -> 'prep-d3'."""
    day_input = day_input.strip().lower()
    if day_input.startswith("prep"):
        return day_input
    # numbers only entered case
    try:
        num = int(day_input)
        return f"day-{num:02d}"
    except ValueError:
        return day_input
