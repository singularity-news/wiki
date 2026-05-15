/* ============================================================
   Singularity University Encyclopedia  |  app.js
   ============================================================ */
(function () {
  'use strict';

  /* -- THEME -- */
  var html = document.documentElement;
  (function () {
    var saved = localStorage.getItem('su-theme');
    var dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    html.dataset.theme = saved || (dark ? 'dark' : 'light');
  })();
  function toggleTheme() {
    var n = html.dataset.theme === 'dark' ? 'light' : 'dark';
    html.dataset.theme = n;
    localStorage.setItem('su-theme', n);
  }

  /* -- SIDEBAR -- */
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
  function toggleSidebar() { isOpen ? closeSidebar() : openSidebar(); }

  /* -- DATA -- */
  var allArticles = [];

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderSidebarList(items) {
    var list = document.getElementById('articleList');
    if (!list) return;
    if (!items.length) {
      list.innerHTML = '<li class="no-results">No articles found.</li>';
      return;
    }
    list.innerHTML = items
      .slice()
      .sort(function (a, b) { return a.title.localeCompare(b.title, 'en'); })
      .map(function (p) {
        return '<li><a href="' + esc(p.file) + '" title="' + esc(p.title) + '">' + esc(p.title) + '</a></li>';
      }).join('');
  }

  function renderIndexGrid(items) {
    var grid = document.getElementById('indexGrid');
    if (!grid) return;
    var cnt = document.getElementById('articleCount');
    if (cnt) cnt.textContent = items.length;
    if (!items.length) {
      grid.innerHTML = '<p class="loading">No articles available.</p>';
      return;
    }
    grid.innerHTML = items
      .slice()
      .sort(function (a, b) { return a.title.localeCompare(b.title, 'en'); })
      .map(function (p) {
        var ex = p.text ? esc(p.text.substring(0, 160).trim()) + '&hellip;' : '';
        return (
          '<a class="article-card" href="' + esc(p.file) + '">' +
          '<div class="card-title">' + esc(p.title) + '</div>' +
          (ex ? '<div class="card-excerpt">' + ex + '</div>' : '') +
          '</a>'
        );
      }).join('');
  }

  function loadArticles() {
    fetch('search-index.json')
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (data) {
        allArticles = Array.isArray(data) ? data : [];
        renderSidebarList(allArticles);
        renderIndexGrid(allArticles);
        var si = document.getElementById('searchInput');
        if (si) {
          si.addEventListener('input', function (e) {
            var q = e.target.value.toLowerCase().trim();
            if (!q) { renderSidebarList(allArticles); return; }
            renderSidebarList(allArticles.filter(function (a) {
              return a.title.toLowerCase().indexOf(q) > -1 ||
                     (a.text && a.text.toLowerCase().indexOf(q) > -1);
            }));
          });
        }
      })
      .catch(function () {
        var list = document.getElementById('articleList');
        if (list) list.innerHTML = '<li class="no-results">Index unavailable.</li>';
        var grid = document.getElementById('indexGrid');
        if (grid) grid.innerHTML = '<p class="loading">Articles unavailable.</p>';
      });
  }

  /* -- TOC (builds from article headings, placed on RIGHT via CSS order:2) -- */
  function buildTOC() {
    var tocList = document.getElementById('toc');
    if (!tocList) return;
    var box = document.querySelector('.article-box');
    if (!box) return;
    var headings = box.querySelectorAll('h2, h3');
    if (headings.length < 2) {
      var wrap = tocList.closest('.toc-box');
      if (wrap) wrap.parentNode.removeChild(wrap);
      return;
    }
    var items = [];
    headings.forEach(function (h) {
      var raw = h.textContent.trim();
      var id = raw.toLowerCase().replace(/\s+/g, '-').replace(/[^\w\u00C0-\u024F-]/g, '');
      h.id = id;
      var cls = h.tagName === 'H3' ? ' class="h3"' : '';
      items.push('<li' + cls + '><a href="#' + id + '">' + esc(raw) + '</a></li>');
    });
    tocList.innerHTML = items.join('');
  }

  /* -- BREADCRUMBS -- */
  function buildBreadcrumbs() {
    var bc = document.getElementById('breadcrumbs');
    if (!bc) return;
    var path = window.location.pathname.split('/').pop();
    var isHome = !path || path === 'index.html' || path === '';
    if (isHome) { bc.innerHTML = '<span>Encyclopedia</span>'; return; }
    if (path === 'search.html') { bc.innerHTML = '<a href="index.html">Encyclopedia</a><span class="bc-sep">&#8250;</span><span>Search</span>'; return; }
    var h = document.querySelector('.article-title');
    var title = h ? h.textContent.trim()
      : decodeURIComponent(path.replace(/\.html$/, '').replace(/_/g, ' '));
    bc.innerHTML = '<a href="index.html">Encyclopedia</a><span class="bc-sep">&#8250;</span><span>' + esc(title) + '</span>';
  }

  /* -- SEARCH PAGE LOGIC -- */
  function initSearchPage() {
    var input  = document.getElementById('searchPageInput');
    var btn    = document.getElementById('searchPageBtn');
    var res    = document.getElementById('searchResults');
    var cnt    = document.getElementById('searchCount');
    if (!input || !res) return;

    /* Pre-fill from URL param */
    var params = new URLSearchParams(window.location.search);
    var initial = params.get('q') || '';
    if (initial) { input.value = initial; }

    function scoreArticle(article, q) {
      var qLow = q.toLowerCase();
      var words = qLow.split(/\s+/).filter(Boolean);
      var score = 0;
      var titleLow = article.title.toLowerCase();
      var textLow  = (article.text || '').toLowerCase();
      words.forEach(function (w) {
        /* Exact title match: highest score */
        if (titleLow === w) score += 100;
        else if (titleLow.indexOf(w) === 0) score += 40;
        else if (titleLow.indexOf(w) > -1) score += 20;
        /* Text matches */
        var idx = 0;
        while ((idx = textLow.indexOf(w, idx)) > -1) { score += 1; idx += w.length; }
      });
      return score;
    }

    function highlight(text, q) {
      if (!q || !text) return esc(text || '');
      var words = q.split(/\s+/).filter(Boolean);
      var result = esc(text);
      words.forEach(function (w) {
        var re = new RegExp(esc(w).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
        result = result.replace(re, function (m) { return '<mark>' + m + '</mark>'; });
      });
      return result;
    }

    function doSearch() {
      var q = input.value.trim();
      if (!q) { res.innerHTML = ''; if (cnt) cnt.textContent = ''; return; }

      /* Update URL without reload */
      var url = new URL(window.location.href);
      url.searchParams.set('q', q);
      window.history.replaceState(null, '', url.toString());

      var scored = allArticles
        .map(function (a) { return { a: a, s: scoreArticle(a, q) }; })
        .filter(function (x) { return x.s > 0; })
        .sort(function (x, y) { return y.s - x.s; });

      if (cnt) cnt.textContent = scored.length
        ? scored.length + ' result' + (scored.length !== 1 ? 's' : '') + ' for "' + esc(q) + '"'
        : 'No results for "' + esc(q) + '"';

      if (!scored.length) {
        res.innerHTML = '<p class="loading">No matches found. Try different keywords.</p>';
        return;
      }

      res.innerHTML = scored.map(function (x) {
        var a = x.a;
        var excerpt = (a.text || '').substring(0, 280);
        return (
          '<a class="search-result" href="' + esc(a.file) + '">' +
          '<div class="sr-title">' + highlight(a.title, q) + '</div>' +
          '<div class="sr-excerpt">' + highlight(excerpt, q) + '&hellip;</div>' +
          '<div class="sr-score">Relevance score: ' + x.s + '</div>' +
          '</a>'
        );
      }).join('');
    }

    btn.addEventListener('click', doSearch);
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') doSearch(); });
    if (initial) doSearch();
  }

  /* -- SERVICE WORKER -- */
  function registerSW() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    }
  }

  /* -- INFINITYFREE FAILOVER -- */
  function checkFailover() {
    var t = document.body.innerText || '';
    if (t.indexOf('suspended') > -1 || t.indexOf('exceeding the free hosting limits') > -1) {
      window.location.replace('https://singularity-news.github.io/wiki/');
    }
  }

  /* -- INIT -- */
  function init() {
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
    initSearchPage();
    registerSW();
    checkFailover();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
