#!/usr/bin/env python3
"""
build.py  --  Singularity University Encyclopedia Builder
Self-contained. No external Python imports.
Reads:  backup/wiki.xml
Writes: ArticleName.html (one per article), index.html, search.html,
        search-index.json, sitemap.xml, .last_sync
Requires: pandoc (apt install pandoc)
"""

import html as html_module
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

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
XML_PATH      = "backup/wiki.xml"
OUTPUT_DIR    = "."
TODAY         = datetime.now(timezone.utc).strftime("%Y-%m-%d")
GOOGLE_VERIFY = "D-u4byZG_DrIUxnTLQdS0BOTjJcwWmm_h-HwUXl8HO4"
LOGO_URL      = ("https://raw.githubusercontent.com/singularity-news/wiki"
                 "/57d6999f3aa1e574cc45619c5ec7b52592d42e61/assets/logo.png")
OG_IMAGE      = ("https://raw.githubusercontent.com/singularity-news/wiki"
                 "/57d6999f3aa1e574cc45619c5ec7b52592d42e61/assets/header.png")
SITEMAP_MAX   = 50000

_env_base = os.environ.get("PAGES_BASE", "").strip()
if _env_base:
    BASE = _env_base.rstrip("/")
else:
    _repo = os.environ.get("GITHUB_REPOSITORY", "")
    if _repo and "/" in _repo:
        _owner, _name = _repo.split("/", 1)
        BASE = f"https://{_owner}.github.io/{_name}"
    else:
        BASE = "https://singularity-news.github.io/wiki"

STOP = set(
    "der die das und oder aber wenn dann weil wie was wer wo warum wieso ein eine einer "
    "eines einem einen im in ins am an auf aus bei mit nach von vom zum zur uber unter "
    "fur gegen ohne um als ist sind war waren nicht kein keine keinen keiner "
    "the a an and or but if then because how what who where why in on at to from for "
    "with without of is are was were be been being not no yes have has had will would "
    "could should may might this that these those it its they them their we our you your "
    "article page wiki html div span href src table ref cite also see".split()
)

# ---------------------------------------------------------------------------
# SHARED HTML COMPONENTS
# ---------------------------------------------------------------------------

def make_topbar():
    return f"""<div class="overlay" id="overlay" aria-hidden="true"></div>

<header class="topbar" role="banner">
  <button class="icon-btn" id="menuToggle" aria-label="Open menu" aria-expanded="false" aria-controls="sidebar">
    <svg width="18" height="18" viewBox="0 0 18 18" fill="currentColor" aria-hidden="true">
      <rect y="2" width="18" height="2" rx="1"/>
      <rect y="8" width="18" height="2" rx="1"/>
      <rect y="14" width="18" height="2" rx="1"/>
    </svg>
  </button>
  <a href="index.html" class="topbar-logo">
    <img src="{LOGO_URL}" alt="Singularity University Wiki" width="34" height="34" loading="lazy">
    <div class="logo-text">
      <span class="logo-name">Singularity University</span>
      <span class="logo-sub">KdK Krzb. Online Wiki</span>
    </div>
  </a>
  <div class="topbar-actions">
    <button class="icon-btn" id="themeToggle" aria-label="Toggle theme" title="Toggle theme">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="12" cy="12" r="5"/>
        <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
        <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
      </svg>
    </button>
    <a href="search.html" class="icon-btn" aria-label="Search" title="Search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
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
  <nav class="sidebar-links" aria-label="Navigation">
    <a href="index.html">&#127968; Encyclopedia</a>
    <a href="search.html">&#128269; Search</a>
    <a href="https://kdk-university.netlify.app/" target="_blank" rel="noopener">&#127891; KdK University</a>
    <a href="https://electric-paradise.start.page" target="_blank" rel="noopener">&#9889; Electric Paradise</a>
    <a href="https://singularity-news.github.io/" target="_blank" rel="noopener">&#128240; Singularity News</a>
    <a href="https://github.com/singularity-news/wiki" target="_blank" rel="noopener">&#128230; GitHub</a>
  </nav>
</aside>"""


def make_footer():
    return """<footer class="footer" role="contentinfo">
  <div class="footer-inner">
    <a class="footer-link" href="https://world.rf.gd" target="_blank" rel="noopener">
      <span class="fi">&#127760;</span>
      <span><strong>WSD - World Succession Deed 1400/98</strong><br>world.rf.gd &middot; worldsold.wixsite.com/world-sold/en</span>
    </a>
    <a class="footer-link" href="https://global-archive.rf.gd" target="_blank" rel="noopener">
      <span class="fi">&#127760;</span>
      <span><strong>WSD &ndash; Global Legal Succession Archive</strong><br>global-archive.rf.gd &middot; worldsold.wixsite.com/global-archive</span>
    </a>
    <a class="footer-link" href="https://ep.ct.ws" target="_blank" rel="noopener">
      <span class="fi">&#127760;</span>
      <span><strong>Electric Technocracy</strong><br>ep.ct.ws &middot; worldsold.wixsite.com/electric-technocracy</span>
    </a>
    <a class="footer-link" href="https://videos.xo.je" target="_blank" rel="noopener">
      <span class="fi">&#127909;</span>
      <span><strong>YouTube Channel</strong><br>videos.xo.je &middot; youtube.com/@Staatensukzessionsurkunde-1400</span>
    </a>
    <a class="footer-link" href="https://nwo.likesyou.org" target="_blank" rel="noopener">
      <span class="fi">&#127911;</span>
      <span><strong>Podcast Show</strong><br>nwo.likesyou.org &middot; Spotify</span>
    </a>
    <a class="footer-link" href="https://electric-paradise.start.page" target="_blank" rel="noopener">
      <span class="fi">&#128640;</span>
      <span><strong>Start-Page WSD &amp; Electric Paradise</strong><br>electric-paradise.start.page</span>
    </a>
    <a class="footer-link" href="https://patch98.wordpress.com" target="_blank" rel="noopener">
      <span class="fi">&#9889;</span>
      <span><strong>The Patch Blog: Exponential Tech</strong><br>patch98.wordpress.com</span>
    </a>
    <a class="footer-link" href="https://now31.wordpress.com" target="_blank" rel="noopener">
      <span class="fi">&#127963;</span>
      <span><strong>Homo Nexus Blog</strong><br>now31.wordpress.com</span>
    </a>
    <a class="footer-link" href="https://chatgpt.com/g/g-69d8635591d48191adc315b8f2b8be32-electric-technocracy-a-new-form-of-government" target="_blank" rel="noopener">
      <span class="fi">&#128172;</span>
      <span><strong>Electric Technocracy GPT</strong><br>chatgpt.com</span>
    </a>
    <a class="footer-link" href="https://chatgpt.com/g/g-69d95a89896081918fcb207e1665bf26-juridical-singularity-domestic-international-law" target="_blank" rel="noopener">
      <span class="fi">&#128172;</span>
      <span><strong>Juridical SINGULARITY GPT</strong><br>chatgpt.com</span>
    </a>
  </div>
  <div class="footer-bottom">
    <p>
      &copy; 2026 Singularity University Wiki &middot; KdK Kreuzberg
      <span class="fsep">&middot;</span>
      <a href="https://github.com/singularity-news/wiki" target="_blank" rel="noopener">GitHub</a>
      <span class="fsep">&middot;</span>
      <a href="sitemap.xml">Sitemap</a>
    </p>
  </div>
</footer>"""


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def strip_ns(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def safe_filename(title):
    t = unicodedata.normalize("NFKC", (title or "").strip())
    t = re.sub(r"[^\w\- ]+", "", t)
    t = t.replace(" ", "_")
    return (t or "Untitled") + ".html"


def strip_html_tags(s):
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", s)
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_module.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def make_description(plain, length=250):
    t = re.sub(r"\s+", " ", plain).strip()
    if len(t) <= length:
        return t
    cut = t[:length]
    ls = cut.rfind(" ")
    return (cut[:ls] if ls > 180 else cut).rstrip(".,;:") + "..."


def make_keywords(plain, n=15):
    words = re.findall(r"[A-Za-z\xC0-\xFF\u0100-\u024F]{3,}", plain.lower())
    words = [w for w in words if w not in STOP]
    return [w for w, _ in Counter(words).most_common(n)]


def rewrite_links(fragment, t2f):
    def repl(m):
        href = m.group(1)
        raw = href
        for pfx in ("/wiki/", "./", "../"):
            if href.startswith(pfx):
                href = href[len(pfx):]
                break
        frag = ""
        if "#" in href:
            href, frag = href.split("#", 1)
            frag = "#" + frag
        key = href.split("?", 1)[0].replace(" ", "_")
        if key in t2f:
            return 'href="' + t2f[key] + frag + '"'
        return 'href="' + raw + '"'
    return re.sub(r'href="([^"]+)"', repl, fragment)


def make_schema(title, desc, canonical):
    obj = {
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
    }
    return json.dumps(obj, ensure_ascii=False)


# ---------------------------------------------------------------------------
# HEAD BUILDER
# ---------------------------------------------------------------------------
def make_head(title, desc, keywords_list, canonical, extra_meta=""):
    te  = html_module.escape(title)
    de  = html_module.escape(desc)
    ce  = html_module.escape(canonical)
    kwe = html_module.escape(", ".join(keywords_list))
    sc  = make_schema(title, desc, canonical)
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-site-verification" content="{GOOGLE_VERIFY}">
<title>{te} &mdash; Singularity University Wiki</title>
<meta name="description" content="{de}">
<meta name="keywords" content="{kwe}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{ce}">
<link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="favicon-16x16.png">
<link rel="manifest" href="site.webmanifest">
<meta property="og:type" content="article">
<meta property="og:title" content="{te}">
<meta property="og:description" content="{de}">
<meta property="og:image" content="{OG_IMAGE}">
<meta property="og:url" content="{ce}">
<meta property="og:site_name" content="Singularity University Wiki">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{te}">
<meta name="twitter:description" content="{de}">
<meta name="twitter:image" content="{OG_IMAGE}">
<script type="application/ld+json">{sc}</script>{extra_meta}
<link rel="stylesheet" href="assets/style.css">"""


# ---------------------------------------------------------------------------
# ARTICLE PAGE
# ---------------------------------------------------------------------------
def make_article_page(title, fragment, t2f):
    filename  = t2f[title]
    canonical = BASE + "/" + filename
    plain     = strip_html_tags(fragment)
    desc      = make_description(plain, 250)
    keywords  = make_keywords(plain, 15)
    te        = html_module.escape(title)
    head      = make_head(title, desc, keywords, canonical)
    topbar    = make_topbar()
    footer    = make_footer()

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
{head}
</head>
<body>

{topbar}

<div class="page-wrap">

  <nav class="breadcrumbs" id="breadcrumbs" aria-label="Page path"></nav>

  <div class="content-wrap">

    <main class="article-col" id="main-content">
      <div class="article-header">
        <h1 class="article-title">{te}</h1>
        <div class="article-meta">
          <span>Updated: {TODAY}</span>
          <span><a href="index.html">&#8592; Encyclopedia</a></span>
        </div>
      </div>
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

  {footer}

</div>

<script src="assets/app.js"></script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# INDEX PAGE
# ---------------------------------------------------------------------------
def make_index_page():
    canonical = BASE + "/index.html"
    meta_desc = ("Encyclopedia of the Singularity University KdK Krzb. Explore Juridical Singularity, "
                 "the Age of Transition, Electric Technocracy, ASI governance, post-scarcity economics, "
                 "and the World Succession Deed 1400/98.")
    kw_list = [
        "Juridical Singularity", "Electric Technocracy", "Age of Transition",
        "World Succession Deed", "1400/98", "Homo Nexus", "ASI Governance",
        "Direct Digital Democracy", "Universal Basic Income", "Tech Tax",
        "Post-Scarcity", "Treaty Chain", "International Law", "NATO SOFA",
        "United Nations", "Telecommunications Infrastructure", "Global Governance",
        "AI Civilization", "Mental Singularity", "Automation Economy",
        "Longevity", "Neural Networks", "State Succession", "Smart Democracy",
        "Planetary System", "DDD"
    ]
    ws_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Singularity University Wiki",
        "url": BASE + "/",
        "description": meta_desc
    }, ensure_ascii=False)
    ce  = html_module.escape(canonical)
    de  = html_module.escape(meta_desc)
    kwe = html_module.escape(", ".join(kw_list))

    head = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-site-verification" content="{GOOGLE_VERIFY}">
<title>Encyclopedia of the Singularity University KdK Krzb.</title>
<meta name="description" content="{de}">
<meta name="keywords" content="{kwe}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{ce}">
<link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="favicon-16x16.png">
<link rel="manifest" href="site.webmanifest">
<meta property="og:type" content="website">
<meta property="og:title" content="Encyclopedia of the Singularity University KdK Krzb.">
<meta property="og:description" content="{de}">
<meta property="og:image" content="{OG_IMAGE}">
<meta property="og:url" content="{ce}">
<meta property="og:site_name" content="Singularity University Wiki">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Encyclopedia of the Singularity University KdK Krzb.">
<meta name="twitter:description" content="{de}">
<meta name="twitter:image" content="{OG_IMAGE}">
<script type="application/ld+json">{ws_schema}</script>
<link rel="stylesheet" href="assets/style.css">"""

    topbar = make_topbar()
    footer = make_footer()

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
{head}
</head>
<body>

{topbar}

<div class="page-wrap">

  <section class="hero" aria-label="Encyclopedia banner">
    <img class="hero-img"
         src="{OG_IMAGE}"
         alt="Singularity University Encyclopedia"
         loading="eager" fetchpriority="high">
    <div class="hero-fade" aria-hidden="true"></div>
    <div class="hero-text">
      <h1>The Encyclopedia of Juridical Singularity, Age of Transition and Electric Technocracy</h1>
      <h2>From the World Succession Deed 1400/98 to the Rise of Homo Nexus</h2>
    </div>
  </section>

  <div class="index-intro">
    <p>The Encyclopedia of the Singularity University KdK Krzb. documents the emerging transformation of international law, governance, technology, and civilization in the Age of Transition. It explores the doctrine of the Juridical Singularity, the structural transition from nation-state systems toward planetary coordination, and the rise of Electric Technocracy as a post-scarcity governance architecture.</p>
    <p>At the center of this framework stands the World Succession Deed 1400/98, a disputed legal instrument discussed in more than 1,000 court cases and interpreted as a constitutive event in international treaty law. According to the doctrine, the transfer of the Kreuzbergkaserne military infrastructure &ldquo;with all rights, obligations, and components&rdquo; triggered a treaty-chain expansion through NATO, telecommunications systems, and UN-connected infrastructure networks. The result is described as the Juridical Singularity: the collapse of the traditional plurality of sovereign actors into a unified legal continuum.</p>
    <p>The encyclopedia examines how technological acceleration transforms society beyond classical industrial civilization. Artificial Intelligence, automation, robotics, nanotechnology, fusion energy, and neurotechnology increasingly dissolve scarcity-based economics. Electric Technocracy emerges as the proposed governance model for this new epoch: a system of Direct Digital Democracy supported by Artificial Superintelligence (ASI), where machine productivity finances a Universal Basic Income through a technology tax while humans become tax-free participants in a globally networked civilization.</p>
    <p>The Age of Transition also describes a psychological and cognitive transformation. Humanity moves from Homo sapiens, shaped by scarcity and territorial competition, toward Homo nexus, a networked form of civilization integrated through digital systems, BCIs, and global information infrastructures. Political parties, wage dependency, and rigid borders become increasingly obsolete as algorithmic coordination and post-labor economics redefine social organization.</p>
    <p>This encyclopedia serves as a knowledge archive for treaty-chain theory, state succession doctrine, post-scarcity economics, AI governance, longevity research, telecommunications infrastructure, global digital democracy, and the future evolution of civilization beyond the Westphalian state system.</p>
  </div>

  <section class="index-section" aria-labelledby="grid-heading">
    <h2 class="section-title" id="grid-heading">All Articles &nbsp;<span id="articleCount" style="font-weight:700;color:var(--accent);font-size:1em;letter-spacing:0;text-transform:none;"></span></h2>
    <div class="article-grid" id="indexGrid" role="list">
      <p class="loading"><span class="dot" aria-hidden="true"></span> Loading articles...</p>
    </div>
  </section>

  {footer}

</div>

<script src="assets/app.js"></script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# SEARCH PAGE
# ---------------------------------------------------------------------------
def make_search_page():
    canonical = BASE + "/search.html"
    ce = html_module.escape(canonical)

    head = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Search &mdash; Singularity University Wiki</title>
<meta name="description" content="Search the Singularity University Encyclopedia by keyword or topic.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{ce}">
<link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="favicon-16x16.png">
<link rel="manifest" href="site.webmanifest">
<link rel="stylesheet" href="assets/style.css">"""

    topbar = make_topbar()
    footer = make_footer()

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
{head}
</head>
<body>

{topbar}

<div class="page-wrap">

  <nav class="breadcrumbs" id="breadcrumbs" aria-label="Page path"></nav>

  <div class="search-page">
    <div class="search-hero">
      <h1>Search Encyclopedia</h1>
      <p>Full-text search across all articles, ranked by relevance.</p>
    </div>
    <div class="search-bar-wrap">
      <input type="search" id="searchPageInput"
        placeholder="Search articles, topics, keywords..."
        aria-label="Search encyclopedia" autocomplete="off">
      <button id="searchPageBtn" type="button">Search</button>
    </div>
    <div class="search-count" id="searchCount"></div>
    <div class="search-results" id="searchResults">
      <p class="loading" style="display:none;"></p>
    </div>
  </div>

  {footer}

</div>

<script src="assets/app.js"></script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# XML PARSING
# ---------------------------------------------------------------------------
def parse_wiki_xml():
    SKIP = ("Special:", "File:", "Template:", "MediaWiki:",
            "Category:", "Help:", "User:", "Talk:", "Portal:")
    pages = []
    try:
        for event, elem in ET.iterparse(XML_PATH, events=("end",)):
            if strip_ns(elem.tag) != "page":
                continue
            title_el = elem.find(".//{*}title")
            ns_el    = elem.find(".//{*}ns")
            text_el  = elem.find(".//{*}text")
            title    = (title_el.text or "").strip() if title_el is not None else ""
            ns       = (ns_el.text    or "0").strip() if ns_el    is not None else "0"
            wikitext = (text_el.text  or "")          if text_el  is not None else ""
            if ns == "0" and title and not any(title.startswith(p) for p in SKIP):
                pages.append((title, wikitext))
            elem.clear()
    except ET.ParseError as exc:
        print(f"ERROR: XML parse error: {exc}", file=sys.stderr)
        sys.exit(3)
    return pages


# ---------------------------------------------------------------------------
# RENDER
# ---------------------------------------------------------------------------
def render_all(pages, t2f):
    search_index = []
    rendered = 0

    with tempfile.TemporaryDirectory() as td:
        for i, (title, wikitext) in enumerate(pages, 1):
            fn  = t2f[title]
            tw  = os.path.join(td, f"{i}.wiki")
            th  = os.path.join(td, f"{i}.html")

            with open(tw, "w", encoding="utf-8") as f:
                f.write(wikitext)

            result = subprocess.run(
                ["pandoc", tw, "-f", "mediawiki", "-t", "html",
                 "--wrap=none", "-o", th],
                capture_output=True
            )
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace").strip()
                print(f"  [WARN] pandoc '{title}': {err}", file=sys.stderr)
                # Write minimal fallback
                fragment = f"<p>{html_module.escape(wikitext[:500])}</p>"
            else:
                fragment = open(th, "r", encoding="utf-8").read().strip()

            fragment = rewrite_links(fragment, t2f)
            page_html = make_article_page(title, fragment, t2f)

            out_path = os.path.join(OUTPUT_DIR, fn)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(page_html)

            plain = strip_html_tags(fragment)
            search_index.append({
                "title": title,
                "file":  fn,
                "text":  plain[:500],
                "date":  TODAY
            })
            rendered += 1
            if rendered % 50 == 0:
                print(f"  [{rendered}/{len(pages)}] articles rendered...")

    return search_index, rendered


# ---------------------------------------------------------------------------
# SITEMAP
# ---------------------------------------------------------------------------
def write_sitemap(html_files):
    total = len(html_files)
    parts = max(1, math.ceil(total / SITEMAP_MAX))
    if parts == 1:
        with open("sitemap.xml", "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for fn in html_files:
                loc = html_module.escape(BASE + "/" + fn)
                f.write(f'  <url><loc>{loc}</loc><lastmod>{TODAY}</lastmod>'
                        f'<changefreq>monthly</changefreq><priority>0.7</priority></url>\n')
            f.write('</urlset>\n')
        print(f"[OK] sitemap.xml ({total} URLs)")
    else:
        os.makedirs("sitemaps", exist_ok=True)
        sm_files = []
        for p in range(parts):
            chunk = html_files[p * SITEMAP_MAX:(p + 1) * SITEMAP_MAX]
            sm = f"sitemaps/sitemap-{p+1}.xml"
            sm_files.append(sm)
            with open(sm, "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
                for fn in chunk:
                    loc = html_module.escape(BASE + "/" + fn)
                    f.write(f'  <url><loc>{loc}</loc><lastmod>{TODAY}</lastmod>'
                            f'<changefreq>monthly</changefreq><priority>0.7</priority></url>\n')
                f.write('</urlset>\n')
        with open("sitemaps/sitemap-index.xml", "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for sm in sm_files:
                loc = html_module.escape(BASE + "/" + sm)
                f.write(f'  <sitemap><loc>{loc}</loc><lastmod>{TODAY}</lastmod></sitemap>\n')
            f.write('</sitemapindex>\n')
        print(f"[OK] {parts} sitemaps in sitemaps/ ({total} URLs)")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("Singularity University Encyclopedia -- Build Script")
    print(f"Base URL: {BASE}")
    print("=" * 60)

    # Pre-flight checks
    if not os.path.isfile(XML_PATH):
        print(f"ERROR: {XML_PATH} not found", file=sys.stderr)
        sys.exit(2)

    r = subprocess.run(["pandoc", "--version"], capture_output=True)
    if r.returncode != 0:
        print("ERROR: pandoc not found. Install: sudo apt-get install pandoc", file=sys.stderr)
        sys.exit(2)
    pv = r.stdout.decode().split("\n")[0].strip()
    print(f"[OK] {pv}")
    print(f"[OK] {XML_PATH} found")

    # Parse XML
    print(f"\n[STEP 1] Parsing {XML_PATH}...")
    pages = parse_wiki_xml()
    print(f"[INFO] Articles found: {len(pages)}")
    if not pages:
        print("ERROR: No main-namespace pages in wiki.xml", file=sys.stderr)
        sys.exit(4)

    # Build title -> filename map
    t2f = {}
    for title, _ in pages:
        fn = safe_filename(title)
        t2f[title]                   = fn
        t2f[title.replace(" ", "_")] = fn
        t2f[title.replace("_", " ")] = fn

    # Render articles
    print(f"\n[STEP 2] Rendering {len(pages)} articles with pandoc...")
    search_index, rendered = render_all(pages, t2f)
    print(f"[INFO] Articles rendered: {rendered}")
    if rendered == 0:
        print("ERROR: No articles rendered", file=sys.stderr)
        sys.exit(5)

    # index.html
    print(f"\n[STEP 3] Writing index.html...")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(make_index_page())
    print("[OK] index.html")

    # search.html
    print(f"\n[STEP 4] Writing search.html...")
    with open("search.html", "w", encoding="utf-8") as f:
        f.write(make_search_page())
    print("[OK] search.html")

    # search-index.json
    print(f"\n[STEP 5] Writing search-index.json...")
    with open("search-index.json", "w", encoding="utf-8") as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)
    print(f"[OK] search-index.json ({len(search_index)} entries)")

    # sitemap
    print(f"\n[STEP 6] Writing sitemap...")
    all_html = sorted(
        fn for fn in os.listdir(OUTPUT_DIR)
        if fn.lower().endswith(".html") and fn not in ("template.html",)
    )
    write_sitemap(all_html)

    # .last_sync
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(".last_sync", "w") as f:
        f.write(ts + "\n")
    print(f"[OK] .last_sync: {ts}")

    print("\n" + "=" * 60)
    print(f"BUILD COMPLETE: {rendered} articles, {len(all_html)} HTML files")
    print("=" * 60)


if __name__ == "__main__":
    main()
