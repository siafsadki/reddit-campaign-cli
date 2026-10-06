# Architecture

## Table of Contents

1. [System Overview](#system-overview)
2. [Module descriptions](#module-descriptions)
3. [Data Flow](#data-flow)
4. [30-Day Scheduling System](#30-day-scheduling-system)
5. [SQLite Schema](#sqlite-schema)

---

## System Overview

```
main.py                            Entry point
  └── src/cli.py                    Click CLI definition
        ├── src/autopilot_browser.py  Browser automation orchestrator
        │     ├── src/pi_browser.py         Reddit browser actions
        │     │     └── src/pi_browser_client.py  WebSocket server
        │     ├── src/marketing/engine.py   Marketing engine (safety guards)
        │     ├── src/schedule.py           30-day schedule generation
        │     └── src/comment_generator.py  Comment generation
        ├── src/state.py             SQLite state management
        └── src/display.py           Rich terminal UI
```

**Dependency direction:** `cli` → `autopilot_browser` → `pi_browser`, `marketing/engine`, `schedule`, `comment_generator` → `state`, `display`

---

## Module descriptions

### `main.py`

Entry point that calls `src.cli.cli()`.

### `src/cli.py`

Click-based CLI definition.

- `browser` — Run browser automation campaign
- `campaign` — Configure/view/edit campaign (subcommand group)
- `report` — Daily strategy report
- `dashboard` — Terminal dashboard
- `influence` — Influence analysis
- `web` — Web dashboard server

### `src/autopilot_browser.py`

Browser automation orchestrator. Runs tasks according to the 30-day schedule.

**`run_browser_campaign()` Function flow:**
1. Start the WebSocket server (port 9877)
2. Wait for the Chrome extension to connect
3. Check Reddit login status
4. Load the 30-day schedule
5. Run tasks for the next incomplete day
6. Save results to the database

**Task execution functions:**
- `_exec_karma()` — Karma-building: r/{sub}/hot → select a post → helpful comment
- `_exec_seed()` — seeding: r/{sub}/search → relevant post → natural product mention
- `_exec_post()` — Post: r/{sub}/submit → enter a title/body → publish
- `_exec_monitor()` — Check new comments on existing posts

### `src/pi_browser_client.py`

WebSocket server. Communicates with the Chrome extension.

- **Port:** 9877
- **Protocol:** JSON messages (id, command, params → id, result/error)
- Sends commands from Python → extension executes → returns results
- `threading.Event` for synchronous request/response handling

**Key commands:**
- `navigate` — Navigate to URL
- `click`, `clickCoords` — Click element/coordinates
- `fill`, `typeText` — Enter text (based on CDP)
- `evaluate` — Run JavaScript
- `snapshot` — List of interactive page elements
- `redditSubmitPost` — Create a Reddit post
- `redditComment` — Write a Reddit comment
- `redditCheckLogin` — Check the login status status

### `src/pi_browser.py`

Reddit-specific browser action wrapper.

**Three-step comment fallback:**
1. Inject JavaScript to enter and submit the comment
2. Retry with CDP typeText
3. Refresh the page and retry everything

**Key methods:**
- `post_comment()` — Write a comment (three-step fallback)
- `submit_post()` — Create a post
- `check_login()` — Check the login status
- `verify_comment()` — Verify successful comment submission

### `src/marketing/engine.py`

Marketing engine. Runs safety checks before every action.

**Preflight checks:**
- Account health (upvote/downvote ratio)
- Timing rating (optimal/good/acceptable/poor/avoid)
- Daily limits (2 posts/day, 8 comments/day)
- Check subreddit-specific rules

### `src/schedule.py`

Generates the 30-day schedule automatically.

**Four phases:**
- Phase 1 (Days 1–8): Karma-building only
- Phase 2 (Days 9–15): Karma + seeding
- Phase 3 (Days 16–22): Seeding + posts
- Phase 4 (Days 23–30): Full campaign

Assigns each day’s tasks based on the target subreddits and keywords in campaign.toml.

### `src/comment_generator.py`

AI based on Comment generation.

- `generate_karma_comment()` — Helpful expert-tone comment
- `generate_seed_comment()` — Natural product-mention comment
- `generate_post_title()` / `generate_post_body()` — Post generation

### `src/state.py`

State management through SQLite.

- Creates the database file and tables automatically on first run
- Provides CRUD methods for each table
- `ON CONFLICT` using the syntax duplicate-key handling

### `src/display.py`

Terminal UI powered by Rich.

### `extension/background.js`

Service Worker for the Chrome extension.

- `ws://localhost:9877`Connects as a WebSocket client to
- Executes commands received from Python through the Chrome DevTools Protocol (CDP) or DOM manipulation
- Reddit-specific handlers: create posts, write comments, check login, and more

---

## Data Flow

### browser command

```
[campaign.toml]
    ↓ schedule.py
[30-day schedule]
    ↓ autopilot_browser.py (orchestration)
    ├──→ marketing/engine.py (Preflight checks)
    ├──→ comment_generator.py (Comment generation)
    ├──→ pi_browser.py (browser actions)
    │       ↓ pi_browser_client.py (WebSocket)
    │       ↓ extension/background.js (CDP/DOM)
    │       ↓ Reddit website
    └──→ state.py (database storage)
           ↓
    [SQLite DB] ←──→ [display.py → terminal output]
```

---

## 30-Day Scheduling System

### Task types (TaskType)

| Value | Description |
|----|------|
| `KARMA_COMMENT` | Karma-building comment (no app mention) |
| `SEED_COMMENT` | Seeding comment (natural product mention) |
| `POST` | Publish a post to a subreddit |
| `MONITOR` | Check comments on existing posts |
| `REST` | Rest |
| `REVIEW` | Review + collect metrics |

### Custom schedule

Save a custom schedule in the database to override the generated schedule.

```bash
# Edit a specific day
python main.py campaign edit-day 5 --clear-tasks --add-karma commandline:terminal,cli

# Restore the generated schedule
python main.py campaign edit-day 5 --revert
```

---

## SQLite Schema

### campaign_state

| Column | Type | Description |
|------|------|------|
| `day_id` | TEXT PK | Day ID (e.g., `day-01`) |
| `status` | TEXT | `pending`, `in_progress`, `completed`, `error` |
| `started_at` | TEXT | Start time (ISO 8601) |
| `completed_at` | TEXT | Completion time (ISO 8601) |

### submissions

| Column | Type | Description |
|------|------|------|
| `id` | INTEGER PK | Auto-increment |
| `day_id` | TEXT | Day ID |
| `reddit_id` | TEXT | Reddit submission ID |
| `subreddit` | TEXT | Subreddit name |
| `title` | TEXT | Post title |
| `url` | TEXT | Post URL |
| `posted_at` | TEXT | Posting time (ISO 8601) |

### comments

| Column | Type | Description |
|------|------|------|
| `id` | INTEGER PK | Auto-increment |
| `reddit_id` | TEXT | Reddit comment ID |
| `submission_id` | TEXT | Target submission ID |
| `subreddit` | TEXT | Subreddit name |
| `body` | TEXT | Comment body |
| `comment_type` | TEXT | `karma_build`, `seeding`, `reply`, `auto_reply` |
| `created_at` | TEXT | Creation time (ISO 8601) |

### metrics

| Column | Type | Description |
|------|------|------|
| `id` | INTEGER PK | Auto-increment |
| `submission_id` | TEXT | Reddit submission ID |
| `upvotes` | INTEGER | Upvote count |
| `comment_count` | INTEGER | Comment count |
| `recorded_at` | TEXT | Recorded time (ISO 8601) |
