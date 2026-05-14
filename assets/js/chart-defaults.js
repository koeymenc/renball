/* ─────────────────────────────────────────────────
   RENBALL CHART.JS GLOBAL DEFAULTS
   Include this AFTER Chart.js loads.
   ───────────────────────────────────────────────── */

(function () {
  if (typeof Chart === 'undefined') {
    console.warn('Chart.js not loaded — load it before chart-defaults.js');
    return;
  }

  // Pull tokens directly from CSS so they stay in sync with design-tokens.css
  const css = getComputedStyle(document.documentElement);
  const C = {
    text: css.getPropertyValue('--text').trim() || '#e8efe8',
    textSecondary: css.getPropertyValue('--text-secondary').trim() || '#8fa68f',
    textMuted: css.getPropertyValue('--text-muted').trim() || '#5a735a',
    border: css.getPropertyValue('--border').trim() || '#1e2e1e',
    borderLight: css.getPropertyValue('--border-light').trim() || '#2d3d2d',
    accent: css.getPropertyValue('--accent').trim() || '#c1ff72',
    accentDim: css.getPropertyValue('--accent-dim').trim() || '#8fbf45',
    bgCard: css.getPropertyValue('--bg-card').trim() || '#111a11',
    serif: css.getPropertyValue('--serif').trim() || "'Instrument Serif', Georgia, serif",
    sans: css.getPropertyValue('--sans').trim() || "'DM Sans', sans-serif",
    mono: css.getPropertyValue('--mono').trim() || "'JetBrains Mono', monospace",
  };

  // Renball palette for charts with multiple series
  window.RENBALL_COLORS = {
    primary: C.accent,
    primaryDim: C.accentDim,
    secondary: '#72c1ff',
    secondaryDim: '#458fbf',
    tertiary: '#ff72c1',
    quaternary: '#ffc172',
    neutral: C.textSecondary,
    palette: ['#c1ff72', '#72c1ff', '#ff72c1', '#ffc172', '#a472ff', '#72ffd4'],
    tokens: C,
  };

  // Shared helpers for chart configs
  window.RENBALL_HELPERS = {
    /**
     * Compute a tight "nice" axis range from data values.
     *
     * Snaps to multiples of `step` and pads beyond the data extent by
     * `padding`. Useful for football percentages where forcing a 0–100
     * scale crushes 60–85% variation flat.
     *
     * Usage:
     *   y: {
     *     ...RENBALL_HELPERS.niceRange(values),
     *     title: { display: true, text: 'Conversion rate (%)' }
     *   }
     *
     * Options:
     *   padding     — pp of headroom above max / below min (default 4)
     *   step        — round to this multiple (default 5)
     *   includeZero — extend lower bound to 0 if data is positive (default false)
     *   floor / ceil — hard clamps (defaults 0 and 100 for percentages)
     */
    niceRange(values, opts) {
      opts = opts || {};
      const padding = opts.padding != null ? opts.padding : 4;
      const step    = opts.step    != null ? opts.step    : 5;
      const includeZero = !!opts.includeZero;
      const floor = opts.floor != null ? opts.floor :   0;
      const ceil  = opts.ceil  != null ? opts.ceil  : 100;

      const clean = (values || []).filter(v => typeof v === 'number' && !isNaN(v));
      if (!clean.length) return { min: floor, max: ceil };

      const dataMin = Math.min(...clean);
      const dataMax = Math.max(...clean);
      let lo = Math.floor((dataMin - padding) / step) * step;
      let hi = Math.ceil ((dataMax + padding) / step) * step;
      if (includeZero) lo = Math.min(lo, 0);
      lo = Math.max(lo, floor);
      hi = Math.min(hi, ceil);
      if (hi - lo < step) hi = lo + step;
      return { min: lo, max: hi };
    },
  };

  // ── Global Chart.js defaults ───────────────────────────
  Chart.defaults.color = C.textSecondary;
  Chart.defaults.borderColor = C.border;
  Chart.defaults.font.family = C.sans;
  Chart.defaults.font.size = 13;

  // Wider-and-shorter charts so the full plot fits on a laptop viewport.
  // aspectRatio = width / height. At a ~980px chart-wrap width, 3.0 → ~325px height.
  Chart.defaults.responsive = true;
  Chart.defaults.maintainAspectRatio = true;
  Chart.defaults.aspectRatio = 3;

  // Layout breathing room
  Chart.defaults.layout = Chart.defaults.layout || {};
  Chart.defaults.layout.padding = { top: 4, right: 8, bottom: 0, left: 4 };

  // Title — serif, left-aligned, prominent
  Chart.defaults.plugins.title.display = true;
  Chart.defaults.plugins.title.color = C.text;
  Chart.defaults.plugins.title.font = { family: C.serif, size: 22, weight: 'normal' };
  Chart.defaults.plugins.title.padding = { top: 4, bottom: 18 };
  Chart.defaults.plugins.title.align = 'start';

  // Legend
  Chart.defaults.plugins.legend.labels.color = C.textSecondary;
  Chart.defaults.plugins.legend.labels.font = { family: C.mono, size: 12 };
  Chart.defaults.plugins.legend.labels.padding = 16;

  // Tooltip
  Chart.defaults.plugins.tooltip.backgroundColor = C.bgCard;
  Chart.defaults.plugins.tooltip.borderColor = C.borderLight;
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.titleColor = C.text;
  Chart.defaults.plugins.tooltip.bodyColor = C.textSecondary;
  Chart.defaults.plugins.tooltip.titleFont = { family: C.mono, size: 12 };
  Chart.defaults.plugins.tooltip.bodyFont = { family: C.sans, size: 13 };
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 0;

  // Cartesian scales — bigger ticks + axis titles so the chart reads at glance
  Chart.defaults.scale.grid.color = C.border;
  Chart.defaults.scale.grid.tickColor = C.border;
  Chart.defaults.scale.ticks.color = C.textMuted;
  Chart.defaults.scale.ticks.font = { family: C.mono, size: 12 };
  Chart.defaults.scale.title.display = true;
  Chart.defaults.scale.title.color = C.textSecondary;
  Chart.defaults.scale.title.font = { family: C.mono, size: 13 };
  Chart.defaults.scale.title.padding = { top: 10, bottom: 8 };
})();
