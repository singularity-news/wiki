// Node 18+, module type
import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';

const PAGES_DIR = process.env.PAGES_DIR || '.';
const BASE_URL = (process.env.BASE_URL || '').replace(/\/$/, '');
const SITEMAP_PATH = process.env.SITEMAP_PATH || 'sitemap.xml';
const REMOTE_BRANCH = process.env.REMOTE_BRANCH || 'main';

if (!BASE_URL) {
  console.error('ERROR: BASE_URL is not set. Set env BASE_URL (e.g. https://example.com).');
  process.exit(2);
}

function walk(dir) {
  const results = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === 'node_modules' || e.name === '.git') continue;
      results.push(...walk(full));
    } else if (e.isFile() && e.name.toLowerCase().endsWith('.html')) {
      results.push(full);
    }
  }
  return results;
}

function toUrl(filePath) {
  let rel = path.relative(PAGES_DIR, filePath).split(path.sep).join('/');
  if (rel === 'index.html') rel = '';
  if (rel.endsWith('/index.html')) rel = rel.slice(0, -'index.html'.length);
  rel = rel.replace(/^\.\//, '');
  const url = `${BASE_URL}/${rel}`.replace(/\/+$/, '');
  return url === `${BASE_URL}/` ? BASE_URL : url;
}

function isoNow() {
  return new Date().toISOString();
}

try {
  // 1) Build URL list
  const files = walk(PAGES_DIR).sort();
  const urls = files.map(f => ({
    loc: toUrl(f),
    lastmod: fs.statSync(f).mtime.toISOString()
  }));

  const entries = urls.map(u => `  <url>\n    <loc>${u.loc}</loc>\n    <lastmod>${u.lastmod}</lastmod>\n  </url>`).join('\n');

  const sitemapXml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${entries}\n</urlset>\n`;

  // 2) Compare with remote sitemap.xml on origin/REMOTE_BRANCH (if exists)
  let remoteExists = false;
  let remoteContent = '';
  try {
    // fetch remote refs (requires checkout with fetch-depth:0 and network access)
    execSync(`git fetch origin ${REMOTE_BRANCH}`, { stdio: 'ignore' });
    // check if remote has sitemap.xml
    const ls = execSync(`git ls-tree --name-only origin/${REMOTE_BRANCH}`, { encoding: 'utf8' });
    if (ls.split('\n').some(name => name.trim() === SITEMAP_PATH)) {
      remoteExists = true;
      remoteContent = execSync(`git show origin/${REMOTE_BRANCH}:${SITEMAP_PATH}`, { encoding: 'utf8' });
    }
  } catch (e) {
    // If git commands fail, be conservative: abort to avoid accidental overwrite
    console.error('ERROR: Could not fetch/inspect origin branch. Aborting to avoid potential conflicts.');
    console.error(e.message || e);
    process.exit(3);
  }

  if (remoteExists) {
    // If remote exists and differs from our generated content, abort to avoid conflict
    if (remoteContent !== sitemapXml) {
      console.error('ABORT: Remote sitemap.xml on origin/' + REMOTE_BRANCH + ' differs from locally generated sitemap.xml.');
      console.error('To proceed automatically, either merge remote changes into main or adjust the workflow to allow controlled rebasing.');
      process.exit(4);
    } else {
      // remote equals generated content -> nothing to change
      console.log('Remote sitemap.xml equals generated sitemap.xml. No update required.');
      process.exit(0);
    }
  }

  // 3) If remote does not exist, write sitemap.xml only if changed
  let write = true;
  if (fs.existsSync(SITEMAP_PATH)) {
    const old = fs.readFileSync(SITEMAP_PATH, 'utf8');
    if (old === sitemapXml) write = false;
  }

  if (write) {
    fs.writeFileSync(SITEMAP_PATH, sitemapXml, 'utf8');
    console.log(`Wrote ${SITEMAP_PATH} with ${urls.length} entries at ${isoNow()}`);
  } else {
    console.log(`No change for ${SITEMAP_PATH}`);
  }

  process.exit(0);

} catch (err) {
  console.error('Error generating sitemap.xml:', err);
  process.exit(1);
}
