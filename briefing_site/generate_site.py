#!/usr/bin/env python3
"""Generate a small static site from briefing_site/posts/*.md.

No external dependencies.
- Produces dist/index.html, dist/archive.html, dist/rss.xml
- Produces dist/posts/YYYY-MM-DD/index.html
- Inlines CSS/JS for offline-ish single-file behavior.

Markdown support is intentionally limited:
- #, ##, ### headings
- paragraphs
- unordered lists (- / *)
- inline links: [text](url)
"""

from __future__ import annotations

import datetime as dt
import html
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"
DIST_DIR = ROOT / "dist"
TEMPL_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def slug_for_date(d: str) -> str:
    # expects YYYY-MM-DD
    return d


def parse_front_matter(md: str) -> Tuple[Dict[str, str], str]:
    md = md.lstrip("\ufeff")
    if not md.startswith("---\n"):
        return {}, md
    end = md.find("\n---\n", 4)
    if end == -1:
        return {}, md
    raw = md[4:end].strip("\n")
    body = md[end + 5 :]
    meta: Dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip().strip('"')
    return meta, body


def md_inline(s: str) -> str:
    s = html.escape(s, quote=False)

    def repl(m: re.Match) -> str:
        text = html.escape(m.group(1), quote=False)
        url = html.escape(m.group(2), quote=True)
        return f'<a href="{url}">{text}</a>'

    return LINK_RE.sub(repl, s)


def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out: List[str] = []

    def flush_paragraph(buf: List[str]):
        if not buf:
            return
        text = " ".join(x.strip() for x in buf).strip()
        if text:
            out.append(f"<p>{md_inline(text)}</p>")
        buf.clear()

    in_list = False
    para_buf: List[str] = []

    for line in lines:
        raw = line.rstrip("\n")
        stripped = raw.strip()

        if not stripped:
            flush_paragraph(para_buf)
            if in_list:
                out.append("</ul>")
                in_list = False
            continue

        if stripped.startswith("### "):
            flush_paragraph(para_buf)
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h3>{md_inline(stripped[4:])}</h3>")
            continue

        if stripped.startswith("## "):
            flush_paragraph(para_buf)
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h2>{md_inline(stripped[3:])}</h2>")
            continue

        if stripped.startswith("# "):
            flush_paragraph(para_buf)
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h2>{md_inline(stripped[2:])}</h2>")
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph(para_buf)
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{md_inline(stripped[2:])}</li>")
            continue

        if stripped == "---" or stripped == "***":
            flush_paragraph(para_buf)
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("<hr />")
            continue

        # paragraph line
        para_buf.append(raw)

    flush_paragraph(para_buf)
    if in_list:
        out.append("</ul>")

    return "\n".join(out)


def load_assets() -> Tuple[str, str, str]:
    base = read_text(TEMPL_DIR / "base.html")
    css = read_text(STATIC_DIR / "theme.css")
    js = read_text(STATIC_DIR / "theme.js")
    return base, css, js


def render_page(base: str, css: str, js: str, title: str, body: str, root: str) -> str:
    return (
        base.replace("{{TITLE}}", html.escape(title))
        .replace("{{CSS}}", css)
        .replace("{{JS}}", js)
        .replace("{{BODY}}", body)
        .replace("{{ROOT}}", root)
    )


def parse_date_from_filename(p: Path) -> Optional[dt.date]:
    m = re.match(r"(\d{4}-\d{2}-\d{2})\.md$", p.name)
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except Exception:
        return None


def rfc3339(d: dt.date) -> str:
    # noon UTC
    return dt.datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=dt.timezone.utc).isoformat()


def build_rss(posts: List[Dict[str, str]], site_url: str) -> str:
    items = []
    for p in posts:
        url = f"{site_url}{p['url']}"
        items.append(
            "\n".join(
                [
                    "<item>",
                    f"  <title>{html.escape(p['title'])}</title>",
                    f"  <link>{html.escape(url)}</link>",
                    f"  <guid>{html.escape(url)}</guid>",
                    f"  <pubDate>{html.escape(p['pubDate'])}</pubDate>",
                    "</item>",
                ]
            )
        )

    return "\n".join(
        [
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            "<rss version=\"2.0\">",
            "<channel>",
            "  <title>Morning Briefing</title>",
            f"  <link>{html.escape(site_url)}/</link>",
            "  <description>Daily morning briefing</description>",
            "  <language>en</language>",
            *items,
            "</channel>",
            "</rss>",
        ]
    )


def main() -> int:
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    base, css, js = load_assets()

    posts: List[Dict[str, str]] = []

    for p in sorted(POSTS_DIR.glob("*.md")):
        d = parse_date_from_filename(p)
        if not d:
            continue
        meta, body_md = parse_front_matter(read_text(p))
        title = meta.get("title") or f"Morning briefing — {d.isoformat()}"
        content_html = md_to_html(body_md)

        body = (
            f"<div class=\"post-title\">{html.escape(title)}</div>\n"
            f"<div class=\"post-meta\">{d.strftime('%b %d, %Y')} • Roundup</div>\n"
            f"<div class=\"prose\">{content_html}</div>\n"
        )

        out_dir = DIST_DIR / "posts" / slug_for_date(d.isoformat())
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(
            render_page(base, css, js, title, body, root="../.."), encoding="utf-8"
        )

        posts.append(
            {
                "date": d.isoformat(),
                "title": title,
                "url": f"/posts/{slug_for_date(d.isoformat())}/",
                "pubDate": dt.datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=dt.timezone.utc).strftime(
                    "%a, %d %b %Y %H:%M:%S %z"
                ),
            }
        )

    posts.sort(key=lambda x: x["date"], reverse=True)

    # Index
    items = []
    for p in posts[:30]:
        items.append(
            "\n".join(
                [
                    '<div class="index-item">',
                    f'  <div class="t"><a href=".{p["url"]}">{html.escape(p["title"])}</a></div>',
                    f'  <div class="m">{html.escape(p["date"])}</div>',
                    "</div>",
                ]
            )
        )

    index_body = (
        "<div class=\"post-title\">Morning Briefing</div>\n"
        "<div class=\"post-meta\">Daily entries • Offline-friendly</div>\n"
        "<div class=\"index-list\">\n" + "\n".join(items) + "\n</div>"
    )
    (DIST_DIR / "index.html").write_text(
        render_page(base, css, js, "Morning Briefing", index_body, root="."), encoding="utf-8"
    )

    # Archive
    arch_items = []
    for p in posts:
        arch_items.append(
            f'<div class="index-item"><div class="t"><a href=".{p["url"]}">{html.escape(p["title"])}</a></div><div class="m">{html.escape(p["date"])}</div></div>'
        )
    archive_body = (
        "<div class=\"post-title\">Archive</div>\n"
        "<div class=\"post-meta\">All entries</div>\n"
        "<div class=\"index-list\">\n" + "\n".join(arch_items) + "\n</div>"
    )
    (DIST_DIR / "archive.html").write_text(
        render_page(base, css, js, "Archive", archive_body, root="."), encoding="utf-8"
    )

    # RSS (site_url is filled in by GitHub Pages; use relative placeholder for now)
    # Users can replace this once they know the final Pages URL.
    site_url = os.environ.get("SITE_URL", "https://example.github.io/morning-briefing")
    (DIST_DIR / "rss.xml").write_text(build_rss(posts[:30], site_url), encoding="utf-8")

    print(f"Generated {len(posts)} posts -> {DIST_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
