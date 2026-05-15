#!/usr/bin/env python3
"""
build.py  --  Singularity University Encyclopedia
Parses backup/wiki.xml -> individual ArticleName.html files + index.html
Requires: pandoc (apt install pandoc), Python 3.10+, stdlib only
"""

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
from collections import Counter
from datetime import datetime, timezone

# -----------------------------------------------------------------------
# Import shared HTML fragments (topbar, sidebar, footer)
# -----------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))
from shared_html import TOPBAR_HTML, FOOTER_HTML, OG_IMAGE, LOGO_URL

# -----------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------
XML_PATH      = "backup/wiki.xml"
TEMPLATE_PATH = "template.html"
OUTPUT_DIR    = "."
SITEMAP_MAX   = 50_000
TODAY         = datetime.now(timezone.utc).strftime("%Y-%m-%d")
GOOGLE_VERIFY = "D-u4byZG_DrIUxnTLQdS0BOTjJcwWmm_h-HwUXl8HO4"

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

STOP = set(
    "der die das und oder aber wenn dann weil wie was wer wo warum wieso ein eine einer "
    "eines einem einen im in ins am an auf aus bei mit nach von vom zum zur ueber unter "
    "fuer gegen ohne um als ist sind war waren nicht kein keine keinen keiner "
    "the a an and or but if then because how what who where why in on at to from for "
    "with without of is are was were be been being not no yes have has had will would "
    "could should may might this that these those it its they them their we our you your "
    "article page wiki html div span href src table ref cite also see".split()
)

# -----------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------
def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag

def safe_filename(title: str) -> str:
    t = unicodedata.normalize("NFKC", (title or "").strip())
    t = re.sub(r"[^\w\- ]+", "", t)
    t = t.replace(" ", "_")
    return (t or "Untitled") + ".html"

def strip_html(s: str) -> str:
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", s)
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def make_keywords(text: str, n: int = 15) -> list[str]:
    words = re.findall(r"[A-Za-z\xC0-\xFF\u0100-\u024F0-9_'-]{3,}", text.lower())
    words = [w for w in words if w not in STOP and not w.isdigit()]
    return [w for w, _ in Counter(words).most_common(n)]

def make_description(text: str, length: int = 250) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    if len(t) <= length:
        return t
    cut = t[:length]
    last_space = cut.rfind(" ")
    return (cut[:last_space] if last_space > 180 else cut) + "..."

def rewrite_links(fragment: str, t2f: dict) -> str:
    def repl(m):
        href = m.group(1)
        raw  = href
        for pfx in ("/wiki/", "./", "../"):
            if href.startswith(pfx):
                href = href[len(pfx):]
                break
        frag_part = ""
        if "#" in href:
            href, frag_part = href.split("#", 1)
            frag_part = "#" + frag_part
        href = href.split("?", 1)[0].replace(" ", "_")
        if href in t2f:
            return f'href="{t2f[href]}{frag_part}"'
        return f'href="{raw}"'
    return re.sub(r'href="([^"]+)"', repl, fragment)

def schema_json(title: str, desc: str, canonical: str) -> str:
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": desc,
        "dateModified": TODAY,
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "publisher": {
            "@type": "Organization",
            "name": "Singularity University Wiki",
            "url": BASE + "/"
        }
    }, ensure_ascii=False)

# -----------------------------------------------------------------------
# FULL PAGE RENDERER
# -----------------------------------------------------------------------
def make_article_page(title: str, fragment: str, t2f: dict) -> str:
    """Build a complete standalone HTML page for one article."""
    filename  = t2f[title]
    canonical = f"{BASE}/{filename}"
    plain     = strip_html(fragment)
    desc      = make_description(plain, 250)
    keywords  = make_keywords(plain, 15)
    schema    = schema_json(title, desc, canonical)
    kw_str    = ", ".join(keywords)

    te  = html.escape(title)
    de  = html.escape(desc)
    ce  = html.escape(canonical)
    kwe = html.escape(kw_str)
    img = OG_IMAGE

    head = (
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta name="google-site-verification" content="{GOOGLE_VERIFY}">\n'
        f'<title>{te} &mdash; Singularity University Wiki</title>\n'
        f'<meta name="description" content="{de}">\n'
        f'<meta name="keywords" content="{kwe}">\n'
        f'<meta name="robots" content="index, follow">\n'
        f'<link rel="canonical" href="{ce}">\n'
        f'<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">\n'
        f'<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">\n'
        f'<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">\n'
        f'<link rel="manifest" href="/site.webmanifest">\n'
        f'<meta property="og:type" content="article">\n'
        f'<meta property="og:title" content="{te}">\n'
        f'<meta property="og:description" content="{de}">\n'
        f'<meta property="og:image" content="{img}">\n'
        f'<meta property="og:url" content="{ce}">\n'
        f'<meta property="og:site_name" content="Singularity University Wiki">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{te}">\n'
        f'<meta name="twitter:description" content="{de}">\n'
        f'<meta name="twitter:image" content="{img}">\n'
        f'<script type="application/ld+json">{schema}</script>\n'
        f'<link rel="stylesheet" href="assets/style.css">'
    )

    # Article header (big title + meta bar)
    article_header = (
        f'<div class="article-header">'
        f'<h1 class="article-title">{te}</h1>'
        f'<div class="article-meta">'
        f'<span>&#128197; {TODAY}</span>'
        f'<span><a href="index.html">&#127968; Encyclopedia</a></span>'
        f'</div>'
        f'</div>'
    )

    page = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
{head}
</head>
<body>

{TOPBAR_HTML}

<div class="page-wrap">

  <nav class="breadcrumbs" id="breadcrumbs" aria-label="Page path"></nav>

  <div class="content-wrap">

    <main class="article-col" id="main-content">
      {article_header}
      <div class="article-box">
        {fragment}
      </div>
    </main>

    <aside class="toc-col" aria-label="Table of contents">
      <div class="toc-box">
        <div class="toc-title">Contents</div>
        <ul id="toc" role="list"></ul>
      </div>
    </aside>

  </div>

  {FOOTER_HTML}

</div>

<script src="assets/app.js"></script>
</body>
</html>"""
    return page

# -----------------------------------------------------------------------
# XML PARSING
# -----------------------------------------------------------------------
def parse_wiki_xml() -> list[tuple[str, str]]:
    SKIP = ("Special:", "File:", "Template:", "MediaWiki:", "Category:",
            "Help:", "User:", "Talk:", "Wikipedia:", "Portal:")
    pages = []
    try:
        for event, elem in ET.iterparse(XML_PATH, events=("end",)):
            if strip_ns(elem.tag) != "page":
                continue
            title_el = elem.find(".//{*}title")
            ns_el    = elem.find(".//{*}ns")
            text_el  = elem.find(".//{*}text")
            title    = (title_el.text or "").strip() if title_el is not None else ""
            ns       = (ns_el.text or "").strip()    if ns_el    is not None else "0"
            wikitext = (text_el.text or "")           if text_el  is not None else ""
            if ns == "0" and title and not any(title.startswith(p) for p in SKIP):
                pages.append((title, wikitext))
            elem.clear()
    except ET.ParseError as e:
        print(f"ERROR: XML parse error: {e}", file=sys.stderr)
        sys.exit(3)
    return pages

# -----------------------------------------------------------------------
# RENDER WITH PANDOC
# -----------------------------------------------------------------------
def render_pages(pages, t2f):
    search_index = []
    rendered     = 0

    with tempfile.TemporaryDirectory() as td:
        for i, (title, wikitext) in enumerate(pages, 1):
            fn       = t2f[title]
            out_path = os.path.join(OUTPUT_DIR, fn)
            tw       = os.path.join(td, f"{i}.wiki")
            th       = os.path.join(td, f"{i}.html")

            with open(tw, "w", encoding="utf-8") as f:
                f.write(wikitext)

            result = subprocess.run(
                ["pandoc", tw, "-f", "mediawiki", "-t", "html", "--wrap=none", "-o", th],
                capture_output=True
            )
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace").strip()
                print(f"  [WARN] pandoc failed '{title}': {err}", file=sys.stderr)
                continue

            fragment = open(th, "r", encoding="utf-8").read().strip()
            fragment = rewrite_links(fragment, t2f)

            page_html = make_article_page(title, fragment, t2f)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(page_html)

            plain = strip_html(fragment)
            search_index.append({
                "title": title,
                "file":  fn,
                "text":  plain[:500],
                "date":  TODAY
            })
            rendered += 1
            if rendered % 50 == 0 or rendered == len(pages):
                print(f"  [{rendered}/{len(pages)}] rendered...")

    return search_index, rendered

# -----------------------------------------------------------------------
# INDEX HTML
# -----------------------------------------------------------------------
def write_index_html(search_index):
    items_html = "\n".join(
        f'<a class="article-card" href="{html.escape(a["file"])}">'
        f'<div class="card-title">{html.escape(a["title"])}</div>'
        f'<div class="card-excerpt">{html.escape(a["text"][:160])}...</div>'
        f'</a>'
        for a in sorted(search_index, key=lambda x: x["title"].lower())
    )

    canonical = BASE + "/index.html"
    ce = html.escape(canonical)
    img = OG_IMAGE
    kw = ("Juridical Singularity, Electric Technocracy, Age of Transition, World Succession Deed, "
          "1400/98, Homo Nexus, ASI Governance, Direct Digital Democracy, Universal Basic Income, "
          "Tech Tax, Post-Scarcity, Treaty Chain, International Law, NATO SOFA, United Nations, "
          "Telecommunications Infrastructure, Global Governance, AI Civilization, Mental Singularity, "
          "Automation Economy, Longevity, Neural Networks, State Succession, Smart Democracy, "
          "Planetary System, DDD")
    meta_desc = ("Encyclopedia of the Singularity University KdK Krzb. Explore Juridical Singularity, "
                 "the Age of Transition, Electric Technocracy, ASI governance, post-scarcity economics, "
                 "and the World Succession Deed 1400/98.")

    head = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-site-verification" content="{GOOGLE_VERIFY}">
<title>Encyclopedia of the Singularity University KdK Krzb.</title>
<meta name="description" content="{html.escape(meta_desc)}">
<meta name="keywords" content="{html.escape(kw)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{ce}">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="manifest" href="/site.webmanifest">
<meta property="og:type" content="website">
<meta property="og:title" content="Encyclopedia of the Singularity University KdK Krzb.">
<meta property="og:description" content="{html.escape(meta_desc)}">
<meta property="og:image" content="{img}">
<meta property="og:url" content="{ce}">
<meta property="og:site_name" content="Singularity University Wiki">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Encyclopedia of the Singularity University KdK Krzb.">
<meta name="twitter:description" content="{html.escape(meta_desc)}">
<meta name="twitter:image" content="{img}">
<script type="application/ld+json">{json.dumps({"@context":"https://schema.org","@type":"WebSite","name":"Singularity University Wiki","url":BASE+"/","description":meta_desc},ensure_ascii=False)}</script>
<link rel="stylesheet" href="assets/style.css">"""

    body = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
{head}
</head>
<body>

{TOPBAR_HTML}

<div class="page-wrap">

  <section class="hero" aria-label="Encyclopedia banner">
    <img class="hero-img"
         src="{img}"
         alt="Singularity University Encyclopedia" loading="eager" fetchpriority="high">
    <div class="hero-fade" aria-hidden="true"></div>
    <div class="hero-text">
      <h1>The Encyclopedia of Juridical Singularity, Age of Transition and Electric Technocracy</h1>
      <h2>From the World Succession Deed 1400/98 to the Rise of Homo Nexus</h2>
    </div>
  </section>

  <div class="index-intro">
    <p>The Encyclopedia of the Singularity University KdK Krzb. documents the emerging transformation of international law, governance, technology, and civilization in the Age of Transition. It explores the doctrine of the Juridical Singularity, the structural transition from nation-state systems toward planetary coordination, and the rise of Electric Technocracy as a post-scarcity governance architecture.</p>
    <p>At the center of this framework stands the <a href="World_Succession_Deed_140098.html">World Succession Deed 1400/98</a>, a disputed legal instrument discussed in more than 1,000 court cases and interpreted as a constitutive event in international treaty law. According to the doctrine, the transfer of the Kreuzbergkaserne military infrastructure &ldquo;with all rights, obligations, and components&rdquo; triggered a treaty-chain expansion through NATO, telecommunications systems, and UN-connected infrastructure networks. The result is described as the Juridical Singularity: the collapse of the traditional plurality of sovereign actors into a unified legal continuum.</p>
    <p>The encyclopedia examines how technological acceleration transforms society beyond classical industrial civilization. Artificial Intelligence, automation, robotics, nanotechnology, fusion energy, and neurotechnology increasingly dissolve scarcity-based economics. Electric Technocracy emerges as the proposed governance model for this new epoch: a system of Direct Digital Democracy supported by Artificial Superintelligence (ASI), where machine productivity finances a Universal Basic Income through a technology tax while humans become tax-free participants in a globally networked civilization.</p>
    <p>The Age of Transition also describes a psychological and cognitive transformation. Humanity moves from Homo sapiens, shaped by scarcity and territorial competition, toward Homo nexus, a networked form of civilization integrated through digital systems, BCIs, and global information infrastructures. Political parties, wage dependency, and rigid borders become increasingly obsolete as algorithmic coordination and post-labor economics redefine social organization.</p>
    <p>This encyclopedia serves as a knowledge archive for treaty-chain theory, state succession doctrine, post-scarcity economics, AI governance, longevity research, telecommunications infrastructure, global digital democracy, and the future evolution of civilization beyond the Westphalian state system.</p>
  </div>

  <section class="index-section" aria-labelledby="grid-heading">
    <h2 class="section-title" id="grid-heading">All Articles &mdash; <span id="articleCount"></span></h2>
    <div class="article-grid" id="indexGrid" role="list">
      <p class="loading"><span class="dot" aria-hidden="true"></span> Loading articles...</p>
    </div>
  </section>

  {FOOTER_HTML}

</div>

<script src="assets/app.js"></script>
</body>
</html>"""

    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(body)
    print("[OK] index.html")

# -----------------------------------------------------------------------
# SEARCH PAGE
# -----------------------------------------------------------------------
def write_search_html():
    canonical = BASE + "/search.html"
    head = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Search &mdash; Singularity University Wiki</title>
<meta name="description" content="Search the Singularity University Encyclopedia. Find articles on Juridical Singularity, Electric Technocracy, and more.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{html.escape(canonical)}">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="stylesheet" href="assets/style.css">"""

    body = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
{head}
</head>
<body>

{TOPBAR_HTML}

<div class="page-wrap">

  <nav class="breadcrumbs" id="breadcrumbs" aria-label="Page path"></nav>

  <div class="search-page">
    <div class="search-hero">
      <h1>Search Encyclopedia</h1>
    </div>
    <div class="search-bar-wrap">
      <input type="search" id="searchPageInput"
        placeholder="Search articles, topics, keywords..."
        aria-label="Search articles" autocomplete="off">
      <button id="searchPageBtn" type="button">Search</button>
    </div>
    <div class="search-count" id="searchCount"></div>
    <div class="search-results" id="searchResults"></div>
  </div>

  {FOOTER_HTML}

</div>

<script src="assets/app.js"></script>
</body>
</html>"""

    with open(os.path.join(OUTPUT_DIR, "search.html"), "w", encoding="utf-8") as f:
        f.write(body)
    print("[OK] search.html")

# -----------------------------------------------------------------------
# SITEMAP + SEARCH INDEX
# -----------------------------------------------------------------------
def write_search_index(search_index):
    with open("search-index.json", "w", encoding="utf-8") as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)
    print(f"[OK] search-index.json ({len(search_index)} entries)")

def write_sitemap(html_files):
    total = len(html_files)
    parts = max(1, math.ceil(total / SITEMAP_MAX))
    if parts == 1:
        with open("sitemap.xml", "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for fn in html_files:
                loc = html.escape(f"{BASE}/{fn}")
                f.write(f'  <url><loc>{loc}</loc><lastmod>{TODAY}</lastmod>'
                        f'<changefreq>monthly</changefreq><priority>0.7</priority></url>\n')
            f.write('</urlset>\n')
        print(f"[OK] sitemap.xml ({total} URLs)")

# -----------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------
def main():
    print("=" * 60)
    print("Singularity University Encyclopedia -- Build")
    print(f"Base URL: {BASE}")
    print("=" * 60)

    # Pre-flight
    for p in [XML_PATH, TEMPLATE_PATH]:
        if not os.path.isfile(p):
            print(f"ERROR: {p} not found", file=sys.stderr)
            sys.exit(2)
    r = subprocess.run(["pandoc", "--version"], capture_output=True)
    if r.returncode != 0:
        print("ERROR: pandoc not found", file=sys.stderr)
        sys.exit(2)
    print("[OK] pandoc found")

    # Parse
    print(f"\n[STEP 1] Parsing {XML_PATH}...")
    pages = parse_wiki_xml()
    print(f"[INFO] Pages parsed: {len(pages)}")
    if not pages:
        print("ERROR: No pages found in wiki.xml", file=sys.stderr)
        sys.exit(4)

    # Title -> filename map
    t2f: dict[str, str] = {}
    for title, _ in pages:
        fn = safe_filename(title)
        t2f[title]                   = fn
        t2f[title.replace(" ", "_")] = fn
        t2f[title.replace("_", " ")] = fn

    # Render articles
    print(f"\n[STEP 2] Rendering {len(pages)} articles...")
    search_index, rendered = render_pages(pages, t2f)
    print(f"[INFO] Rendered: {rendered}")
    if rendered == 0:
        print("ERROR: No articles rendered", file=sys.stderr)
        sys.exit(5)

    # Index page
    print(f"\n[STEP 3] Writing index.html...")
    write_index_html(search_index)

    # Search page
    print(f"\n[STEP 4] Writing search.html...")
    write_search_html()

    # Search index
    write_search_index(search_index)

    # Sitemap
    all_html = sorted(
        f for f in os.listdir(OUTPUT_DIR)
        if f.lower().endswith(".html") and f not in ("template.html",)
    )
    write_sitemap(all_html)

    # .last_sync
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(".last_sync", "w") as f:
        f.write(ts + "\n")

    print("\n" + "=" * 60)
    print(f"DONE -- {rendered} articles, {len(all_html)} HTML files total")
    print("=" * 60)

if __name__ == "__main__":
    main()
