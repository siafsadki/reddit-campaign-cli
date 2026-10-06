"""PRAW rapper — Reddit API call."""

from __future__ import annotations

import time

import praw
from praw.models import Submission

from .config import Config


class RedditClient:
    def __init__(self, config: Config):
        self.config = config
        self.reddit = praw.Reddit(
            client_id=config.reddit.client_id,
            client_secret=config.reddit.client_secret,
            username=config.reddit.username,
            password=config.reddit.password,
            user_agent=config.reddit.user_agent,
        )
        self.delay = config.settings.comment_delay

    def verify_auth(self) -> str:
        """certification check, username return."""
        return str(self.reddit.user.me())

    def submit_post(self, subreddit: str, title: str, body: str) -> Submission:
        """On the subreddit text post submit."""
        sub = self.reddit.subreddit(subreddit.removeprefix("r/"))
        submission = sub.submit(title=title, selftext=body)
        return submission

    def post_comment(self, submission_id: str, body: str) -> praw.models.Comment:
        """in the post Write a comment."""
        submission = self.reddit.submission(id=submission_id)
        comment = submission.reply(body)
        time.sleep(self.delay)
        return comment

    def reply_to_comment(self, comment_id: str, body: str) -> praw.models.Comment:
        """In the comments Reply write."""
        comment = self.reddit.comment(id=comment_id)
        reply = comment.reply(body)
        time.sleep(self.delay)
        return reply

    def get_submission(self, submission_id: str) -> Submission:
        """submission check."""
        return self.reddit.submission(id=submission_id)

    def get_new_comments(self, submission_id: str) -> list[praw.models.Comment]:
        """of the post every comment import."""
        submission = self.reddit.submission(id=submission_id)
        submission.comments.replace_more(limit=0)
        return list(submission.comments.list())

    def search_subreddit(
        self, subreddit: str, query: str, limit: int = 10
    ) -> list[Submission]:
        """On the subreddit Search related posts."""
        sub = self.reddit.subreddit(subreddit.removeprefix("r/"))
        return list(sub.search(query, sort="new", time_filter="week", limit=limit))

    def get_hot_posts(self, subreddit: str, limit: int = 10) -> list[Submission]:
        """subreddit popularity writing check."""
        sub = self.reddit.subreddit(subreddit.removeprefix("r/"))
        return list(sub.hot(limit=limit))

    def get_submission_metrics(self, submission_id: str) -> dict:
        """submission metric check."""
        s = self.reddit.submission(id=submission_id)
        return {
            "upvotes": s.score,
            "upvote_ratio": s.upvote_ratio,
            "comment_count": s.num_comments,
            "url": f"https://reddit.com{s.permalink}",
        }
