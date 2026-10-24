/* ─────────────────────────────────────────────────
   RENBALL RESEARCH-STANDARD COMPONENTS
   Shared by every projects/XX/analysis.html. Styles live in design-tokens.css.

   1. Takeaways — "Who should care", four audiences, evidence-labelled.
        RENBALL.renderTakeaways(el, data.takeaways)
      data.takeaways (written by code/build.py, so every number traces to data.json):
        {
          "intro": "optional one-liner",
          "coaches":  [{ "text": "...", "evidence": "strong|moderate|exploratory", "basis": "n = 3,857 · CI excludes 0" }],
          "managers": [...], "clubs": [...], "agents": [...]
        }
      An empty list renders an honest "no defensible claim" line.

   2. Slide viewer — slides.pdf rendered page-by-page with PDF.js (works on
      mobile, unlike <iframe>-embedded PDFs). Lazy-loads when scrolled near.
        <div class="slide-viewer" data-renball="slide-viewer" data-src="slides.pdf"></div>
      Mounted automatically on DOMContentLoaded.

   Audience + evidence definitions mirror assets/slides/renball_slide_master.py
   (AUDIENCES / EVIDENCE) — keep the two in sync.
   ───────────────────────────────────────────────── */

(function () {
  const AUDIENCES = [
    { key: 'coaches',  label: 'Coaches',  focus: 'Training & tactics' },
    { key: 'managers', label: 'Managers', focus: 'Match-day decisions' },
    { key: 'clubs',    label: 'Clubs',    focus: 'Recruitment & contracts' },
    { key: 'agents',   label: 'Agents',   focus: 'Positioning a player' },
  ];

  const EVIDENCE = {
    strong: {
      label: 'Strong', level: 3,
      def: 'Large sample; the 95% interval excludes zero (or, for a "no effect" claim, sits inside a stated equivalence margin); survives the main controls; holds across leagues or seasons.',
    },
    moderate: {
      label: 'Moderate', level: 2,
      def: 'Consistent direction and plausible size, with one gap: the interval touches zero, a single method or sample, or only partial replication.',
    },
    exploratory: {
      label: 'Exploratory', level: 1,
      def: 'Small samples, an interval that comfortably includes zero, untested confounders, or a pattern found by looking rather than tested. A question worth asking, not advice.',
    },
  };

  const PDFJS_VERSION = '4.10.38';
  const PDFJS_BASE = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${PDFJS_VERSION}/build/`;

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // Takeaway copy may use **bold** for the number that matters; nothing else.
  const rich = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  function evidencePill(key) {
    const ev = EVIDENCE[key];
    if (!ev) throw new Error(`Unknown evidence label "${key}" — use strong | moderate | exploratory`);
    return `<span class="evidence-pill ${key}" title="${esc(ev.def)}">` +
      `<span class="evidence-meter" aria-hidden="true"><i></i><i></i><i></i></span>${ev.label}</span>`;
  }

  // ── 1. Takeaways ─────────────────────────────────────────
  function renderTakeaways(el, takeaways, opts) {
    if (!el) return;
    opts = opts || {};
    if (!takeaways) {
      el.innerHTML = '';
      console.warn('renderTakeaways: data.takeaways missing');
      return;
    }
    const title = opts.title || 'Who should care';
    const legend = Object.entries(EVIDENCE).map(([k, ev]) =>
      `<dt>${evidencePill(k)}</dt><dd>${esc(ev.def)}</dd>`).join('');

    const cards = AUDIENCES.map((a) => {
      const items = takeaways[a.key] || [];
      const body = items.length
        ? `<ul class="takeaway-list">${items.map((t) => `
            <li>
              <p class="takeaway-text">${rich(t.text)}</p>
              <div class="takeaway-meta">${evidencePill(t.evidence)}${t.basis ? `<span class="takeaway-basis">${esc(t.basis)}</span>` : ''}</div>
            </li>`).join('')}</ul>`
        : `<p class="takeaway-empty">No defensible claim for this audience from this study.</p>`;
      return `
        <article class="takeaway-card" data-audience="${a.key}">
          <header><span class="takeaway-audience">${a.label}</span><span class="takeaway-focus">${a.focus}</span></header>
          ${body}
        </article>`;
    }).join('');

    el.innerHTML = `
      <h2>${esc(title)}</h2>
      ${takeaways.intro ? `<p class="takeaways-intro">${rich(takeaways.intro)}</p>` : ''}
      <div class="evidence-legend">
        <span>Evidence</span>${Object.keys(EVIDENCE).map(evidencePill).join('')}
        <details><summary>What the labels mean</summary><dl>${legend}</dl></details>
      </div>
      <div class="takeaways-grid">${cards}</div>`;
  }

  // ── 2. Slide viewer ──────────────────────────────────────
  let pdfjsPromise = null;
  function loadPdfjs() {
    if (!pdfjsPromise) {
      pdfjsPromise = import(PDFJS_BASE + 'pdf.min.mjs').then((lib) => {
        lib.GlobalWorkerOptions.workerSrc = PDFJS_BASE + 'pdf.worker.min.mjs';
        return lib;
      });
    }
    return pdfjsPromise;
  }

  function mountSlideViewer(el) {
    if (!el || el.dataset.mounted) return;
    el.dataset.mounted = '1';
    const src = el.dataset.src || 'slides.pdf';
    el.tabIndex = 0;
    el.setAttribute('role', 'region');
    el.setAttribute('aria-label', 'Slide deck viewer');
    el.innerHTML = `
      <div class="slide-stage"><div class="slide-status">Loading slides…</div></div>
      <div class="slide-progress"><span></span></div>
      <div class="slide-controls">
        <button type="button" data-act="prev" aria-label="Previous slide">← Prev</button>
        <span class="slide-counter" aria-live="polite">— / —</span>
        <button type="button" data-act="next" aria-label="Next slide">Next →</button>
        <span class="spacer"></span>
        <button type="button" data-act="full" class="hide-sm">Fullscreen</button>
        <a href="${esc(src)}" target="_blank" rel="noopener">PDF ↓</a>
      </div>`;

    const stage = el.querySelector('.slide-stage');
    const counter = el.querySelector('.slide-counter');
    const bar = el.querySelector('.slide-progress span');
    const prev = el.querySelector('[data-act="prev"]');
    const next = el.querySelector('[data-act="next"]');
    const full = el.querySelector('[data-act="full"]');
    let doc = null, page = 1, rendering = null, queued = null;

    const fail = (err) => {
      console.warn('slide viewer:', err);
      stage.innerHTML = `<div class="slide-status">Couldn't render the deck here — <a href="${esc(src)}" target="_blank" rel="noopener">open slides.pdf</a></div>`;
      prev.disabled = next.disabled = true;
    };

    async function render(n) {
      if (!doc) return;
      if (rendering) { queued = n; return; }
      page = Math.min(Math.max(1, n), doc.numPages);
      counter.textContent = `${String(page).padStart(2, '0')} / ${String(doc.numPages).padStart(2, '0')}`;
      bar.style.width = `${(page / doc.numPages) * 100}%`;
      prev.disabled = page <= 1;
      next.disabled = page >= doc.numPages;
      rendering = (async () => {
        const p = await doc.getPage(page);
        const base = p.getViewport({ scale: 1 });
        const box = stage.getBoundingClientRect();
        const fit = Math.min(box.width / base.width, box.height / base.height);
        const dpr = window.devicePixelRatio || 1;
        const vp = p.getViewport({ scale: fit * dpr });
        const canvas = document.createElement('canvas');
        canvas.width = Math.floor(vp.width);
        canvas.height = Math.floor(vp.height);
        canvas.style.width = `${Math.floor(vp.width / dpr)}px`;
        canvas.style.height = `${Math.floor(vp.height / dpr)}px`;
        canvas.setAttribute('aria-label', `Slide ${page} of ${doc.numPages}`);
        await p.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;
        stage.replaceChildren(canvas);
      })();
      try { await rendering; } catch (e) { fail(e); }
      rendering = null;
      if (queued != null) { const q = queued; queued = null; render(q); }
    }

    async function start() {
      try {
        const lib = await loadPdfjs();
        doc = await lib.getDocument({ url: src, isEvalSupported: false }).promise;
        render(1);
      } catch (e) { fail(e); }
    }

    prev.addEventListener('click', () => render(page - 1));
    next.addEventListener('click', () => render(page + 1));
    full.addEventListener('click', () => {
      if (document.fullscreenElement) document.exitFullscreen();
      else el.requestFullscreen?.();
    });
    el.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === 'PageDown') { render(page + 1); e.preventDefault(); }
      if (e.key === 'ArrowLeft' || e.key === 'PageUp') { render(page - 1); e.preventDefault(); }
      if (e.key === 'Home') render(1);
      if (e.key === 'End' && doc) render(doc.numPages);
    });
    let x0 = null;
    stage.addEventListener('touchstart', (e) => { x0 = e.touches[0].clientX; }, { passive: true });
    stage.addEventListener('touchend', (e) => {
      if (x0 == null) return;
      const dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 40) render(page + (dx < 0 ? 1 : -1));
      x0 = null;
    });
    let t = null;
    const rerender = () => { clearTimeout(t); t = setTimeout(() => render(page), 150); };
    window.addEventListener('resize', rerender);
    document.addEventListener('fullscreenchange', rerender);

    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((entries) => {
        if (entries.some((en) => en.isIntersecting)) { io.disconnect(); start(); }
      }, { rootMargin: '400px' });
      io.observe(el);
    } else {
      start();
    }
  }

  function autoMount() {
    document.querySelectorAll('[data-renball="slide-viewer"]').forEach(mountSlideViewer);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', autoMount);
  else autoMount();

  window.RENBALL = Object.assign(window.RENBALL || {}, {
    AUDIENCES, EVIDENCE, renderTakeaways, mountSlideViewer, evidencePill,
  });
})();
