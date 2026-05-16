#!/usr/bin/env python3
"""
build.py  —  Singularity University Wiki
MediaWiki XML export → static HTML encyclopedia
Generates: ArticleName.html, index.html, search.html,
           search-index.json, sitemap.xml, robots.txt
Requires: pandoc, Python 3.10+ stdlib only
"""

import gzip, html, json, math, os, re, shlex, subprocess, sys, tempfile, unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone

# ── Config ─────────────────────────────────────────────────────────────────
XML_PATH      = "backup/wiki.xml"
TEMPLATE_PATH = "template.html"
OUTPUT_DIR    = "."
SITEMAP_MAX   = 50_000
TODAY         = datetime.now(timezone.utc).strftime("%Y-%m-%d")
GOOGLE_VERIFY = "D-u4byZG_DrIUxnTLQdS0BOTjJcwWmm_h-HwUXl8HO4"

LOGO_URL   = "https://raw.githubusercontent.com/singularity-news/wiki/57d6999f3aa1e574cc45619c5ec7b52592d42e61/assets/logo.png"
HEADER_IMG = "https://raw.githubusercontent.com/singularity-news/wiki/57d6999f3aa1e574cc45619c5ec7b52592d42e61/assets/header.png"

# Base URL detection
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
    "could should may might this that these those it its they them their "
    "article page wiki html div span href src img table code pre ref cite".split()
)

# ── Footer HTML (shared by all pages) ──────────────────────────────────────
FOOTER_LINKS = [
    ("🌐", "WSD — World Succession Deed 1400/98",
     "https://world.rf.gd", "world.rf.gd"),
    ("🌐", "WSD — Global Legal Succession Archive",
     "https://global-archive.rf.gd", "global-archive.rf.gd"),
    ("🌐", "Electric Technocracy",
     "https://ep.ct.ws", "ep.ct.ws"),
    ("🎥", "YouTube Channel",
     "https://videos.xo.je", "videos.xo.je"),
    ("🎙️", "Podcast Show",
     "https://nwo.likesyou.org", "nwo.likesyou.org"),
    ("🚀", "Start-Page WSD &amp; Electric Paradise",
     "https://electric-paradise.start.page", "electric-paradise.start.page"),
    ("⚡", "The Patch Blog: Exponential Tech",
     "https://patch98.wordpress.com", "patch98.wordpress.com"),
    ("🏛️", "Homo Nexus Blog",
     "https://now31.wordpress.com", "now31.wordpress.com"),
    ("🗨️", "Electric Technocracy GPT",
     "https://chatgpt.com/g/g-69d8635591d48191adc315b8f2b8be32-electric-technocracy-a-new-form-of-government",
     "chatgpt.com"),
    ("🗨️", "Juridical SINGULARITY GPT",
     "https://chatgpt.com/g/g-69d95a89896081918fcb207e1665bf26-juridical-singularity-domestic-international-law",
     "chatgpt.com"),
]

def build_footer_html() -> str:
    items = "\n".join(
        f'      <a class="footer-link" href="{url}" target="_blank" rel="noopener">'
        f'<span class="footer-icon">{icon}</span>'
        f'<span>{label}<br><small>{domain}</small></span></a>'
        for icon, label, url, domain in FOOTER_LINKS
    )
    return f"""  <footer class="footer" role="contentinfo">
    <div class="footer-links">
{items}
    </div>
    <div class="footer-bottom">
      &copy; 2026 Singularity University Wiki &middot; KdK Kreuzberg
      <span class="footer-sep">&middot;</span>
      <a href="https://github.com/singularity-news/wiki" target="_blank" rel="noopener">GitHub</a>
      <span class="footer-sep">&middot;</span>
      <a href="sitemap.xml">Sitemap</a>
      <span class="footer-sep">&middot;</span>
      <a href="https://kdk-university.netlify.app/" target="_blank" rel="noopener">KdK University</a>
    </div>
  </footer>"""

FOOTER_HTML = build_footer_html()

# ── Helpers ─────────────────────────────────────────────────────────────────
def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag

def safe_filename(title: str) -> str:
    t = (title or "").strip()
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"[^\w\- ]+", "", t)
    t = t.replace(" ", "_")
    return (t or "Untitled") + ".html"

def strip_html_tags(s: str) -> str:
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", s)
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def top_keywords(text: str, n: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z\xC0-\xD6\xD8-\xF6\xF8-\xFF\u0100-\u024F0-9_'-]{3,}", text.lower())
    words = [w for w in words if w not in STOP and not w.isdigit()]
    return [w for w, _ in Counter(words).most_common(n)]

def rewrite_internal_links(fragment: str, title_to_file: dict) -> str:
    def repl(m: re.Match) -> str:
        href = m.group(1)
        raw = href
        for prefix in ("/wiki/", "./", "../"):
            if href.startswith(prefix):
                href = href[len(prefix):]
                break
        bare = href.split("#", 1)[0].split("?", 1)[0].replace(" ", "_")
        if bare in title_to_file:
            frag = ("#" + href.split("#", 1)[1]) if "#" in href else ""
            return f'href="{title_to_file[bare]}{frag}"'
        return f'href="{raw}"'
    return re.sub(r'href="([^"]+)"', repl, fragment)

def make_schema_json(title: str, description: str, canonical: str) -> str:
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "dateModified": TODAY,
        "image": HEADER_IMG,
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "publisher": {
            "@type": "Organization",
            "name": "Singularity University Wiki",
            "url": BASE + "/"
        }
    }, ensure_ascii=False)

# ── Preflight ────────────────────────────────────────────────────────────────
def preflight() -> str:
    if not os.path.isfile(XML_PATH):
        print(f"ERROR: {XML_PATH} not found", file=sys.stderr); sys.exit(2)
    if not os.path.isfile(TEMPLATE_PATH):
        print(f"ERROR: {TEMPLATE_PATH} not found", file=sys.stderr); sys.exit(2)
    tpl = open(TEMPLATE_PATH, encoding="utf-8").read()
    if "{html_body}" not in tpl:
        print("ERROR: template.html must contain {html_body}", file=sys.stderr); sys.exit(2)
    result = subprocess.run(["pandoc", "--version"], capture_output=True)
    if result.returncode != 0:
        print("ERROR: pandoc not found", file=sys.stderr); sys.exit(2)
    print(f"[OK] XML: {XML_PATH}  |  Template: {TEMPLATE_PATH}  |  Base: {BASE}")
    return tpl

# ── XML Parsing ──────────────────────────────────────────────────────────────
SKIP_PREFIXES = ("Special:", "File:", "Template:", "MediaWiki:",
                 "Category:", "Help:", "User:", "Talk:", "Wikipedia:")

def parse_wiki_xml() -> list[tuple[str, str]]:
    pages = []
    try:
        for event, elem in ET.iterparse(XML_PATH, events=("end",)):
            if strip_ns(elem.tag) == "page":
                title_el = elem.find(".//{*}title")
                ns_el    = elem.find(".//{*}ns")
                text_el  = elem.find(".//{*}text")
                title    = (title_el.text or "").strip() if title_el is not None else ""
                ns       = (ns_el.text or "").strip()    if ns_el is not None else "0"
                wikitext = (text_el.text or "")           if text_el is not None else ""
                if ns == "0" and title and not any(title.startswith(p) for p in SKIP_PREFIXES):
                    pages.append((title, wikitext))
                elem.clear()
    except ET.ParseError as exc:
        print(f"ERROR: XML parse error: {exc}", file=sys.stderr); sys.exit(3)
    return pages

# ── Rendering ────────────────────────────────────────────────────────────────
def render_pages(pages, template, title_to_file) -> tuple[list[dict], int]:
    search_index = []
    rendered = 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        for i, (title, wikitext) in enumerate(pages, 1):
            filename = title_to_file[title]
            out_path = os.path.join(OUTPUT_DIR, filename)
            tmp_wiki = os.path.join(tmp_dir, f"{i}.wiki")
            tmp_html = os.path.join(tmp_dir, f"{i}.html")

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

            fragment = open(tmp_html, encoding="utf-8").read().strip()
            fragment = rewrite_internal_links(fragment, title_to_file)

            plain_text  = strip_html_tags(fragment)
            description = plain_text[:300] + ("..." if len(plain_text) > 300 else "")
            keywords    = top_keywords(plain_text, 12)
            canonical   = f"{BASE}/{filename}"
            schema_json = make_schema_json(title, description, canonical)
            title_esc   = html.escape(title)
            desc_esc    = html.escape(description)
            canon_esc   = html.escape(canonical)
            kw_esc      = html.escape(", ".join(keywords))

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
                f'<meta property="og:image" content="{html.escape(HEADER_IMG)}">\n'
                f'<meta name="twitter:card" content="summary_large_image">\n'
                f'<script type="application/ld+json">{schema_json}</script>'
            )

            # Inject breadcrumb data attribute on body
            page_html = template.replace("{html_body}", fragment)
            page_html = page_html.replace('<body>', f'<body data-title="{title_esc}">', 1)
            if "</head>" in page_html:
                page_html = page_html.replace("</head>", head_meta + "\n</head>", 1)
            # Inject footer
            page_html = page_html.replace("{footer}", FOOTER_HTML)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(page_html)

            search_index.append({
                "title": title,
                "file":  filename,
                "text":  plain_text[:500],
                "date":  TODAY
            })
            rendered += 1
            if rendered % 50 == 0:
                print(f"  Rendered {rendered}/{len(pages)} ...")

    print(f"[INFO] Rendered: {rendered}  Total: {len(pages)}")
    return search_index, rendered

# ── Index page ───────────────────────────────────────────────────────────────
INDEX_INTRO = """<section class="encyclopedia-intro">
  <h1>The Encyclopedia of Juridical Singularity, Age of Transition and Electric Technocracy</h1>
  <h2>From the World Succession Deed 1400/98 to the Rise of Homo Nexus</h2>
  <div class="intro-text">
    <p>The Encyclopedia of the Singularity University KdK Krzb. documents the emerging transformation of international law, governance, technology, and civilization in the Age of Transition. It explores the doctrine of the Juridical Singularity, the structural transition from nation-state systems toward planetary coordination, and the rise of Electric Technocracy as a post-scarcity governance architecture.</p>
    <p>At the center of this framework stands the World Succession Deed 1400/98, a disputed legal instrument discussed in more than 1,000 court cases and interpreted as a constitutive event in international treaty law. According to the doctrine, the transfer of the Kreuzbergkaserne military infrastructure &ldquo;with all rights, obligations, and components&rdquo; triggered a treaty-chain expansion through NATO, telecommunications systems, and UN-connected infrastructure networks. The result is described as the Juridical Singularity: the collapse of the traditional plurality of sovereign actors into a unified legal continuum.</p>
    <p>The encyclopedia examines how technological acceleration transforms society beyond classical industrial civilization. Artificial Intelligence, automation, robotics, nanotechnology, fusion energy, and neurotechnology increasingly dissolve scarcity-based economics. Electric Technocracy emerges as the proposed governance model for this new epoch: a system of Direct Digital Democracy supported by Artificial Superintelligence (ASI), where machine productivity finances a Universal Basic Income through a technology tax while humans become tax-free participants in a globally networked civilization.</p>
    <p>The Age of Transition also describes a psychological and cognitive transformation. Humanity moves from Homo sapiens, shaped by scarcity and territorial competition, toward Homo nexus, a networked form of civilization integrated through digital systems, BCIs, and global information infrastructures. Political parties, wage dependency, and rigid borders become increasingly obsolete as algorithmic coordination and post-labor economics redefine social organization.</p>
    <p>This encyclopedia serves as a knowledge archive for treaty-chain theory, state succession doctrine, post-scarcity economics, AI governance, longevity research, telecommunications infrastructure, global digital democracy, and the future evolution of civilization beyond the Westphalian state system.</p>
  </div>
</section>
<section class="index-section" aria-labelledby="grid-heading">
  <h2 class="section-title" id="grid-heading">All Articles</h2>
  <div class="article-grid" id="indexGrid" role="list">
    <p class="loading"><span class="dot" aria-hidden="true"></span> Loading articles...</p>
  </div>
</section>"""

def write_index_html(html_files, title_to_file, template):
    file_to_title = {v: k for k, v in title_to_file.items()}
    article_files = sorted([f for f in html_files if f not in ("index.html", "search.html", "template.html")])

    head_meta = (
        '<title>Encyclopedia &mdash; Singularity University KdK Krzb.</title>\n'
        '<meta name="description" content="Encyclopedia of the Singularity University KdK Krzb. Explore Juridical Singularity, Age of Transition, Electric Technocracy, ASI governance, and the World Succession Deed 1400/98.">\n'
        '<meta name="keywords" content="Juridical Singularity, Electric Technocracy, Age of Transition, World Succession Deed, 1400/98, Homo Nexus, ASI Governance, Direct Digital Democracy, Universal Basic Income, Tech Tax, Post-Scarcity, Treaty Chain, International Law, NATO SOFA, United Nations, Global Governance, AI Civilization, State Succession, Smart Democracy, Planetary System">\n'
        f'<link rel="canonical" href="{html.escape(BASE)}/">\n'
        f'<meta name="google-site-verification" content="{GOOGLE_VERIFY}">\n'
        f'<meta property="og:title" content="Encyclopedia — Singularity University Wiki">\n'
        f'<meta property="og:image" content="{html.escape(HEADER_IMG)}">\n'
        '<meta property="og:type" content="website">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
    )

    page_html = template.replace("{html_body}", INDEX_INTRO)
    page_html = page_html.replace("{footer}", FOOTER_HTML)
    if "</head>" in page_html:
        page_html = page_html.replace("</head>", head_meta + "\n</head>", 1)

    index_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(page_html)
    print(f"[OK] index.html  ({len(article_files)} articles)")

# ── Search page ──────────────────────────────────────────────────────────────
SEARCH_HTML_BODY = """<div class="search-page">
  <h1>Search Articles</h1>
  <div class="search-wrap">
    <input type="search" id="pageSearchInput" placeholder="Search the encyclopedia..." autofocus aria-label="Search articles">
    <div id="searchStats" class="search-stats"></div>
  </div>
  <div id="searchResults" class="search-results" role="list"></div>
</div>"""

def write_search_html(template):
    head_meta = (
        '<title>Search &mdash; Singularity University Wiki</title>\n'
        '<meta name="description" content="Search the Singularity University Encyclopedia.">\n'
        f'<link rel="canonical" href="{html.escape(BASE)}/search.html">\n'
        f'<meta name="google-site-verification" content="{GOOGLE_VERIFY}">\n'
    )
    page_html = template.replace("{html_body}", SEARCH_HTML_BODY)
    page_html = page_html.replace("{footer}", FOOTER_HTML)
    if "</head>" in page_html:
        page_html = page_html.replace("</head>", head_meta + "\n</head>", 1)
    with open(os.path.join(OUTPUT_DIR, "search.html"), "w", encoding="utf-8") as f:
        f.write(page_html)
    print("[OK] search.html")

# ── search-index.json ────────────────────────────────────────────────────────
def write_search_index(search_index):
    path = os.path.join(OUTPUT_DIR, "search-index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)
    print(f"[OK] search-index.json  ({len(search_index)} entries)")

# ── sitemap.xml ──────────────────────────────────────────────────────────────
def write_sitemap(html_files):
    total = len(html_files)
    parts = max(1, -(-total // SITEMAP_MAX))  # ceiling div

    if parts == 1:
        path = os.path.join(OUTPUT_DIR, "sitemap.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for fn in html_files:
                loc = html.escape(f"{BASE}/{fn}")
                prio = "1.0" if fn == "index.html" else "0.7"
                f.write(
                    f'  <url><loc>{loc}</loc>'
                    f'<lastmod>{TODAY}</lastmod>'
                    f'<changefreq>monthly</changefreq>'
                    f'<priority>{prio}</priority></url>\n'
                )
            f.write('</urlset>\n')
        print(f"[OK] sitemap.xml  ({total} URLs)")

# ── robots.txt ───────────────────────────────────────────────────────────────
def write_robots():
    path = os.path.join(OUTPUT_DIR, "robots.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    print("[OK] robots.txt")

# ── Timestamp ────────────────────────────────────────────────────────────────
def write_last_sync():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(".last_sync", "w") as f:
        f.write(ts + "\n")

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Singularity University Wiki  —  Build Script")
    print("=" * 60)

    template = preflight()

    print(f"\n[STEP 1] Parsing {XML_PATH} ...")
    pages = parse_wiki_xml()
    print(f"[INFO] Parsed: {len(pages)} pages")
    if not pages:
        print("ERROR: No main-namespace pages found", file=sys.stderr); sys.exit(4)

    # Build title → filename map
    title_to_file: dict[str, str] = {}
    for title, _ in pages:
        fn = safe_filename(title)
        title_to_file[title]                   = fn
        title_to_file[title.replace(" ", "_")] = fn
        title_to_file[title.replace("_", " ")] = fn

    print(f"\n[STEP 2] Rendering {len(pages)} pages ...")
    search_index, rendered = render_pages(pages, template, title_to_file)
    if rendered == 0:
        print("ERROR: No HTML rendered", file=sys.stderr); sys.exit(5)

    # Collect HTML files (excluding template)
    html_files = sorted([
        f for f in os.listdir(OUTPUT_DIR)
        if f.lower().endswith(".html") and f.lower() != "template.html"
    ])

    print(f"\n[STEP 3] Writing index.html ...")
    write_index_html(html_files, title_to_file, template)

    print(f"\n[STEP 4] Writing search.html ...")
    write_search_html(template)

    # Refresh html_files list after new pages written
    html_files = sorted([
        f for f in os.listdir(OUTPUT_DIR)
        if f.lower().endswith(".html") and f.lower() != "template.html"
    ])

    print(f"\n[STEP 5] Writing search-index.json ...")
    write_search_index(search_index)

    print(f"\n[STEP 6] Writing sitemap.xml ...")
    write_sitemap(html_files)

    print(f"\n[STEP 7] Writing robots.txt ...")
    write_robots()

    write_last_sync()

    print("\n" + "=" * 60)
    print(f"BUILD COMPLETE  —  {rendered} articles  |  Base: {BASE}")
    print("=" * 60)

if __name__ == "__main__":
    main()
