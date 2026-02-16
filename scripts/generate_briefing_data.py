#!/usr/bin/env python3
"""Generate machine-readable seed data for the daily Morning Briefing.

This script is used by the morning-briefing cron pipeline (GitHub Pages post generator)
to gather *inputs* (HN, Reddit, anti-bubble reading picks, Readwise recents).

Key guarantees (as of 2026-02-16):
- Anti-bubble picks are sourced from a curated pool (RSS-first), with daily rotation.
  We aim for >=3 items from >=2-3 distinct domains and avoid Wikipedia dominance.
- Reddit pulls via subreddit Atom/RSS; filters out recurring mod/sticky threads and
  obvious repetition (e.g. "Monthly Discussion Thread", "Weekly", "Reminder").
  Ensures 3 entries per subreddit after filtering by fetching more candidates.

No external dependencies.
"""

from __future__ import annotations

import hashlib
import html as _html
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

UA = "morningbriefing-bot/1.3 (+https://github.com/hipcheck/morningbriefing)"


def http_get(url: str, headers: Optional[dict] = None, timeout: int = 30) -> Tuple[int, str, bytes]:
    hdrs = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    req = Request(url, headers=hdrs)
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            status = getattr(resp, "status", 200)
            ctype = resp.headers.get("content-type", "")
        return status, ctype, data
    except Exception as e:
        # urllib raises for HTTP errors; treat as a normal non-200.
        try:
            from urllib.error import HTTPError

            if isinstance(e, HTTPError):
                body = e.read() if getattr(e, "fp", None) else b""
                ctype = (e.headers.get("content-type", "") if getattr(e, "headers", None) else "")
                return int(getattr(e, "code", 0) or 0), ctype, body
        except Exception:
            pass
        return 0, "", b""  # network/timeout/other


def html_to_text(s: str) -> str:
    if not s:
        return ""
    s = _html.unescape(s)
    # normalize block-level tags to newlines
    s = re.sub(r"(?is)<\s*(br|/p|/div|/li|/pre|/blockquote)\s*>", "\n", s)
    s = re.sub(r"(?is)<\s*(p|div|li|pre|blockquote)(\s+[^>]*)?>", "\n", s)

    def _a(m: re.Match) -> str:
        href = m.group(1) or ""
        text = m.group(2) or ""
        text = re.sub(r"(?is)<[^>]+>", "", text)
        text = _html.unescape(text).strip()
        href = _html.unescape(href).strip()
        if href and text and href not in text:
            return f"{text} ({href})"
        return text or href

    s = re.sub(r"(?is)<a\s+[^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", _a, s)
    s = re.sub(r"(?is)</?code[^>]*>", "", s)
    s = re.sub(r"(?is)<[^>]+>", "", s)
    s = re.sub(r"\r", "", s)
    s = re.sub(r"\n[ \t\f\v]*\n+", "\n\n", s)
    s = re.sub(r"[ \t\f\v]+", " ", s)
    return s.strip()


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


# -------------------- Hacker News --------------------


def fetch_hn_top(n: int = 5) -> List[dict]:
    st, _, data = http_get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if st != 200:
        raise RuntimeError(f"HN topstories failed: {st}")
    ids = json.loads(data.decode("utf-8"))[:n]
    items: List[dict] = []
    for iid in ids:
        st2, _, d2 = http_get(f"https://hacker-news.firebaseio.com/v0/item/{iid}.json")
        if st2 != 200:
            continue
        it = json.loads(d2.decode("utf-8"))
        url = it.get("url")
        text = html_to_text(it.get("text") or "")
        items.append(
            {
                "id": iid,
                "title": it.get("title"),
                "url": url,
                "domain": domain_of(url) if url else "news.ycombinator.com",
                "score": it.get("score"),
                "comments": it.get("descendants"),
                "hn_link": f"https://news.ycombinator.com/item?id={iid}",
                "post_text": text,
                "type": it.get("type"),
            }
        )
    return items


def fetch_hn_top_comments_algolia(item_id: int, n: int = 3) -> List[dict]:
    url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{item_id}&hitsPerPage={max(n*3,20)}"
    try:
        st, _, data = http_get(url)
        if st != 200:
            return []
        j = json.loads(data.decode("utf-8"))
        out: List[dict] = []
        for h in j.get("hits", []):
            if h.get("author") and h.get("comment_text") and not h.get("deleted"):
                txt = html_to_text(h.get("comment_text"))
                txt = txt.replace("\n\n", " ").strip()
                if len(txt) > 520:
                    txt = txt[:520].rsplit(" ", 1)[0] + "…"
                out.append(
                    {
                        "author": h.get("author"),
                        "excerpt": txt,
                        "comment_id": h.get("objectID"),
                        "link": f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                    }
                )
            if len(out) >= n:
                break
        return out
    except Exception:
        return []


# -------------------- Reddit (RSS/Atom) --------------------


REDDIT_RECURRING_TITLE_RE = re.compile(
    r"(?i)\b(weekly|monthly|daily)\b.*\b(thread|discussion|check[- ]?in)\b|\bdiscussion thread\b|\bopen thread\b|\breminder\b|\brule\b|\badvertis(ing|ement)\b|\bama\b|\bcommunity update\b"
)


def _looks_like_official_account(author: str, subreddit: str) -> bool:
    a = (author or "").strip().lstrip("/u/").lower()
    s = subreddit.lower()
    if not a:
        return False
    if a == "automoderator":
        return True
    # Heuristics for official accounts: contains "official" or matches subreddit name.
    if "official" in a:
        return True
    if a == s or a == f"{s}_official" or a == f"{s}official":
        return True
    return False


def fetch_reddit_sub_rss(sub: str, desired: int = 3, max_fetch: int = 40) -> dict:
    url = f"https://www.reddit.com/r/{sub}/.rss"
    st, ctype, data = http_get(
        url,
        headers={"Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9"},
    )
    if st != 200:
        return {"subreddit": sub, "status": st, "error": f"HTTP {st}", "entries": []}

    try:
        root = ET.fromstring(data)
    except Exception as e:
        return {"subreddit": sub, "status": st, "error": f"parse_error: {e}", "entries": []}

    ns = {"a": "http://www.w3.org/2005/Atom"}

    # Over-fetch then filter (sticky/pinned not explicitly marked in feed).
    raw_entries = []
    for e in root.findall("a:entry", ns)[: max_fetch]:
        title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
        link_el = None
        for le in e.findall("a:link", ns):
            if le.get("rel") in (None, "alternate"):
                link_el = le
                break
        link = (link_el.get("href") if link_el is not None else "").strip()
        author = (e.findtext("a:author/a:name", default="", namespaces=ns) or "").strip()
        content = e.findtext("a:content", default="", namespaces=ns)
        summary = e.findtext("a:summary", default="", namespaces=ns)
        full_text = html_to_text(content or summary or "")

        raw_entries.append({"title": title, "link": link, "author": author, "post_text": full_text})

    filtered: List[dict] = []
    seen_links: set[str] = set()
    for ent in raw_entries:
        title = ent.get("title") or ""
        author = ent.get("author") or ""
        link = ent.get("link") or ""

        if not title or not link:
            continue
        if link in seen_links:
            continue
        seen_links.add(link)

        if REDDIT_RECURRING_TITLE_RE.search(title):
            continue
        if _looks_like_official_account(author, sub):
            continue

        filtered.append(ent)
        if len(filtered) >= desired:
            break

    return {"subreddit": sub, "status": st, "error": None, "entries": filtered, "fetched": len(raw_entries)}


def fetch_reddit_comments_rss(post_url: str, n: int = 3) -> Optional[List[dict]]:
    if not post_url or "reddit.com" not in post_url:
        return None

    comments_url = post_url.rstrip("/")
    if not comments_url.endswith(".rss"):
        comments_url += ".rss"

    st, _, data = http_get(
        comments_url,
        headers={"Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9"},
    )
    if st != 200:
        return None

    try:
        root = ET.fromstring(data)
    except Exception:
        return None

    ns = {"a": "http://www.w3.org/2005/Atom"}
    out: List[dict] = []
    for e in root.findall("a:entry", ns):
        author = (e.findtext("a:author/a:name", default="", namespaces=ns) or "").strip()
        link_el = None
        for le in e.findall("a:link", ns):
            if le.get("rel") in (None, "alternate"):
                link_el = le
                break
        link = (link_el.get("href") if link_el is not None else "").strip()
        content = e.findtext("a:content", default="", namespaces=ns) or ""
        txt = html_to_text(content)
        txt = txt.replace("\n\n", " ").strip()
        if not txt:
            continue
        if len(txt) > 520:
            txt = txt[:520].rsplit(" ", 1)[0] + "…"
        out.append({"author": author, "excerpt": txt, "link": link or comments_url})
        if len(out) >= n:
            break
    return out


# -------------------- Anti-bubble picks --------------------


@dataclass(frozen=True)
class AntiBubbleSource:
    name: str
    rss_url: str
    homepage: str


ANTI_BUBBLE_SOURCES: List[AntiBubbleSource] = [
    AntiBubbleSource("Aeon", "https://aeon.co/feed", "https://aeon.co"),
    AntiBubbleSource("Arts & Letters Daily", "https://www.aldaily.com/rss.xml", "https://www.aldaily.com"),
    AntiBubbleSource("Nautilus", "https://nautil.us/feed/", "https://nautil.us"),
    AntiBubbleSource("Quanta Magazine", "https://www.quantamagazine.org/feed/", "https://www.quantamagazine.org"),
    AntiBubbleSource("Smithsonian", "https://www.smithsonianmag.com/rss/latest_articles/", "https://www.smithsonianmag.com"),
    AntiBubbleSource("The Conversation", "https://theconversation.com/us/articles.atom", "https://theconversation.com"),
    AntiBubbleSource("The Marginalian", "https://www.themarginalian.org/feed/", "https://www.themarginalian.org"),
    AntiBubbleSource("BBC Future", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "https://www.bbc.com"),
    AntiBubbleSource("JSTOR Daily", "https://daily.jstor.org/feed/", "https://daily.jstor.org"),
    AntiBubbleSource("Longreads", "https://longreads.com/feed/", "https://longreads.com"),
]

ANTI_BUBBLE_HISTORY_PATH = "/home/clawd/clawd/tmp/antibubble_history.json"


def _stable_shuffle(items: List[AntiBubbleSource], seed: str) -> List[AntiBubbleSource]:
    # Deterministic shuffle by sorting on hash(seed||item)
    def _key(it: AntiBubbleSource) -> str:
        h = hashlib.sha256((seed + "|" + it.rss_url).encode("utf-8")).hexdigest()
        return h

    return sorted(items, key=_key)


def _load_antibubble_history(max_items: int = 300) -> List[str]:
    try:
        if os.path.exists(ANTI_BUBBLE_HISTORY_PATH):
            j = json.loads(open(ANTI_BUBBLE_HISTORY_PATH, "r", encoding="utf-8").read())
            if isinstance(j, list):
                return [str(x) for x in j][-max_items:]
    except Exception:
        pass
    return []


def _save_antibubble_history(urls: List[str]) -> None:
    try:
        os.makedirs(os.path.dirname(ANTI_BUBBLE_HISTORY_PATH), exist_ok=True)
        with open(ANTI_BUBBLE_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(urls[-500:], f, ensure_ascii=False, indent=2)
    except Exception:
        return


def _fetch_rss_entries(rss_url: str, limit: int = 12) -> List[dict]:
    st, ctype, data = http_get(rss_url, headers={"Accept": "application/xml, application/rss+xml, application/atom+xml"})
    if st != 200:
        return []
    try:
        root = ET.fromstring(data)
    except Exception:
        return []

    entries: List[dict] = []
    # Atom
    if root.tag.endswith("feed"):
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for e in root.findall("a:entry", ns)[:limit]:
            title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
            link = ""
            for le in e.findall("a:link", ns):
                if le.get("rel") in (None, "alternate") and le.get("href"):
                    link = le.get("href").strip()
                    break
            entries.append({"title": title, "link": link})
        return entries

    # RSS 2.0
    channel = root.find("channel")
    if channel is None:
        return []
    for it in channel.findall("item")[:limit]:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        entries.append({"title": title, "link": link})
    return entries


def _url_fetch_seems_accessible(url: str) -> bool:
    # Best-effort paywall avoidance: if we can't even fetch HTML, don't include.
    if not url or not url.startswith("http"):
        return False
    try:
        st, ctype, data = http_get(url, headers={"Accept": "text/html,application/xhtml+xml"}, timeout=25)
        if st != 200:
            return False
        if "text/html" not in (ctype or ""):
            return True  # some sites serve as application/xhtml+xml etc; don't over-filter
        body = data[:200000].decode("utf-8", errors="ignore").lower()
        # crude paywall cues
        if "subscribe" in body and ("paywall" in body or "subscription" in body or "sign in" in body):
            return False
        if "enable javascript" in body and "cloudflare" in body:
            return False
        return True
    except Exception:
        return False


def pick_antibubble_items(now_utc: datetime, n: int = 3, min_domains: int = 2) -> List[dict]:
    seed = now_utc.date().isoformat()
    ordered_sources = _stable_shuffle(ANTI_BUBBLE_SOURCES, seed)

    history = _load_antibubble_history()
    history_set = set(history)

    picks: List[dict] = []
    used_domains: set[str] = set()

    # Try to gather more than n to enforce domain diversity.
    for src in ordered_sources:
        if len(picks) >= n and len(used_domains) >= min_domains:
            break

        for ent in _fetch_rss_entries(src.rss_url, limit=15):
            title = (ent.get("title") or "").strip()
            link = (ent.get("link") or "").strip()
            if not title or not link:
                continue
            if link in history_set:
                continue
            dom = domain_of(link)
            if not dom:
                continue
            # Prefer variety; don't let one domain dominate.
            if dom in used_domains and len(picks) < n:
                # Allow duplicates only if we still need to fill n.
                pass
            if not _url_fetch_seems_accessible(link):
                continue

            picks.append({"source": src.name, "title": title, "link": link, "domain": dom})
            used_domains.add(dom)
            break

    # If we failed domain diversity, keep best-effort.
    picks = picks[:n]

    # Update history
    if picks:
        new_hist = (history + [p["link"] for p in picks])
        _save_antibubble_history(new_hist)

    return picks


# -------------------- Readwise (recent highlights) --------------------


def fetch_readwise_recent(max_highlights: int = 2000, days: int = 90) -> dict:
    token_path = "/home/clawd/clawd/secrets/readwise_token.txt"
    if not os.path.exists(token_path):
        return {"status": "no_token", "highlights": []}
    token = open(token_path, "r", encoding="utf-8").read().strip()
    if not token:
        return {"status": "empty_token", "highlights": []}

    since_dt = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0)
    since = since_dt.isoformat()

    headers = {"Authorization": f"Token {token}", "Accept": "application/json"}
    url = f"https://readwise.io/api/v2/highlights/?page_size=100&updated__gt={quote(since)}"

    all_h: List[dict] = []
    page = 1
    while url and len(all_h) < max_highlights and page <= 50:
        st, _, data = http_get(url, headers=headers, timeout=60)
        if st != 200:
            return {"status": f"http_{st}", "highlights": all_h}
        j = json.loads(data.decode("utf-8"))
        for r in j.get("results", []):
            all_h.append(
                {
                    "text": (r.get("text") or "").strip(),
                    "tags": [t.get("name") for t in (r.get("tags") or []) if t.get("name")],
                    "title": r.get("book_title") or r.get("title") or "",
                    "author": r.get("book_author") or r.get("author") or "",
                    "source": r.get("source") or "",
                    "url": r.get("url") or "",
                    "highlighted_at": r.get("highlighted_at") or "",
                }
            )
            if len(all_h) >= max_highlights:
                break
        url = j.get("next")
        page += 1

    return {"status": "ok", "highlights": all_h, "since": since}


def main() -> None:
    now = datetime.now(timezone.utc)

    out: Dict[str, object] = {
        "generated_at": now.isoformat(),
        "hn": [],
        "reddit": [],
        "antibubble": [],
        "readwise": {},
    }

    out["hn"] = fetch_hn_top(5)
    for it in out["hn"]:  # type: ignore[assignment]
        it["top_comments"] = fetch_hn_top_comments_algolia(int(it["id"]), 3)

    subs = ["Biohackers", "blueprint_", "productivity", "whoop", "slatestarcodex"]
    reddit: List[dict] = []
    for sub in subs:
        r = fetch_reddit_sub_rss(sub, desired=3, max_fetch=40)
        for e in r.get("entries", []):
            cmts = fetch_reddit_comments_rss(e.get("link"), 3)
            e["top_comments"] = cmts
        reddit.append(r)
    out["reddit"] = reddit

    out["antibubble"] = pick_antibubble_items(now, n=3, min_domains=2)

    out["readwise"] = fetch_readwise_recent()

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
