#!/usr/bin/env python3
"""
build.py — Singularity University Wiki
MediaWiki XML export → static SEO-optimised HTML encyclopedia

Architecture:
  index-template.html  → index.html   (Startseite, CollectionPage JSON-LD)
  template.html        → Article.html  (Article JSON-LD per page)

Generates:
  index.html, Article-Title.html, search.html,
  search-index.json, sitemap.xml, robots.txt, .nojekyll
"""

import html
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET

from collections import Counter
from datetime import datetime, timezone
from urllib.parse import unquote

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

XML_PATH            = "backup/wiki.xml"
TEMPLATE_PATH       = "template.html"        # article template
INDEX_TEMPLATE_PATH = "index-template.html"  # index / Startseite template
OUTPUT_DIR          = "."
TODAY               = datetime.now(timezone.utc).strftime("%Y-%m-%d")

GOOGLE_VERIFY_1 = "D-u4byZG_DrIUxnTLQdS0BOTjJcwWmm_h-HwUXl8HO4"
GOOGLE_VERIFY_2 = "POS6A_n9nSGi6W4cWi-49r84-3ML8vTuLRBZQX-OFBc"

LOGO_URL   = "https://raw.githubusercontent.com/singularity-news/wiki/main/assets/logo.png"
HEADER_IMG = "https://raw.githubusercontent.com/singularity-news/wiki/main/assets/header.png"

# Base URL — env override > GitHub Actions > fallback
_env_base = os.environ.get("PAGES_BASE", "").strip()
if _env_base:
    BASE = _env_base.rstrip("/")
else:
    _repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in _repo:
        _owner, _repo_name = _repo.split("/", 1)
        BASE = f"https://{_owner}.github.io/{_repo_name}"
    else:
        BASE = "https://singularity-news.github.io/wiki"

SITEMAP_MAX = 50_000

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
    "Special:", "File:", "Template:", "MediaWiki:",
    "Category:", "Help:", "User:", "Talk:", "Wikipedia:"
)

# ─────────────────────────────────────────────────────────────
# FOOTER (used in article pages via {footer} placeholder)
# index-template.html has its own hardcoded footer
# ─────────────────────────────────────────────────────────────

FOOTER_HTML = """  <footer class="footer" role="contentinfo">
    <div class="footer-links">
      <a class="footer-link" href="https://world.rf.gd" target="_blank" rel="noopener">
        <span class="footer-icon">&#127760;</span>
        <span><strong>WSD — World Succession Deed 1400/98</strong><br><small>world.rf.gd &middot; worldsold.wixsite.com/world-sold/en</small></span>
      </a>
      <a class="footer-link" href="https://global-archive.rf.gd" target="_blank" rel="noopener">
        <span class="footer-icon">&#127760;</span>
        <span><strong>WSD — Global Legal Succession Archive</strong><br><small>global-archive.rf.gd</small></span>
      </a>
      <a class="footer-link" href="https://ep.ct.ws" target="_blank" rel="noopener">
        <span class="footer-icon">&#127760;</span>
        <span><strong>Electric Technocracy</strong><br><small>ep.ct.ws</small></span>
      </a>
      <a class="footer-link" href="https://videos.xo.je" target="_blank" rel="noopener">
        <span class="footer-icon">&#127909;</span>
        <span><strong>YouTube Channel</strong><br><small>videos.xo.je</small></span>
      </a>
      <a class="footer-link" href="https://nwo.likesyou.org" target="_blank" rel="noopener">
        <span class="footer-icon">&#127911;&#65039;</span>
        <span><strong>Podcast Show</strong><br><small>nwo.likesyou.org</small></span>
      </a>
      <a class="footer-link" href="https://electric-paradise.start.page" target="_blank" rel="noopener">
        <span class="footer-icon">&#128640;</span>
        <span><strong>Start-Page WSD &amp; Electric Paradise</strong><br><small>electric-paradise.start.page</small></span>
      </a>
      <a class="footer-link" href="https://patch98.wordpress.com" target="_blank" rel="noopener">
        <span class="footer-icon">&#9889;</span>
        <span><strong>The Patch Blog: Exponential Tech</strong><br><small>patch98.wordpress.com</small></span>
      </a>
      <a class="footer-link" href="https://now31.wordpress.com" target="_blank" rel="noopener">
        <span class="footer-icon">&#127963;&#65039;</span>
        <span><strong>Homo Nexus Blog</strong><br><small>now31.wordpress.com</small></span>
      </a>
      <a class="footer-link" href="https://chatgpt.com/g/g-69d8635591d48191adc315b8f2b8be32-electric-technocracy-a-new-form-of-government" target="_blank" rel="noopener">
        <span class="footer-icon">&#128172;</span>
        <span><strong>Electric Technocracy GPT</strong><br><small>chatgpt.com</small></span>
      </a>
      <a class="footer-link" href="https://chatgpt.com/g/g-69d95a89896081918fcb207e1665bf26-juridical-singularity-domestic-international-law" target="_blank" rel="noopener">
        <span class="footer-icon">&#128172;</span>
        <span><strong>Juridical SINGULARITY GPT</strong><br><small>chatgpt.com</small></span>
      </a>
    </div>
    <div class="footer-bottom">
      &copy; 2026 Singularity University Wiki &middot; KdK Kreuzberg
      <span class="footer-sep">&middot;</span>
      <a href="https://github.com/singularity-news/wiki" target="_blank" rel="noopener">GitHub</a>
      <span class="footer-sep">&middot;</span>
      <a href="sitemap.xml">Sitemap</a>
      <span class="footer-sep">&middot;</span>
      <a href="search.html">Search</a>
      <span class="footer-sep">&middot;</span>
      <a href="index.html">&#8592; Encyclopedia</a>
    </div>
  </footer>"""

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def safe_filename(title: str) -> str:
    """Clean SEO-friendly filename: Article_Title.html"""
    t = unicodedata.normalize("NFKC", (title or "").strip())
    t = re.sub(r"[^\w\- ]+", "", t)
    t = t.replace(" ", "_")
    return (t or "Untitled") + ".html"


def sanitize_html(fragment: str) -> str:
    fragment = re.sub(r"(?is)<script.*?>.*?</script>", "", fragment)
    fragment = re.sub(r"(?is)<iframe.*?>.*?</iframe>", "", fragment)
    fragment = re.sub(r'on\w+="[^"]*"', "", fragment)
    fragment = re.sub(r"javascript:", "", fragment, flags=re.IGNORECASE)
    return fragment


def strip_html_tags(s: str) -> str:
    s = re.sub(r"(?is)<script.*?>.*?</script>", " ", s)
    s = re.sub(r"(?is)<style.*?>.*?</style>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def top_keywords(text: str, n: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-zÀ-ÿ0-9_\-']{3,}", text.lower())
    words = [w for w in words if w not in STOP and not w.isdigit()]
    return [w for w, _ in Counter(words).most_common(n)]


def rewrite_internal_links(fragment: str, title_to_file: dict) -> str:
    def repl(m: re.Match) -> str:
        raw = m.group(1)
        href = unquote(unicodedata.normalize("NFKC", raw))
        for prefix in ("/wiki/", "./", "../"):
            if href.startswith(prefix):
                href = href[len(prefix):]
        bare = href.split("#", 1)[0].split("?", 1)[0]
        bare = bare.replace("_", " ").strip()
        if bare in title_to_file:
            frag = ("#" + href.split("#", 1)[1]) if "#" in href else ""
            return f'href="{title_to_file[bare]}{frag}"'
        return f'href="{raw}"'
    return re.sub(r'href="([^"]+)"', repl, fragment)


def make_article_schema(title: str, description: str, canonical: str) -> str:
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "dateModified": TODAY,
        "image": HEADER_IMG,
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "author": {"@type": "Organization", "name": "Singularity University Wiki"},
        "publisher": {
            "@type": "Organization",
            "name": "Singularity University Wiki",
            "url": BASE + "/"
        }
    }, ensure_ascii=False)


def make_collection_schema(pages: list, title_to_file: dict) -> str:
    # Limit hasPart to avoid oversized JSON-LD (Google recommends <100 items)
    parts = [
        {
            "@type": "Article",
            "name": t,
            "url": f"{BASE}/{title_to_file[t]}"
        }
        for t, _ in sorted(pages, key=lambda p: p[0].lower())[:100]
    ]
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Singularity University Wiki",
        "description": "Encyclopedia of Electric Technocracy, AI Governance, "
                       "Juridical Singularity and Global Jurisdiction",
        "url": BASE + "/",
        "hasPart": parts
    }, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────
# PREFLIGHT
# ─────────────────────────────────────────────────────────────

def preflight() -> tuple[str, str]:
    """Returns (article_template, index_template)"""
    errors = []
    if not os.path.isfile(XML_PATH):
        errors.append(f"Missing {XML_PATH}")
    if not os.path.isfile(TEMPLATE_PATH):
        errors.append(f"Missing {TEMPLATE_PATH}")
    if not os.path.isfile(INDEX_TEMPLATE_PATH):
        errors.append(f"Missing {INDEX_TEMPLATE_PATH}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    article_tpl = open(TEMPLATE_PATH, encoding="utf-8").read()
    index_tpl   = open(INDEX_TEMPLATE_PATH, encoding="utf-8").read()

    if "{html_body}" not in article_tpl:
        print("ERROR: template.html missing {html_body}", file=sys.stderr)
        sys.exit(2)
    if "{footer}" not in article_tpl:
        print("ERROR: template.html missing {footer}", file=sys.stderr)
        sys.exit(2)
    if "<!-- ARTICLE_LIST -->" not in index_tpl:
        print("ERROR: index-template.html missing <!-- ARTICLE_LIST -->", file=sys.stderr)
        sys.exit(2)

    result = subprocess.run(["pandoc", "--version"], capture_output=True)
    if result.returncode != 0:
        print("ERROR: pandoc not installed", file=sys.stderr)
        sys.exit(2)

    print(f"[OK] XML:            {XML_PATH}")
    print(f"[OK] Template:       {TEMPLATE_PATH}")
    print(f"[OK] Index template: {INDEX_TEMPLATE_PATH}")
    print(f"[OK] Base URL:       {BASE}")
    return article_tpl, index_tpl

# ─────────────────────────────────────────────────────────────
# XML PARSING
# ─────────────────────────────────────────────────────────────

def parse_wiki_xml() -> list[tuple[str, str]]:
    pages = []
    try:
        for event, elem in ET.iterparse(XML_PATH, events=("end",)):
            if strip_ns(elem.tag) != "page":
                continue
            title_el = elem.find(".//{*}title")
            ns_el    = elem.find(".//{*}ns")
            text_el  = elem.find(".//{*}text")
            title = (title_el.text or "").strip() if title_el is not None else ""
            ns    = (ns_el.text or "").strip()    if ns_el is not None else "0"
            text  = (text_el.text or "")          if text_el is not None else ""
            if (ns == "0"
                    and title
                    and not any(title.startswith(p) for p in SKIP_PREFIXES)):
                pages.append((title, text))
            elem.clear()
    except ET.ParseError as exc:
        print(f"ERROR: XML parse error: {exc}", file=sys.stderr)
        sys.exit(3)
    return pages

# ─────────────────────────────────────────────────────────────
# ARTICLE RENDERING
# ─────────────────────────────────────────────────────────────

def render_pages(
    pages: list[tuple[str, str]],
    article_tpl: str,
    title_to_file: dict
) -> tuple[list[dict], int]:

    search_index: list[dict] = []
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
                ["pandoc", tmp_wiki, "-f", "mediawiki", "-t", "html",
                 "--wrap=none", "-o", tmp_html],
                capture_output=True
            )
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace").strip()
                print(f"  [WARN] pandoc failed for '{title}': {err}", file=sys.stderr)
                continue

            fragment = open(tmp_html, encoding="utf-8").read()
            fragment = sanitize_html(fragment)
            fragment = rewrite_internal_links(fragment, title_to_file)

            plain       = strip_html_tags(fragment)
            description = plain[:300] + ("..." if len(plain) > 300 else "")
            keywords    = top_keywords(plain, 12)
            canonical   = f"{BASE}/{filename}"
            schema_json = make_article_schema(title, description, canonical)

            head_meta = (
                f'<title>{html.escape(title)} — Singularity University Wiki</title>\n'
                f'<meta name="description" content="{html.escape(description)}">\n'
                f'<meta name="keywords" content="{html.escape(", ".join(keywords))}">\n'
                f'<link rel="canonical" href="{html.escape(canonical)}">\n'
                f'<meta name="google-site-verification" content="{GOOGLE_VERIFY_1}">\n'
                f'<meta name="google-site-verification" content="{GOOGLE_VERIFY_2}">\n'
                f'<meta property="og:title" content="{html.escape(title)}">\n'
                f'<meta property="og:description" content="{html.escape(description)}">\n'
                f'<meta property="og:type" content="article">\n'
                f'<meta property="og:url" content="{html.escape(canonical)}">\n'
                f'<meta property="og:image" content="{html.escape(HEADER_IMG)}">\n'
                f'<meta name="twitter:card" content="summary_large_image">\n'
                f'<script type="application/ld+json">\n{schema_json}\n</script>'
            )

            # Also inject back-link to index after article h1
            back_link = '<p class="back-link"><a href="index.html">&#8592; Encyclopedia Index</a></p>\n'
            fragment  = re.sub(r'(<h1[^>]*>.*?</h1>)', r'\1\n' + back_link, fragment, count=1, flags=re.DOTALL)

            page_html = article_tpl.replace("{html_body}", fragment)
            page_html = page_html.replace("{footer}", FOOTER_HTML)

            if "</head>" in page_html:
                page_html = page_html.replace("</head>", head_meta + "\n</head>", 1)

            # Add body data-title for breadcrumbs
            page_html = page_html.replace(
                "<body>",
                f'<body data-title="{html.escape(title)}">',
                1
            )

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(page_html)

            search_index.append({
                "title": title,
                "file":  filename,
                "text":  plain[:500],
                "date":  TODAY
            })

            rendered += 1
            if rendered % 50 == 0:
                print(f"  ... {rendered}/{len(pages)} rendered")

    print(f"[INFO] Rendered: {rendered}  Skipped: {len(pages) - rendered}")
    return search_index, rendered

# ─────────────────────────────────────────────────────────────
# INDEX PAGE (from index-template.html)
# ─────────────────────────────────────────────────────────────

def write_index_html(
    pages: list[tuple[str, str]],
    title_to_file: dict,
    index_tpl: str
) -> None:
    """
    Generates index.html from index-template.html.
    Replaces <!-- ARTICLE_LIST --> with static SEO-friendly article links.
    Injects CollectionPage JSON-LD into <head>.
    """
    # Alphabetical static article links — SEO-critical, crawlable without JS
    sorted_pages = sorted(pages, key=lambda p: p[0].lower())

    links_html = "\n".join(
        f'<a class="article-card" href="{html.escape(title_to_file[title])}">'
        f'<div class="card-title">{html.escape(title)}</div>'
        f'</a>'
        for title, _ in sorted_pages
    )

    page_html = index_tpl.replace("<!-- ARTICLE_LIST -->", links_html)

    # CollectionPage JSON-LD
    collection_schema = make_collection_schema(pages, title_to_file)
    schema_tag = (
        f'<script type="application/ld+json">\n{collection_schema}\n</script>'
    )

    # Replace the existing WebSite JSON-LD with CollectionPage (or append both)
    # Keep existing WebSite schema + add CollectionPage schema
    if "</head>" in page_html:
        page_html = page_html.replace(
            "</head>",
            schema_tag + "\n</head>",
            1
        )

    # Update article count display if present
    page_html = page_html.replace(
        '<strong id="articleCount">--</strong>',
        f'<strong id="articleCount">{len(sorted_pages)}</strong>'
    )

    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(page_html)

    print(f"[OK] index.html  ({len(sorted_pages)} articles, static links)")

# ─────────────────────────────────────────────────────────────
# SEARCH PAGE
# ─────────────────────────────────────────────────────────────

SEARCH_BODY = """<div class="content-wrap content-wrap--full">
  <main class="article-col">
    <div class="article-box search-page-box">
      <h1>Search Articles</h1>
      <p class="search-intro">Full-text search across all encyclopedia articles.</p>
      <div class="search-field-wrap">
        <label class="sr-only" for="pageSearchInput">Search articles</label>
        <input type="search" id="pageSearchInput"
          placeholder="Type to search..." autofocus
          aria-label="Search all articles" autocomplete="off">
        <svg class="search-icon" width="18" height="18" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </div>
      <div id="searchStats" class="search-stats" role="status" aria-live="polite"></div>
      <div id="searchResults" class="search-results" role="list"></div>
      <div id="searchEmpty" class="search-empty" hidden>
        <p>No articles found. <a href="index.html">&#8592; Back to Encyclopedia</a></p>
      </div>
    </div>
  </main>
</div>"""

def write_search_html(article_tpl: str) -> None:
    canonical = f"{BASE}/search.html"
    head_meta = (
        '<title>Search — Singularity University Wiki</title>\n'
        '<meta name="description" content="Search all articles in the Singularity University Encyclopedia.">\n'
        f'<link rel="canonical" href="{html.escape(canonical)}">\n'
        f'<meta name="google-site-verification" content="{GOOGLE_VERIFY_1}">\n'
        f'<meta name="google-site-verification" content="{GOOGLE_VERIFY_2}">\n'
    )
    page_html = article_tpl.replace("{html_body}", SEARCH_BODY)
    page_html = page_html.replace("{footer}", FOOTER_HTML)
    if "</head>" in page_html:
        page_html = page_html.replace("</head>", head_meta + "\n</head>", 1)

    # Add inline search logic
    search_js = """
<script>
(function(){
  var all=[];
  var inp=document.getElementById('pageSearchInput');
  var res=document.getElementById('searchResults');
  var stats=document.getElementById('searchStats');
  var empty=document.getElementById('searchEmpty');
  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
  function hi(t,q){if(!q)return esc(t);var r=new RegExp(q.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'),'gi');return esc(t).replace(r,function(m){return'<mark>'+m+'</mark>';});}
  function search(q){
    q=(q||'').trim();
    if(!q){res.innerHTML='';stats.textContent='';if(empty)empty.hidden=true;return;}
    var lq=q.toLowerCase();
    var found=all.filter(function(a){return a.title.toLowerCase().includes(lq)||(a.text&&a.text.toLowerCase().includes(lq));});
    found.sort(function(a,b){
      var at=a.title.toLowerCase().indexOf(lq)>=0?1:0;
      var bt=b.title.toLowerCase().indexOf(lq)>=0?1:0;
      return bt-at;
    });
    if(empty)empty.hidden=found.length>0;
    stats.textContent=found.length?found.length+' result'+(found.length===1?'':'s')+' for "'+q+'"':'';
    res.innerHTML=found.map(function(a){
      var idx=a.text?a.text.toLowerCase().indexOf(lq):-1;
      var ex=idx>-1?a.text.slice(Math.max(0,idx-60),idx+lq.length+120):(a.text||'').slice(0,180);
      if(idx>30)ex='...'+ex;
      if(ex.length<(a.text||'').length)ex+=('...');
      return'<a class="search-result" href="'+a.file+'" role="listitem"><div class="sr-title">'+hi(a.title,q)+'</div><div class="sr-excerpt">'+hi(ex,q)+'</div></a>';
    }).join('');
  }
  fetch('search-index.json').then(function(r){return r.ok?r.json():[];}).then(function(d){
    all=Array.isArray(d)?d:[];
    var q=new URLSearchParams(location.search).get('q')||'';
    if(q&&inp){inp.value=q;search(q);}
  }).catch(function(){});
  if(inp){
    inp.addEventListener('input',function(e){
      search(e.target.value);
      var u=new URL(location.href);
      if(e.target.value.trim())u.searchParams.set('q',e.target.value.trim());
      else u.searchParams.delete('q');
      history.replaceState(null,'',u.toString());
    });
  }
}());
</script>"""

    page_html = page_html.replace("</body>", search_js + "\n</body>", 1)

    with open(os.path.join(OUTPUT_DIR, "search.html"), "w", encoding="utf-8") as f:
        f.write(page_html)
    print("[OK] search.html")

# ─────────────────────────────────────────────────────────────
# SEARCH INDEX
# ─────────────────────────────────────────────────────────────

def write_search_index(search_index: list[dict]) -> None:
    with open("search-index.json", "w", encoding="utf-8") as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)
    print(f"[OK] search-index.json  ({len(search_index)} entries)")

# ─────────────────────────────────────────────────────────────
# SITEMAP
# ─────────────────────────────────────────────────────────────

def write_sitemap() -> None:
    html_files = sorted([
        f for f in os.listdir(".")
        if f.endswith(".html")
        and f not in ("template.html", "index-template.html")
    ])
    total = len(html_files)
    parts = max(1, math.ceil(total / SITEMAP_MAX))

    if parts == 1:
        with open("sitemap.xml", "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for fn in html_files:
                loc   = html.escape(f"{BASE}/{fn}")
                prio  = "1.0" if fn == "index.html" else "0.7"
                f.write(
                    f'  <url><loc>{loc}</loc>'
                    f'<lastmod>{TODAY}</lastmod>'
                    f'<changefreq>monthly</changefreq>'
                    f'<priority>{prio}</priority></url>\n'
                )
            f.write('</urlset>\n')
        print(f"[OK] sitemap.xml  ({total} URLs)")

# ─────────────────────────────────────────────────────────────
# ROBOTS
# ─────────────────────────────────────────────────────────────

def write_robots() -> None:
    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    print("[OK] robots.txt")

# ─────────────────────────────────────────────────────────────
# .NOJEKYLL (prevents GitHub Pages from ignoring _ files)
# ─────────────────────────────────────────────────────────────

def write_nojekyll() -> None:
    with open(".nojekyll", "w") as f:
        f.write("")
    print("[OK] .nojekyll")

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("Singularity University Wiki  —  Build")
    print("=" * 60)

    article_tpl, index_tpl = preflight()

    # ── 1. Parse XML ──
    print("\n[STEP 1] Parsing XML ...")
    pages = parse_wiki_xml()
    print(f"[INFO] Parsed: {len(pages)} pages")
    if not pages:
        print("ERROR: No main-namespace pages found", file=sys.stderr)
        sys.exit(4)

    # ── 2. Build title → filename map (collision-safe) ──
    title_to_file: dict[str, str] = {}
    used_files: dict[str, int]    = {}

    for title, _ in pages:
        fn = safe_filename(title)
        # Handle collisions by appending a counter
        if fn in used_files:
            used_files[fn] += 1
            base = fn[:-5]  # strip .html
            fn   = f"{base}_{used_files[fn]}.html"
        else:
            used_files[fn] = 0

        title_to_file[title]                   = fn
        title_to_file[title.replace("_", " ")] = fn
        title_to_file[title.replace(" ", "_")] = fn

    # ── 3. Render articles ──
    print(f"\n[STEP 2] Rendering {len(pages)} articles ...")
    search_index, rendered = render_pages(pages, article_tpl, title_to_file)
    if rendered == 0:
        print("ERROR: Nothing rendered — check pandoc and wiki.xml", file=sys.stderr)
        sys.exit(5)

    # ── 4. Index page ──
    print("\n[STEP 3] Writing index.html ...")
    write_index_html(pages, title_to_file, index_tpl)

    # ── 5. Search page ──
    print("\n[STEP 4] Writing search.html ...")
    write_search_html(article_tpl)

    # ── 6. Search index ──
    print("\n[STEP 5] Writing search-index.json ...")
    write_search_index(search_index)

    # ── 7. Sitemap ──
    print("\n[STEP 6] Writing sitemap.xml ...")
    write_sitemap()

    # ── 8. Robots + .nojekyll ──
    print("\n[STEP 7] Writing robots.txt + .nojekyll ...")
    write_robots()
    write_nojekyll()

    # ── 9. Timestamp ──
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(".last_sync", "w") as f:
        f.write(ts + "\n")

    print("\n" + "=" * 60)
    print(f"BUILD COMPLETE  —  {rendered} articles  |  {BASE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
