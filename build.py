#!/usr/bin/env python3
"""
build.py
Singularity University Wiki -- MediaWiki XML to static HTML
------------------------------------------------------------------------
Reads   : backup/wiki.xml   (MediaWiki XML export, any namespace)
          template.html      (must contain placeholder: {html_body})
Writes  : <ArticleName>.html  (one file per wiki page, flat in root)
          search-index.json
          sitemap.xml
          .last_sync
Requires: pandoc (apt install pandoc)
          Python 3.10+ standard library only
------------------------------------------------------------------------
"""

import gzip
import html
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone

# -----------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------

XML_PATH      = "backup/wiki.xml"
TEMPLATE_PATH = "template.html"
OUTPUT_DIR    = "."          # flat root, all .html files here
SITEMAP_MAX   = 50_000       # split sitemap after this many URLs

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Base URL: env override > GitHub Actions > fallback
_env_base = os.environ.get("PAGES_BASE", "").strip()
if _env_base:
    BASE = _env_base.rstrip("/")
else:
    _repo = os.environ.get("GITHUB_REPOSITORY", "")
    if _repo and "/" in _repo:
        _owner, _repo_name = _repo.split("/", 1)
        BASE = f"https://{_owner}.github.io/{_repo_name}"
    else:
        BASE = "https://singularity-news.github.io/wiki"

GOOGLE_VERIFY = "D-u4byZG_DrIUxnTLQdS0BOTjJcwWmm_h-HwUXl8HO4"

# Stopwords for keyword extraction
STOP = set(
    "der die das und oder aber wenn dann weil wie was wer wo warum wieso ein eine einer "
    "eines einem einen im in ins am an auf aus bei mit nach von vom zum zur ueber unter "
    "fuer gegen ohne um als ist sind war waren nicht kein keine keinen keiner "
    "the a an and or but if then because how what who where why in on at to from for "
    "with without of is are was were be been being not no yes have has had will would "
    "could should may might this that these those it its they them their "
    "article page wiki html div span href src img table code pre ref cite".split()
)

# -----------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------

def strip_ns(tag: str) -> str:
    """Remove XML namespace prefix from tag name."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def safe_filename(title: str) -> str:
    """Convert a wiki page title to a safe flat filename."""
    t = (title or "").strip()
    t = unicodedata.normalize("NFKC", t)
    # Keep alphanumeric, hyphens, underscores, spaces
    t = re.sub(r"[^\w\- ]+", "", t)
    t = t.replace(" ", "_")
    return (t or "Untitled") + ".html"


def strip_html_tags(s: str) -> str:
    """Remove all HTML tags and decode entities; collapse whitespace."""
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", s)
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def top_keywords(text: str, n: int = 12) -> list[str]:
    """Extract top-N significant words by frequency."""
    words = re.findall(r"[A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u024F0-9_'-]{3,}", text.lower())
    words = [w for w in words if w not in STOP and not w.isdigit()]
    counter = Counter(words)
    return [w for w, _ in counter.most_common(n)]


def rewrite_internal_links(fragment: str, title_to_file: dict) -> str:
    """Rewrite /wiki/Name and relative links to local ArticleName.html."""
    def repl(m: re.Match) -> str:
        href = m.group(1)
        raw  = href
        for prefix in ("/wiki/", "./", "../"):
            if href.startswith(prefix):
                href = href[len(prefix):]
                break
        # Strip fragment and query for lookup
        bare = href.split("#", 1)[0].split("?", 1)[0]
        bare = bare.replace(" ", "_")
        if bare in title_to_file:
            # Preserve fragment
            frag = ("#" + href.split("#", 1)[1]) if "#" in href else ""
            return f'href="{title_to_file[bare]}{frag}"'
        return f'href="{raw}"'

    return re.sub(r'href="([^"]+)"', repl, fragment)


def make_schema_json(title: str, description: str, canonical: str) -> str:
    obj = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "dateModified": TODAY,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical
        },
        "publisher": {
            "@type": "Organization",
            "name": "Singularity University Wiki",
            "url": BASE + "/"
        }
    }
    return json.dumps(obj, ensure_ascii=False)


# -----------------------------------------------------------------------
# PRE-FLIGHT CHECKS
# -----------------------------------------------------------------------

def preflight() -> str:
    """Check required files exist and template is valid. Returns template text."""
    if not os.path.isfile(XML_PATH):
        print(f"ERROR: {XML_PATH} not found", file=sys.stderr)
        sys.exit(2)
    if not os.path.isfile(TEMPLATE_PATH):
        print(f"ERROR: {TEMPLATE_PATH} not found", file=sys.stderr)
        sys.exit(2)
    tpl = open(TEMPLATE_PATH, encoding="utf-8").read()
    if "{html_body}" not in tpl:
        print("ERROR: template.html must contain {html_body}", file=sys.stderr)
        sys.exit(2)
    # Check pandoc
    result = subprocess.run(["pandoc", "--version"], capture_output=True)
    if result.returncode != 0:
        print("ERROR: pandoc not found -- install with: apt install pandoc", file=sys.stderr)
        sys.exit(2)
    print(f"[OK] XML:      {XML_PATH}")
    print(f"[OK] Template: {TEMPLATE_PATH}")
    print(f"[OK] Base URL: {BASE}")
    return tpl


# -----------------------------------------------------------------------
# XML PARSING (streaming)
# -----------------------------------------------------------------------

def parse_wiki_xml() -> list[tuple[str, str]]:
    """
    Stream-parse backup/wiki.xml.
    Returns list of (title, wikitext) for all main-namespace pages.
    Skips Special:, File:, Template:, MediaWiki:, Category:, Help: pages.
    """
    SKIP_PREFIXES = (
        "Special:", "File:", "Template:", "MediaWiki:",
        "Category:", "Help:", "User:", "Talk:", "Wikipedia:"
    )
    pages = []
    ns_filter = None   # will hold the detected main namespace number

    try:
        for event, elem in ET.iterparse(XML_PATH, events=("end",)):
            tag = strip_ns(elem.tag)

            # Detect main namespace (ns=0)
            if tag == "namespace":
                if elem.get("key") == "0":
                    # main namespace canonical name (often empty)
                    pass

            if tag == "page":
                title_el = elem.find(".//{*}title")
                ns_el    = elem.find(".//{*}ns")
                text_el  = elem.find(".//{*}text")

                title    = (title_el.text or "").strip() if title_el is not None else ""
                ns       = (ns_el.text or "").strip()    if ns_el is not None else "0"
                wikitext = (text_el.text or "")           if text_el is not None else ""

                # Only include main namespace (ns=0)
                if ns != "0":
                    elem.clear()
                    continue

                # Skip internal pages by title prefix
                if any(title.startswith(p) for p in SKIP_PREFIXES):
                    elem.clear()
                    continue

                if title:
                    pages.append((title, wikitext))

                # Free memory
                elem.clear()

    except ET.ParseError as exc:
        print(f"ERROR: XML parse error: {exc}", file=sys.stderr)
        sys.exit(3)
    except Exception as exc:
        print(f"ERROR: Unexpected XML error: {exc}", file=sys.stderr)
        sys.exit(3)

    return pages


# -----------------------------------------------------------------------
# HTML RENDERING
# -----------------------------------------------------------------------

def render_pages(
    pages: list[tuple[str, str]],
    template: str,
    title_to_file: dict
) -> tuple[list[dict], int]:
    """
    Convert each (title, wikitext) pair to HTML using pandoc.
    Returns (search_index, rendered_count).
    """
    search_index = []
    rendered     = 0
    errors       = 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        for i, (title, wikitext) in enumerate(pages, 1):
            filename  = title_to_file[title]
            out_path  = os.path.join(OUTPUT_DIR, filename)
            tmp_wiki  = os.path.join(tmp_dir, f"{i}.wiki")
            tmp_html  = os.path.join(tmp_dir, f"{i}.html")

            # Write wikitext to temp file
            with open(tmp_wiki, "w", encoding="utf-8") as f:
                f.write(wikitext)

            # Invoke pandoc: mediawiki -> html fragment
            cmd = [
                "pandoc",
                shlex.quote(tmp_wiki),
                "-f", "mediawiki",
                "-t", "html",
                "--wrap=none",
                "-o", shlex.quote(tmp_html)
            ]
            # Use list form for subprocess (safe, no shell injection)
            result = subprocess.run(
                ["pandoc", tmp_wiki, "-f", "mediawiki", "-t", "html",
                 "--wrap=none", "-o", tmp_html],
                capture_output=True
            )
            if result.returncode != 0:
                err_msg = result.stderr.decode("utf-8", errors="replace").strip()
                print(f"  [WARN] pandoc failed for '{title}': {err_msg}", file=sys.stderr)
                errors += 1
                continue

            # Read pandoc output
            fragment = open(tmp_html, "r", encoding="utf-8").read().strip()

            # Rewrite internal wiki links
            fragment = rewrite_internal_links(fragment, title_to_file)

            # Build metadata
            plain_text  = strip_html_tags(fragment)
            description = plain_text[:300] + ("..." if len(plain_text) > 300 else "")
            keywords    = top_keywords(plain_text, 12)
            canonical   = f"{BASE}/{filename}"
            schema_json = make_schema_json(title, description, canonical)
            title_esc   = html.escape(title)
            desc_esc    = html.escape(description)
            canon_esc   = html.escape(canonical)
            kw_esc      = html.escape(", ".join(keywords))

            # Build <head> injection block
            head_meta = (
                f'<title>{title_esc} &mdash; Singularity University Wiki</title>\n'
                f'<meta name="description" content="{desc_esc}">\n'
                f'<meta name="keywords" content="{kw_esc}">\n'
                f'<link rel="canonical" href="{canon_esc}">\n'
                f'<meta name="google-site-verification" content="{GOOGLE_VERIFY}">\n'
                f'<meta property="og:title" content="{title_esc}">\n'
                f'<meta property="og:description" content="{desc_esc}">\n'
                f'<meta property="og:type" content="article">\n'
                f'<meta property="og:url" content="{canon_esc}">\n'
                f'<meta name="twitter:card" content="summary_large_image">\n'
                f'<script type="application/ld+json">{schema_json}</script>'
            )

            # Insert fragment into template
            page_html = template.replace("{html_body}", fragment)

            # Inject metadata into <head>
            if "</head>" in page_html:
                page_html = page_html.replace("</head>", head_meta + "\n</head>", 1)
            else:
                page_html = f"<head>\n{head_meta}\n</head>\n" + page_html

            # Write output file
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(page_html)

            # Accumulate search index entry
            search_index.append({
                "title": title,
                "file":  filename,
                "text":  plain_text[:500],
                "date":  TODAY
            })

            rendered += 1
            if rendered % 50 == 0:
                print(f"  Rendered {rendered}/{len(pages)} pages...")

    print(f"[INFO] Rendered: {rendered}  Errors: {errors}")
    return search_index, rendered


# -----------------------------------------------------------------------
# OUTPUT FILES
# -----------------------------------------------------------------------

def write_search_index(search_index: list[dict]) -> None:
    path = os.path.join(OUTPUT_DIR, "search-index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)
    print(f"[OK] search-index.json ({len(search_index)} entries)")


def write_sitemap(html_files: list[str]) -> None:
    """Write sitemap.xml (or split into multiple if > SITEMAP_MAX)."""
    total = len(html_files)
    parts = max(1, math.ceil(total / SITEMAP_MAX))

    if parts == 1:
        # Single sitemap
        path = os.path.join(OUTPUT_DIR, "sitemap.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for fn in html_files:
                loc = html.escape(f"{BASE}/{fn}")
                f.write(
                    f'  <url>'
                    f'<loc>{loc}</loc>'
                    f'<lastmod>{TODAY}</lastmod>'
                    f'<changefreq>monthly</changefreq>'
                    f'<priority>0.7</priority>'
                    f'</url>\n'
                )
            f.write('</urlset>\n')
        print(f"[OK] sitemap.xml ({total} URLs)")
    else:
        # Multiple sitemaps + index
        os.makedirs("sitemaps", exist_ok=True)
        sitemap_files = []
        for part in range(parts):
            chunk     = html_files[part * SITEMAP_MAX : (part + 1) * SITEMAP_MAX]
            sm_path   = f"sitemaps/sitemap-{part+1}.xml"
            sitemap_files.append(sm_path)
            with open(sm_path, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
                for fn in chunk:
                    loc = html.escape(f"{BASE}/{fn}")
                    f.write(
                        f'  <url>'
                        f'<loc>{loc}</loc>'
                        f'<lastmod>{TODAY}</lastmod>'
                        f'<changefreq>monthly</changefreq>'
                        f'<priority>0.7</priority>'
                        f'</url>\n'
                    )
                f.write('</urlset>\n')

        # Sitemap index
        idx_path = "sitemaps/sitemap-index.xml"
        with open(idx_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for sf in sitemap_files:
                loc = html.escape(f"{BASE}/{sf}")
                f.write(
                    f'  <sitemap>'
                    f'<loc>{loc}</loc>'
                    f'<lastmod>{TODAY}</lastmod>'
                    f'</sitemap>\n'
                )
            f.write('</sitemapindex>\n')
        print(f"[OK] {parts} sitemap files + sitemaps/sitemap-index.xml ({total} URLs)")


def write_index_html(html_files: list[str], title_to_file: dict, template: str) -> None:
    """
    Write or update index.html if it does not already exist as a real article.
    Generates a clean article-grid listing page.
    """
    index_path = os.path.join(OUTPUT_DIR, "index.html")

    # Build file->title reverse map
    file_to_title = {v: k for k, v in title_to_file.items()}
    article_files = [f for f in html_files if f != "index.html"]

    items_html = []
    for fn in sorted(article_files):
        title = file_to_title.get(fn, fn.replace(".html", "").replace("_", " "))
        items_html.append(
            f'<a class="article-card" href="{html.escape(fn)}">'
            f'<div class="card-title">{html.escape(title)}</div>'
            f'</a>'
        )

    grid_html = (
        '<h1>Encyclopedia</h1>'
        '<p style="color:var(--text2);font-family:system-ui,sans-serif;font-size:0.88rem;margin-bottom:2rem;">'
        f'Knowledge Archive &middot; {len(article_files)} articles</p>'
        '<div class="article-grid">' +
        "\n".join(items_html) +
        "</div>"
    )

    page_html = template.replace("{html_body}", grid_html)
    head_meta = (
        '<title>Encyclopedia &mdash; Singularity University Wiki</title>\n'
        '<meta name="description" content="Public knowledge archive of Singularity University. KdK Kreuzberg Online Wiki.">\n'
        f'<link rel="canonical" href="{html.escape(BASE)}/">\n'
        f'<meta name="google-site-verification" content="{GOOGLE_VERIFY}">\n'
    )
    if "</head>" in page_html:
        page_html = page_html.replace("</head>", head_meta + "\n</head>", 1)

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(page_html)
    print(f"[OK] index.html ({len(article_files)} article links)")


def write_last_sync() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(".last_sync", "w") as f:
        f.write(ts + "\n")
    print(f"[OK] .last_sync: {ts}")


# -----------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Singularity University Wiki -- Build Script")
    print("=" * 60)

    # 1. Pre-flight
    template = preflight()

    # 2. Parse XML
    print(f"\n[STEP 1] Parsing {XML_PATH} ...")
    pages = parse_wiki_xml()
    print(f"[INFO] Parsed pages: {len(pages)}")

    if not pages:
        print("ERROR: No main-namespace pages found in wiki.xml", file=sys.stderr)
        sys.exit(4)

    # 3. Build title -> filename map (before rendering, needed for link rewriting)
    title_to_file: dict[str, str] = {}
    for title, _ in pages:
        fn = safe_filename(title)
        title_to_file[title]                    = fn
        title_to_file[title.replace(" ", "_")]  = fn
        title_to_file[title.replace("_", " ")]  = fn

    # 4. Render pages
    print(f"\n[STEP 2] Rendering {len(pages)} pages with pandoc ...")
    search_index, rendered = render_pages(pages, template, title_to_file)

    if rendered == 0:
        print("ERROR: No HTML files were rendered -- check pandoc and wiki.xml", file=sys.stderr)
        sys.exit(5)

    # 5. Collect all generated HTML files
    html_files = sorted([
        f for f in os.listdir(OUTPUT_DIR)
        if f.lower().endswith(".html")
        and f.lower() not in ("template.html",)
        and not f.startswith("index")
    ])

    # 6. Write index.html (article listing)
    print(f"\n[STEP 3] Writing index.html ...")
    write_index_html(html_files, title_to_file, template)

    # 7. All html files including index for sitemap
    all_html = sorted([
        f for f in os.listdir(OUTPUT_DIR)
        if f.lower().endswith(".html") and f.lower() != "template.html"
    ])

    # 8. Search index
    print(f"\n[STEP 4] Writing search-index.json ...")
    write_search_index(search_index)

    # 9. Sitemap
    print(f"\n[STEP 5] Writing sitemap.xml ...")
    write_sitemap(all_html)

    # 10. Timestamp
    write_last_sync()

    print("\n" + "=" * 60)
    print(f"BUILD COMPLETE -- {rendered} articles rendered")
    print(f"Base URL: {BASE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
