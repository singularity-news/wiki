/* Singularity University Encyclopedia | app.js */
(function () {
  'use strict';

  /* THEME */
  var html = document.documentElement;
  (function () {
    var s = localStorage.getItem('su-theme');
    var d = window.matchMedia('(prefers-color-scheme: dark)').matches;
    html.dataset.theme = s || (d ? 'dark' : 'light');
  }());
  function toggleTheme() {
    var n = html.dataset.theme === 'dark' ? 'light' : 'dark';
    html.dataset.theme = n;
    localStorage.setItem('su-theme', n);
  }

  /* SIDEBAR */
  var open = false;
  function openSB() {
    open = true;
    var sb = document.getElementById('sidebar');
    var ov = document.getElementById('overlay');
    var btn = document.getElementById('menuToggle');
    if (sb) sb.classList.add('open');
    if (ov) ov.classList.add('active');
    if (btn) btn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }
  function closeSB() {
    open = false;
    var sb = document.getElementById('sidebar');
    var ov = document.getElementById('overlay');
    var btn = document.getElementById('menuToggle');
    if (sb) sb.classList.remove('open');
    if (ov) ov.classList.remove('active');
    if (btn) btn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  /* ESCAPE HTML */
  function esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  /* DATA */
  var articles = [];

  function renderList(items) {
    var el = document.getElementById('articleList');
    if (!el) return;
    if (!items.length) { el.innerHTML = '<li class="no-results">No results.</li>'; return; }
    el.innerHTML = items.slice().sort(function(a,b){return a.title.localeCompare(b.title,'en');})
      .map(function(p){ return '<li><a href="'+esc(p.file)+'" title="'+esc(p.title)+'">'+esc(p.title)+'</a></li>'; })
      .join('');
  }

  function renderGrid(items) {
    var el = document.getElementById('indexGrid');
    if (!el) return;
    var cnt = document.getElementById('articleCount');
    if (cnt) cnt.textContent = items.length;
    if (!items.length) { el.innerHTML = '<p class="loading">No articles available.</p>'; return; }
    el.innerHTML = items.slice().sort(function(a,b){return a.title.localeCompare(b.title,'en');})
      .map(function(p){
        var ex = p.text ? esc(p.text.substring(0,160))+'&hellip;' : '';
        return '<a class="article-card" href="'+esc(p.file)+'">'+
          '<div class="card-title">'+esc(p.title)+'</div>'+
          (ex?'<div class="card-excerpt">'+ex+'</div>':'')+
          '</a>';
      }).join('');
  }

  function loadArticles() {
    fetch('search-index.json')
      .then(function(r){ if(!r.ok) throw 0; return r.json(); })
      .then(function(d){
        articles = Array.isArray(d) ? d : [];
        renderList(articles);
        renderGrid(articles);
        var si = document.getElementById('searchInput');
        if (si) {
          si.addEventListener('input', function(e){
            var q = e.target.value.toLowerCase().trim();
            renderList(!q ? articles : articles.filter(function(a){
              return a.title.toLowerCase().indexOf(q)>-1 || (a.text&&a.text.toLowerCase().indexOf(q)>-1);
            }));
          });
        }
      })
      .catch(function(){
        var l=document.getElementById('articleList');
        if(l) l.innerHTML='<li class="no-results">Index unavailable.</li>';
        var g=document.getElementById('indexGrid');
        if(g) g.innerHTML='<p class="loading">Articles unavailable.</p>';
      });
  }

  /* TOC — right side via CSS order:2 */
  function buildTOC() {
    var toc = document.getElementById('toc');
    if (!toc) return;
    var box = document.querySelector('.article-box');
    if (!box) return;
    var hh = box.querySelectorAll('h2, h3');
    if (hh.length < 2) {
      var wrap = toc.closest('.toc-box');
      if (wrap) wrap.parentNode.removeChild(wrap);
      return;
    }
    var items = [];
    hh.forEach(function(h){
      var raw = h.textContent.trim();
      var id = raw.toLowerCase().replace(/\s+/g,'-').replace(/[^\w\u00C0-\u024F-]/g,'');
      h.id = id;
      var cls = h.tagName==='H3' ? ' class="h3"' : '';
      items.push('<li'+cls+'><a href="#'+id+'">'+esc(raw)+'</a></li>');
    });
    toc.innerHTML = items.join('');
  }

  /* BREADCRUMBS */
  function buildBC() {
    var bc = document.getElementById('breadcrumbs');
    if (!bc) return;
    var path = window.location.pathname.split('/').pop();
    var isHome = !path || path === 'index.html' || path === '';
    if (isHome) { bc.innerHTML = '<span>Encyclopedia</span>'; return; }
    if (path === 'search.html') {
      bc.innerHTML = '<a href="index.html">Encyclopedia</a><span class="bc-sep">&#8250;</span><span>Search</span>';
      return;
    }
    var h = document.querySelector('.article-title');
    var title = h ? h.textContent.trim()
      : decodeURIComponent(path.replace(/\.html$/,'').replace(/_/g,' '));
    bc.innerHTML = '<a href="index.html">Encyclopedia</a><span class="bc-sep">&#8250;</span><span>'+esc(title)+'</span>';
  }

  /* SEARCH PAGE */
  function initSearch() {
    var inp = document.getElementById('searchPageInput');
    var btn = document.getElementById('searchPageBtn');
    var res = document.getElementById('searchResults');
    var cnt = document.getElementById('searchCount');
    if (!inp || !res) return;

    var params = new URLSearchParams(window.location.search);
    var init = params.get('q') || '';
    if (init) inp.value = init;

    function score(a, q) {
      var qLow = q.toLowerCase();
      var ww = qLow.split(/\s+/).filter(Boolean);
      var s = 0;
      var tLow = a.title.toLowerCase();
      var txLow = (a.text||'').toLowerCase();
      ww.forEach(function(w){
        if (tLow === w)           s += 100;
        else if (tLow.indexOf(w) === 0) s += 40;
        else if (tLow.indexOf(w) > -1)  s += 20;
        var idx = 0;
        while ((idx = txLow.indexOf(w, idx)) > -1) { s += 1; idx += w.length; }
      });
      return s;
    }

    function hl(text, q) {
      if (!q||!text) return esc(text||'');
      var ww = q.split(/\s+/).filter(Boolean);
      var r = esc(text);
      ww.forEach(function(w){
        var re = new RegExp(w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi');
        r = r.replace(re, function(m){ return '<mark>'+m+'</mark>'; });
      });
      return r;
    }

    function doSearch() {
      var q = inp.value.trim();
      if (!q) { res.innerHTML=''; if(cnt) cnt.textContent=''; return; }
      var url = new URL(window.location.href);
      url.searchParams.set('q', q);
      window.history.replaceState(null,'',url.toString());
      var scored = articles
        .map(function(a){ return {a:a, s:score(a,q)}; })
        .filter(function(x){ return x.s>0; })
        .sort(function(x,y){ return y.s-x.s; });
      if (cnt) cnt.textContent = scored.length
        ? scored.length+' result'+(scored.length!==1?'s':'')+' for "'+esc(q)+'"'
        : 'No results for "'+esc(q)+'"';
      if (!scored.length) { res.innerHTML='<p class="loading">No matches. Try different keywords.</p>'; return; }
      res.innerHTML = scored.map(function(x){
        var a = x.a;
        var ex = (a.text||'').substring(0,280);
        return '<a class="search-result" href="'+esc(a.file)+'">'+
          '<div class="sr-title">'+hl(a.title,q)+'</div>'+
          '<div class="sr-excerpt">'+hl(ex,q)+'&hellip;</div>'+
          '<div class="sr-score">Relevance: '+x.s+'</div>'+
          '</a>';
      }).join('');
    }

    btn.addEventListener('click', doSearch);
    inp.addEventListener('keydown', function(e){ if(e.key==='Enter') doSearch(); });
    if (init) doSearch();
  }

  /* SW */
  function regSW() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js').catch(function(){});
    }
  }

  /* FAILOVER */
  function failover() {
    var t = document.body.innerText||'';
    if (t.indexOf('suspended')>-1||t.indexOf('exceeding the free hosting')>-1) {
      window.location.replace('https://singularity-news.github.io/wiki/');
    }
  }

  /* INIT */
  function init() {
    var tb = document.getElementById('themeToggle');
    if (tb) tb.addEventListener('click', toggleTheme);
    var mb = document.getElementById('menuToggle');
    var ov = document.getElementById('overlay');
    if (mb) mb.addEventListener('click', function(){ open ? closeSB() : openSB(); });
    if (ov) ov.addEventListener('click', closeSB);
    document.addEventListener('keydown', function(e){ if(e.key==='Escape'&&open) closeSB(); });
    loadArticles();
    buildTOC();
    buildBC();
    initSearch();
    regSW();
    failover();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
