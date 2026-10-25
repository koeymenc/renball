"""
renball_chart_style.py — Renball matplotlib theme + X (Twitter) image export
===========================================================================

One chart = one idea, readable on a phone. Mirrors assets/css/design-tokens.css
and assets/js/chart-defaults.js so a PNG posted on X looks like the site.

Formats (exact pixel output, 200 dpi):
    "landscape"  1600 x  900   (16:9 — timeline default)
    "portrait"   1080 x 1350   (4:5  — takes more of the phone screen)

Each format carries a type scale sized for a ~390 px-wide phone timeline;
save() warns when any text would render below ~9 css px on that phone.

Typical use (from a project's code/build_social.py):

    import sys; sys.path.insert(0, str(REPO_ROOT / "assets" / "social"))
    import renball_chart_style as S

    def draw(ax, f):                      # f = format spec (sizes, palette)
        bars = ax.bar(labels, values, color=S.ACCENT)
        S.label_bars(ax, bars, "{:.1f}%", f)

    S.export(draw, OUT_DIR, "01_conversion",
             title="Fouled takers convert *3 pp less*",
             subtitle="Penalty conversion, top 5 leagues 2017–2024",
             source="FBref player-match data · n = 3,857 penalties")

Titles accept *accent* markers (italic + lime), same convention as the slide
master. Fonts are registered from assets/fonts/ (if vendored), then the
Windows per-user and system font folders; missing faces fall back to the
CSS fallbacks (Georgia / Segoe UI / Consolas) with a printed warning.
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.text import Text

REPO_ROOT = Path(__file__).resolve().parents[2]

# ════════════════════════════════════════════════════════════════════════
# Tokens (mirror design-tokens.css / chart-defaults.js)
# ════════════════════════════════════════════════════════════════════════
BG             = "#080c08"
BG_ELEVATED    = "#0e150e"
BG_CARD        = "#111a11"
SURFACE        = "#1a261a"
BORDER         = "#1e2e1e"
BORDER_LIGHT   = "#2d3d2d"
TEXT           = "#e8efe8"
TEXT_SECONDARY = "#8fa68f"
TEXT_MUTED     = "#5a735a"
ACCENT         = "#c1ff72"
ACCENT_DIM     = "#8fbf45"
SECONDARY      = "#72c1ff"            # RENBALL_COLORS.secondary
PALETTE        = ["#c1ff72", "#72c1ff", "#ff72c1", "#ffc172", "#a472ff", "#72ffd4"]

# ════════════════════════════════════════════════════════════════════════
# Formats + type scale
# ════════════════════════════════════════════════════════════════════════
DPI = 200
PHONE_CSS_WIDTH = 390          # px a timeline image occupies on a typical phone
MIN_PHONE_PX = 9.0             # warn below this for any text...
MIN_PHONE_PX_FOOTER = 7.0      # ...and below this for source line / watermark

FORMATS = {
    "landscape": {
        "name": "landscape", "px": (1600, 900),
        "pad": 64, "header_gap": 34, "footer_h": 74,
        "size": {"eyebrow": 13.5, "title": 30, "subtitle": 17, "label": 15, "tick": 15,
                 "annot": 17, "legend": 15, "source": 11.5, "mark": 15, "hero": 64},
    },
    "portrait": {
        "name": "portrait", "px": (1080, 1350),
        "pad": 52, "header_gap": 30, "footer_h": 64,
        "size": {"eyebrow": 9.5, "title": 22, "subtitle": 12.5, "label": 12, "tick": 11,
                 "annot": 12.5, "legend": 11, "source": 8.5, "mark": 11, "hero": 48},
    },
}


def spec(fmt: str = "landscape") -> dict:
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}; use one of {sorted(FORMATS)}")
    return FORMATS[fmt]


# ════════════════════════════════════════════════════════════════════════
# Fonts
# ════════════════════════════════════════════════════════════════════════
SERIF, SERIF_ITALIC, SANS, MONO = "Georgia", "Georgia", "Segoe UI", "Consolas"
_FONT_PATTERNS = {
    "serif":        ("InstrumentSerif-Regular",),
    "serif_italic": ("InstrumentSerif-Italic",),
    "sans":         ("DMSans-Regular", "DMSans-VariableFont", "DMSans[", "DMSans-Variable"),
    "mono":         ("JetBrainsMono-Regular", "JetBrainsMono-VariableFont", "JetBrainsMono[",
                     "JetBrainsMono-Variable"),
}
_FALLBACK = {"serif": "Georgia", "serif_italic": "Georgia", "sans": "Segoe UI", "mono": "Consolas"}
_registered = False
_HAS_SERIF_ITALIC = False


def _font_dirs() -> list[Path]:
    dirs = [REPO_ROOT / "assets" / "fonts"]
    if os.name == "nt":
        dirs += [Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
                 Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
    else:
        dirs += [Path.home() / "Library" / "Fonts", Path("/Library/Fonts"),
                 Path.home() / ".fonts", Path.home() / ".local/share/fonts", Path("/usr/share/fonts")]
    return [d for d in dirs if d.is_dir()]


def register_fonts(verbose: bool = False) -> dict[str, str]:
    """
    Register the brand fonts with matplotlib and resolve the family names it
    assigned. Returns {"serif", "serif_italic", "sans", "mono"} -> family.
    Idempotent.
    """
    global SERIF, SERIF_ITALIC, SANS, MONO, _registered, _HAS_SERIF_ITALIC
    resolved = dict(_FALLBACK)
    files = [p for d in _font_dirs() for p in d.rglob("*") if p.suffix.lower() in (".ttf", ".otf")]
    for role, patterns in _FONT_PATTERNS.items():
        match = next((p for pat in patterns for p in files if p.name.startswith(pat)), None)
        if match is None:
            continue
        font_manager.fontManager.addfont(str(match))
        entry = next((e for e in font_manager.fontManager.ttflist
                      if Path(e.fname).resolve() == match.resolve()), None)
        if entry is not None:
            resolved[role] = entry.name
    missing = [r for r in _FONT_PATTERNS if resolved[r] == _FALLBACK[r]]
    # An italic-only Instrument Serif would make every upright title italic:
    # keep serif + italic in the same family so titles never mix two serifs.
    if resolved["serif"] == _FALLBACK["serif"]:
        resolved["serif_italic"] = _FALLBACK["serif_italic"]
    _HAS_SERIF_ITALIC = resolved["serif_italic"] != _FALLBACK["serif_italic"]
    if missing and (verbose or not _registered):
        warnings.warn("renball_chart_style: brand font(s) not found for "
                      f"{', '.join(missing)} -> using {', '.join(_FALLBACK[m] for m in missing)}. "
                      "Install the static TTFs or vendor them in assets/fonts/.", stacklevel=2)
    SERIF, SERIF_ITALIC, SANS, MONO = (resolved["serif"], resolved["serif_italic"],
                                       resolved["sans"], resolved["mono"])
    _registered = True
    return resolved


def apply_theme() -> None:
    """Set global rcParams to the Renball dark theme (safe to call repeatedly)."""
    register_fonts()
    plt.rcParams.update({
        "figure.facecolor": BG, "savefig.facecolor": BG, "axes.facecolor": BG,
        "text.color": TEXT, "axes.labelcolor": TEXT_SECONDARY,
        "axes.edgecolor": BORDER_LIGHT, "axes.linewidth": 1.0,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
        "grid.color": BORDER, "grid.linewidth": 0.9,
        "xtick.color": TEXT_MUTED, "ytick.color": TEXT_MUTED,
        "xtick.labelcolor": TEXT_SECONDARY, "ytick.labelcolor": TEXT_SECONDARY,
        "xtick.major.size": 0, "ytick.major.size": 0,
        "xtick.major.pad": 8, "ytick.major.pad": 8,
        "font.family": SANS, "font.size": 12,
        "legend.frameon": False, "legend.labelcolor": TEXT_SECONDARY,
        "axes.prop_cycle": matplotlib.cycler(color=PALETTE),
        "errorbar.capsize": 6, "lines.linewidth": 2.6, "lines.solid_capstyle": "round",
        "patch.edgecolor": "none",
    })


# ════════════════════════════════════════════════════════════════════════
# Rich text (*accent* runs) — same parser as the slide master
# ════════════════════════════════════════════════════════════════════════
_ACCENT_RE = re.compile(r"\*([^*]+)\*")


def parse_accent_runs(text: str) -> list[tuple[str, bool]]:
    parts, pos = [], 0
    for m in _ACCENT_RE.finditer(text):
        if m.start() > pos:
            parts.append((text[pos:m.start()], False))
        parts.append((m.group(1), True))
        pos = m.end()
    if pos < len(text):
        parts.append((text[pos:], False))
    return parts or [(text, False)]


def _text_width_px(fig, t: Text) -> float:
    return t.get_window_extent(renderer=fig.canvas.get_renderer()).width


def rich_text(fig, x_px: float, y_px: float, text: str, *, size: float,
              color: str = TEXT, accent: str = ACCENT, family: Optional[str] = None,
              accent_family: Optional[str] = None, accent_italic: bool = True,
              ha: str = "left", va: str = "top", gid: Optional[str] = None) -> list[Text]:
    """
    Draw one line with *accent* runs at pixel coords (origin top-left).
    Accent runs are italic + lime (slide-master convention) unless
    accent_italic=False (the wordmark). ha='right' right-aligns the line.
    """
    family = family or SERIF
    accent_family = accent_family or SERIF_ITALIC
    # Only ask for italic when a real italic face is registered — never faux
    italic = accent_italic and _HAS_SERIF_ITALIC
    W, H = fig.canvas.get_width_height()
    runs = parse_accent_runs(text)
    artists: list[Text] = []
    for seg, is_acc in runs:
        artists.append(fig.text(0, 0, seg, fontsize=size, color=accent if is_acc else color,
                                family=accent_family if is_acc else family,
                                style="italic" if (is_acc and italic) else "normal",
                                va=va, ha="left", gid=gid))
    widths = [_text_width_px(fig, a) for a in artists]
    x = x_px - sum(widths) if ha == "right" else x_px
    for a, w in zip(artists, widths):
        a.set_position((x / W, 1 - y_px / H))
        x += w
    return artists


# ════════════════════════════════════════════════════════════════════════
# Figure scaffold: header (eyebrow / title / subtitle), plot box, footer
# ════════════════════════════════════════════════════════════════════════
def new_figure(fmt: str = "landscape", *, title: Optional[str] = None,
               subtitle: Optional[str] = None, eyebrow: Optional[str] = None,
               source: Optional[str] = None, watermark: bool = True):
    """
    Create a themed (fig, ax) at the exact pixel size of `fmt`, with the
    header and footer already drawn. The axes are fitted into the remaining
    box by finish()/save(), so tick labels never collide with the header.
    """
    apply_theme()
    f = spec(fmt)
    W, H = f["px"]
    s = f["size"]
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
    fig.canvas.draw()   # renderer for text measurement
    pad = f["pad"]
    pt = DPI / 72.0
    y = pad

    if eyebrow:
        fig.text(pad / W, 1 - y / H, eyebrow.upper(), fontsize=s["eyebrow"], color=ACCENT,
                 family=MONO, va="top")
        y += s["eyebrow"] * pt * 1.9
    if title:
        for line in title.split("\n"):
            rich_text(fig, pad, y, line, size=s["title"])
            y += s["title"] * pt * 1.18
    if subtitle:
        y += 4
        for line in subtitle.split("\n"):
            fig.text(pad / W, 1 - y / H, line, fontsize=s["subtitle"], color=TEXT_SECONDARY,
                     family=SANS, va="top")
            y += s["subtitle"] * pt * 1.35
    header_bottom = y + f["header_gap"]

    footer_y = H - f["footer_h"] / 2
    if source:
        fig.text(pad / W, 1 - footer_y / H, source.upper(), fontsize=s["source"],
                 color=TEXT_MUTED, family=MONO, va="center", gid="rb-footer")
    if watermark:
        rich_text(fig, W - pad, footer_y, "ren*ball*.com", size=s["mark"], color=TEXT_SECONDARY,
                  accent=ACCENT, family=SERIF, accent_family=SERIF, accent_italic=False,
                  ha="right", va="center", gid="rb-footer")

    # Provisional axes inside the content box; finish() refines it.
    box = (pad, header_bottom, W - pad, H - f["footer_h"] - 10)   # l, t, r, b in px
    ax = fig.add_axes([box[0] / W, 1 - box[3] / H, (box[2] - box[0]) / W, (box[3] - box[1]) / H])
    style_axes(ax, fmt)
    fig._renball = {"fmt": fmt, "box": box}
    return fig, ax


def style_axes(ax, fmt: str = "landscape", *, grid: str = "y") -> None:
    s = spec(fmt)["size"]
    ax.set_facecolor(BG)
    ax.tick_params(labelsize=s["tick"])
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_family(MONO)
    ax.xaxis.label.set_size(s["label"]); ax.yaxis.label.set_size(s["label"])
    ax.xaxis.label.set_family(MONO);     ax.yaxis.label.set_family(MONO)
    ax.grid(False)
    if grid in ("y", "both"):
        ax.grid(axis="y", color=BORDER, linewidth=0.9)
    if grid in ("x", "both"):
        ax.grid(axis="x", color=BORDER, linewidth=0.9)


def finish(fig, ax=None, *, iterations: int = 3) -> None:
    """
    Re-apply tick fonts (matplotlib recreates tick labels after plotting) and
    shrink/shift the axes so ticks + axis labels sit inside the content box.
    """
    meta = getattr(fig, "_renball", None)
    if meta is None or meta.get("box") is None:      # stat cards have nothing to fit
        return
    axes = [ax] if ax is not None else fig.axes
    W, H = fig.canvas.get_width_height()
    l, t, r, b = meta["box"]
    s = spec(meta["fmt"])["size"]
    for a in axes:
        a.tick_params(labelsize=s["tick"])
        for lbl in a.get_xticklabels() + a.get_yticklabels():
            lbl.set_family(MONO)
        # Rotated y-labels are unreadable on a phone and eat the plot height:
        # move them to a horizontal unit label above the y-axis.
        if a.get_ylabel() and not getattr(a, "_renball_ylabel", False):
            a.text(0, 1, a.get_ylabel(), transform=a.transAxes, ha="left", va="bottom",
                   fontsize=s["label"], color=TEXT_SECONDARY, family=MONO,
                   gid="rb-ylabel").set_y(1.03)
            a.set_ylabel("")
            a._renball_ylabel = True
    if len(axes) != 1:
        return   # multi-axes layouts manage their own geometry
    a = axes[0]
    for _ in range(iterations):
        fig.canvas.draw()
        tb = a.get_tightbbox(fig.canvas.get_renderer())          # px, origin bottom-left
        pos = a.get_position()
        ax_l, ax_r = pos.x0 * W, pos.x1 * W
        ax_t, ax_b = (1 - pos.y1) * H, (1 - pos.y0) * H           # px from top
        # Space the decorations (tick labels, axis labels) need around the axes
        left_extra, right_extra = ax_l - tb.x0, tb.x1 - ax_r
        top_extra, bottom_extra = ax_t - (H - tb.y1), (H - tb.y0) - ax_b
        L, R = l + left_extra, r - right_extra
        T, B = t + top_extra, b - bottom_extra
        a.set_position([L / W, 1 - B / H, (R - L) / W, (B - T) / H])


# ════════════════════════════════════════════════════════════════════════
# Save / export
# ════════════════════════════════════════════════════════════════════════
def check_legibility(fig) -> list[str]:
    """Return warnings for text that would render too small on a phone."""
    meta = getattr(fig, "_renball", {"fmt": "landscape"})
    W, _ = fig.canvas.get_width_height()
    css_per_pt = (DPI / 72.0) * PHONE_CSS_WIDTH / W
    problems = []
    for t in fig.findobj(Text):
        if not t.get_visible() or not t.get_text().strip():
            continue
        px = t.get_fontsize() * css_per_pt
        floor = MIN_PHONE_PX_FOOTER if t.get_gid() == "rb-footer" else MIN_PHONE_PX
        if px < floor - 1e-6:
            problems.append(f"'{t.get_text()[:30]}' {t.get_fontsize():.1f}pt -> "
                            f"{px:.1f} css px on phone (< {floor:.0f}) [{meta['fmt']}]")
    return problems


def save(fig, path, *, check: bool = True) -> Path:
    """Write a PNG at the format's exact pixel size (no tight bbox cropping)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    finish(fig)
    if check:
        for p in check_legibility(fig):
            print(f"  [WARN] legibility: {p}")
    fig.savefig(path, dpi=DPI, facecolor=BG)
    plt.close(fig)
    return path


def export(draw: Callable, out_dir, name: str, *,
           formats: Sequence[str] = ("landscape", "portrait"), **header) -> list[Path]:
    """
    Render the same chart in each format: draw(ax, spec) does the plotting;
    header kwargs (title, subtitle, eyebrow, source, watermark) go to
    new_figure(). Writes <out_dir>/<name>_<format>.png.
    """
    out = []
    for fmt in formats:
        fig, ax = new_figure(fmt, **header)
        draw(ax, spec(fmt))
        out.append(save(fig, Path(out_dir) / f"{name}_{fmt}.png"))
    return out


# ════════════════════════════════════════════════════════════════════════
# Chart helpers (keep charts to one idea)
# ════════════════════════════════════════════════════════════════════════
def label_bars(ax, bars, fmt_str: str = "{:.1f}", f: Optional[dict] = None, *,
               where: str = "above", color: Optional[str] = None,
               values: Optional[Iterable[float]] = None) -> None:
    """
    Value labels on bars, large enough to read on a phone.
    where: "above" (default), "top" (inside, under the bar end) or "base"
    (inside, at the bottom — use with CI whiskers so labels never collide).
    """
    f = f or spec("landscape")
    size = f["size"]["annot"]
    vals = list(values) if values is not None else [b.get_height() for b in bars]
    ymin, ymax = ax.get_ylim()
    off = (ymax - ymin) * 0.025
    for b, v in zip(bars, vals):
        x = b.get_x() + b.get_width() / 2
        txt = fmt_str.format(v)
        if where == "top":
            ax.text(x, b.get_height() - off, txt, ha="center", va="top",
                    fontsize=size, color=color or BG, family=MONO)
        elif where == "base":
            ax.text(x, max(ymin, b.get_y()) + off, txt, ha="center", va="bottom",
                    fontsize=size, color=color or BG, family=MONO)
        else:
            ax.text(x, b.get_height() + off, txt, ha="center", va="bottom",
                    fontsize=size, color=color or TEXT, family=MONO)


def ci_whiskers(ax, xs, lo, hi, *, color: str = TEXT, cap: float = 0.08,
                lw: float = 2.0) -> None:
    """Vertical CI whiskers with caps at each x (data units)."""
    for x, l, h in zip(xs, lo, hi):
        ax.plot([x, x], [l, h], color=color, lw=lw, solid_capstyle="butt", zorder=5)
        ax.plot([x - cap, x + cap], [l, l], color=color, lw=lw, zorder=5)
        ax.plot([x - cap, x + cap], [h, h], color=color, lw=lw, zorder=5)


def callout(ax, text: str, xy, xytext, f: Optional[dict] = None, *,
            color: str = ACCENT) -> None:
    """Short annotation with a thin arrow — use instead of a legend."""
    f = f or spec("landscape")
    ax.annotate(text, xy=xy, xytext=xytext, color=color, fontsize=f["size"]["annot"],
                family=SANS, arrowprops=dict(arrowstyle="-", color=color, lw=1.2),
                va="center")


def nice_range(values: Iterable[float], *, padding: float = 4, step: float = 5,
               floor: float = 0, ceil: float = 100) -> tuple[float, float]:
    """Python twin of RENBALL_HELPERS.niceRange — don't crush 60–85% onto 0–100."""
    v = [x for x in values if x is not None]
    lo = max(floor, (min(v) - padding) // step * step)
    hi = min(ceil, -(-(max(v) + padding) // step) * step)
    return (lo, hi if hi - lo >= step else lo + step)


def stat_card(value: str, label: str, fmt: str = "landscape", *,
              title: Optional[str] = None, eyebrow: Optional[str] = None,
              sub: Optional[str] = None, source: Optional[str] = None):
    """A single headline number as an image — for hook posts."""
    fig, ax = new_figure(fmt, title=title, eyebrow=eyebrow, source=source)
    ax.axis("off")
    s = spec(fmt)["size"]
    ax.text(0.0, 0.62, value, transform=ax.transAxes, fontsize=s["hero"] * 1.6,
            color=ACCENT, family=SERIF, va="center", ha="left")
    ax.text(0.0, 0.22, label.upper(), transform=ax.transAxes, fontsize=s["label"],
            color=TEXT_SECONDARY, family=MONO, va="center")
    if sub:
        ax.text(0.0, 0.06, sub, transform=ax.transAxes, fontsize=s["subtitle"],
                color=TEXT_MUTED, family=SANS, va="center")
    fig._renball["box"] = None  # nothing to fit
    return fig, ax


AUDIENCES = (("coaches", "Coaches", "training & tactics"), ("managers", "Managers", "match-day decisions"),
             ("clubs", "Clubs", "recruitment & contracts"), ("agents", "Agents", "positioning a player"))
EVIDENCE = {"strong": ("Strong", 3, ACCENT), "moderate": ("Moderate", 2, ACCENT_DIM),
            "exploratory": ("Exploratory", 1, TEXT_SECONDARY)}


def takeaways_card(takeaways: dict, fmt: str = "portrait", *, title: Optional[str] = None,
                   eyebrow: Optional[str] = None, source: Optional[str] = None):
    """The four-audience takeaways (data.json["takeaways"]) as one image for the thread's
    "Who should care?" post: audience, evidence label with its 3-step meter, the takeaway.
    Portrait stacks the four audiences; landscape uses two columns. Text shrinks to fit, never
    below the phone-legibility floor. En dashes become hyphens (X copy, CLAUDE.md §12)."""
    import textwrap
    from matplotlib.patches import Rectangle

    fig, ax = new_figure(fmt, title=title, eyebrow=eyebrow, source=source)
    ax.axis("off")
    fig._renball["box"] = None
    f = spec(fmt)
    W, H = f["px"]
    pad, pt = f["pad"], DPI / 72.0
    top = H - (ax.get_position().y1 * H)
    bottom = H - f["footer_h"] - 16
    floor = MIN_PHONE_PX / ((DPI / 72.0) * PHONE_CSS_WIDTH / W) + 0.05
    gap = 48
    ncol = 1 if fmt == "portrait" else 2
    col_w = (W - 2 * pad - gap * (ncol - 1)) / ncol
    if ncol == 1:
        splits = [[AUDIENCES]]
    else:   # every way to share the four audiences between two columns, order kept within a column
        splits = [[[a for i, a in enumerate(AUDIENCES) if not (m >> i) & 1],
                   [a for i, a in enumerate(AUDIENCES) if (m >> i) & 1]] for m in range(1, 15)]

    def layout(size: float, cols):
        small = max(size * 0.8, floor)
        width = int(col_w / (size * pt * 0.5))
        rows, ends = [], []
        for ci, audiences in enumerate(cols):
            x0, y = pad + ci * (col_w + gap), top
            for key, name, focus in audiences:
                rows.append(("head", (name, focus, small), x0, y))
                y += size * pt * 1.55
                items = takeaways.get(key) or []
                if not items:
                    rows.append(("none", "No defensible claim from this study.", x0, y))
                    y += size * pt * 1.45
                for it in items:
                    rows.append(("pill", (it["evidence"], small), x0, y))
                    y += max(small, size * 0.85) * pt * 1.45
                    text = it["text"].replace("**", "").replace("–", "-")
                    for line in textwrap.wrap(text, width):
                        rows.append(("text", line, x0, y))
                        y += size * pt * 1.32
                    y += size * pt * 0.35
                y += size * pt * 0.75
            ends.append(y)
        return rows, max(ends)

    def best(size: float):
        return min((layout(size, cols) for cols in splits), key=lambda r: r[1])

    size = f["size"]["annot"]
    rows, end = best(size)
    while end > bottom and size > floor:
        size = max(floor, size - 0.25)
        rows, end = best(size)
    for kind, payload, x0, y in rows:
        yf = 1 - y / H
        if kind == "head":
            name, focus, small = payload
            t = fig.text(x0 / W, yf, name, fontsize=size * 1.25, color=TEXT, family=SERIF, va="top")
            x = x0 + _text_width_px(fig, t) + 14
            fig.text(x / W, yf - 0.004, focus.upper(), fontsize=small, color=TEXT_MUTED, family=MONO, va="top")
        elif kind == "pill":
            key, small = payload
            label, level, color = EVIDENCE[key]
            sq = small * pt * 0.62
            for i in range(3):
                fig.patches.append(Rectangle(((x0 + i * (sq + 5)) / W, yf - (sq + 5) / H), sq / W, sq / H,
                                             transform=fig.transFigure, facecolor=color if i < level else BORDER_LIGHT,
                                             edgecolor="none"))
            fig.text((x0 + 3 * (sq + 5) + 8) / W, yf, label.upper(), fontsize=small, color=color, family=MONO,
                     va="top")
        elif kind == "none":
            fig.text(x0 / W, yf, payload, fontsize=size, color=TEXT_MUTED, family=SANS, style="italic", va="top")
        else:
            fig.text(x0 / W, yf, payload, fontsize=size, color=TEXT_SECONDARY, family=SANS, va="top")
    return fig, ax


register_fonts()
