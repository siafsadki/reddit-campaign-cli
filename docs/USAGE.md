# Usage Guide

## Table of Contents

1. [Installation](#installation)
2. [Browser Automation Setup](#browser-automation-setup)
3. [Running a Campaign](#running-a-campaign)
4. [Campaign Management](#campaign-management)
5. [Monitoring and Reports](#monitoring-and-reports)
6. [30-day schedule](#30-day-schedule)
7. [Typical Usage Flow](#typical-usage-flow)
8. [Troubleshooting](#troubleshooting)

---

## Installation

### Requirements

- Python 3.11 or later
- Google Chrome
- Reddit account (logged in through Chrome)
- [kimi CLI](https://github.com/anthropics/kimi) — required to automatically generate AI comments/posts

### Installation Steps

```bash
cd redit-market

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

---

## Browser Automation Setup

Automates the campaign using a Reddit session logged in through Google Chrome. No Reddit API key is required.

### Architecture

```
┌─────────────┐    WebSocket     ┌──────────────────┐     Chrome     ┌─────────┐
│ Python CLI  │ ←──(port 9877)──→ │ RedditBrowser extension │ ←──────────→  │ Reddit  │
│ main.py     │                  │ background.js    │    CDP/DOM     │  Website │
│ browser cmd │                  │ (Service Worker) │               │         │
└─────────────┘                  └──────────────────┘               └─────────┘
       │                                │
       ▼                                ▼
  data/campaign.db               Uses the Chrome login session
  (Stores state/history)
```

### Step 1: Install the Chrome extension

1. Open `chrome://extensions` in Chrome
2. Turn on **Developer mode** in the top-right corner
3. Click **Load unpacked**
4. Select the `extension/` folder
5. The **RedditBrowser** icon appears once the extension is installed

### Step 2: Log in to Reddit

**Log in directly** to https://www.reddit.com in Google Chrome. Browser automation uses this existing login session.

### Step 3: Configure the campaign

```bash
# Create campaign.toml (interactive)
python main.py campaign init
```

Specify product information, target subreddits, tone settings, and more in `campaign.toml`.

### Check the extension connection

Click the extension icon in Chrome to see the connection status in the popup:
- **"Connected"** (green): Python server is connected successfully
- **"Waiting for connection..."** (red): Server not running or connection lost

---

## Running a Campaign

### Basic Usage

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run the next incomplete day
python main.py browser

# Start from a specific day
python main.py browser --day 4

# Run all incomplete days consecutively
python main.py browser --all

# Preview (Do not actually post)
python main.py browser --dry-run

# Set the delay between days (default: 30 seconds)
python main.py browser --delay 60
```

When run, Python starts the WebSocket server (port 9877), and the Chrome extension connects automatically.

### Command options

| Option | Description | Default |
|------|------|--------|
| `--day N` | Start from day N | next incomplete day |
| `--all` | Run all incomplete days consecutively | run one day only |
| `--dry-run` | preview only (no real actions) | off |
| `--delay N` | delay between days (seconds) | 30 |
| `--schedule` | view the full 30-day schedule | - |
| `--status` | Check progress | - |
| `--campaign PATH` | campaign.toml Specify the path | campaign.toml |

### Execution flow

```
python main.py browser
  │
  ├─ 1. Start the WebSocket server (port 9877)
  ├─ 2. Wait for the Chrome extension to connect
  ├─ 3. Check Reddit login status
  ├─ 4. Load the 30-day schedule (campaign.toml based on)
  ├─ 5. next incomplete day Run
  │     │
  │     ├─ KARMA task: r/{sub}/hot → select a post → Write a comment
  │     ├─ SEED task: r/{sub}/search → relevant post → seeding comment
  │     ├─ POST task: r/{sub}/submit → enter a title/body → publish
  │     └─ MONITOR task: Check comments on existing posts
  │
  └─ 6. Save results to the database and generate a report
```

### Safety Measures

- **Marketing engine preflight checks**: Check account health, daily limits, and timing rating before every action
- **Daily limits**: 2 posts/day, 8 comments/day (configurable in campaign.toml)
- **Random delay**: Random 90–180 second delay between actions (to avoid bot detection)
- **Timing blocked**: Automatically blocked during EST early-morning hours (lowest traffic)
- **Duplicate prevention**: Automatically skip posts already commented on and subreddits already posted to
- **Three-step comment fallback**: JavaScript injection → CDP retry → Refresh the page and retry everything

---

## Campaign Management

### Campaign Configuration

```bash
# Create a new campaign
python main.py campaign init

# Show campaign configuration
python main.py campaign show

# Show campaign status
python main.py campaign status
```

### View and edit the schedule

```bash
# View the full 30-day plan
python main.py campaign plan

# View day details and preview comments
python main.py campaign day 5

# Preview N comment variants
python main.py campaign preview 5 -n 3

# Edit a specific day’s schedule
python main.py campaign edit-day 5 --desc "karma + seeding" \
  --clear-tasks --add-karma commandline:terminal,cli

# Restore a specific day to the automatic schedule
python main.py campaign edit-day 5 --revert

# Reset a specific day (can be rerun)
python main.py campaign reset 5
```

### Activity History

```bash
# View all history
python main.py campaign history

# Filter by date/type
python main.py campaign history --date 2026-03-15 --type karma_build
```

---

## Monitoring and Reports

```bash
# Progress dashboard
python main.py browser --status

# Daily strategy report
python main.py report --karma 150

# Web dashboard (view in a browser)
python main.py web --port 8090

# Terminal dashboard
python main.py dashboard

# Influence analysis
python main.py influence --user YOUR_USERNAME
python main.py influence --url "/r/rust/comments/..."
```

---

## 30-Day Schedule

### Four phases

| Phase | Period | Activity | Purpose |
|-------|------|------|------|
| Phase 1 | Days 1–8 | Karma-building only | Build account trust |
| Phase 2 | Days 9–15 | karma + light seeding | Begin natural product mentions |
| Phase 3 | Days 16–22 | seeding + first post | Publish substantial content |
| Phase 4 | Days 23–30 | Full campaign | Posts + seeding + monitoring |

### Task types

| Task | Description |
|--------|------|
| KARMA | write helpful comments in target subreddits (no app mention) |
| SEED | Comment naturally mentioning the product on a relevant post |
| POST | Publish a post directly to a subreddit |
| MONITOR | Check for new comments on existing posts |
| REST | Rest (no activity) |
| REVIEW | Collect metrics + review |

---

## Typical Usage Flow

### Before starting a campaign

```bash
# 1. Campaign Configuration
python main.py campaign init

# 2. Check the schedule
python main.py campaign plan

# 3. Preview
python main.py browser --dry-run
```

### Run daily

```bash
# Run today (automatically select the next incomplete day)
python main.py browser
```

### Check progress

```bash
# Check status
python main.py browser --status

# Activity History
python main.py campaign history
```

### Rerun a day

```bash
# Reset and rerun a specific day
python main.py campaign reset 5
python main.py browser --day 5
```

---

## Troubleshooting

### "Waiting for connection..." (extension is not connected)

- `python main.py browser`is running
- In Chrome, open `chrome://extensions` and confirm RedditBrowser is enabled
- Check whether another process is using port 9877: `lsof -i :9877`
- Reload the extension

### Reddit login fails

- Confirm that you are logged in directly to https://www.reddit.com in Google Chrome
- The extension may not work in Incognito (private) mode

### Comment submission fails

- If the Reddit UI is updated, DOM selectors may change
- Check the error log in the extension console (`chrome://extensions` → RedditBrowser → Service Worker)
- three-step fallback (JavaScript injection → CDP → full retry) if all attempts fail, restart Chrome

### Timing blocked (BLOCKED)

- Actions are automatically blocked during EST early-morning hours (lowest traffic)
- Running during daytime or evening in Korea corresponds to EST morning or afternoon and should work normally

### Reset the database

To restart campaign data from scratch::

```bash
rm data/campaign.db
```

A new database is created automatically on the next run.
