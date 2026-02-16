# Morning briefing → GitHub Pages (cron payload instructions)

This document is the **source-of-truth** for the daily Morning Briefing cron job payload.

## Schedule
- Runs daily at **06:00am ET**.

## High-level pipeline
1) Generate machine-readable seed data (HN, Reddit, anti-bubble picks, Readwise):

```bash
python3 scripts/generate_briefing_data.py > tmp/briefing_data.json
```

2) Use the seed data to draft a markdown post at:
- `briefing_site/posts/YYYY-MM-DD.md`

3) Post-process the markdown post:

```bash
python3 scripts/update_briefing_post.py briefing_site/posts/YYYY-MM-DD.md
```

4) Rebuild the static site:

```bash
cd briefing_site && python3 generate_site.py
```

5) Commit + push to `master` to trigger GitHub Pages deploy.

## Content rules (generator MUST follow)

### Anti-bubble picks
Goal: break filter bubbles and avoid Wikipedia dominance.

Rules:
- Use the curated source pool gathered by `scripts/generate_briefing_data.py` (RSS-first).
- Include **at least 3 items** daily.
- Ensure **at least 2–3 distinct domains** across the items (source diversity).
- Do **not** select more than **1 item** from Wikipedia unless there are no viable alternatives.
- If an item appears paywalled / not fetchable, skip it.

Curated sources (non-exhaustive; see code for canonical list):
- Aeon, Arts & Letters Daily, Nautilus, Quanta Magazine, Smithsonian,
  The Conversation, The Marginalian, BBC (science/environment as Future-proxy),
  JSTOR Daily, Longreads.

### Reddit
Goal: avoid sticky/pinned mod threads and recurring meta posts.

Rules:
- Pull subreddit posts via Reddit Atom/RSS (`/r/{sub}/.rss`).
- Filter out recurring mod/sticky patterns by title regex, including:
  - "Monthly Discussion Thread", "Weekly", "AMA", "Reminder", "Rule",
    "Advertising", "Discussion Thread", "Check-in" (case-insensitive)
- Filter out entries where the author is:
  - `AutoModerator`
  - obvious "official" accounts (heuristic; e.g., contains "official")
- Ensure **3 entries per subreddit after filtering**.
  - If fewer than 3 remain, widen the candidate set (fetch more entries) before giving up.

### Readwise saves
- Save **all** HN story URLs + **all** anti-bubble pick URLs to Readwise Reader.
- Do **not** save HN discussion links.

### Other
- Prefer sources that are fetchable without login.
- Keep dedupe in mind (avoid repeating the same anti-bubble links day-to-day).
