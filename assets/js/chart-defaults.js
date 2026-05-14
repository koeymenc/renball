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

  // Expose a Renball color palette for charts that need multiple series
  window.RENBALL_COLORS = {
    primary: C.accent,
    primaryDim: C.accentDim,
    secondary: '#72c1ff',     // sky-blue counterpart to lime
    secondaryDim: '#458fbf',
    tertiary: '#ff72c1',      // pink for 3rd series if needed
    quaternary: '#ffc172',    // orange for 4th
    neutral: C.textSecondary,
    palette: ['#c1ff72', '#72c1ff', '#ff72c1', '#ffc172', '#a472ff', '#72ffd4'],
    tokens: C,
  };

  // Global Chart.js defaults
  Chart.defaults.color = C.textSecondary;
  Chart.defaults.borderColor = C.border;
  Chart.defaults.font.family = C.sans;
  Chart.defaults.font.size = 12;

  // Default plugin (legend, title, tooltip) styling
  Chart.defaults.plugins.legend.labels.color = C.textSecondary;
  Chart.defaults.plugins.legend.labels.font = { family: C.mono, size: 11 };

  Chart.defaults.plugins.title.color = C.text;
  Chart.defaults.plugins.title.font = { family: C.serif, size: 18, weight: 'normal' };
  Chart.defaults.plugins.title.padding = { top: 0, bottom: 20 };

  Chart.defaults.plugins.tooltip.backgroundColor = C.bgCard;
  Chart.defaults.plugins.tooltip.borderColor = C.borderLight;
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.titleColor = C.text;
  Chart.defaults.plugins.tooltip.bodyColor = C.textSecondary;
  Chart.defaults.plugins.tooltip.titleFont = { family: C.mono, size: 11 };
  Chart.defaults.plugins.tooltip.bodyFont = { family: C.sans, size: 12 };
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 0;

  // Grid lines / axes for cartesian charts
  Chart.defaults.scale.grid.color = C.border;
  Chart.defaults.scale.grid.tickColor = C.border;
  Chart.defaults.scale.ticks.color = C.textMuted;
  Chart.defaults.scale.ticks.font = { family: C.mono, size: 10 };
  Chart.defaults.scale.title.color = C.textSecondary;
  Chart.defaults.scale.title.font = { family: C.mono, size: 11 };
})();
