#!/usr/bin/env python3
"""Update a Morning Briefing post.

- Adds HN discussion links under each Hacker News item.
- Saves all HN story URLs + all Anti-bubble pick URLs to Readwise Reader.

Usage:
  python3 tmp/update_briefing_post.py briefing_site/posts/2026-02-13.md

Requires:
  READWISE_TOKEN env var (stored in OpenClaw gateway config env.vars).
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from urllib.request import Request, urlopen

HN_TOPSTORIES = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
READER_SAVE = "https://readwise.io/api/v3/save/"
UA = "morningbriefing-bot/1.1 (+https://github.com/hipcheck/morningbriefing)"


def http_get_json(url: str, timeout: int = 30) -> object:
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8")
    return json.loads(data)


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def fetch_hn_top(n: int = 5) -> List[dict]:
    ids = http_get_json(HN_TOPSTORIES)
    if not isinstance(ids, list):
        return []
    ids = ids[:n]
    out: List[dict] = []
    for iid in ids:
        try:
            it = http_get_json(HN_ITEM.format(id=iid))
            if isinstance(it, dict):
                it["hn_link"] = f"https://news.ycombinator.com/item?id={iid}"
                out.append(it)
        except Exception:
            continue
    return out


def hn_discussion_from_algolia(url: str) -> Optional[str]:
    """Best-effort: resolve a story URL to its HN item link via Algolia."""
    if not url:
        return None
    try:
        q = json.dumps({"query": url, "tags": "story"})
        # Use simple query param encoding by replacing spaces; url is already a URL so ok-ish.
        api = f"https://hn.algolia.com/api/v1/search?query={url}&tags=story"
        j = http_get_json(api)
        if isinstance(j, dict):
            hits = j.get("hits") or []
            if hits:
                obj = hits[0]
                story_id = obj.get("objectID")
                if story_id:
                    return f"https://news.ycombinator.com/item?id={story_id}"
    except Exception:
        return None
    return None


def save_to_readwise_reader(url: str, token: str) -> Tuple[bool, str]:
    body = json.dumps({"url": url}).encode("utf-8")
    req = Request(
        READER_SAVE,
        method="POST",
        data=body,
        headers={
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Authorization": f"Token {token}",
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            text = resp.read().decode("utf-8", errors="replace")
        if 200 <= status < 300:
            return True, text
        return False, f"HTTP {status}: {text}"
    except Exception as e:
        return False, str(e)


HN_SECTION_RE = re.compile(r"^## A\) Hacker News — Top 5\s*$", re.M)
ANTI_SECTION_RE = re.compile(r"^## C\) Anti-bubble picks \(outside the usual sources\)\s*$", re.M)
LINK_LINE_RE = re.compile(r"^Link:\s*(https?://\S+)\s*$", re.M)


def extract_section(md: str, header_re: re.Pattern) -> Optional[Tuple[int, int]]:
    m = header_re.search(md)
    if not m:
        return None
    start = m.end()
    # next '## ' header or EOF
    m2 = re.search(r"^##\s+", md[start:], re.M)
    end = start + m2.start() if m2 else len(md)
    return start, end


def add_hn_discussion_links(md: str, hn_url_to_discuss: Dict[str, str]) -> str:
    sec = extract_section(md, HN_SECTION_RE)
    if not sec:
        return md
    start, end = sec
    before, mid, after = md[:start], md[start:end], md[end:]

    lines = mid.splitlines(True)
    out_lines: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out_lines.append(line)

        m = re.match(r"^Link:\s*(https?://\S+)\s*$", line.strip())
        if m:
            url = m.group(1)
            discuss = hn_url_to_discuss.get(url)
            # If the next non-empty line is already an HN discussion link, skip
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if discuss and not (j < len(lines) and lines[j].lstrip().startswith("HN discussion:")):
                out_lines.append(f"HN discussion: {discuss}\n")
                out_lines.append("\n")
        i += 1

    return before + "".join(out_lines) + after


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("Usage: update_briefing_post.py <post.md>", file=sys.stderr)
        return 2

    path = argv[1]
    md = read_file(path)

    # Build map story URL -> hn discussion URL.
    # We can't rely on "current" top 5 matching the post, so resolve per URL via Algolia.
    hn_url_to_discuss: Dict[str, str] = {}
    hn_sec = extract_section(md, HN_SECTION_RE)
    if hn_sec:
        s, e = hn_sec
        for m in LINK_LINE_RE.finditer(md[s:e]):
            u = m.group(1).strip()
            discuss = hn_discussion_from_algolia(u)
            if discuss:
                hn_url_to_discuss[u] = discuss

    md2 = add_hn_discussion_links(md, hn_url_to_discuss)
    if md2 != md:
        write_file(path, md2)
        print(f"Updated HN discussion links in {path}")
    else:
        print(f"No HN discussion link changes needed in {path}")

    # Collect HN links + anti-bubble links for Readwise
    token = os.environ.get("READWISE_TOKEN", "").strip()
    if not token:
        print("READWISE_TOKEN not set; skipping Readwise saves", file=sys.stderr)
        return 0

    urls: Set[str] = set()

    hn_sec = extract_section(md2, HN_SECTION_RE)
    if hn_sec:
        s, e = hn_sec
        for m in LINK_LINE_RE.finditer(md2[s:e]):
            urls.add(m.group(1).strip())

    anti_sec = extract_section(md2, ANTI_SECTION_RE)
    if anti_sec:
        s, e = anti_sec
        for m in LINK_LINE_RE.finditer(md2[s:e]):
            urls.add(m.group(1).strip())

    if not urls:
        print("No URLs found to save.")
        return 0

    ok_count = 0
    err_count = 0
    for u in sorted(urls):
        success, msg = save_to_readwise_reader(u, token)
        if success:
            ok_count += 1
        else:
            err_count += 1
            print(f"Readwise save failed for {u}: {msg}", file=sys.stderr)

    print(f"Readwise saved: ok={ok_count} err={err_count} total={len(urls)}")
    return 0 if err_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
