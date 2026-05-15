/* ============================================================
   Singularity University Encyclopedia  |  assets/app.js
   Vanilla JS - no dependencies
   ============================================================ */

(function () {
  'use strict';

  /* ----------------------------------------------------------
     THEME
  ---------------------------------------------------------- */
  var html = document.documentElement;

  function initTheme() {
    var saved = localStorage.getItem('su-theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    html.dataset.theme = saved || (prefersDark ? 'dark' : 'light');
  }

  function toggleTheme() {
    var next = html.dataset.theme === 'dark' ? 'light' : 'dark';
    html.dataset.theme = next;
    localStorage.setItem('su-theme', next);
  }

  /* ----------------------------------------------------------
     SIDEBAR
  ---------------------------------------------------------- */
  var isOpen = false;

  function openSidebar() {
    isOpen = true;
    var sb = document.getElementById('sidebar');
    var ov = document.getElementById('overlay');
    var btn = document.getElementById('menuToggle');
    if (sb) sb.classList.add('open');
    if (ov) ov.classList.add('active');
    if (btn) btn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    isOpen = false;
    var sb = document.getElementById('sidebar');
    var ov = document.getElementById('overlay');
    var btn = document.getElementById('menuToggle');
    if (sb) sb.classList.remove('open');
    if (ov) ov.classList.remove('active');
    if (btn) btn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  function toggleSidebar() {
    isOpen ? closeSidebar() : openSidebar();
  }

  /* ----------------------------------------------------------
     ARTICLE DATA
  ---------------------------------------------------------- */
  var allArticles = [];

  function renderList(items) {
    var list = document.getElementById('articleList');
    if (!list) return;
    if (!items.length) {
      list.innerHTML = '<li class="no-results">No articles found.</li>';
      return;
    }
    var sorted = items.slice().sort(function (a, b) {
      return a.title.localeCompare(b.title, 'en');
    });
    list.innerHTML = sorted.map(function (p) {
      return '<li><a href="' + p.file + '" title="' + esc(p.title) + '">' + esc(p.title) + '</a></li>';
    }).join('');
  }

  function renderGrid(items) {
    var grid = document.getElementById('indexGrid');
    if (!grid) return;

    var countEl = document.getElementById('articleCount');
    if (countEl) countEl.textContent = items.length;

    if (!items.length) {
      grid.innerHTML = '<p class="loading">No articles available.</p>';
      return;
    }

    var sorted = items.slice().sort(function (a, b) {
      return a.title.localeCompare(b.title, 'en');
    });

    grid.innerHTML = sorted.map(function (p) {
      var excerpt = p.text ? p.text.substring(0, 185).trim() + '...' : '';
      var tags = p.tags
        ? p.tags.map(function (t) { return '<span class="tag">' + esc(t) + '</span>'; }).join('')
        : '';
      return (
        '<a class="article-card" href="' + p.file + '">' +
          '<div class="card-title">' + esc(p.title) + '</div>' +
          '<div class="card-excerpt">' + esc(excerpt) + '</div>' +
          (tags ? '<div class="card-tags">' + tags + '</div>' : '') +
        '</a>'
      );
    }).join('');
  }

  function filterArticles(q) {
    if (!q.trim()) return allArticles;
    var lq = q.toLowerCase();
    return allArticles.filter(function (p) {
      return (
        p.title.toLowerCase().indexOf(lq) > -1 ||
        (p.text && p.text.toLowerCase().indexOf(lq) > -1)
      );
    });
  }

  function loadArticles() {
    fetch('search-index.json')
      .then(function (r) {
        if (!r.ok) throw new Error('Not found');
        return r.json();
      })
      .then(function (data) {
        allArticles = Array.isArray(data) ? data : [];
        renderList(allArticles);
        renderGrid(allArticles);

        var lastEl = document.getElementById('lastUpdate');
        if (lastEl) {
          var dates = allArticles
            .filter(function (a) { return a.date; })
            .map(function (a) { return a.date; })
            .sort();
          var latest = dates.pop();
          lastEl.textContent = latest
            ? new Date(latest).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
            : '--';
        }

        var searchEl = document.getElementById('searchInput');
        if (searchEl) {
          searchEl.addEventListener('input', function (e) {
            renderList(filterArticles(e.target.value));
          });
        }
      })
      .catch(function () {
        var list = document.getElementById('articleList');
        if (list) list.innerHTML = '<li class="no-results">Index unavailable.</li>';
        var grid = document.getElementById('indexGrid');
        if (grid) grid.innerHTML = '<p class="loading">Article index not available.</p>';
      });
  }

  /* ----------------------------------------------------------
     TABLE OF CONTENTS
  ---------------------------------------------------------- */
  function buildTOC() {
    var tocList = document.getElementById('toc');
    if (!tocList) return;
    var article = document.querySelector('.article-box');
    if (!article) return;

    var headings = article.querySelectorAll('h2, h3');
    if (headings.length < 2) {
      var box = tocList.closest('.toc-box');
      if (box) box.parentNode.removeChild(box);
      return;
    }

    var items = [];
    headings.forEach(function (h) {
      var raw = h.textContent.trim();
      var id = raw.toLowerCase().replace(/\s+/g, '-').replace(/[^\w-]/g, '');
      h.id = id;
      var cls = h.tagName === 'H3' ? ' class="h3"' : '';
      items.push('<li' + cls + '><a href="#' + id + '">' + esc(raw) + '</a></li>');
    });
    tocList.innerHTML = items.join('');
  }

  /* ----------------------------------------------------------
     BREADCRUMBS
  ---------------------------------------------------------- */
  function buildBreadcrumbs() {
    var bc = document.getElementById('breadcrumbs');
    if (!bc) return;
    var path = window.location.pathname.split('/').pop();
    var isHome = !path || path === 'index.html';

    if (isHome) {
      bc.innerHTML = '<span>Encyclopedia</span>';
      return;
    }

    var h1 = document.querySelector('.article-box h1');
    var title = h1
      ? h1.textContent.trim()
      : decodeURIComponent(path.replace(/\.html$/, '').replace(/_/g, ' '));

    bc.innerHTML =
      '<a href="index.html">Encyclopedia</a>' +
      '<span class="bc-sep">&#8250;</span>' +
      '<span>' + esc(title) + '</span>';
  }

  /* ----------------------------------------------------------
     AUTO META TAGS
  ---------------------------------------------------------- */
  function buildMeta() {
    var article = document.querySelector('.article-box');
    if (!article) return;

    if (!document.querySelector('meta[name="description"]')) {
      var raw = (article.innerText || '').replace(/\s+/g, ' ').trim();
      var m = document.createElement('meta');
      m.name = 'description';
      m.content = raw.substring(0, 300);
      document.head.appendChild(m);
    }
  }

  /* ----------------------------------------------------------
     SERVICE WORKER
  ---------------------------------------------------------- */
  function registerSW() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    }
  }

  /* ----------------------------------------------------------
     INFINITYFREE FAILOVER GUARD
  ---------------------------------------------------------- */
  function checkFailover() {
    var t = document.body.innerText || '';
    if (
      t.indexOf('suspended') > -1 ||
      t.indexOf('exceeding the free hosting limits') > -1 ||
      t.indexOf('This site is suspended') > -1
    ) {
      window.location.replace('https://singularity-news.github.io/');
    }
  }

  /* ----------------------------------------------------------
     UTILITY
  ---------------------------------------------------------- */
  function esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* ----------------------------------------------------------
     INIT
  ---------------------------------------------------------- */
  function init() {
    initTheme();

    var themeBtn = document.getElementById('themeToggle');
    if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

    var menuBtn = document.getElementById('menuToggle');
    var overlay = document.getElementById('overlay');
    if (menuBtn) menuBtn.addEventListener('click', toggleSidebar);
    if (overlay) overlay.addEventListener('click', closeSidebar);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen) closeSidebar();
    });

    loadArticles();
    buildTOC();
    buildBreadcrumbs();
    buildMeta();
    registerSW();
    checkFailover();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

}());
