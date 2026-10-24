"""
renball_social.py — X (Twitter) package tooling for every Renball project
=========================================================================

Parses a project's social/ drafts, counts characters the way X does,
validates the package against the Research Standard and renders a local
preview.html that looks like the thread will on X.

    projects/XX/social/
      thread.md          one deep-dive thread, 12–18 posts
      posts/NN-slug.md   5–8 standalone posts (one finding each)
      images/*.png       charts from renball_chart_style (+ alt_text.md)
      alt_text.md        alt text for every image
      posting_guide.md   order, timing experiments, objections, metrics
      preview.html       generated here — open locally

File formats
------------
thread.md — one post per "## N" heading; image lines are "[image: images/x.png]"
(max 4 per post); HTML comments are notes and never count:

    ## 1
    Post text. Line breaks are kept.
    [image: images/01_hook_landscape.png]

    ## 2
    ...

posts/NN-slug.md — sections by "## " heading:

    # Post 03 — late equalisers
    ## Post
    The post copy (<= 280).
    ## Alt hook
    An alternative first line / variant to A/B (<= 280).
    ## Image
    [image: ../images/03_late_landscape.png]
    ## Caption
    One-line chart caption (used in the image source line or a reply).

alt_text.md — "## <image path relative to social/>" then the alt text (<= 1000).

CLI (from repo root):
    python assets/social/renball_social.py projects/01-penalty-analysis [--handle @renball]
Prints per-post counts, writes social/preview.html, exits 1 on any violation.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

MAX_WEIGHTED = 280
URL_WEIGHT = 23
ALT_MAX = 1000
THREAD_RANGE = (12, 18)
POSTS_RANGE = (5, 8)
MAX_IMAGES = 4
# CK's X account (confirmed 2026-10-24). Changing it here updates every
# preview, and validate() flags threads still using an old one.
DEFAULT_HANDLE = "@renball"

# ════════════════════════════════════════════════════════════════════════
# X weighted length (twitter-text v3 config)
# ════════════════════════════════════════════════════════════════════════
# Code points in these ranges weigh 1; everything else (CJK, emoji, arrows,
# '…', '≥', subscripts) weighs 2. URLs — including bare domains such as
# renball.com, which X auto-links — always weigh 23.
_LIGHT_RANGES = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
_URL_RE = re.compile(
    r"(?:https?://\S+)|(?<![@\w.])(?:[a-z0-9-]+\.)+(?:com|org|net|io|co|ai|app|dev|uk|de|ch)(?:/[^\s)]*)?",
    re.I)
_IMAGE_RE = re.compile(r"^\s*\[image:\s*([^\]]+)\]\s*$", re.M)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _char_weight(ch: str) -> int:
    cp = ord(ch)
    if cp in (0x200D, 0xFE0E, 0xFE0F):          # ZWJ / variation selectors ride along
        return 0
    return 1 if any(lo <= cp <= hi for lo, hi in _LIGHT_RANGES) else 2


def x_length(text: str) -> int:
    """Weighted length as X counts it (limit 280)."""
    text = unicodedata.normalize("NFC", text)
    total, pos = 0, 0
    for m in _URL_RE.finditer(text):
        total += sum(_char_weight(c) for c in text[pos:m.start()]) + URL_WEIGHT
        pos = m.end()
    return total + sum(_char_weight(c) for c in text[pos:])


# ════════════════════════════════════════════════════════════════════════
# Parsing
# ════════════════════════════════════════════════════════════════════════
@dataclass
class Post:
    key: str                      # "1".."18" for the thread, file stem for posts
    text: str
    images: list[str] = field(default_factory=list)   # paths relative to social/
    alt_hook: Optional[str] = None
    caption: Optional[str] = None
    title: Optional[str] = None

    @property
    def length(self) -> int:
        return x_length(self.text)


def _clean(block: str) -> tuple[str, list[str]]:
    block = _COMMENT_RE.sub("", block)
    images = [m.strip() for m in _IMAGE_RE.findall(block)]
    text = _IMAGE_RE.sub("", block)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, images


def parse_thread(path: Path) -> list[Post]:
    raw = Path(path).read_text(encoding="utf-8")
    parts = re.split(r"^##\s+(\d+)\s*$", raw, flags=re.M)
    posts = []
    for i in range(1, len(parts), 2):
        text, images = _clean(parts[i + 1])
        posts.append(Post(key=parts[i], text=text, images=images))
    return posts


def _sections(raw: str) -> dict[str, str]:
    raw = _COMMENT_RE.sub("", raw)
    out, current = {}, None
    for line in raw.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip().lower()
            out[current] = ""
        elif current:
            out[current] += line + "\n"
    return {k: v.strip() for k, v in out.items()}


def parse_post(path: Path) -> Post:
    raw = Path(path).read_text(encoding="utf-8")
    title = (re.search(r"^#\s+(.+)$", raw, re.M) or [None, None])[1]
    sec = _sections(raw)
    images = [str((Path("posts") / p).as_posix()) for p in _IMAGE_RE.findall(sec.get("image", ""))]
    images = [_normalise_rel(p) for p in images]
    text, inline_imgs = _clean(sec.get("post", ""))
    return Post(key=Path(path).stem, text=text, images=images + inline_imgs,
                alt_hook=sec.get("alt hook") or None, caption=sec.get("caption") or None,
                title=title)


def _normalise_rel(p: str) -> str:
    """'posts/../images/x.png' -> 'images/x.png' (paths relative to social/)."""
    parts: list[str] = []
    for seg in Path(p).as_posix().split("/"):
        if seg == "..":
            if parts:
                parts.pop()
        elif seg not in ("", "."):
            parts.append(seg)
    return "/".join(parts)


def parse_alt_text(path: Path) -> dict[str, str]:
    if not Path(path).exists():
        return {}
    return {_normalise_rel(k): v for k, v in _sections(Path(path).read_text(encoding="utf-8")).items()}


@dataclass
class Package:
    social_dir: Path
    thread: list[Post]
    posts: list[Post]
    alt: dict[str, str]

    @classmethod
    def load(cls, project_dir: Path) -> "Package":
        sd = Path(project_dir) / "social"
        thread = parse_thread(sd / "thread.md") if (sd / "thread.md").exists() else []
        posts = [parse_post(p) for p in sorted((sd / "posts").glob("*.md"))] if (sd / "posts").exists() else []
        return cls(sd, thread, posts, parse_alt_text(sd / "alt_text.md"))

    def all_text(self) -> list[tuple[str, str]]:
        """(label, text) for every piece of copy — used by renball_verify."""
        out = [(f"thread #{p.key}", p.text) for p in self.thread]
        for p in self.posts:
            out.append((f"posts/{p.key}", p.text))
            if p.alt_hook:
                out.append((f"posts/{p.key} alt hook", p.alt_hook))
            if p.caption:
                out.append((f"posts/{p.key} caption", p.caption))
        out += [(f"alt {k}", v) for k, v in self.alt.items()]
        return out


# ════════════════════════════════════════════════════════════════════════
# Validation
# ════════════════════════════════════════════════════════════════════════
def validate(pkg: Package, *, verbose: bool = True, handle: str = DEFAULT_HANDLE) -> list[str]:
    errs: list[str] = []
    sd = pkg.social_dir

    def row(label: str, text: str, n_images: int = 0) -> None:
        n = x_length(text)
        flag = "OK " if n <= MAX_WEIGHTED else "!! "
        if n > MAX_WEIGHTED:
            errs.append(f"{label}: {n}/{MAX_WEIGHTED} characters")
        if verbose:
            img = f"  [{n_images} img]" if n_images else ""
            first = text.splitlines()[0][:58] if text else ""
            print(f"  [{flag}] {label:<26} {n:>3}/280{img:<9} {first}")

    if verbose:
        print(f"== X package: {sd.parent.name} ==")
        print("-- thread.md")
    for p in pkg.thread:
        row(f"thread #{p.key}", p.text, len(p.images))
    lo, hi = THREAD_RANGE
    if not pkg.thread:
        errs.append("social/thread.md missing or has no '## N' posts")
    elif not lo <= len(pkg.thread) <= hi:
        errs.append(f"thread has {len(pkg.thread)} posts (standard: {lo}–{hi})")
    if pkg.thread and not pkg.thread[0].images:
        errs.append("thread #1 has no image (post 1 = hook + headline number + chart)")
    if pkg.thread and not _URL_RE.search(pkg.thread[-1].text):
        errs.append("last thread post has no renball.com link")
    if pkg.thread and handle.lower() not in pkg.thread[-1].text.lower():
        errs.append(f"last thread post doesn't mention {handle}")

    if verbose:
        print("-- posts/")
    for p in pkg.posts:
        row(f"posts/{p.key}", p.text, len(p.images))
        if p.alt_hook:
            row(f"posts/{p.key} (alt hook)", p.alt_hook)
        else:
            errs.append(f"posts/{p.key}: no '## Alt hook' section")
        if not p.images:
            errs.append(f"posts/{p.key}: no image")
        if not p.caption:
            errs.append(f"posts/{p.key}: no '## Caption' section")
    lo, hi = POSTS_RANGE
    if not lo <= len(pkg.posts) <= hi:
        errs.append(f"{len(pkg.posts)} standalone posts (standard: {lo}–{hi})")

    used = {img for p in pkg.thread + pkg.posts for img in p.images}
    for p in pkg.thread + pkg.posts:
        if len(p.images) > MAX_IMAGES:
            errs.append(f"{p.key}: {len(p.images)} images (X max {MAX_IMAGES})")
    for img in sorted(used):
        if not (sd / img).exists():
            errs.append(f"image not found: social/{img}")
        if img not in pkg.alt:
            errs.append(f"no alt text for {img} (add '## {img}' to alt_text.md)")
    for img, alt in pkg.alt.items():
        if len(alt) > ALT_MAX:
            errs.append(f"alt text for {img} is {len(alt)} chars (X max {ALT_MAX})")
    if (sd / "images").exists():
        for png in sorted((sd / "images").glob("*.png")):
            rel = f"images/{png.name}"
            if rel not in pkg.alt:
                errs.append(f"no alt text for {rel}")
    for required in ("posting_guide.md", "alt_text.md"):
        if not (sd / required).exists():
            errs.append(f"social/{required} missing")
    return errs


# ════════════════════════════════════════════════════════════════════════
# preview.html — an X-like dark timeline, local only
# ════════════════════════════════════════════════════════════════════════
PREVIEW_CSS = """
:root { --bg:#000; --text:#e7e9ea; --sub:#71767b; --line:#2f3336; --link:#1d9bf0; --ok:#00ba7c; --bad:#f4212e; }
* { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--text); font:15px/1.4 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
main { max-width:600px; margin:0 auto; border-left:1px solid var(--line); border-right:1px solid var(--line); min-height:100vh; }
header.top { position:sticky; top:0; background:rgba(0,0,0,.75); backdrop-filter:blur(12px); padding:12px 16px; border-bottom:1px solid var(--line); z-index:2; }
header.top h1 { font-size:20px; font-weight:700; }
header.top p { color:var(--sub); font-size:13px; }
.section { padding:12px 16px; color:var(--sub); font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; border-bottom:1px solid var(--line); }
.post { display:grid; grid-template-columns:40px 1fr; gap:12px; padding:12px 16px 4px; position:relative; }
.post.last, .post.solo { border-bottom:1px solid var(--line); padding-bottom:12px; }
.avatar { width:40px; height:40px; border-radius:50%; background:#080c08; border:1px solid #2d3d2d; display:flex; align-items:center; justify-content:center; font:italic 17px Georgia, serif; color:#e8efe8; }
.avatar b { color:#c1ff72; font-weight:400; }
.post:not(.last):not(.solo)::before { content:""; position:absolute; left:35px; top:56px; bottom:-8px; width:2px; background:var(--line); }
.meta { font-size:15px; } .meta .name { font-weight:700; } .meta .handle { color:var(--sub); }
.body { white-space:pre-wrap; word-wrap:break-word; margin:2px 0 10px; }
.body a { color:var(--link); text-decoration:none; }
.media { display:grid; gap:2px; border:1px solid var(--line); border-radius:16px; overflow:hidden; margin-bottom:10px; }
.media.n2, .media.n3, .media.n4 { grid-template-columns:1fr 1fr; }
.media img { width:100%; max-height:510px; object-fit:cover; display:block; }
.media .missing { padding:40px; color:var(--bad); text-align:center; font-size:13px; }
.alt { color:var(--sub); font-size:12px; margin:-4px 0 10px; }
.counts { display:flex; gap:12px; color:var(--sub); font-size:12px; margin-bottom:6px; }
.counts .ok { color:var(--ok); } .counts .bad { color:var(--bad); font-weight:700; }
.variant { border:1px dashed var(--line); border-radius:12px; padding:8px 12px; margin:0 0 10px; color:var(--sub); font-size:14px; white-space:pre-wrap; }
.variant b { color:var(--text); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
.errors { margin:12px 16px; padding:12px; border:1px solid var(--bad); border-radius:12px; color:var(--bad); font-size:13px; }
"""


def _linkify(text: str) -> str:
    out, pos = [], 0
    for m in _URL_RE.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        out.append(f'<a href="#">{html.escape(m.group(0))}</a>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return re.sub(r"(?<![\w&])([@#]\w+)", r'<a href="#">\1</a>', "".join(out))


def _post_html(p: Post, *, handle: str, alt: dict[str, str], cls: str) -> str:
    n = p.length
    media = ""
    if p.images:
        tiles = "".join(f'<img src="{html.escape(img)}" alt="{html.escape(alt.get(img, ""))}">'
                        for img in p.images)
        media = f'<div class="media n{len(p.images)}">{tiles}</div>'
        alts = " · ".join(f"ALT: {html.escape(alt.get(i, 'MISSING'))[:140]}" for i in p.images)
        media += f'<div class="alt">{alts}</div>'
    variant = ""
    if p.alt_hook:
        variant = (f'<div class="variant"><b>Alt hook · {x_length(p.alt_hook)}/280</b>\n'
                   f'{_linkify(p.alt_hook)}</div>')
    if p.caption:
        variant += f'<div class="variant"><b>Caption</b>\n{html.escape(p.caption)}</div>'
    label = f"{p.key}/" if cls != "solo" else html.escape(p.title or p.key)
    return f"""
<article class="post {cls}">
  <div class="avatar">r<b>b</b></div>
  <div>
    <div class="meta"><span class="name">Renball</span> <span class="handle">{html.escape(handle)} · {label}</span></div>
    <div class="body">{_linkify(p.text)}</div>
    {media}{variant}
    <div class="counts"><span class="{'ok' if n <= MAX_WEIGHTED else 'bad'}">{n}/280</span><span>{len(p.images)} image(s)</span></div>
  </div>
</article>"""


def render_preview(pkg: Package, *, handle: str = DEFAULT_HANDLE,
                   errors: Optional[list[str]] = None) -> str:
    thread = "".join(_post_html(p, handle=handle, alt=pkg.alt,
                                cls="last" if i == len(pkg.thread) - 1 else "")
                     for i, p in enumerate(pkg.thread))
    posts = "".join(_post_html(p, handle=handle, alt=pkg.alt, cls="solo") for p in pkg.posts)
    errs = ""
    if errors:
        errs = '<div class="errors"><b>Standard violations</b><ul>' + "".join(
            f"<li>{html.escape(e)}</li>" for e in errors) + "</ul></div>"
    longest = max((p.length for p in pkg.thread + pkg.posts), default=0)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>X preview — {html.escape(pkg.social_dir.parent.name)}</title><style>{PREVIEW_CSS}</style></head>
<body><main>
<header class="top"><h1>X preview · {html.escape(pkg.social_dir.parent.name)}</h1>
<p>{len(pkg.thread)}-post thread · {len(pkg.posts)} standalone posts · longest post {longest}/280 · local draft, not published</p></header>
{errs}
<div class="section">Thread</div>
{thread}
<div class="section">Standalone posts</div>
{posts}
</main></body></html>
"""


def build(project_dir: Path, *, handle: str = DEFAULT_HANDLE, verbose: bool = True) -> list[str]:
    pkg = Package.load(project_dir)
    errors = validate(pkg, verbose=verbose, handle=handle)
    out = pkg.social_dir / "preview.html"
    if pkg.social_dir.exists():
        out.write_text(render_preview(pkg, handle=handle, errors=errors), encoding="utf-8")
        if verbose:
            print(f"[OK] wrote {out.relative_to(Path(project_dir))}")
    for e in errors:
        print(f"  [FAIL] {e}")
    return errors


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Validate a project's X package and render preview.html")
    ap.add_argument("project")
    ap.add_argument("--handle", default=DEFAULT_HANDLE)
    a = ap.parse_args(argv)
    return 1 if build(Path(a.project), handle=a.handle) else 0


if __name__ == "__main__":
    sys.exit(main())
