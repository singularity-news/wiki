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
    } else if (e.isFile()) {
      const lower = e.name.toLowerCase();
      if (lower.endsWith('.html')) results.push(full);
    }
  }
  return results;
}

function toUrl(filePath) {
  let rel = path.relative(PAGES_DIR, filePath).split(path.sep).join('/');
  rel = rel.replace(/^\.\//, '');
  if (rel === 'index.html' || rel === '') return BASE_URL;
  if (rel.endsWith('/index.html')) return `${BASE_URL}/${rel.slice(0, -'index.html'.length)}`.replace(/\/+$/, '');
  return `${BASE_URL}/${rel}`.replace(/\/+$/, '');
}

function isoNow() {
  return new Date().toISOString();
}

try {
  console.log('Scanning for HTML files under', PAGES_DIR);
  const files = walk(PAGES_DIR).sort();
  console.log('Found', files.length, 'HTML files');
  if (files.length === 0) {
    console.warn('No HTML files found. Check PAGES_DIR and build step output.');
  } else {
    files.forEach((f, i) => {
      console.log(`${i+1}. ${f}`);
    });
  }

  const urls = files.map(f => ({
    loc: toUrl(f),
    lastmod: fs.statSync(f).mtime.toISOString()
  }));

  // Build sitemap content
  const entries = urls.map(u => `  <url>\n    <loc>${u.loc}</loc>\n    <lastmod>${u.lastmod}</lastmod>\n  </url>`).join('\n');
  const sitemapXml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${entries}\n</urlset>\n`;

  // Compare with existing local file
  let write = true;
  if (fs.existsSync(SITEMAP_PATH)) {
    const old = fs.readFileSync(SITEMAP_PATH, 'utf8');
    if (old === sitemapXml) {
      write = false;
      console.log('Local sitemap.xml is identical to generated content. No write needed.');
    }
  }

  // Optional: compare with remote and abort if remote}`, { stdio: 'ignore' });
    const ls = execSync(`git ls-tree --name-only origin/${REMOTE_BRANCH}`, { encoding: 'utf8' });
    if (ls.split('\n').some(name => name.trim() === SITEMAP_PATH)) {
      const remoteContent = execSync(`git show origin/${REMOTE_BRANCH}:${SITEMAP_PATH}`, { encoding: 'utf8' });
      if (remoteContent !== sitemapXml) {
        console.error('Remote sitemap.xml differs from generated sitemap.xml. Aborting to avoid conflict.');
        console.error('Remote file exists and is different. Resolve remote changes manually or allow controlled merge.');
        process.exit(4);
      } else {
        console.log('Remote sitemap.xml equals generated content.');
        // If identical and local file exists, nothing to do
        if (!write) process.exit(0);
      }
    } else {
      console.log('No remote sitemap.xml found on origin/' + REMOTE_BRANCH);
    }
  } catch (e) {
    console.warn('Warning: could not compare with remote. Continuing with local write if needed.');
  }

  if (write) {
    fs.writeFileSync(SITEMAP_PATH, sitemapXml, 'utf8');
    console.log(`Wrote ${SITEMAP_PATH} with ${urls.length} entries at ${isoNow()}`);
  }

  // Print small sample of sitemap for debugging
  console.log('Sitemap sample (first 200 chars):');
  console.log(sitemapXml.slice(0, 200));

  process.exit(0);

} catch (err) {
  console.error('Error generating sitemap.xml:', err);
  process.exit(1);
}
