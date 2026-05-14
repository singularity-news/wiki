/* ===================================================
   Singularity University Encyclopedia
   assets/app.js  —  Vanilla JS, no dependencies
   =================================================== */

(function () {
  'use strict';

  /* ════════════════════════════════
     1. THEME
  ════════════════════════════════ */
  const html = document.documentElement;

  (function initTheme() {
    const saved = localStorage.getItem('su-theme');
    const prefersDark = matchMedia('(prefers-color-scheme: dark)').matches;
    html.dataset.theme = saved || (prefersDark ? 'dark' : 'light');
  })();

  function toggleTheme() {
    const next = html.dataset.theme === 'dark' ? 'light' : 'dark';
    html.dataset.theme = next;
    localStorage.setItem('su-theme', next);
  }

  /* ════════════════════════════════
     2. SIDEBAR
  ════════════════════════════════ */
  let sidebarOpen = false;

  function openSidebar() {
    sidebarOpen = true;
    document.getElementById('sidebar')?.classList.add('open');
    document.getElementById('overlay')?.classList.add('active');
    const btn = document.getElementById('menuToggle');
    if (btn) btn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    sidebarOpen = false;
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('overlay')?.classList.remove('active');
    const btn = document.getElementById('menuToggle');
    if (btn) btn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  function toggleSidebar() {
    sidebarOpen ? closeSidebar() : openSidebar();
  }

  /* ════════════════════════════════
     3. ARTICLE DATA & SEARCH
  ════════════════════════════════ */
  let allArticles = [];

  function renderSidebarList(items) {
    const list = document.getElementById('articleList');
    if (!list) return;
    if (!items.length) {
      list.innerHTML = '<li class="no-results">Keine Treffer.</li>';
      return;
    }
    list.innerHTML = items
      .slice()
      .sort((a, b) => a.title.localeCompare(b.title, 'de'))
      .map(p => `<li><a href="${p.file}" title="${p.title}">${p.title}</a></li>`)
      .join('');
  }

  function renderIndexGrid(items) {
    const grid = document.getElementById('indexGrid');
    if (!grid) return;

    /* Update count stat */
    const countEl = document.getElementById('articleCount');
    if (countEl) countEl.textContent = items.length;

    if (!items.length) {
      grid.innerHTML = '<p class="loading-text">Keine Artikel verfügbar.</p>';
      return;
    }

    grid.innerHTML = items
      .slice()
      .sort((a, b) => a.title.localeCompare(b.title, 'de'))
      .map(p => {
        const excerpt = p.text ? p.text.substring(0, 180).trim() + '…' : '';
        const tags = p.tags
          ? p.tags.map(t => `<span class="tag">${t}</span>`).join('')
          : '';
        return `
          <a class="article-card" href="${p.file}">
            <div class="card-title">${p.title}</div>
            <div class="card-excerpt">${excerpt}</div>
            ${tags ? `<div class="card-tags">${tags}</div>` : ''}
          </a>`;
      })
      .join('');
  }

  function filterArticles(q) {
    if (!q.trim()) return allArticles;
    const lq = q.toLowerCase();
    return allArticles.filter(p =>
      p.title.toLowerCase().includes(lq) ||
      (p.text && p.text.toLowerCase().includes(lq))
    );
  }

  function loadArticles() {
    /* Resolve path relative to current page location */
    const base = document.querySelector('base')?.href || '';
    const indexPath = base ? new URL('search-index.json', base).href : 'search-index.json';

    fetch(indexPath)
      .then(r => {
        if (!r.ok) throw new Error('Index not found');
        return r.json();
      })
      .then(data => {
        allArticles = Array.isArray(data) ? data : [];
        renderSidebarList(allArticles);
        renderIndexGrid(allArticles);

        /* Last update */
        const lastEl = document.getElementById('lastUpdate');
        if (lastEl) {
          const latest = allArticles
            .filter(a => a.date)
            .map(a => a.date)
            .sort()
            .pop();
          lastEl.textContent = latest
            ? new Date(latest).toLocaleDateString('de-DE', { year:'numeric', month:'short', day:'numeric' })
            : '–';
        }

        /* Wire search input */
        const searchEl = document.getElementById('searchInput');
        if (searchEl) {
          searchEl.addEventListener('input', e => {
            renderSidebarList(filterArticles(e.target.value));
          });
        }
      })
      .catch(() => {
        const list = document.getElementById('articleList');
        if (list) list.innerHTML = '<li class="no-results">Index nicht geladen.</li>';
        const grid = document.getElementById('indexGrid');
        if (grid) grid.innerHTML = '<p class="loading-text">Artikel-Index nicht verfügbar.</p>';
      });
  }

  /* ════════════════════════════════
     4. TABLE OF CONTENTS
  ════════════════════════════════ */
  function buildTOC() {
    const tocList = document.getElementById('toc');
    if (!tocList) return;
    const article = document.querySelector('.article-body');
    if (!article) return;

    const headings = article.querySelectorAll('h2, h3');
    if (headings.length < 2) {
      tocList.closest('.toc-box')?.remove();
      return;
    }

    const items = [];
    headings.forEach(h => {
      const raw = h.textContent.trim();
      const id = raw
        .toLowerCase()
        .replace(/\s+/g, '-')
        .replace(/[^\w\u00C0-\u024F-]/g, '');
      h.id = id;
      const isH3 = h.tagName === 'H3';
      items.push(`<li class="${isH3 ? 'toc-h3' : ''}"><a href="#${id}">${raw}</a></li>`);
    });

    tocList.innerHTML = items.join('');
  }

  /* ════════════════════════════════
     5. BREADCRUMBS
  ════════════════════════════════ */
  function buildBreadcrumbs() {
    const bc = document.getElementById('breadcrumbs');
    if (!bc) return;

    const pathEnd = window.location.pathname.split('/').pop();
    const isHome  = !pathEnd || pathEnd === 'index.html';

    if (isHome) {
      bc.innerHTML = '<span>Encyclopedia</span>';
      return;
    }

    const articleH1 = document.querySelector('.article-body h1');
    const title = articleH1
      ? articleH1.textContent.trim()
      : decodeURIComponent(pathEnd.replace(/\.html$/, '').replace(/_/g, ' '));

    bc.innerHTML = `
      <a href="index.html">Encyclopedia</a>
      <span class="breadcrumb-sep">›</span>
      <span>${title}</span>`;
  }

  /* ════════════════════════════════
     6. AUTO META TAGS
  ════════════════════════════════ */
  function buildMetaTags() {
    const article = document.querySelector('.article-body');
    if (!article) return;

    /* Description */
    if (!document.querySelector('meta[name="description"]')) {
      const rawText = (article.innerText || '').replace(/\s+/g, ' ').trim();
      const desc = rawText.substring(0, 300);
      const meta = document.createElement('meta');
      meta.name = 'description';
      meta.content = desc;
      document.head.appendChild(meta);
    }

    /* Keywords from word frequency */
    if (!document.querySelector('meta[name="keywords"]')) {
      const words = (article.innerText || '')
        .toLowerCase()
        .match(/\b[a-zäöüß]{5,}\b/g) || [];
      const freq = {};
      words.forEach(w => { freq[w] = (freq[w] || 0) + 1; });
      const keywords = Object.entries(freq)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(e => e[0])
        .join(', ');
      const meta = document.createElement('meta');
      meta.name = 'keywords';
      meta.content = keywords;
      document.head.appendChild(meta);
    }
  }

  /* ════════════════════════════════
     7. SERVICE WORKER
  ════════════════════════════════ */
  function registerSW() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker
        .register('/sw.js', { scope: '/' })
        .catch(() => {
          /* Silent fail – SW optional */
        });
    }
  }

  /* ════════════════════════════════
     8. INFINITYFREE FAILOVER GUARD
        (only runs if somehow loaded
         from InfinityFree)
  ════════════════════════════════ */
  function checkFailover() {
    const bodyText = document.body.innerText || '';
    if (
      bodyText.includes('suspended') ||
      bodyText.includes('exceeding the free hosting limits') ||
      bodyText.includes('This site is suspended')
    ) {
      window.location.replace('https://singularity-news.github.io/');
    }
  }

  /* ════════════════════════════════
     INIT
  ════════════════════════════════ */
  function init() {
    /* Theme */
    const themeBtn = document.getElementById('themeToggle');
    if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

    /* Sidebar */
    const menuBtn  = document.getElementById('menuToggle');
    const overlay  = document.getElementById('overlay');
    if (menuBtn) menuBtn.addEventListener('click', toggleSidebar);
    if (overlay) overlay.addEventListener('click', closeSidebar);

    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && sidebarOpen) closeSidebar();
    });

    /* Data */
    loadArticles();

    /* Article features */
    buildTOC();
    buildBreadcrumbs();
    buildMetaTags();

    /* SW */
    registerSW();

    /* Failover check */
    checkFailover();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
