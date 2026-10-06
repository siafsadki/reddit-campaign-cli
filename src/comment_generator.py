"""Kimi CLI based comment automatic generation + verification.

kimi --quiet as comment/title/text generation.
existing comments read in context fit natural Write a comment.
write after kimigo page in text comment existence Whether verification.
"""

from __future__ import annotations

import random
import subprocess

from .campaign_config import CampaignConfig


def _ask_kimi(prompt: str, timeout: int = 60) -> str:
    """kimi CLIto prompt send Results only Received."""
    try:
        result = subprocess.run(
            ["kimi", "--quiet"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if output:
            return output
    except subprocess.TimeoutExpired:
        pass
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return ""


def _fallback_comment(keywords: list[str]) -> str:
    """kimi failure city simple fallback."""
    fallbacks = [
        "yeah this is pretty much what i do too",
        "nice setup, been looking into something similar",
        "solid approach, thanks for sharing",
        "been doing something similar lately, works well",
    ]
    return random.choice(fallbacks)


# prompt exposure detect keyword
_PROMPT_LEAK_PATTERNS = [
    "i understand this is",
    "i see the comment",
    "the user wants me",
    "reddit marketing",
    "campaign cli",
    "generate a comment",
    "following the same rules",
    "comment generator module",
    "let me write",
    "here's a natural",
    "here is a comment",
    "output only",
    "rules:",
    "post content:",
    "existing comments on this post:",
    "do not mention any product",
    "be casual and natural like",
]


def _is_clean_comment(text: str) -> bool:
    """In the comments prompt the content not exposed Wasn't it check."""
    low = text.lower()
    for pattern in _PROMPT_LEAK_PATTERNS:
        if pattern in low:
            return False
    # too If it's long doubt (prompt repeat possibility)
    if len(text) > 800:
        return False
    # --- The dividing line If there is prompt exposure
    if "---" in text and len(text) > 200:
        return False
    return True


def _generate_with_retry(prompt: str, max_retries: int = 3, timeout: int = 60) -> str:
    """kimito prompt send, the result Is it clean? 3Until verification."""
    for attempt in range(max_retries):
        result = _ask_kimi(prompt, timeout=timeout)
        if not result:
            continue
        # quotes eliminate
        result = result.strip('"').strip("'")
        # --- back and forth cut (kimigo sometimes --- as Separately Sent)
        if "---" in result:
            parts = result.split("---")
            # most long part In comments considered
            result = max(parts, key=lambda p: len(p.strip())).strip()
        # Is it clean? check
        if _is_clean_comment(result):
            return result
        # prompt exposure → retry
    return ""


def _format_existing_comments(existing_comments: list[dict] | None) -> str:
    """existing comments For prompt by text conversion."""
    if not existing_comments:
        return ""
    lines = []
    for c in existing_comments[:8]:  # maximum 8dog
        author = c.get("author", "user")
        body = (c.get("body") or c.get("text") or "")[:200]
        if body:
            lines.append(f"  - u/{author}: {body}")
    if not lines:
        return ""
    return "\n\nExisting comments on this post:\n" + "\n".join(lines)


def generate_karma_comment(
    post_text: str,
    sub: str,
    tone: str,
    keywords: list[str] | None = None,
    existing_comments: list[dict] | None = None,
) -> str:
    """karma building comment — kimigo existing Leave a comment by reference generation."""
    kw_str = ", ".join(keywords[:3]) if keywords else sub
    post_snippet = post_text[:1000] if post_text else ""
    comments_context = _format_existing_comments(existing_comments)

    prompt = f"""You are a real Reddit user browsing r/{sub}. Write a short comment (1-3 sentences) replying to this post.

Rules:
- Be casual and natural like a real redditor
- lowercase is fine, minor typos are ok
- use reddit abbreviations sometimes (tbh, imo, fwiw, ngl, etc)
- sometimes skip punctuation at the end
- DO NOT mention any product or app name
- DO NOT use quotation marks around your answer
- Read the existing comments and add a DIFFERENT perspective or agree with someone naturally
- If other commenters share opinions, reference or build on them (e.g. "yeah like [user] said..." or "adding to what others mentioned...")
- Just be helpful or share a related experience about: {kw_str}
- Output ONLY the comment text, nothing else

Post content:
{post_snippet}{comments_context}"""

    comment = _generate_with_retry(prompt)
    if not comment:
        comment = _fallback_comment(keywords or [])
    return comment


def generate_seed_comment(
    post_text: str,
    config: CampaignConfig,
    tone: str,
    keywords: list[str] | None = None,
    existing_comments: list[dict] | None = None,
) -> str:
    """sow seeds comment — kimigo existing comment reference + product naturally mention."""
    kw_str = ", ".join(keywords[:3]) if keywords else "tools"
    post_snippet = post_text[:1000] if post_text else ""
    comments_context = _format_existing_comments(existing_comments)

    prompt = f"""You are a real Reddit user. Write a short comment (1-3 sentences) replying to this post.

Rules:
- Be casual and natural like a real redditor
- lowercase is fine, minor typos ok, use abbreviations (tbh, imo, fwiw etc)
- Naturally mention "{config.product_name}" as something you personally use/tried
- Brief description: {config.tagline}
- URL: {config.product_url}
- Make it sound like a genuine personal recommendation, NOT an ad
- Read existing comments — if someone asks for alternatives or recommendations, your mention fits naturally
- DO NOT use quotation marks around your answer
- Output ONLY the comment text, nothing else

Post topic: {kw_str}
Post content:
{post_snippet}{comments_context}"""

    comment = _generate_with_retry(prompt)
    if not comment:
        comment = f"been using {config.product_name} for this, works pretty well tbh"
    return comment


def verify_comment_posted(page_text: str, my_comment: str, my_username: str = "") -> dict:
    """kimigo page in text Comment actually Has it been posted? verification.

    Returns:
        {"verified": True/False, "reason": "..."}
    """
    # comment front part (core word)
    comment_snippet = my_comment[:150]
    page_snippet = page_text[:5000] if page_text else ""

    prompt = f"""Check if this comment was successfully posted on a Reddit page.

My comment:
{comment_snippet}

Page text (after reload):
{page_snippet}

Rules:
- Search the page text for my comment or very similar text
- If the comment text (or most of it) appears in the page, answer YES
- If NOT found, answer NO
- Output ONLY one line in this exact format: YES|reason or NO|reason
- Example: YES|found matching text in comments section
- Example: NO|comment text not found on page"""

    result = _ask_kimi(prompt, timeout=20)
    if not result:
        # kimi failure city simple text matching fallback
        words = my_comment.split()[:5]
        key_phrase = " ".join(words)
        found = key_phrase.lower() in page_text.lower() if page_text else False
        return {"verified": found, "reason": "fallback text match" if found else "fallback: key phrase not found"}

    result = result.strip()
    if result.upper().startswith("YES"):
        reason = result.split("|", 1)[1].strip() if "|" in result else "verified by kimi"
        return {"verified": True, "reason": reason}
    else:
        reason = result.split("|", 1)[1].strip() if "|" in result else "not found by kimi"
        return {"verified": False, "reason": reason}


def generate_post_title(config: CampaignConfig, sub: str, hint: str = "") -> str:
    """post title — kimigo generation."""
    prompt = f"""Write a Reddit post title for r/{sub}.

Product: {config.product_name}
Description: {config.tagline}
Hint: {hint or "sharing a project"}

Rules:
- Keep it under 100 characters
- Make it sound like a real person sharing their project
- Don't be overly salesy
- Output ONLY the title, nothing else"""

    title = _ask_kimi(prompt, timeout=20)
    if not title:
        title = f"I built {config.product_name} — {config.tagline}"
    title = title.strip('"').strip("'")
    return title


def generate_post_body(config: CampaignConfig, sub: str, hint: str = "") -> str:
    """post text — kimigo generation."""
    prompt = f"""Write a Reddit post body for r/{sub}.

Product: {config.product_name}
URL: {config.product_url}
Description: {config.tagline}
Category: {config.category}
Hint: {hint or "sharing a project"}

Rules:
- 3-5 paragraphs, casual tone
- Explain what it does and why you built it
- Include the URL naturally
- Ask for feedback at the end
- Sound like a real developer sharing their side project
- Use markdown formatting (bold, bullet points if needed)
- Output ONLY the post body, nothing else"""

    body = _ask_kimi(prompt, timeout=30)
    if not body:
        body = f"""Hey r/{sub}!

I've been working on **{config.product_name}** — {config.tagline}.

Check it out: {config.product_url}

Would love to hear your feedback!"""
    return body


def estimate_comment_quality(comment: str) -> dict:
    """comment quality calculation."""
    words = comment.split()
    return {
        "word_count": len(words),
        "has_link": "http" in comment,
        "is_short": len(words) < 5,
        "is_too_long": len(words) > 100,
        "has_product_mention": False,
        "quality_score": min(10, max(1, len(words) // 3)),
    }
