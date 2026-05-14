#!/usr/bin/env python3
"""
build.py -- MediaWiki to GitHub Pages HTML generator
Called by .github/workflows/wiki-mirror.yml

Reads:  pages.txt        (list of changed page titles, one per line)
        .last_sync       (ISO timestamp of last run, optional)
Writes: <ArticleName>.html for each page
        search-index.json
        sitemap.xml
        .last_sync       (updated timestamp)
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import escape

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
API_BASE  = "https://wiki.free.nf/api.php"
SITE_BASE = "https://singularity-news.github.io"
SITE_NAME = "Singularity University Wiki"
LOGO_URL  = "https://raw.githubusercontent.com/singularity-news/wiki/57d6999f3aa1e574cc45619c5ec7b52592d42e61/assets/logo.png"
OG_IMAGE  = "https://raw.githubusercontent.com/singularity-news/wiki/57d6999f3aa1e574cc45619c5ec7b52592d42e61/assets/header.png"
GOOGLE_VERIFY = "D-u4byZG_DrIUxnTLQdS0BOTjJcwWmm_h-HwUXl8HO4"

# ------------------------------------------------------------------
# SHARED TOPBAR / SIDEBAR  (reused in every page)
# ------------------------------------------------------------------
SHARED_HEADER = """
<div class="overlay" id="overlay" aria-hidden="true"></div>

<header class="topbar" role="banner">
  <button class="icon-btn" id="menuToggle" aria-label="Open menu" aria-expanded="false" aria-controls="sidebar">
    <svg width="18" height="18" viewBox="0 0 18 18" fill="currentColor" aria-hidden="true">
      <rect y="2" width="18" height="2" rx="1"/>
      <rect y="8" width="18" height="2" rx="1"/>
      <rect y="14" width="18" height="2" rx="1"/>
    </svg>
  </button>
  <a href="index.html" class="topbar-logo">
    <img src="{logo}" alt="Logo" width="34" height="34" loading="lazy">
    <div class="logo-text">
      <span class="logo-name">Singularity University</span>
      <span class="logo-sub">KdK Krzb. Online Wiki</span>
    </div>
  </a>
  <div class="topbar-actions">
    <button class="icon-btn" id="themeToggle" aria-label="Toggle theme" title="Toggle theme">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="12" cy="12" r="5"/>
        <line x1="12" y1="1" x2="12" y2="3"/>
        <line x1="12" y1="21" x2="12" y2="23"/>
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
        <line x1="1" y1="12" x2="3" y2="12"/>
        <line x1="21" y1="12" x2="23" y2="12"/>
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
      </svg>
    </button>
    <a href="https://wiki.free.nf" class="icon-btn" target="_blank" rel="noopener" aria-label="MediaWiki">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="12" cy="12" r="10"/>
        <line x1="2" y1="12" x2="22" y2="12"/>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
      </svg>
    </a>
    <a href="https://github.com/singularity-news/wiki" class="icon-btn" target="_blank" rel="noopener" aria-label="GitHub">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.54-1.38-1.33-1.74-1.33-1.74-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.8 1.3 3.48.99.11-.78.42-1.3.76-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.12-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 3-.4c1.02.005 2.04.14 3 .4 2.28-1.55 3.29-1.23 3.29-1.23.66 1.66.25 2.88.12 3.18.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.63-5.49 5.92.43.37.82 1.1.82 2.22v3.29c0 .32.22.69.83.57C20.57 21.8 24 17.3 24 12 24 5.37 18.63 0 12 0z"/>
      </svg>
    </a>
  </div>
</header>

<aside class="sidebar" id="sidebar" role="navigation" aria-label="Article navigation">
  <div class="sidebar-search">
    <input type="search" id="searchInput" placeholder="Search articles..." aria-label="Search articles" autocomplete="off">
  </div>
  <div class="sidebar-section">
    <div class="sidebar-label">Articles</div>
    <ul id="articleList" role="list">
      <li class="no-results">Loading...</li>
    </ul>
  </div>
  <nav class="sidebar-links">
    <a href="index.html">&#127968; Encyclopedia</a>
    <a href="https://kdk-university.netlify.app/" target="_blank" rel="noopener">&#127891; KdK University</a>
    <a href="https://electric-paradise.start.page" target="_blank" rel="noopener">&#9889; Electric Paradise</a>
    <a href="https://singularity-news.github.io/" target="_blank" rel="noopener">&#128240; Singularity News</a>
    <a href="https://wiki.free.nf" target="_blank" rel="noopener">&#128214; MediaWiki Live</a>
    <a href="https://github.com/singularity-news/wiki" target="_blank" rel="noopener">&#128230; GitHub</a>
  </nav>
</aside>
""".strip().format(logo=LOGO_URL)

SHARED_FOOTER = """
<footer class="footer" role="contentinfo">
  <p>
    &copy; 2026 Singularity University Wiki
    <span class="footer-sep">&middot;</span>
    <a href="https://github.com/singularity-news/wiki" target="_blank" rel="noopener">GitHub</a>
    <span class="footer-sep">&middot;</span>
    <a href="https://wiki.free.nf" target="_blank" rel="noopener">MediaWiki Live</a>
    <span class="footer-sep">&middot;</span>
    <a href="sitemap.xml">Sitemap</a>
  </p>
</footer>
""".strip()

# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def safe_filename(title):
    """Convert a MediaWiki title to a safe flat filename (no subfolders)."""
    s = title.replace(" ", "_")
    s = re.sub(r"[^\w\-]", "", s)
    return s


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "wiki-mirror-bot/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"  [WARN] fetch failed: {url} -> {exc}", file=sys.stderr)
        return None


def get_page_html(title):
    encoded = urllib.parse.quote(title, safe="")
    url = f"{API_BASE}?action=parse&page={encoded}&prop=text&format=json"
    data = fetch_json(url)
    if data and "parse" in data:
        return data["parse"]["text"].get("*", "")
    return None


def strip_tags(html_text):
    return re.sub(r"<[^>]+>", " ", html_text)


def make_description(html_body):
    plain = strip_tags(html_body)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain[:300]


def make_schema(title_esc, safe, desc_esc):
    obj = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title_esc,
        "description": desc_esc,
        "url": f"{SITE_BASE}/{safe}.html",
        "image": OG_IMAGE,
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "url": f"{SITE_BASE}/"
        }
    }
    return json.dumps(obj, ensure_ascii=False)


def render_article_page(title, html_body):
    """Return a complete HTML page string for one article."""
    safe = safe_filename(title)
    title_esc = escape(title)
    desc = make_description(html_body)
    desc_esc = escape(desc)
    wiki_url = f"https://wiki.free.nf/index.php?title={urllib.parse.quote(title, safe='')}"
    page_url = f"{SITE_BASE}/{safe}.html"
    schema = make_schema(title_esc, safe, desc_esc)

    page = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-site-verification" content="{GOOGLE_VERIFY}">
<title>{title_esc} &mdash; {escape(SITE_NAME)}</title>
<meta name="description" content="{desc_esc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{page_url}">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="manifest" href="/site.webmanifest">
<meta property="og:type" content="article">
<meta property="og:title" content="{title_esc} &mdash; {escape(SITE_NAME)}">
<meta property="og:description" content="{desc_esc}">
<meta property="og:image" content="{OG_IMAGE}">
<meta property="og:url" content="{page_url}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{schema}</script>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>

{SHARED_HEADER}

<div class="page-wrap">

  <nav class="breadcrumbs" id="breadcrumbs" aria-label="Page path"></nav>

  <div class="content-wrap">

    <aside class="toc-col" aria-label="Table of contents">
      <div class="toc-box">
        <div class="toc-title">Contents</div>
        <ul id="toc" role="list"></ul>
      </div>
    </aside>

    <main class="article-col" id="main-content">
      <div class="article-box">
        <h1>{title_esc}</h1>
        <div class="article-meta">
          <span>Source: <a href="{wiki_url}" target="_blank" rel="noopener">MediaWiki</a></span>
        </div>
        {html_body}
      </div>
    </main>

  </div>

  {SHARED_FOOTER}

</div>

<script src="assets/app.js"></script>
</body>
</html>"""
    return page


# ------------------------------------------------------------------
# SEARCH INDEX
# ------------------------------------------------------------------

def rebuild_search_index():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = []
    for fname in sorted(os.listdir(".")):
        if not fname.endswith(".html"):
            continue
        if fname in ("index.html", "template.html"):
            continue
        title = fname[:-5].replace("_", " ")
        try:
            with open(fname, encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            continue
        plain = strip_tags(raw)
        plain = re.sub(r"\s+", " ", plain).strip()
        excerpt = plain[:300]
        entries.append({
            "title": title,
            "file": fname,
            "text": excerpt,
            "date": today
        })
    with open("search-index.json", "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"  search-index.json: {len(entries)} entries written.")


# ------------------------------------------------------------------
# SITEMAP
# ------------------------------------------------------------------

def rebuild_sitemap():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f'  <url><loc>{SITE_BASE}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>',
    ]
    for fname in sorted(os.listdir(".")):
        if not fname.endswith(".html"):
            continue
        if fname in ("index.html", "template.html"):
            continue
        lines.append(
            f'  <url><loc>{SITE_BASE}/{fname}</loc>'
            f'<lastmod>{today}</lastmod>'
            f'<changefreq>weekly</changefreq>'
            f'<priority>0.8</priority></url>'
        )
    lines.append("</urlset>")
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  sitemap.xml updated.")


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------

def main():
    pages_file = "pages.txt"
    if not os.path.exists(pages_file):
        print("pages.txt not found -- nothing to do.")
        return

    with open(pages_file, encoding="utf-8") as f:
        titles = [line.strip() for line in f if line.strip()]

    if not titles:
        print("pages.txt is empty -- nothing to do.")
        return

    # Filter out MediaWiki-internal namespaces
    skip_prefixes = ("Special:", "MediaWiki:", "File:", "Template:", "Category:", "Help:", "User:")
    titles = [t for t in titles if not any(t.startswith(p) for p in skip_prefixes)]

    print(f"Building {len(titles)} article(s)...")

    errors = 0
    for title in titles:
        print(f"  Rendering: {title}")
        html_body = get_page_html(title)
        if not html_body:
            print(f"  [SKIP] Could not fetch HTML for: {title}")
            errors += 1
            continue

        page_html = render_article_page(title, html_body)
        safe = safe_filename(title)
        filename = f"{safe}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(page_html)
        print(f"  OK -> {filename}")

    print("Rebuilding search-index.json and sitemap.xml...")
    rebuild_search_index()
    rebuild_sitemap()

    # Update .last_sync
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(".last_sync", "w") as f:
        f.write(ts + "\n")
    print(f"  .last_sync set to {ts}")

    if errors:
        print(f"[WARN] {errors} page(s) could not be rendered.")

    print("Done.")


if __name__ == "__main__":
    main()
