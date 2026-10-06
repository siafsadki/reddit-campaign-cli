"""Reddit Browser Reddit automation client.

Chrome Extension WebSocket by communication Redditto directly post/Write a comment.
No API key required - uses the user's logged-in Chrome session.

page-agent method: shreddit DOM directly farthing + native event simulation.
structured data(post inventory, comment etc.)Is redd library fallback.
"""

from __future__ import annotations

import base64
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from .pi_browser_client import PiBrowserClient, init_browser

SCREENSHOT_DIR = Path("data/screenshots")


def _try_import_redd():
    """redd library import trial."""
    try:
        from redd import Redd
        return Redd()
    except ImportError:
        return None


class RedditBrowser:
    """Pi Browser + redd hybrid Reddit automation.

    read: redd library (structured data) + getText (text)
    write: navigate + fill + click (browser automation)
    """

    def __init__(self):
        self.browser: PiBrowserClient | None = None
        self.redd = _try_import_redd()

    def connect(self) -> bool:
        """Reddit Browser connection."""
        try:
            self.browser = init_browser()
            if self.browser.is_alive():
                print("[Reddit] Reddit Browser connection success", flush=True)
                return True
            print("[Reddit] Reddit Browser connection status... Chromeat Reddit Browser expansion check", flush=True)
            return False
        except Exception as e:
            print(f"[Reddit] connection failure: {e}", flush=True)
            return False

    def _wait_load(self, seconds: int = 3):
        """page load status."""
        time.sleep(seconds)
        self.browser._wait_for_connection()

    # ── log in check ──

    def check_login(self) -> dict:
        """Reddit login status check."""
        self.browser.ext_navigate("https://www.reddit.com")
        self._wait_load(6)

        # Debugging: today page URLclass title check
        page_info = self.browser.ext_evaluate("({url: location.href, title: document.title})")
        print(f"[Reddit] today page: {page_info}", flush=True)

        # Debugging: log in related element check
        debug = self.browser.ext_evaluate("""
            (() => {
                const expandBtn = document.querySelector('#expand-user-drawer-button');
                const loginBtn = document.querySelector('a[href*="login"]');
                const loginBtn2 = document.querySelector('button[data-testid="login-button"]');
                const userMenu = document.querySelector('faceplate-dropdown-menu-button');
                const allBtns = [...document.querySelectorAll('button')].slice(0, 10).map(b => b.textContent.trim().substring(0, 30));
                return {
                    expandBtn: !!expandBtn,
                    loginBtn: !!loginBtn,
                    loginBtn2: !!loginBtn2,
                    userMenu: !!userMenu,
                    sampleButtons: allBtns,
                    bodyLen: document.body?.innerHTML?.length || 0,
                };
            })()
        """)
        print(f"[Reddit] DOM debug: {debug}", flush=True)

        result = self.browser.reddit_check_login()
        print(f"[Reddit] log in result: {result}", flush=True)
        return {"logged_in": result.get("loggedIn", False), "username": result.get("username")}

    # ── read (redd library) ──

    def get_subreddit_posts(self, subreddit: str, sort: str = "hot", limit: int = 10) -> list[dict]:
        """subreddit's post inventory (Extension native farthing)."""
        sub = subreddit.replace("r/", "")

        self.browser.ext_navigate(f"https://www.reddit.com/r/{sub}/{sort}/")
        self._wait_load(4)

        # Extensionof reddit_get_posts use (shreddit-post directly farthing)
        posts = self.browser.reddit_get_posts(limit)
        if posts:
            return posts

        # fallback: redd library
        if self.redd:
            try:
                redd_posts = self.redd.get_subreddit_posts(sub, sort=sort, limit=limit)
                return [
                    {
                        "title": p.title,
                        "url": f"https://www.reddit.com{p.permalink}" if hasattr(p, 'permalink') else p.url,
                        "permalink": getattr(p, 'permalink', ''),
                        "score": getattr(p, 'score', 0),
                        "num_comments": getattr(p, 'num_comments', 0),
                        "author": getattr(p, 'author', 'unknown'),
                    }
                    for p in redd_posts
                ]
            except Exception as e:
                print(f"[redd] r/{sub} fallback failure: {e}", flush=True)

        # final fallback: text based
        return self._get_posts_via_text(sub, sort)

    def _get_posts_via_text(self, sub: str, sort: str = "hot") -> list[dict]:
        """getText based post farthing (redd failure city alternative)."""
        self.browser.ext_navigate(f"https://www.reddit.com/r/{sub}/{sort}/")
        self._wait_load(4)

        text = self.browser.ext_get_text()
        if not text:
            return []

        # in text post title pattern extraction
        posts = []
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if len(line) > 15 and not line.startswith(("Skip", "r/", "Create", "Expand", "Advertise")):
                # username pattern (u/xxx • N hours ago) next line title
                if line.startswith("u/"):
                    continue
                # enough long text post title as a candidate
                if not any(skip in line.lower() for skip in ["upvote", "downvote", "share", "comment", "promoted"]):
                    posts.append({"title": line[:200], "url": "", "score": 0, "num_comments": 0})
                    if len(posts) >= 10:
                        break

        return posts

    def get_post_detail(self, permalink: str) -> dict:
        """post particular information (redd library)."""
        if self.redd:
            try:
                detail = self.redd.get_post_detail(permalink)
                return {
                    "title": detail.title,
                    "body": getattr(detail, 'selftext', '') or getattr(detail, 'body', ''),
                    "score": getattr(detail, 'score', 0),
                    "num_comments": getattr(detail, 'num_comments', 0),
                    "author": getattr(detail, 'author', 'unknown'),
                    "url": getattr(detail, 'url', ''),
                    "comments": [
                        {
                            "author": getattr(c, 'author', 'unknown'),
                            "body": getattr(c, 'body', '')[:500],
                            "score": getattr(c, 'score', 0),
                        }
                        for c in (getattr(detail, 'comments', []) or [])[:20]
                    ],
                }
            except Exception as e:
                print(f"[redd] post particular failure: {e}", flush=True)

        # text based alternative
        url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else permalink
        return self._get_post_via_text(url)

    def _get_post_via_text(self, url: str) -> dict:
        """getText based post particular."""
        self.browser.ext_navigate(url)
        self._wait_load(4)

        text = self.browser.ext_get_text()
        return {
            "title": "",
            "body": text[:2000] if text else "",
            "score": 0,
            "num_comments": 0,
            "author": "",
            "url": url,
            "comments": [],
            "raw_text": text or "",
        }

    def search_subreddit(self, subreddit: str, query: str, limit: int = 5) -> list[dict]:
        """subreddit my search (redd library)."""
        sub = subreddit.replace("r/", "")

        if self.redd:
            try:
                results = self.redd.search(query, subreddit=sub, sort="new", time_filter="week", limit=limit)
                return [
                    {
                        "title": getattr(r, 'title', ''),
                        "url": f"https://www.reddit.com{r.permalink}" if hasattr(r, 'permalink') else getattr(r, 'url', ''),
                        "permalink": getattr(r, 'permalink', ''),
                        "score": getattr(r, 'score', 0),
                        "num_comments": getattr(r, 'num_comments', 0),
                        "author": getattr(r, 'author', 'unknown'),
                    }
                    for r in results
                ]
            except Exception as e:
                print(f"[redd] search failure: {e}", flush=True)

        # text based alternative
        return self._search_via_text(sub, query)

    def _search_via_text(self, sub: str, query: str) -> list[dict]:
        """getText based search (redd failure city)."""
        encoded = quote_plus(query)
        self.browser.ext_navigate(
            f"https://www.reddit.com/r/{sub}/search/?q={encoded}&restrict_sr=1&sort=new&t=week"
        )
        self._wait_load(4)

        text = self.browser.ext_get_text()
        if not text:
            return []

        # in text post title extraction (simple farthing)
        posts = []
        for line in text.split("\n"):
            line = line.strip()
            if len(line) > 20 and not line.startswith(("Skip", "r/", "u/", "Search")):
                if not any(skip in line.lower() for skip in ["upvote", "sort by", "promoted"]):
                    posts.append({"title": line[:200], "url": "", "score": 0})
                    if len(posts) >= 5:
                        break
        return posts

    # ── write (browser automation) ──

    def submit_post(self, subreddit: str, title: str, body: str, auto_submit: bool = False) -> dict:
        """On the subreddit text post write — CDP based upgrade.

        1car: Extensionof redditSubmitPost command use (CDP typeText)
        2car fallback: fill command
        """
        sub = subreddit.replace("r/", "")
        print(f"[Reddit Browser] post write: r/{sub} — '{title[:50]}'", flush=True)

        # method 1: Extensionof redditSubmitPost (CDP based)
        try:
            result = self.browser._send_ext_command("redditSubmitPost", {
                "subreddit": sub,
                "title": title,
                "body": body,
                "autoSubmit": auto_submit,
            })
            log = result.get("log", [])
            for l in log:
                print(f"  [submitPost] {l}", flush=True)

            if result.get("success"):
                return {"status": "posted", "url": result.get("url", ""), "message": "CDP based publication success"}
            if result.get("ready"):
                return {"status": "ready", "message": f"r/{sub}to post preparation complete — publication check necessary"}
        except Exception as e:
            print(f"[Reddit Browser] redditSubmitPost failure: {e}", flush=True)

        # method 2: fill command fallback
        print("[Reddit Browser] fill fallback use", flush=True)
        self.browser.ext_navigate(f"https://www.reddit.com/r/{sub}/submit?type=TEXT")
        self._wait_load(5)

        self.browser.ext_fill('textarea[name="title"]', title)
        time.sleep(1)
        self.browser.ext_fill('div[contenteditable="true"]', body)
        time.sleep(1)

        return {"status": "ready", "message": f"r/{sub}to post preparation complete — publication check necessary"}

    def confirm_submit(self) -> dict:
        """post publication button click."""
        # JS method trial
        result = self.browser.ext_evaluate("""
            (() => {
                const postBtn = Array.from(document.querySelectorAll('button')).find(
                    b => b.textContent?.trim().toLowerCase() === 'post'
                );
                if (postBtn && !postBtn.disabled) {
                    postBtn.click();
                    return {clicked: true};
                }
                return {clicked: false};
            })()
        """)

        if not (isinstance(result, dict) and result.get("clicked")):
            # fallback: click command
            self.browser.ext_click('button[type="submit"]')

        self._wait_load(5)

        # URL check
        page_info = self.browser.ext_evaluate("({url: location.href})")
        url = page_info.get("url", "") if isinstance(page_info, dict) else ""

        if "/comments/" in url:
            return {"status": "posted", "url": url}

        text = self.browser.ext_get_text()
        return {"status": "submitted", "url": url, "page_text": (text or "")[:500]}

    def scroll_down(self, amount: int = 500) -> dict:
        """page scroll knockdown."""
        return self.browser.ext_scroll("down", amount)

    def scroll_up(self, amount: int = 500) -> dict:
        """page scroll up."""
        return self.browser.ext_scroll("up", amount)

    def _save_comment_to_db(self, post_url: str, comment_body: str, comment_type: str = "seeding"):
        """Leave a comment dashboard DBto record."""
        try:
            from .state import StateDB
            # URLat subreddit extraction
            m = re.search(r'/r/([^/]+)', post_url)
            subreddit = m.group(1) if m else "unknown"
            # URLat submission id extraction
            m2 = re.search(r'/comments/([^/]+)', post_url)
            submission_id = m2.group(1) if m2 else None

            db = StateDB("data/campaign.db")
            db.save_comment(
                reddit_id=f"browser_{int(time.time())}",
                submission_id=submission_id,
                subreddit=subreddit,
                body=comment_body,
                comment_type=comment_type,
            )
            db.close()
            print(f"[Reddit Browser] DB record complete (r/{subreddit}, type={comment_type})", flush=True)
        except Exception as e:
            print(f"[Reddit Browser] DB record failure: {e}", flush=True)

    def post_comment(self, post_url: str, comment_body: str, save_screenshot: bool = True, comment_type: str = "seeding") -> dict:
        """in the post Write a comment — 3step: JS inject → button Find → CDP full fallback.

        core: text input after page absoluteness not reload No (input text preservation).
        """
        print(f"[Reddit Browser] Write a comment start: {post_url[:80]}...", flush=True)
        self.browser.ext_navigate(post_url)
        self._wait_load(5)

        if save_screenshot:
            self.save_screenshot("before_comment")

        # ══════════════════════════════════════
        # method 1: JS injectas text input trial
        # ══════════════════════════════════════
        print("[Reddit Browser] Step 1: JS inject text input...", flush=True)
        result = self.browser.reddit_comment(comment_body)
        log = result.get("log", [])
        for l in log:
            print(f"  [JS] {l}", flush=True)

        if result.get("success") and result.get("verified"):
            print("[Reddit Browser] JS perfection success + Verified!", flush=True)
            self._save_comment_to_db(post_url, comment_body, comment_type)
            if save_screenshot:
                self.save_screenshot("verified_comment")
            return {"status": "commented", "verified": True}

        # JSgo text I typed it but button click failed case
        # → page not reload Without as soon as button Find trial
        if result.get("success") or "CDP typeText done" in str(log):
            print("[Reddit Browser] text Entered — button click retry (reload without)...", flush=True)
            btn_clicked = self._try_click_comment_button()
            if btn_clicked:
                time.sleep(3)
                if save_screenshot:
                    self.save_screenshot("after_submit_retry")
                # verification
                verified = self._verify_comment(post_url, comment_body)
                if verified:
                    self._save_comment_to_db(post_url, comment_body, comment_type)
                    if save_screenshot:
                        self.save_screenshot("verified_comment")
                    return {"status": "commented", "verified": True}

        # ══════════════════════════════════════
        # method 2: CDP full — from the beginning again (trigger click → typing → button)
        # ══════════════════════════════════════
        print("[Reddit Browser] Step 2: CDP full fallback...", flush=True)
        # beforeunload popup prevention after page reload
        self.browser.ext_evaluate("window.onbeforeunload = null")
        time.sleep(0.3)
        self.browser.ext_navigate(post_url)
        self._wait_load(5)

        # scroll get off comment area Make it visible
        self.browser.ext_scroll("down", 400)
        time.sleep(1.5)

        # 2a: comment trigger click (join the conversation / add a comment)
        trigger_clicked = self._click_comment_trigger()
        if not trigger_clicked:
            print("[Reddit Browser] trigger pond drawing out — faceplate-textarea directly click", flush=True)
            self.browser.ext_click("faceplate-textarea-input")
        time.sleep(2)

        # 2b: editor Find + focus
        editor_found = self._focus_editor()
        time.sleep(0.5)

        # 2c: CDP typing
        print(f"[Reddit Browser] CDP typing ({len(comment_body)}ruler)...", flush=True)
        type_result = self.browser.ext_type_text(comment_body)
        if type_result.get("error"):
            print("[Reddit Browser] CDP typing failure — fill trial", flush=True)
            self.browser.ext_fill('div[contenteditable="true"]', comment_body)
            time.sleep(0.5)
            # textareado trial
            self.browser.ext_fill('textarea', comment_body)
        time.sleep(1)

        if save_screenshot:
            self.save_screenshot("after_text_input")

        # 2d: In the editor the text Is there check
        editor_text = self.browser.ext_evaluate("""
            (() => {
                const ed = document.querySelector('div[contenteditable="true"]');
                if (ed && ed.textContent.trim()) return ed.textContent.trim().substring(0, 100);
                const ta = document.querySelector('textarea');
                if (ta && ta.value.trim()) return ta.value.trim().substring(0, 100);
                return '';
            })()
        """)
        if editor_text:
            print(f"[Reddit Browser] editor text check: {str(editor_text)[:60]}", flush=True)
        else:
            print("[Reddit Browser] editor text doesn't exist — still continue progress", flush=True)

        # 2e: Comment button click
        btn_clicked = self._try_click_comment_button()
        if not btn_clicked:
            # JSas directly click trial
            print("[Reddit Browser] snapshot button failure — JS directly click trial", flush=True)
            self.browser.ext_evaluate("""
                (() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = b.textContent.trim().toLowerCase();
                        if (t === 'comment' && b.offsetWidth > 30) {
                            b.click();
                            return 'clicked';
                        }
                    }
                    // submit type button
                    for (const b of btns) {
                        if (b.type === 'submit' && b.offsetWidth > 30) {
                            const t = b.textContent.trim().toLowerCase();
                            if (!['reply','cancel','search','chat'].includes(t)) {
                                b.click();
                                return 'clicked-submit';
                            }
                        }
                    }
                    return 'not-found';
                })()
            """)

        time.sleep(3)
        if save_screenshot:
            self.save_screenshot("after_submit")

        # ══════════════════════════════════════
        # verification (reload after)
        # ══════════════════════════════════════
        verified = self._verify_comment(post_url, comment_body)
        if verified:
            self._save_comment_to_db(post_url, comment_body, comment_type)
            if save_screenshot:
                self.save_screenshot("verified_comment")
            return {"status": "commented", "verified": True}

        if save_screenshot:
            self.save_screenshot("unverified_comment")
        print("[Reddit Browser] comment unconfirmed", flush=True)
        return {"status": "unverified", "message": "It was submitted, but on the page unconfirmed"}

    def _click_comment_trigger(self) -> bool:
        """comment trigger (join the conversation / add a comment) click."""
        snap = self.browser._send_ext_command("snapshot")
        for el in snap.get("elements", []):
            sel = el.get("selector", "")
            text = (el.get("text") or "").lower()
            rect = el.get("rect", {})
            if ("faceplate-textarea" in sel or "join" in text or
                "conversation" in text or "add a comment" in text):
                if rect.get("width", 0) > 0 and rect.get("height", 0) > 0:
                    x = rect["x"] + rect["width"] // 2
                    y = rect["y"] + rect["height"] // 2
                    print(f"  trigger click: ({x}, {y}) - {text[:40]}", flush=True)
                    self.browser.ext_click_coords(x, y)
                    return True
        return False

    def _focus_editor(self) -> bool:
        """editor (textbox/textarea) find focus."""
        snap = self.browser._send_ext_command("snapshot")
        for el in snap.get("elements", []):
            role = el.get("role", "")
            tag = el.get("tag", "")
            rect = el.get("rect", {})
            if (role == "textbox" or tag == "textarea" or
                "contenteditable" in str(el.get("attributes", ""))):
                if rect.get("width", 0) > 100 and rect.get("height", 0) > 20:
                    ex = rect["x"] + rect["width"] // 2
                    ey = rect["y"] + rect["height"] // 2
                    print(f"  editor focus: ({ex}, {ey}) tag={tag} role={role}", flush=True)
                    self.browser.ext_click_coords(ex, ey)
                    return True
        return False

    def _try_click_comment_button(self) -> bool:
        """snapshotat Comment button find click."""
        snap = self.browser._send_ext_command("snapshot")
        # 1car: textgo accurately "comment"person button
        for el in snap.get("elements", []):
            if el.get("tag") == "button":
                text = (el.get("text") or "").strip().lower()
                rect = el.get("rect", {})
                if text == "comment" and rect.get("width", 0) > 30:
                    sx = rect["x"] + rect["width"] // 2
                    sy = rect["y"] + rect["height"] // 2
                    print(f"  Comment button: ({sx}, {sy})", flush=True)
                    self.browser.ext_click_coords(sx, sy)
                    return True
        # 2car: submit type button (reply, cancel etc. exception)
        exclude = {"open chat", "search", "collapse", "expand", "chat", "reply", "cancel", "save draft", "post"}
        for el in snap.get("elements", []):
            if el.get("tag") == "button":
                text = (el.get("text") or "").strip().lower()
                btn_type = el.get("type", "")
                rect = el.get("rect", {})
                if btn_type == "submit" and rect.get("width", 0) > 30:
                    if not any(ex in text for ex in exclude):
                        sx = rect["x"] + rect["width"] // 2
                        sy = rect["y"] + rect["height"] // 2
                        print(f"  Submit button: ({sx}, {sy}) text={text}", flush=True)
                        self.browser.ext_click_coords(sx, sy)
                        return True
        return False

    def _verify_comment(self, post_url: str, comment_body: str) -> bool:
        """comment post verification — today page + reload after check."""
        snippet = comment_body[:40]

        # today on the page check
        print("[Reddit Browser] verification: today page...", flush=True)
        text = self.browser.ext_get_text() or ""
        if snippet in text:
            print("[Reddit Browser] comment confirmed!", flush=True)
            return True

        # reload after check
        print("[Reddit Browser] verification: reload after...", flush=True)
        self.browser.ext_evaluate("window.onbeforeunload = null")
        time.sleep(1)
        self.browser.ext_navigate(post_url)
        self._wait_load(5)
        text = self.browser.ext_get_text() or ""
        if snippet in text:
            print("[Reddit Browser] reload after comment confirmed!", flush=True)
            return True

        print("[Reddit Browser] comment unconfirmed", flush=True)
        return False

    def save_screenshot(self, label: str = "screenshot") -> str | None:
        """today page Take a screenshot with file save."""
        try:
            result = self.browser.ext_screenshot()
            if not result or not result.get("image"):
                return None

            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{ts}_{label}.png"
            filepath = SCREENSHOT_DIR / filename

            # data:image/png;base64,... in format base64 extraction
            img_data = result["image"]
            if "," in img_data:
                img_data = img_data.split(",", 1)[1]
            filepath.write_bytes(base64.b64decode(img_data))

            print(f"[Reddit Browser] screenshot save: {filepath}", flush=True)
            return str(filepath)
        except Exception as e:
            print(f"[Reddit Browser] screenshot failure: {e}", flush=True)
            return None

    def search_and_comment(self, subreddit: str, query: str, comment_body: str, max_posts: int = 1) -> list[dict]:
        """subreddit search → related in the post comment.

        reddas post search → by browser Write a comment.
        """
        results = []
        posts = self.search_subreddit(subreddit, query, limit=max_posts + 2)

        if not posts:
            return [{"status": "no_posts_found", "subreddit": subreddit, "query": query}]

        for post in posts[:max_posts]:
            url = post.get("url", "")
            if not url:
                continue

            result = self.post_comment(url, comment_body)
            result["url"] = url
            result["subreddit"] = subreddit
            result["title"] = post.get("title", "")
            results.append(result)

            if len(results) < max_posts:
                time.sleep(5)

        return results

    # ── monitoring ──

    def get_post_comments(self, post_url: str) -> list[dict]:
        """of the post comment inventory (Extension native)."""
        self.browser.ext_navigate(post_url)
        self._wait_load(4)

        comments = self.browser.reddit_get_comments(limit=30)
        if comments:
            return comments

        # fallback: redd
        permalink = _url_to_permalink(post_url)
        if self.redd and permalink:
            try:
                detail = self.redd.get_post_detail(permalink)
                return [
                    {"author": getattr(c, 'author', 'unknown'), "body": getattr(c, 'body', '')[:500], "score": getattr(c, 'score', 0)}
                    for c in (getattr(detail, 'comments', []) or [])[:50]
                ]
            except Exception:
                pass

        return self._get_comments_via_text(post_url)

    def _get_comments_via_text(self, url: str) -> list[dict]:
        """getText based comment farthing."""
        self.browser.ext_navigate(url)
        self._wait_load(4)

        text = self.browser.ext_get_text()
        if not text:
            return []

        # simple comment farthing (text block)
        return [{"body": text[:2000], "raw": True}]

    def get_post_stats(self, post_url: str) -> dict:
        """post statistics (Extension native)."""
        self.browser.ext_navigate(post_url)
        self._wait_load(3)

        detail = self.browser.reddit_get_post_detail()
        if detail and detail.get("title"):
            return {
                "score": detail.get("score", 0),
                "comment_count": detail.get("commentCount", 0),
                "title": detail.get("title", ""),
                "author": detail.get("author", ""),
                "url": post_url,
            }

        return {"title": "", "score": 0, "comment_count": 0, "url": post_url}

    # ── Upvote ──

    def upvote_post(self, post_url: str = None) -> dict:
        """today page or designation URLof post Upvote."""
        if post_url:
            self.browser.ext_navigate(post_url)
            self._wait_load(3)
        return self.browser.reddit_upvote()

    # ── subreddit movement ──

    def navigate_subreddit(self, subreddit: str, sort: str = "hot") -> dict:
        """To subreddit movement + subreddit information collection."""
        sub = subreddit.replace("r/", "")
        return self.browser.reddit_navigate_sub(sub, sort)

    # ── user information ──

    def get_user_info(self) -> dict:
        """today logged in user information."""
        return self.browser.reddit_get_user_info()

    # ── comment Reply ──

    def reply_to_comment(self, thing_id: str, body: str) -> dict:
        """specific In the comments Reply."""
        return self.browser.reddit_reply_to_comment(thing_id, body)

    # ── DOM tree (page-agent method) ──

    def get_dom_tree(self, max_depth: int = 5, max_nodes: int = 200) -> dict:
        """page-agent method DOM tree extraction."""
        return self.browser.get_dom_tree(max_depth, max_nodes)

    def click_by_index(self, index: int) -> dict:
        """DOM index based click."""
        return self.browser.click_by_index(index)

    def fill_by_index(self, index: int, value: str) -> dict:
        """DOM index based input."""
        return self.browser.fill_by_index(index, value)

    # ── page text read ──

    def read_page(self, url: str) -> str:
        """URLof text detail read."""
        self.browser.ext_navigate(url)
        self._wait_load(4)
        return self.browser.ext_get_text() or ""

    def stop(self):
        """browser connection end."""
        if self.browser:
            self.browser.stop()


def _url_to_permalink(url: str) -> str:
    """Reddit URLsecond permalinkas conversion."""
    if not url:
        return ""
    # https://www.reddit.com/r/sub/comments/xxx/title/ → /r/sub/comments/xxx/title/
    m = re.search(r"(\/r\/\w+\/comments\/\w+\/[^?#]*)", url)
    return m.group(1) if m else ""
