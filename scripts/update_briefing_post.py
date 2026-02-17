#!/usr/bin/env python3
"""Update a Morning Briefing post.

Edits the markdown post in-place:

1) Adds HN discussion links under each Hacker News item.
2) Saves all HN story URLs + all Anti-bubble pick URLs to Readwise Reader.
3) Replaces the YouTube placeholder with real daily YouTube anti-bubble picks
   (3–5 videos), selected from a curated channel pool.

Usage:
  python3 scripts/update_briefing_post.py briefing_site/posts/YYYY-MM-DD.md

Requires:
  READWISE_TOKEN env var (stored in OpenClaw gateway config env.vars) for Readwise saves.

Notes:
- YouTube picking uses public RSS feeds; no YouTube auth required.
- Channel IDs are resolved lazily from channel URLs and cached under tmp/.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

HN_TOPSTORIES = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
READER_SAVE = "https://readwise.io/api/v3/save/"
UA = "morningbriefing-bot/1.2 (+https://github.com/hipcheck/morningbriefing)"


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
ANTI_SECTION_RE = re.compile(r"^## C\) Anti-bubble picks \(outside.*\)\s*$", re.M)
YOUTUBE_H3_RE = re.compile(r"^###\s+YouTube\s*$", re.M)
LINK_LINE_RE = re.compile(r"^-?\s*\*\*Link:\*\*\s*(https?://\S+)\s*$|^Link:\s*(https?://\S+)\s*$", re.M)


def extract_section(md: str, header_re: re.Pattern) -> Optional[Tuple[int, int]]:
    m = header_re.search(md)
    if not m:
        return None
    start = m.end()
    # next '## ' header or EOF
    m2 = re.search(r"^##\s+", md[start:], re.M)
    end = start + m2.start() if m2 else len(md)
    return start, end


def _first_url_match(m: re.Match) -> Optional[str]:
    # LINK_LINE_RE has two possible capture groups
    for idx in range(1, 3):
        try:
            v = m.group(idx)
        except IndexError:
            continue
        if v:
            return v
    return None


# --- YouTube anti-bubble picks (Option A: curated channel pool) ---

YOUTUBE_CHANNEL_POOL = [
    # English
    {"name": "Huberman Lab", "url": "https://www.youtube.com/@hubermanlab"},
    {"name": "Peter Attia MD", "url": "https://www.youtube.com/@PeterAttiaMD"},
    {"name": "FoundMyFitness", "url": "https://www.youtube.com/@FoundMyFitness"},
    {"name": "Physionic", "url": "https://www.youtube.com/@Physionic"},
    {"name": "Nutrition Made Simple", "url": "https://www.youtube.com/@NutritionMadeSimple"},
    {"name": "Renaissance Periodization", "url": "https://www.youtube.com/@RenaissancePeriodization"},
    {"name": "SmarterEveryDay", "url": "https://www.youtube.com/@smartereveryday"},
    {"name": "Veritasium", "url": "https://www.youtube.com/@veritasium"},
    {"name": "PBS Space Time", "url": "https://www.youtube.com/@pbsspacetime"},
    {"name": "PBS Eons", "url": "https://www.youtube.com/@PBSEons"},
    {"name": "Kurzgesagt", "url": "https://www.youtube.com/@kurzgesagt"},
    {"name": "Real Engineering", "url": "https://www.youtube.com/@RealEngineering"},
    {"name": "Wendover Productions", "url": "https://www.youtube.com/@Wendoverproductions"},
    {"name": "How Money Works", "url": "https://www.youtube.com/@HowMoneyWorks"},
    {"name": "Big Think", "url": "https://www.youtube.com/@bigthink"},
    {"name": "Closer To Truth", "url": "https://www.youtube.com/@CloserToTruthTV"},
    {"name": "LEMMiNO", "url": "https://www.youtube.com/@LEMMiNO"},
    {"name": "Technology Connections", "url": "https://www.youtube.com/@TechnologyConnections"},
    {"name": "Tom Scott", "url": "https://www.youtube.com/@TomScottGo"},
    {"name": "Every Frame a Painting", "url": "https://www.youtube.com/@everyframeapainting"},
    # German
    {"name": "ARTEde", "url": "https://www.youtube.com/@artede"},
    {"name": "Kurzgesagt DE", "url": "https://www.youtube.com/@KurzgesagtDE"},
]


def http_get(url: str, timeout: int = 30) -> bytes:
    req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def resolve_channel_id(channel_url: str, cache: dict) -> Optional[str]:
    if channel_url in cache:
        return cache[channel_url]

    # If already a channel-id URL
    m = re.search(r"/channel/([A-Za-z0-9_-]{12,})", channel_url)
    if m:
        cache[channel_url] = m.group(1)
        return m.group(1)

    # Fetch HTML and extract channelId
    try:
        html = http_get(channel_url, timeout=30).decode("utf-8", errors="ignore")
        m2 = re.search(r"\"channelId\"\s*:\s*\"(UC[a-zA-Z0-9_-]{20,})\"", html)
        if not m2:
            m2 = re.search(r"channel_id=\"(UC[a-zA-Z0-9_-]{20,})\"", html)
        if m2:
            cache[channel_url] = m2.group(1)
            return m2.group(1)
    except Exception:
        return None

    return None


@dataclass
class YtVideo:
    channel: str
    title: str
    url: str
    published: datetime


def fetch_channel_rss_videos(channel_id: str, channel_name: str, max_items: int = 8) -> List[YtVideo]:
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    data = http_get(rss_url, timeout=30)
    root = ET.fromstring(data)
    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }
    out: List[YtVideo] = []
    for entry in root.findall("a:entry", ns)[:max_items]:
        title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        link = ""
        for le in entry.findall("a:link", ns):
            if le.get("rel") in (None, "alternate"):
                link = (le.get("href") or "").strip()
                break
        pub = (entry.findtext("a:published", default="", namespaces=ns) or "").strip()
        try:
            published = datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            published = datetime.now(timezone.utc)
        if title and link:
            out.append(YtVideo(channel=channel_name, title=title, url=link, published=published))
    return out


def pick_youtube_videos(now: datetime, n: int = 5) -> List[YtVideo]:
    cache_path = os.path.join("tmp", "youtube_channel_cache.json")
    os.makedirs("tmp", exist_ok=True)
    try:
        cache = json.loads(read_file(cache_path)) if os.path.exists(cache_path) else {}
    except Exception:
        cache = {}

    candidates: List[YtVideo] = []
    for ch in YOUTUBE_CHANNEL_POOL:
        cid = resolve_channel_id(ch["url"], cache)
        if not cid:
            continue
        try:
            candidates.extend(fetch_channel_rss_videos(cid, ch["name"], max_items=6))
        except Exception:
            continue

    # persist cache best-effort
    try:
        write_file(cache_path, json.dumps(cache, indent=2, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # Filter recency (start with 14 days; if too few, widen to 30)
    def filter_days(days: int) -> List[YtVideo]:
        cutoff = now - timedelta(days=days)
        return [v for v in candidates if v.published >= cutoff]

    recent = filter_days(14)
    if len(recent) < 3:
        recent = filter_days(30)

    # Drop Shorts by default (too low signal for this slot)
    recent = [v for v in recent if "/shorts/" not in v.url]

    recent.sort(key=lambda v: v.published, reverse=True)

    picked: List[YtVideo] = []
    used_channels: Set[str] = set()
    used_urls: Set[str] = set()
    for v in recent:
        if v.channel in used_channels:
            continue
        if v.url in used_urls:
            continue
        picked.append(v)
        used_channels.add(v.channel)
        used_urls.add(v.url)
        if len(picked) >= n:
            break

    return picked


def upsert_youtube_section(md: str, videos: List[YtVideo]) -> str:
    if not videos:
        # Remove the placeholder line if present
        md = md.replace("- YouTube: not configured yet — add 3–5 channel IDs to enable daily anti-bubble videos.", "")
        md = md.replace("YouTube: not configured yet — add 3–5 channel IDs to enable daily anti-bubble videos.", "")
        return md

    block_lines = ["### YouTube", ""]
    for v in videos:
        date = v.published.strftime("%Y-%m-%d")
        block_lines.append(f"- **{v.channel}** ({date}) — [{v.title}]({v.url})")
    block_lines.append("")
    new_block = "\n".join(block_lines)

    # If a YouTube section exists, replace it (until next ## header or EOF)
    m = YOUTUBE_H3_RE.search(md)
    if m:
        start = m.start()
        # end at next '## ' header or EOF
        m2 = re.search(r"^##\s+", md[m.end():], re.M)
        end = m.end() + (m2.start() if m2 else (len(md) - m.end()))
        return md[:start] + new_block + md[end:]

    # Else, insert at end of anti-bubble section if present, otherwise append.
    anti = extract_section(md, ANTI_SECTION_RE)
    if anti:
        s, e = anti
        return md[:e].rstrip() + "\n\n" + new_block + md[e:]

    return md.rstrip() + "\n\n" + new_block


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
            u = _first_url_match(m)
            if not u:
                continue
            u = u.strip()
            discuss = hn_discussion_from_algolia(u)
            if discuss:
                hn_url_to_discuss[u] = discuss

    md2 = add_hn_discussion_links(md, hn_url_to_discuss)

    # YouTube anti-bubble picks
    yt = pick_youtube_videos(datetime.now(timezone.utc), n=5)
    md3 = upsert_youtube_section(md2, yt)

    if md3 != md:
        write_file(path, md3)
        print(f"Updated post in {path} (HN discussion and/or YouTube)")
    else:
        print(f"No post changes needed in {path}")

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
            u = _first_url_match(m)
            if u:
                urls.add(u.strip())

    anti_sec = extract_section(md2, ANTI_SECTION_RE)
    if anti_sec:
        s, e = anti_sec
        for m in LINK_LINE_RE.finditer(md2[s:e]):
            u = _first_url_match(m)
            if u:
                urls.add(u.strip())

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
