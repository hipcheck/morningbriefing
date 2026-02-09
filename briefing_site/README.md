# Morning Briefing Site

Static blog-style rendering for the daily "Morning briefing".

## Goals
- One post per day
- Index + archive + RSS
- Max Read–inspired styling (dark-first, big mono headline)
- Offline-friendly: each post is rendered as self-contained HTML (inline CSS + no external assets)

## Build

```bash
cd briefing_site
python3 generate_site.py
```

Outputs to `briefing_site/dist/`.

## Content
- Add posts as Markdown in `briefing_site/posts/YYYY-MM-DD.md`
- Front-matter (optional):

```yaml
---
title: "Morning briefing — Mon, Feb 9, 2026 (ET)"
date: 2026-02-09
---
```
