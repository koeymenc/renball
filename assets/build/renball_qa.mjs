#!/usr/bin/env node
/*
  renball_qa.mjs — headless page QA for Renball (desktop + phone)
  ===============================================================

  Serves the repo on a throwaway local port, drives headless Chrome over the
  DevTools protocol (Node 22+ built-in WebSocket, no npm installs) and, for
  every page x viewport:
    - waits in real time (web fonts, PDF.js workers, fetch(data.json) all run)
    - scrolls the page so lazy components (slide viewer) mount
    - collects console errors, uncaught exceptions, failed / 4xx requests
    - checks horizontal overflow (the #1 mobile bug) and names offenders
    - flags faux-bold Instrument Serif (one real weight; weight > 400 without
      font-synthesis: none means the browser is smearing it)
    - runs the page under a Swiss-German locale (de-CH groups 3,857 as
      3'857 in Chrome) and flags any number that escaped the pinned en-GB formatting
    - writes a full-page screenshot

  Usage (from repo root):
    node assets/build/renball_qa.mjs projects/01-penalty-analysis/analysis.html
    node assets/build/renball_qa.mjs --out <dir> --wait 6000 page1.html page2.html
    node assets/build/renball_qa.mjs --viewports mobile index.html

  Exit code 1 if any page has errors, overflow, faux bold or locale leaks.
*/

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

const VIEWPORTS = {
  desktop: { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false },
  mobile:  { width: 390,  height: 844, deviceScaleFactor: 1, mobile: true },
};

const CHROME_PATHS = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  path.join(process.env.LOCALAPPDATA || '', 'Google\\Chrome\\Application\\chrome.exe'),
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
];

const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript',
  '.mjs': 'text/javascript', '.json': 'application/json', '.pdf': 'application/pdf',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.woff2': 'font/woff2',
  '.py': 'text/plain; charset=utf-8', '.md': 'text/plain; charset=utf-8',
};

// ── args ────────────────────────────────────────────────
function parseArgs(argv) {
  const a = { out: null, wait: 6000, viewports: ['desktop', 'mobile'], pages: [] };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--out') a.out = argv[++i];
    else if (k === '--wait') a.wait = Number(argv[++i]);
    else if (k === '--viewports') a.viewports = argv[++i].split(',');
    else a.pages.push(k.replace(/\\/g, '/'));
  }
  a.out = a.out || path.join(os.tmpdir(), 'renball_qa');
  return a;
}

// ── static server ───────────────────────────────────────
function serve(root) {
  const server = http.createServer((req, res) => {
    const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    let file = path.join(root, rel);
    if (!file.startsWith(root)) { res.writeHead(403).end(); return; }
    if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
    fs.readFile(file, (err, buf) => {
      if (err) { res.writeHead(404).end('not found'); return; }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream' });
      res.end(buf);
    });
  });
  return new Promise((ok) => server.listen(0, '127.0.0.1', () =>
    ok({ server, base: `http://127.0.0.1:${server.address().port}` })));
}

// ── chrome + CDP ────────────────────────────────────────
async function launchChrome() {
  const chrome = CHROME_PATHS.find((p) => p && fs.existsSync(p));
  if (!chrome) throw new Error('Chrome/Edge not found');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'renball_qa_profile_'));
  const proc = spawn(chrome, ['--headless=new', '--disable-gpu', '--no-first-run',
    '--no-default-browser-check', '--disable-extensions', '--hide-scrollbars',
    '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
  const portFile = path.join(profile, 'DevToolsActivePort');
  // Chrome creates the file before it finishes writing it (and Windows may hold
  // it locked for a moment), so retry until a port number can be read.
  let port = '';
  for (let i = 0; i < 150 && !/^\d+$/.test(port); i++) {
    try { port = fs.readFileSync(portFile, 'utf8').split('\n')[0].trim(); } catch { /* not there / locked yet */ }
    if (!/^\d+$/.test(port)) await sleep(100);
  }
  if (!/^\d+$/.test(port)) throw new Error('Chrome did not report a DevTools port');
  return { proc, port, profile };
}

class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.handlers = {}; }
  static connect(url) {
    return new Promise((ok, fail) => {
      const ws = new WebSocket(url);
      const c = new CDP(ws);
      ws.onopen = () => ok(c);
      ws.onerror = (e) => fail(e);
      ws.onmessage = (m) => {
        const msg = JSON.parse(m.data);
        if (msg.id && c.pending.has(msg.id)) {
          const { ok: res, fail: rej } = c.pending.get(msg.id);
          c.pending.delete(msg.id);
          msg.error ? rej(new Error(msg.error.message)) : res(msg.result);
        } else if (msg.method) (c.handlers[msg.method] || []).forEach((h) => h(msg.params));
      };
    });
  }
  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((ok, fail) => this.pending.set(id, { ok, fail }));
  }
  on(method, h) { (this.handlers[method] ||= []).push(h); }
  once(method, timeoutMs) {
    return new Promise((ok) => {
      const t = setTimeout(() => ok(null), timeoutMs);
      this.on(method, (p) => { clearTimeout(t); ok(p); });
    });
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Visitor locale the pages are tested under: its grouping mark (' in Chrome, ’ in CLDR) can't be
// mistaken for an en-GB comma or a decimal point.
const TEST_LOCALE = 'de-CH';

const PROBE_JS = `(() => {
  const iw = window.innerWidth, sw = document.documentElement.scrollWidth;
  const offenders = [];
  if (sw > iw + 1) {
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.right > iw + 1 && r.width > 0 && getComputedStyle(el).position !== 'fixed') {
        const id = el.id ? '#' + el.id : '';
        const cls = el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).join('.') : '';
        offenders.push(el.tagName.toLowerCase() + id + cls + ' (right=' + Math.round(r.right) + ')');
        if (offenders.length >= 6) break;
      }
    }
  }
  const ownText = (el) => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
  const fauxBold = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!ownText(el)) continue;
    const cs = getComputedStyle(el);
    if (!/Instrument Serif/.test(cs.fontFamily.split(',')[0])) continue;
    if (parseInt(cs.fontWeight, 10) > 400 && (cs.fontSynthesisWeight || cs.fontSynthesis) !== 'none') {
      fauxBold.push(el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + ' "' + el.textContent.trim().slice(0, 40) + '"');
      if (fauxBold.length >= 6) break;
    }
  }
  const localeLeaks = (document.body.innerText.match(/\\d['\\u2019]\\d{3}/g) || []).slice(0, 6);
  return JSON.stringify({ iw, sw, offenders, fauxBold, localeLeaks,
    canvases: document.querySelectorAll('canvas').length,
    slideViewer: [...document.querySelectorAll('.slide-viewer')].map(v =>
      v.querySelector('.slide-stage canvas') ? 'rendered' : (v.querySelector('.slide-status')?.textContent || 'empty')) });
})()`;

async function checkPage(cdp, base, page, vpName, a) {
  const vp = VIEWPORTS[vpName];
  const errors = [];
  const urls = new Map();
  const onReq = (p) => urls.set(p.requestId, p.request.url);
  const onFail = (p) => { if (!p.canceled) errors.push(`request failed: ${urls.get(p.requestId)} (${p.errorText})`); };
  const onResp = (p) => {
    // Browsers probe /favicon.ico on their own; the site doesn't ship one
    if (p.response.status >= 400 && !p.response.url.endsWith('/favicon.ico'))
      errors.push(`HTTP ${p.response.status} ${p.response.url}`);
  };
  const onExc = (p) => errors.push(`exception: ${p.exceptionDetails.exception?.description || p.exceptionDetails.text}`);
  const onCon = (p) => { if (p.type === 'error') errors.push(`console.error: ${p.args.map((x) => x.value ?? x.description).join(' ')}`); };
  cdp.handlers = { 'Network.requestWillBeSent': [onReq], 'Network.loadingFailed': [onFail],
    'Network.responseReceived': [onResp], 'Runtime.exceptionThrown': [onExc], 'Runtime.consoleAPICalled': [onCon] };

  await cdp.send('Emulation.setDeviceMetricsOverride', vp);
  await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: vp.mobile });
  const loaded = cdp.once('Page.loadEventFired', 30000);
  await cdp.send('Page.navigate', { url: `${base}/${page}` });
  await loaded;
  // Walk down the page so IntersectionObserver-mounted components start
  const { result } = await cdp.send('Runtime.evaluate', { expression: 'document.documentElement.scrollHeight', returnByValue: true });
  for (let y = 0; y < result.value; y += vp.height * 0.8) {
    await cdp.send('Runtime.evaluate', { expression: `window.scrollTo(0, ${y})` });
    await sleep(120);
  }
  await sleep(a.wait);
  await cdp.send('Runtime.evaluate', { expression: 'window.scrollTo(0, 0)' });
  await sleep(300);
  const probe = JSON.parse((await cdp.send('Runtime.evaluate', { expression: PROBE_JS, returnByValue: true })).result.value);

  const metrics = await cdp.send('Page.getLayoutMetrics');
  const h = Math.min(Math.ceil(metrics.cssContentSize.height), 16000);
  const shot = await cdp.send('Page.captureScreenshot', {
    format: 'png', captureBeyondViewport: true,
    clip: { x: 0, y: 0, width: vp.width, height: h, scale: 1 } });
  const file = path.join(a.out, `${page.replace(/[\/\\]/g, '__').replace(/\.html$/, '')}__${vpName}.png`);
  fs.writeFileSync(file, Buffer.from(shot.data, 'base64'));
  return { page, viewport: vpName, errors, overflow: probe.sw > probe.iw + 1, probe, file };
}

async function main() {
  const a = parseArgs(process.argv.slice(2));
  if (!a.pages.length) { console.error('usage: node assets/build/renball_qa.mjs <page.html> [...]'); process.exit(2); }
  fs.mkdirSync(a.out, { recursive: true });
  const { server, base } = await serve(REPO);
  const { proc, port, profile } = await launchChrome();
  let failed = 0;
  try {
    const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    const cdp = await CDP.connect(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
    for (const d of ['Page', 'Runtime', 'Network', 'Log']) await cdp.send(`${d}.enable`);
    await cdp.send('Emulation.setLocaleOverride', { locale: TEST_LOCALE });
    for (const page of a.pages) {
      for (const vp of a.viewports) {
        const r = await checkPage(cdp, base, page, vp, a);
        const bad = r.errors.length || r.overflow || r.probe.fauxBold.length || r.probe.localeLeaks.length;
        failed += bad ? 1 : 0;
        console.log(`[${bad ? 'FAIL' : ' OK '}] ${page}  @${vp}  canvases=${r.probe.canvases}` +
          (r.probe.slideViewer.length ? `  slides=${r.probe.slideViewer.join(',')}` : '') +
          (r.overflow ? `  OVERFLOW ${r.probe.sw}px > ${r.probe.iw}px` : ''));
        r.errors.forEach((e) => console.log(`         ${e}`));
        r.probe.offenders.forEach((o) => console.log(`         overflow: ${o}`));
        r.probe.fauxBold.forEach((o) => console.log(`         faux bold: ${o}`));
        r.probe.localeLeaks.forEach((o) => console.log(`         ${TEST_LOCALE} number formatting leaked: ${o}`));
        console.log(`         -> ${r.file}`);
      }
    }
    cdp.ws.close();
  } finally {
    const exited = new Promise((r) => proc.once('exit', r));
    proc.kill();
    server.close();
    await Promise.race([exited, sleep(5000)]);
    try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 }); }
    catch { /* Windows can hold Crashpad files briefly; the OS temp cleaner gets it */ }
  }
  console.log(failed ? `${failed} check(s) failed` : 'All checks passed');
  process.exit(failed ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(2); });
