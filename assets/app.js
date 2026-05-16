/* ============================================================
   Singularity University Encyclopedia  |  assets/app.js
   Vanilla JS — no dependencies
   ============================================================ */

(function () {
  'use strict';

  /* ── Utility ─────────────────────────────────────────────── */
  function esc(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ── Theme ───────────────────────────────────────────────── */
  var htmlEl = document.documentElement;

  function initTheme() {
    var saved = localStorage.getItem('su-theme');
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    htmlEl.dataset.theme = saved || (prefersDark ? 'dark' : 'light');
  }

  function toggleTheme() {
    var next = htmlEl.dataset.theme === 'dark' ? 'light' : 'dark';
    htmlEl.dataset.theme = next;
    localStorage.setItem('su-theme', next);
  }

  /* ── Header scroll hide/show ─────────────────────────────── */
  var lastScrollY = 0;
  var scrollTicking = false;

  function handleScroll() {
    if (scrollTicking) return;
    scrollTicking = true;
    requestAnimationFrame(function () {
      var topbar = document.getElementById('topbar');
      if (!topbar) { scrollTicking = false; return; }
      var current = window.scrollY;
      // Hide on scroll down (after 80px), show on scroll up
      if (current > 80 && current > lastScrollY) {
        topbar.classList.add('topbar--hidden');
      } else {
        topbar.classList.remove('topbar--hidden');
      }
      lastScrollY = current;
      scrollTicking = false;
    });
  }

  /* ── Sidebar ─────────────────────────────────────────────── */
  var sidebarOpen = false;

  function openSidebar() {
    sidebarOpen = true;
    var sb  = document.getElementById('sidebar');
    var ov  = document.getElementById('overlay');
    var btn = document.getElementById('menuToggle');
    if (sb)  sb.classList.add('open');
    if (ov)  ov.classList.add('active');
    if (btn) btn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    sidebarOpen = false;
    var sb  = document.getElementById('sidebar');
    var ov  = document.getElementById('overlay');
    var btn = document.getElementById('menuToggle');
    if (sb)  sb.classList.remove('open');
    if (ov)  ov.classList.remove('active');
    if (btn) btn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  /* ── Right TOC collapse ──────────────────────────────────── */
  function initTOCToggle() {
    var tocCol    = document.getElementById('tocCol');
    var tocToggle = document.getElementById('tocToggle');
    if (!tocCol || !tocToggle) return;

    var collapsed = localStorage.getItem('su-toc-collapsed') === '1';
    if (collapsed) tocCol.classList.add('collapsed');

    tocToggle.addEventListener('click', function () {
      tocCol.classList.toggle('collapsed');
      var isCollapsed = tocCol.classList.contains('collapsed');
      localStorage.setItem('su-toc-collapsed', isCollapsed ? '1' : '0');
    });
  }

  /* ── Article data ────────────────────────────────────────── */
  var allArticles = [];

  function renderSidebarList(items) {
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
    var grid    = document.getElementById('indexGrid');
    var countEl = document.getElementById('articleCount');
    if (!grid) return;

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
        '<a class="article-card" href="' + p.file + '" role="listitem">' +
          '<div class="card-title">' + esc(p.title) + '</div>' +
          '<div class="card-excerpt">' + esc(excerpt) + '</div>' +
          (tags ? '<div class="card-tags">' + tags + '</div>' : '') +
        '</a>'
      );
    }).join('');
  }

  function filterSidebar(q) {
    if (!q.trim()) return renderSidebarList(allArticles);
    var lq = q.toLowerCase();
    renderSidebarList(allArticles.filter(function (p) {
      return p.title.toLowerCase().indexOf(lq) > -1 ||
             (p.text && p.text.toLowerCase().indexOf(lq) > -1);
    }));
  }

  function loadArticles() {
    fetch('search-index.json')
      .then(function (r) {
        if (!r.ok) throw new Error('Not found');
        return r.json();
      })
      .then(function (data) {
        allArticles = Array.isArray(data) ? data : [];
        renderSidebarList(allArticles);
        renderGrid(allArticles);

        var searchEl = document.getElementById('searchInput');
        if (searchEl) {
          searchEl.addEventListener('input', function (e) {
            filterSidebar(e.target.value);
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

  /* ── Table of Contents ───────────────────────────────────── */
  function buildTOC() {
    var tocList = document.getElementById('toc');
    if (!tocList) return;
    var article = document.querySelector('.article-box');
    if (!article) return;

    var headings = article.querySelectorAll('h2, h3');
    if (headings.length < 2) {
      var box = document.getElementById('tocCol');
      if (box) box.style.display = 'none';
      return;
    }

    var items = [];
    headings.forEach(function (h) {
      var raw = h.textContent.trim();
      var id  = raw.toLowerCase().replace(/\s+/g, '-').replace(/[^\w-]/g, '');
      h.id = id;
      var cls = h.tagName === 'H3' ? ' class="h3"' : '';
      items.push('<li' + cls + '><a href="#' + id + '">' + esc(raw) + '</a></li>');
    });
    tocList.innerHTML = items.join('');
  }

  /* ── Breadcrumbs ─────────────────────────────────────────── */
  function buildBreadcrumbs() {
    var bc = document.getElementById('breadcrumbs');
    if (!bc) return;
    var path = window.location.pathname.split('/').pop();
    var isHome = !path || path === 'index.html';

    if (isHome) {
      bc.innerHTML = '<span>Encyclopedia</span>';
      return;
    }
    if (path === 'search.html') {
      bc.innerHTML = '<a href="index.html">Encyclopedia</a><span class="bc-sep">&#8250;</span><span>Search</span>';
      return;
    }

    // Try to get title from body data-title or h1
    var bodyTitle = document.body.dataset.title;
    var h1 = document.querySelector('.article-box h1');
    var title = bodyTitle ||
      (h1 ? h1.textContent.trim() : decodeURIComponent(path.replace(/\.html$/, '').replace(/_/g, ' ')));

    bc.innerHTML =
      '<a href="index.html">Encyclopedia</a>' +
      '<span class="bc-sep">&#8250;</span>' +
      '<span>' + esc(title) + '</span>';
  }

  /* ── Auto meta ───────────────────────────────────────────── */
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

  /* ── Service Worker ──────────────────────────────────────── */
  function registerSW() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    }
  }

  /* ── Smooth anchor scroll ────────────────────────────────── */
  function initAnchorScroll() {
    document.addEventListener('click', function (e) {
      var a = e.target.closest('a[href^="#"]');
      if (!a) return;
      var id = a.getAttribute('href').slice(1);
      var target = document.getElementById(id);
      if (!target) return;
      e.preventDefault();
      var barH = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--bar-h')) || 56;
      var top  = target.getBoundingClientRect().top + window.scrollY - barH - 12;
      window.scrollTo({ top: top, behavior: 'smooth' });
    });
  }

  /* ── Init ────────────────────────────────────────────────── */
  function init() {
    initTheme();

    var themeBtn = document.getElementById('themeToggle');
    if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

    var menuBtn = document.getElementById('menuToggle');
    var overlay = document.getElementById('overlay');
    if (menuBtn) menuBtn.addEventListener('click', function () { sidebarOpen ? closeSidebar() : openSidebar(); });
    if (overlay) overlay.addEventListener('click', closeSidebar);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && sidebarOpen) closeSidebar();
    });

    window.addEventListener('scroll', handleScroll, { passive: true });

    loadArticles();
    buildTOC();
    buildBreadcrumbs();
    buildMeta();
    initTOCToggle();
    initAnchorScroll();
    registerSW();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

}());
