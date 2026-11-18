"""HTML pages -> PNG slides in a hidden browser (Playwright for Python, the "slides" component).

    from slides.shoot import shoot, font_css, file_url
    shots = shoot(pages, out_dir, 1080, 1350, work_dir)

Each page is a whole HTML document. Mark what QA must check:
    data-role="words" | "label"      his words or one of the style's fixed labels (measured as the ink of the text)
    data-red="1"                     the element is the slide's one red
    data-mark="<what>"               a red shape that is not text (underline, box, brush)
    data-text="..."                  the text to record, when it differs from what the element shows
Returns, per page, {"file", "elements": [{"role"|"mark", "text", "box": [x, y, w, h], "lines", "color", "red"}],
"overflow": [texts that run off the slide]}.
"""
import re
from pathlib import Path

from studio_engine import paths
from studio_engine.errors import StudioError
from studio_engine.util import say

FONTS = [  # (family, file, weight range, style)
    ("Inter", "Inter.ttf", "100 900", "normal"),
    ("Cormorant Garamond", "CormorantGaramond.ttf", "300 700", "normal"),
    ("Cormorant Garamond", "CormorantGaramond-Italic.ttf", "300 700", "italic"),
    ("Raleway", "Raleway.ttf", "100 900", "normal"),
    ("Special Elite", "SpecialElite-Regular.ttf", "400", "normal"),
    ("Permanent Marker", "PermanentMarker-Regular.ttf", "400", "normal"),
]

MEASURE = """() => [...document.querySelectorAll('[data-role],[data-mark]')].map(e => {
  let r = e.getBoundingClientRect(), lines = 0;
  if (e.dataset.role) { const g = document.createRange(); g.selectNodeContents(e); const q = g.getBoundingClientRect();
                        if (q.width > 0) r = q;
                        lines = new Set([...g.getClientRects()].filter(x => x.width > 1).map(x => Math.round(x.bottom))).size; }
  const cs = getComputedStyle(e);
  return {role: e.dataset.role || null, mark: e.dataset.mark || null,
          text: e.dataset.text !== undefined ? e.dataset.text : (e.innerText || e.textContent || '').replace(/\\s+/g, ' ').trim(),
          box: [r.x, r.y, r.width, r.height], lines, color: cs.color, red: e.dataset.red === '1'};
})"""


def file_url(p):
    return Path(p).resolve().as_uri()


def font_css():
    """@font-face rules for every kit font, so pages use the same files the rest of the studio uses."""
    out = []
    for fam, f, wt, st in FONTS:
        p = paths.fonts_dir() / f
        if p.exists():
            out.append(f"@font-face{{font-family:'{fam}';src:url('{file_url(p)}');font-weight:{wt};font-style:{st}}}")
    return "\n".join(out)


def kit_head(css="", w=1080, h=1440):
    """The top of a page in his kit: the studio's fonts, kit.css (tokens, grain) and the page's own CSS."""
    kit = Path(__file__).resolve().parent / "kit.css"
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{font_css()}</style>'
            f'<link rel="stylesheet" href="{file_url(kit)}"><style>.slide{{width:{w}px;height:{h}px}}\n{css}</style>'
            '</head><body>')


def hex_color(css):
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", css or "")
    return "#%02X%02X%02X" % tuple(int(v) for v in m.groups()) if m else None


def _browser(p):
    try:
        return p.chromium.launch()
    except Exception as e:
        raise StudioError("The slide maker's browser is not installed. Run: studio install slides") from e


def shoot(pages, out_dir, w, h, work, names=None, settle_ms=150, transparent=()):
    """`transparent`: names of pages shot with a see-through background (layers to lay over video frames)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise StudioError("The slide maker is not installed. Run: studio install slides") from e
    out_dir, work = Path(out_dir), Path(work) / "html"
    out_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    names = names or [f"slide-{k:02d}" for k in range(1, len(pages) + 1)]
    shots = []
    with sync_playwright() as p:          # a few screenshots: light, so it does not wait for the heavy-job lock
        b = _browser(p)
        try:
            page = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            for k, (html, name) in enumerate(zip(pages, names), 1):
                say(f"Drawing slide {k} of {len(pages)}.")
                f = work / f"{name}.html"
                f.write_text(html)
                page.goto(file_url(f), wait_until="load")
                page.evaluate("() => document.fonts.ready")
                page.wait_for_timeout(settle_ms)
                broken = page.evaluate("() => [...document.images].filter(i => !i.complete || !i.naturalWidth)"
                                       ".map(i => i.getAttribute('src'))")
                if broken:
                    raise StudioError(f"Slide {k} has a picture that could not be loaded.")
                els = page.evaluate(MEASURE)
                png = out_dir / f"{name}.png"
                clear = name in transparent
                if clear:
                    page.evaluate("() => { document.documentElement.style.background = 'transparent';"
                                  " document.body.style.background = 'transparent'; }")
                page.screenshot(path=str(png), omit_background=clear)
                for e in els:
                    e["box"] = [round(v, 1) for v in e["box"]]
                    e["color"] = hex_color(e["color"])
                over = [e["text"] for e in els if e["role"] and (e["box"][0] < 0 or e["box"][1] < 0 or
                        e["box"][0] + e["box"][2] > w or e["box"][1] + e["box"][3] > h)]
                shots.append({"file": png, "name": name, "elements": els, "overflow": over})
        finally:
            b.close()
    return shots


def record(layout, shots, kinds=None):
    """One layout beat per slide (t0 = t1 = the slide number), with every measured text and red mark."""
    for k, s in enumerate(shots):
        bt = layout.beat((kinds or {}).get(k, "slide"), k, k, i=k, slide=s["file"].name)
        for e in s["elements"]:
            if e["role"]:
                layout.text(bt, e["text"], e["box"], role=e["role"], color=e["color"], red=e["red"] or None)
            elif e["mark"]:
                layout.mark(bt, e["mark"], e["box"], red=True, color=e["color"])
    return layout
