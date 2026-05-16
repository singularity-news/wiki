#!/usr/bin/env python3
"""
build.py — Singularity University Wiki
MediaWiki XML export → static HTML encyclopedia

Generates:
- ArticleName.html
- index.html
- search.html
- search-index.json
- sitemap.xml
- robots.txt

Requirements:
- Python 3.10+
- pandoc installed
"""

import html
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import hashlib
import xml.etree.ElementTree as ET

from collections import Counter
from datetime import datetime, timezone
from urllib.parse import unquote

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

XML_PATH = "backup/wiki.xml"
TEMPLATE_PATH = "template.html"
OUTPUT_DIR = "."
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

GOOGLE_VERIFY = "D-u4byZG_DrIUxnTLQdS0BOTjJcwWmm_h-HwUXl8HO4"

LOGO_URL = "https://raw.githubusercontent.com/singularity-news/wiki/main/assets/logo.png"
HEADER_IMG = "https://raw.githubusercontent.com/singularity-news/wiki/main/assets/header.png"

_env_base = os.environ.get("PAGES_BASE", "").strip()

if _env_base:
    BASE = _env_base.rstrip("/")
else:
    _repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in _repo:
        owner, repo = _repo.split("/", 1)
        BASE = f"https://{owner}.github.io/{repo}"
    else:
        BASE = "https://singularity-news.github.io/wiki"

STOP = set("""
der die das und oder aber wenn dann weil wie was wer wo warum wieso
ein eine einer eines einem einen im in ins am an auf aus bei mit nach
von vom zum zur ueber unter fuer gegen ohne um als ist sind war waren
nicht kein keine keinen keiner

the a an and or but if then because how what who where why
in on at to from for with without of is are was were be been
being not no yes have has had will would could should may might

this that these those it its they them their

article page wiki html div span href src img table code pre ref cite
""".split())

SKIP_PREFIXES = (
    "Special:",
    "File:",
    "Template:",
    "MediaWiki:",
    "Category:",
    "Help:",
    "User:",
    "Talk:",
    "Wikipedia:"
)

# ─────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────

FOOTER_LINKS = [
    ("🌐", "World Succession Deed", "https://world.rf.gd"),
    ("⚡", "Electric Technocracy", "https://ep.ct.ws"),
    ("🎥", "Videos", "https://videos.xo.je"),
    ("🎙️", "Podcast", "https://nwo.likesyou.org"),
    ("🚀", "Electric Paradise", "https://electric-paradise.start.page"),
]

def build_footer_html() -> str:
    links = []

    for icon, label, url in FOOTER_LINKS:
        links.append(
            f'''
<a class="footer-link" href="{url}" target="_blank" rel="noopener">
  <span class="footer-icon">{icon}</span>
  <span>{label}</span>
</a>
'''
        )

    return f"""
<footer class="footer">
  <div class="footer-links">
    {''.join(links)}
  </div>

  <div class="footer-bottom">
    © 2026 Singularity University Wiki · KdK Kreuzberg
  </div>
</footer>
"""

FOOTER_HTML = build_footer_html()

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag

def sanitize_html(fragment: str) -> str:
    """
    Remove dangerous HTML.
    """

    fragment = re.sub(
        r"(?is)<script.*?>.*?</script>",
        "",
        fragment
    )

    fragment = re.sub(
        r"(?is)<iframe.*?>.*?</iframe>",
        "",
        fragment
    )

    fragment = re.sub(
        r'on\w+="[^"]*"',
        "",
        fragment
    )

    fragment = re.sub(
        r"javascript:",
        "",
        fragment,
        flags=re.IGNORECASE
    )

    return fragment

def safe_filename(title: str) -> str:
    """
    Generate collision-safe filenames.
    """

    normalized = unicodedata.normalize("NFKC", title)

    slug = re.sub(r"[^\w\- ]+", "", normalized)
    slug = slug.strip().replace(" ", "_")

    if not slug:
        slug = "Untitled"

    digest = hashlib.md5(title.encode("utf-8")).hexdigest()[:6]

    return f"{slug}-{digest}.html"

def strip_html_tags(s: str) -> str:

    s = re.sub(r"(?is)<script.*?>.*?</script>", " ", s)
    s = re.sub(r"(?is)<style.*?>.*?</style>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)

    s = html.unescape(s)

    return re.sub(r"\s+", " ", s).strip()

def top_keywords(text: str, n: int = 12) -> list[str]:

    words = re.findall(
        r"[A-Za-zÀ-ÿ0-9_\-']{3,}",
        text.lower()
    )

    words = [
        w for w in words
        if w not in STOP and not w.isdigit()
    ]

    return [
        w for w, _ in Counter(words).most_common(n)
    ]

# ─────────────────────────────────────────────────────────────
# INTERNAL LINKS
# ─────────────────────────────────────────────────────────────

def rewrite_internal_links(fragment: str, title_to_file: dict) -> str:

    def repl(match: re.Match) -> str:

        raw_href = match.group(1)

        href = unquote(raw_href)
        href = unicodedata.normalize("NFKC", href)

        for prefix in ("/wiki/", "./", "../"):
            if href.startswith(prefix):
                href = href[len(prefix):]

        bare = href.split("#", 1)[0]
        bare = bare.split("?", 1)[0]
        bare = bare.replace("_", " ").strip()

        if bare in title_to_file:

            fragment_part = ""

            if "#" in href:
                fragment_part = "#" + href.split("#", 1)[1]

            return f'href="{title_to_file[bare]}{fragment_part}"'

        return f'href="{raw_href}"'

    return re.sub(
        r'href="([^"]+)"',
        repl,
        fragment
    )

# ─────────────────────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────────────────────

def make_schema_json(title, description, canonical):

    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "dateModified": TODAY,
        "image": HEADER_IMG,
        "mainEntityOfPage": canonical,
        "publisher": {
            "@type": "Organization",
            "name": "Singularity University Wiki",
            "url": BASE
        }
    }

    return json.dumps(data, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────
# PREFLIGHT
# ─────────────────────────────────────────────────────────────

def preflight() -> str:

    if not os.path.isfile(XML_PATH):
        print(f"ERROR: Missing {XML_PATH}")
        sys.exit(2)

    if not os.path.isfile(TEMPLATE_PATH):
        print(f"ERROR: Missing {TEMPLATE_PATH}")
        sys.exit(2)

    template = open(
        TEMPLATE_PATH,
        encoding="utf-8"
    ).read()

    if "{html_body}" not in template:
        print("ERROR: template missing {html_body}")
        sys.exit(2)

    if "{footer}" not in template:
        print("ERROR: template missing {footer}")
        sys.exit(2)

    result = subprocess.run(
        ["pandoc", "--version"],
        capture_output=True
    )

    if result.returncode != 0:
        print("ERROR: pandoc not installed")
        sys.exit(2)

    return template

# ─────────────────────────────────────────────────────────────
# XML PARSING
# ─────────────────────────────────────────────────────────────

def parse_wiki_xml():

    pages = []

    context = ET.iterparse(
        XML_PATH,
        events=("end",)
    )

    for event, elem in context:

        if strip_ns(elem.tag) != "page":
            continue

        title_el = elem.find(".//{*}title")
        ns_el = elem.find(".//{*}ns")
        text_el = elem.find(".//{*}text")

        title = (
            title_el.text.strip()
            if title_el is not None and title_el.text
            else ""
        )

        namespace = (
            ns_el.text.strip()
            if ns_el is not None and ns_el.text
            else "0"
        )

        text = (
            text_el.text
            if text_el is not None and text_el.text
            else ""
        )

        if (
            namespace == "0"
            and title
            and not any(title.startswith(p) for p in SKIP_PREFIXES)
        ):
            pages.append((title, text))

        elem.clear()

    return pages

# ─────────────────────────────────────────────────────────────
# RENDERING
# ─────────────────────────────────────────────────────────────

def render_pages(pages, template, title_to_file):

    search_index = []
    rendered = 0

    with tempfile.TemporaryDirectory() as tmp:

        for idx, (title, wikitext) in enumerate(pages, 1):

            filename = title_to_file[title]
            out_path = os.path.join(OUTPUT_DIR, filename)

            tmp_wiki = os.path.join(tmp, f"{idx}.wiki")
            tmp_html = os.path.join(tmp, f"{idx}.html")

            with open(tmp_wiki, "w", encoding="utf-8") as f:
                f.write(wikitext)

            result = subprocess.run(
                [
                    "pandoc",
                    tmp_wiki,
                    "-f", "mediawiki",
                    "-t", "html",
                    "--wrap=none",
                    "-o", tmp_html
                ],
                capture_output=True
            )

            if result.returncode != 0:
                print(f"[WARN] Failed: {title}")
                continue

            fragment = open(
                tmp_html,
                encoding="utf-8"
            ).read()

            fragment = sanitize_html(fragment)
            fragment = rewrite_internal_links(
                fragment,
                title_to_file
            )

            plain_text = strip_html_tags(fragment)

            description = plain_text[:300]

            keywords = top_keywords(plain_text)

            canonical = f"{BASE}/{filename}"

            schema_json = make_schema_json(
                title,
                description,
                canonical
            )

            head_meta = f"""
<title>{html.escape(title)} — Singularity University Wiki</title>

<meta name="description" content="{html.escape(description)}">
<meta name="keywords" content="{html.escape(', '.join(keywords))}">
<link rel="canonical" href="{html.escape(canonical)}">

<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{html.escape(canonical)}">
<meta property="og:image" content="{html.escape(HEADER_IMG)}">

<meta name="twitter:card" content="summary_large_image">

<meta name="google-site-verification" content="{GOOGLE_VERIFY}">

<script type="application/ld+json">
{schema_json}
</script>
"""

            page_html = template.replace(
                "{html_body}",
                fragment
            )

            page_html = page_html.replace(
                "{footer}",
                FOOTER_HTML
            )

            if "</head>" in page_html:
                page_html = page_html.replace(
                    "</head>",
                    head_meta + "\n</head>",
                    1
                )

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(page_html)

            search_index.append({
                "title": title,
                "file": filename,
                "text": plain_text[:500],
                "date": TODAY
            })

            rendered += 1

            print(f"[OK] {filename}")

    return search_index, rendered

# ─────────────────────────────────────────────────────────────
# INDEX PAGE
# ─────────────────────────────────────────────────────────────

INDEX_HTML = """
<section class="hero">
  <h1>Singularity University Encyclopedia</h1>

  <p>
    Encyclopedia of Juridical Singularity,
    Electric Technocracy,
    Age of Transition,
    Homo Nexus,
    AI Civilization
    and post-scarcity governance.
  </p>
</section>

<section class="index-section">

  <h2>Articles</h2>

  <div id="indexGrid" class="article-grid"></div>

</section>
"""

def write_index_html(template):

    page_html = template.replace(
        "{html_body}",
        INDEX_HTML
    )

    page_html = page_html.replace(
        "{footer}",
        FOOTER_HTML
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page_html)

# ─────────────────────────────────────────────────────────────
# SEARCH PAGE
# ─────────────────────────────────────────────────────────────

SEARCH_HTML = """
<div class="search-page">

<h1>Search Articles</h1>

<input
  type="search"
  id="pageSearchInput"
  placeholder="Search encyclopedia..."
>

<div id="searchResults"></div>

</div>
"""

def write_search_html(template):

    page_html = template.replace(
        "{html_body}",
        SEARCH_HTML
    )

    page_html = page_html.replace(
        "{footer}",
        FOOTER_HTML
    )

    with open("search.html", "w", encoding="utf-8") as f:
        f.write(page_html)

# ─────────────────────────────────────────────────────────────
# SEARCH INDEX
# ─────────────────────────────────────────────────────────────

def write_search_index(search_index):

    with open(
        "search-index.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            search_index,
            f,
            ensure_ascii=False,
            indent=2
        )

# ─────────────────────────────────────────────────────────────
# SITEMAP
# ─────────────────────────────────────────────────────────────

def write_sitemap():

    html_files = sorted([
        f for f in os.listdir(".")
        if f.endswith(".html")
        and f != "template.html"
    ])

    with open("sitemap.xml", "w", encoding="utf-8") as f:

        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')

        f.write(
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        )

        for fn in html_files:

            loc = html.escape(f"{BASE}/{fn}")

            priority = "1.0" if fn == "index.html" else "0.7"

            f.write(
                f"""
<url>
  <loc>{loc}</loc>
  <lastmod>{TODAY}</lastmod>
  <changefreq>monthly</changefreq>
  <priority>{priority}</priority>
</url>
"""
            )

        f.write("</urlset>")

# ─────────────────────────────────────────────────────────────
# ROBOTS
# ─────────────────────────────────────────────────────────────

def write_robots():

    with open("robots.txt", "w", encoding="utf-8") as f:

        f.write(
            f"""User-agent: *
Allow: /
Sitemap: {BASE}/sitemap.xml
"""
        )

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():

    print("=" * 60)
    print("Singularity University Wiki Builder")
    print("=" * 60)

    template = preflight()

    print("\n[1] Parsing XML")

    pages = parse_wiki_xml()

    print(f"[INFO] Parsed {len(pages)} pages")

    if not pages:
        print("ERROR: No pages found")
        sys.exit(4)

    title_to_file = {}
    used_files = set()

    for title, _ in pages:

        filename = safe_filename(title)

        if filename in used_files:
            print(f"ERROR: Duplicate filename {filename}")
            sys.exit(5)

        used_files.add(filename)

        title_to_file[title] = filename
        title_to_file[title.replace("_", " ")] = filename
        title_to_file[title.replace(" ", "_")] = filename

    print("\n[2] Rendering Articles")

    search_index, rendered = render_pages(
        pages,
        template,
        title_to_file
    )

    print(f"[INFO] Rendered {rendered} pages")

    print("\n[3] Writing index.html")
    write_index_html(template)

    print("\n[4] Writing search.html")
    write_search_html(template)

    print("\n[5] Writing search-index.json")
    write_search_index(search_index)

    print("\n[6] Writing sitemap.xml")
    write_sitemap()

    print("\n[7] Writing robots.txt")
    write_robots()

    print("\nBUILD COMPLETE")

if __name__ == "__main__":
    main()
