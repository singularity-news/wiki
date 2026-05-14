# build.py

import os
import re
import json
import html
import unicodedata
import subprocess

from collections import Counter
import xml.etree.ElementTree as ET

BASE_URL = "https://singularity-news.github.io/wiki"

XML_FILE = "backup/wiki.xml"

TEMPLATE_FILE = "template.html"

SEARCH_FILE = "search-index.json"

STOPWORDS = set("""
the and with from this that these those your their our
der die das und oder eine einer einem eines
""".split())

if not os.path.exists(XML_FILE):
    raise SystemExit(f"Missing XML file: {XML_FILE}")

if not os.path.exists(TEMPLATE_FILE):
    raise SystemExit(f"Missing template: {TEMPLATE_FILE}")

TEMPLATE = open(
    TEMPLATE_FILE,
    encoding="utf-8"
).read()

ns = {
    "mw": "http://www.mediawiki.org/xml/export-0.10/"
}


def safe_filename(title):
    title = unicodedata.normalize("NFKC", title)

    title = re.sub(r"[^\w\s\-]", "", title)

    title = re.sub(r"\s+", "_", title.strip())

    return f"{title}.html"


def strip_tags(text):
    text = re.sub(r"<[^>]+>", " ", text)

    text = html.unescape(text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_keywords(text):
    words = re.findall(r"[a-zA-Z0-9]{4,}", text.lower())

    filtered = [
        w for w in words
        if w not in STOPWORDS
    ]

    return [
        w for w, _ in Counter(filtered).most_common(10)
    ]


def build_toc(content):

    headings = re.findall(
        r"<h([23])[^>]*>(.*?)</h[23]>",
        content,
        re.I
    )

    toc = []

    for i, (level, text) in enumerate(headings):

        clean = re.sub(r"<[^>]+>", "", text)

        anchor = f"section-{i}"

        old = f"<h{level}"

        new = f'<h{level} id="{anchor}"'

        content = content.replace(old, new, 1)

        toc.append({
            "level": level,
            "title": clean,
            "anchor": anchor
        })

    if not toc:
        return content

    html_toc = """
    <aside class="toc-box">
      <h3>Contents</h3>
      <ul>
    """

    for item in toc:

        html_toc += f"""
        <li class="toc-level-{item['level']}">
          <a href="#{item['anchor']}">
            {html.escape(item['title'])}
          </a>
        </li>
        """

    html_toc += """
      </ul>
    </aside>
    """

    return html_toc + content


pages = []

for _, elem in ET.iterparse(
    XML_FILE,
    events=("end",)
):

    if elem.tag.endswith("page"):

        title_el = elem.find("mw:title", ns)

        text_el = elem.find(".//mw:text", ns)

        if title_el is not None:

            title = title_el.text.strip()

            raw = ""

            if text_el is not None and text_el.text:
                raw = text_el.text

            pages.append((title, raw))

        elem.clear()

print(f"FOUND {len(pages)} PAGES")

title_map = {}

for title, _ in pages:

    fn = safe_filename(title)

    title_map[title] = fn

    title_map[title.replace(" ", "_")] = fn

search_index = []

generated = []

for index, (title, raw_text) in enumerate(pages):

    print(f"BUILDING: {title}")

    filename = safe_filename(title)

    with open(
        "/tmp/wiki_input.wiki",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(raw_text)

    subprocess.run([
        "pandoc",
        "/tmp/wiki_input.wiki",
        "-f",
        "mediawiki",
        "-t",
        "html",
        "--wrap=none",
        "-o",
        "/tmp/wiki_output.html"
    ], check=True)

    body = open(
        "/tmp/wiki_output.html",
        encoding="utf-8"
    ).read()

    def fix_link(match):

        target = match.group(1)

        if target in title_map:
            return f'href="{title_map[target]}"'

        return f'href="{target}"'

    body = re.sub(
        r'href="([^"]+)"',
        fix_link,
        body
    )

    body = build_toc(body)

    plain = strip_tags(body)

    desc = plain[:300]

    keywords = extract_keywords(plain)

    canonical = f"{BASE_URL}/{filename}"

    schema = f"""
    <script type="application/ld+json">
    {{
      "@context":"https://schema.org",
      "@type":"Article",
      "headline":"{html.escape(title)}",
      "description":"{html.escape(desc)}",
      "url":"{canonical}"
    }}
    </script>
    """

    breadcrumbs = f"""
    <nav class="breadcrumbs">
      <a href="encyclopedia.html">Home</a>
      <span>›</span>
      <span>{html.escape(title)}</span>
    </nav>
    """

    final_html = TEMPLATE.format(
        title_esc=html.escape(title),
        desc_esc=html.escape(desc),
        html_body=breadcrumbs + body,
        schema=schema,
        page_url=canonical,
        safe=filename.replace(".html", ""),
        wiki_url=BASE_URL
    )

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(final_html)

    generated.append(filename)

    search_index.append({
        "title": title,
        "file": filename,
        "text": plain[:50000]
    })

print("WRITING SEARCH INDEX")

with open(
    SEARCH_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        search_index,
        f,
        ensure_ascii=False,
        indent=2
    )

print("WRITING ENCYCLOPEDIA")

encyclopedia_cards = ""

for item in search_index:

    encyclopedia_cards += f"""
    <a class="article-card" href="{item['file']}">
      <h2>{html.escape(item['title'])}</h2>
      <p>{html.escape(item['text'][:160])}</p>
    </a>
    """

encyclopedia_html = TEMPLATE.format(
    title_esc="Encyclopedia",
    desc_esc="Knowledge Archive",
    schema="",
    page_url=f"{BASE_URL}/encyclopedia.html",
    safe="encyclopedia",
    wiki_url=BASE_URL,
    html_body=f"""
    <section class="hero">
      <h1>Encyclopedia</h1>
      <p>Static Knowledge Archive</p>
    </section>

    <section class="article-grid">
      {encyclopedia_cards}
    </section>
    """
)

with open(
    "encyclopedia.html",
    "w",
    encoding="utf-8"
) as f:

    f.write(encyclopedia_html)

print("WRITING SITEMAP")

sitemap = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
]

for file in generated:

    sitemap.append(f"""
    <url>
      <loc>{BASE_URL}/{file}</loc>
    </url>
    """)

sitemap.append(f"""
<url>
  <loc>{BASE_URL}/encyclopedia.html</loc>
</url>
""")

sitemap.append("</urlset>")

with open(
    "sitemap.xml",
    "w",
    encoding="utf-8"
) as f:

    f.write("\n".join(sitemap))

print("DONE")
