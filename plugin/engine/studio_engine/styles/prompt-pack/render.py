"""Prompt pack: a carousel of his prompts at 1080 x 1440 with a raked-sand garden cover (see SPEC.md).

Slide 1: the garden (one stone per prompt, tagged 01, 02 ...) under his title and the red brush.
Slides 2..: one prompt per slide: a crop of the garden lit on its own stone, the heading, a line of his, the prompt in
a copy box with one red underline on the phrase to change, and a tip.
Last slide: the dimmed garden, his closing line with a red brush, his call to save.
cover.mp4: the garden draws itself while his voice line plays (rings stone by stone, then the straight lines, the last
line landing on his last word). With no recording, the slides and a still cover are made.
"""
from html import escape as esc

import numpy as np

from studio_engine import heavy
from studio_engine.errors import StudioError
from studio_engine.render import Encoder, mux

KIND = "carousel"
W, H = 1080, 1440
FPS = 30
NAME = "Bernard Ablola"
LABELS = (["Prompt pack", "Copy", NAME, "Save this", "THEN", "MINE", "TRY", "TIP", "Follow @bernardablola", "→"]
          + [f"Nº {i:02d}" for i in range(1, 100)] + [f"{i:02d}" for i in range(1, 6)]
          + [f"PROMPT {i:02d} / {n:02d}" for n in range(1, 6) for i in range(1, n + 1)]
          + [f"Prompt {i:02d}" for i in range(1, 6)])
SS_FRAMES, SS_STILL = 1.5, 2.0
PUSH = 0.045                     # slow push-in over the cover clip
TAIL = 1.75                      # garden holds after the last rake line
RAKE_UNDER = 28                  # rake strokes under his voice (round one used 26; 28 keeps short words clear)

CSS = """
.cover { background: #0b0b0b center/cover no-repeat; }
.cover .shade { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,.28) 0%, rgba(0,0,0,0) 14%, rgba(0,0,0,0) 56%, rgba(0,0,0,.55) 74%, rgba(0,0,0,.78) 100%); }
.kick { position: absolute; left: 80px; top: 96px; font-family: var(--arch); font-size: 30px; letter-spacing: .14em; color: rgba(238,233,223,.82); text-transform: uppercase; }
.kick b { font-weight: 400; color: rgba(238,233,223,.5); margin-left: 18px; }
.tag { position: absolute; font-family: var(--arch); font-size: 30px; letter-spacing: .12em; color: rgba(238,233,223,.9); white-space: nowrap; }
.tag i { position: absolute; height: 1.5px; background: rgba(238,233,223,.55); transform-origin: 0 50%; }
.title { position: absolute; z-index: 2; left: 80px; right: 80px; top: 858px; font-family: var(--display); font-weight: 500; font-size: 132px; line-height: .96; letter-spacing: -.015em; color: #F3EEE4; }
.title em { font-style: italic; font-weight: 500; }
.brush { position: absolute; width: 400px; left: 418px; top: 1186px; opacity: .95; z-index: 0; }
.foot { position: absolute; left: 80px; right: 80px; bottom: 92px; display: flex; justify-content: space-between; align-items: center; font-family: var(--body); font-weight: 700; font-size: 24px; letter-spacing: .26em; color: rgba(238,233,223,.62); text-transform: uppercase; }
.foot .arr { font-family: var(--body); font-weight: 300; letter-spacing: 0; font-size: 44px; color: rgba(238,233,223,.8); }
.band { position: absolute; left: 0; top: 0; width: 1080px; height: 470px; background-size: cover; }
.band::after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(13,13,13,0) 55%, rgba(13,13,13,1) 100%); }
.num { position: absolute; left: 80px; top: 96px; font-family: var(--arch); font-size: 30px; letter-spacing: .14em; color: rgba(238,233,223,.82); }
.stack { position: absolute; left: 80px; right: 80px; top: 410px; display: flex; flex-direction: column; }
.h { position: relative; font-family: var(--display); font-weight: 500; font-size: 96px; line-height: 1; letter-spacing: -.01em; color: #F3EEE4; }
.h em { font-style: italic; }
.sub { position: relative; margin-top: 14px; font-family: var(--body); font-weight: 500; font-size: 34px; line-height: 1.35; color: rgba(238,233,223,.72); }
.box { position: relative; margin-top: 52px; border: 1.5px solid #3a3835; background: linear-gradient(180deg, #161514, #121110); border-radius: 4px; }
.box .bar { display: flex; justify-content: space-between; align-items: center; padding: 22px 34px 18px; border-bottom: 1.5px solid #2c2a28; font-family: var(--body); font-weight: 700; font-size: 22px; letter-spacing: .24em; text-transform: uppercase; color: rgba(238,233,223,.55); }
.box .bar span.copy { display: flex; align-items: center; gap: 12px; color: rgba(238,233,223,.8); }
.box .txt { padding: 30px 34px 36px; font-family: var(--arch); font-size: 36px; line-height: 1.42; color: #EEE9DF; }
.box .txt u { white-space: nowrap; text-decoration: none; background-image: linear-gradient(var(--red-footage), var(--red-footage)); background-size: 100% 4px; background-repeat: no-repeat; background-position: 0 96%; padding-bottom: 2px; }
.tip { position: relative; margin-top: 44px; font-family: var(--body); font-weight: 500; font-size: 32px; line-height: 1.35; color: rgba(238,233,223,.78); display: flex; gap: 18px; align-items: baseline; }
.tip b { font-family: var(--arch); font-weight: 400; font-size: 26px; letter-spacing: .14em; color: rgba(238,233,223,.5); white-space: nowrap; }
.pfoot { position: absolute; left: 80px; right: 80px; bottom: 80px; display: flex; justify-content: space-between; font-family: var(--body); font-weight: 700; font-size: 22px; letter-spacing: .26em; color: rgba(238,233,223,.42); text-transform: uppercase; }
.close { background: #0b0b0b center/cover no-repeat; }
.close .veil { position: absolute; inset: 0; background: radial-gradient(70% 45% at 50% 52%, rgba(10,10,10,.82) 0%, rgba(10,10,10,.55) 60%, rgba(10,10,10,.2) 100%); }
.close .line { position: absolute; z-index: 2; left: 80px; right: 80px; top: 530px; text-align: center; font-family: var(--display); font-weight: 500; font-size: 104px; line-height: 1.04; color: #F3EEE4; }
.close .line em { font-style: italic; }
.close .brush2 { position: absolute; z-index: 1; width: 300px; left: 520px; top: 608px; opacity: .92; }
.close .cta { position: absolute; left: 80px; right: 80px; bottom: 120px; text-align: center; font-family: var(--body); font-weight: 800; font-size: 30px; letter-spacing: .24em; line-height: 1.9; color: #F3EEE4; text-transform: uppercase; }
.close .cta span { color: rgba(238,233,223,.6); font-weight: 700; }
"""
COPY_ICON = ('<svg width="26" height="26" viewBox="0 0 26 26" fill="none" stroke="rgba(238,233,223,.8)" '
             'stroke-width="2"><rect x="8" y="8" width="15" height="15" rx="2"/><path d="M4 18V5a1 1 0 0 1 1-1h13"/></svg>')


def _garden():
    """garden.py beside this file (the studio loads style renderers by path, so no package import)."""
    import importlib.util
    import sys
    from pathlib import Path
    name = "studio_engine.styles.prompt_pack.garden"
    if name not in sys.modules:
        sp = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / "garden.py")
        m = importlib.util.module_from_spec(sp)
        sys.modules[name] = m
        sp.loader.exec_module(m)
    return sys.modules[name]


def with_italic(text, italic):
    """His text with line breaks (\\n) and the italic part (a phrase of it) in <em>."""
    out = esc(text)
    if italic and esc(italic) in out:
        i = out.rindex(esc(italic))
        out = out[:i] + f"<em>{esc(italic)}</em>" + out[i + len(esc(italic)):]
    return out.replace("\n", "<br>")


# The underlined phrase never breaks over two lines (CSS nowrap moves it whole to the next line). A phrase wider than
# the box shrinks the prompt's text a pixel at a time until it fits (down to MARK_MIN_PX).
MARK_MIN_PX = 24
FIT_MARK = ("<script>document.fonts.ready.then(()=>{const t=document.querySelector('.box .txt');"
            "const u=t&&t.querySelector('u');if(!u)return;const cs=getComputedStyle(t);"
            "const room=()=>t.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight);"
            "let fs=parseFloat(cs.fontSize);"
            f"while(u.getBoundingClientRect().width>room()+0.5&&fs>{MARK_MIN_PX}){{fs-=1;t.style.fontSize=fs+'px';}}"
            "});</script>")
MARK_ONE_LINE = 56           # px: one line of the phrase is 38 px tall at 36 px; two lines at the smallest size are 61


def with_mark(text, mark):
    out = esc(text)
    if mark:
        if esc(mark) not in out:
            raise StudioError(f'The phrase to underline, "{mark}", is not in its prompt word for word.')
        i = out.index(esc(mark))
        out = out[:i] + f'<u data-mark="underline" data-red="1">{esc(mark)}</u>' + out[i + len(esc(mark)):]
    return out


def tags_html(n):
    TAGS = _garden().TAGS
    out = []
    for k, ((x, y), (lx, ly, lw, la)) in enumerate(TAGS[n]):
        out.append(f'<div class="tag" data-role="label" data-text="{k + 1:02d}" style="left:{x}px; top:{y}px">{k + 1:02d}'
                   f'<i style="left:{lx}px; top:{ly}px; width:{lw}px; transform:rotate({la}deg)"></i></div>')
    return out


def cover_parts(spec, brush):
    num = spec.get("number", "01")
    return ['<div class="shade"></div>',
            f'<div class="kick"><span data-role="label">Prompt pack</span> <b data-role="label">Nº {esc(num)}</b></div>',
            f'<div class="title" data-role="words" data-text="{esc(spec["title"].replace(chr(10), " "))}">'
            f'{with_italic(spec["title"], spec.get("title_italic"))}</div>',
            f'<img class="brush" src="{brush}" data-mark="brush" data-red="1">',
            f'<div class="foot"><span data-role="label">{NAME}</span><span class="arr" data-role="label">&rarr;</span></div>']


def pages(spec, img):
    """img: {"cover", "close", "band-1".. "brush-a", "brush-b"} as file URLs."""
    from slides.shoot import kit_head
    head = kit_head(CSS, W, H)
    n = len(spec["prompts"])
    out, names, transparent = [], [], []
    parts = cover_parts(spec, img["brush-a"])
    out.append(head + f'<article class="slide cover grain" style="background-image:url(\'{img["cover"]}\')">'
               + parts[0] + parts[1] + "".join(tags_html(n)) + "".join(parts[2:]) + "</article></body></html>")
    names.append("slide-01")
    for k, p in enumerate(spec["prompts"], 1):
        tool = (f' &middot; <span data-role="words">{esc(p["tool"])}</span>') if p.get("tool") else ""
        tip = (f'<div class="tip"><b data-role="label">{esc(p.get("tip_label", "THEN"))}</b>'
               f'<span data-role="words">{esc(p["tip"])}</span></div>') if p.get("tip") else ""
        out.append(head + '<article class="slide grain">'
                   f'<div class="band" style="background-image:url(\'{img[f"band-{k}"]}\')"></div>'
                   f'<div class="num" data-role="label">PROMPT {k:02d} / {n:02d}</div>'
                   f'<div class="stack"><div class="h" data-role="words" data-text="{esc(p["heading"])}">'
                   f'{with_italic(p["heading"], p.get("heading_italic"))}</div>'
                   + (f'<div class="sub" data-role="words">{esc(p["sub"])}</div>' if p.get("sub") else "")
                   + '<div class="box"><div class="bar"><span><span data-role="label">Prompt '
                   f'{k:02d}</span>{tool}</span><span class="copy">{COPY_ICON}<span data-role="label">Copy</span></span></div>'
                   f'<div class="txt" data-role="words" data-text="{esc(p["text"])}">{with_mark(p["text"], p.get("mark"))}</div></div>'
                   + tip + '</div><div class="pfoot"><span data-role="label">' + NAME + '</span>'
                   '<span data-role="label">Save this</span></div></article>' + FIT_MARK + '</body></html>')
        names.append(f"slide-{k + 1:02d}")
    c = spec["close"]
    out.append(head + f'<article class="slide close grain" style="background-image:url(\'{img["close"]}\')">'
               '<div class="veil"></div>'
               + (f'<div class="num" data-role="words" style="color:rgba(238,233,223,.6)">{esc(c["kicker"])}</div>'
                  if c.get("kicker") else "")
               + f'<div class="line" data-role="words" data-text="{esc(c["line"].replace(chr(10), " "))}">'
               f'{with_italic(c["line"], c.get("italic"))}</div>'
               f'<img class="brush2" src="{img["brush-b"]}" data-mark="brush" data-red="1">'
               f'<div class="cta"><em data-role="words" style="font-style:normal">{esc(c["cta"])}</em><br>'
               '<span data-role="label">Follow @bernardablola</span></div></article></body></html>')
    names.append(f"slide-{n + 2:02d}")
    # layers for the moving cover: the title block, then one tag per stone (see-through)
    out.append(head + '<article class="slide layer">' + "".join(parts) + "</article></body></html>")
    names.append("L-title")
    for k, t in enumerate(tags_html(n), 1):
        out.append(head + f'<article class="slide layer">{t}</article></body></html>')
        names.append(f"L-t{k}")
    transparent = [x for x in names if x.startswith("L-")]
    return out, names, transparent


def bands(flat, stones):
    """One crop of the finished garden per prompt, lit on its own stone (470 px tall)."""
    out = []
    Hh, Ww = flat.shape[:2]
    bh = 470
    for s in stones:
        cx, cy = s["c"]
        y0 = int(np.clip(cy - bh * 0.52, 0, Hh - bh))
        c = flat[y0:y0 + bh].copy()
        yy, xx = np.mgrid[0:bh, 0:Ww].astype(np.float32)
        d = ((xx - cx) / 430) ** 2 + ((yy - (cy - y0)) / 300) ** 2
        out.append(np.clip(c * (0.35 + 0.95 * np.exp(-d))[..., None], 0, 1))
    return out


def schedule(ctx):
    """When the rings finish and when the last straight line lands, on the passage clock."""
    c = ctx.spec.get("cover") or {}
    words = ctx.words
    end = ctx.at(c["lines_until"], "cover.lines_until") if c.get("lines_until") else (words[-1]["t1"] if words else 0)
    rings = ctx.at(c["rings_until"], "cover.rings_until") if c.get("rings_until") else round(0.27 * end, 2)
    if not 0.6 < rings < end - 1.0:
        raise StudioError("cover.rings_until must fall well inside the voice line (the rake needs time after it).")
    return (0.15, rings), (rings, end)


def save_png(rgb01_bgr, path):
    from PIL import Image
    Image.fromarray((np.clip(rgb01_bgr[..., ::-1], 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def load_rgba(p):
    from PIL import Image
    a = np.asarray(Image.open(p).convert("RGBA")).astype(np.float32) / 255
    return a[..., :3], a[..., 3:4]


def validate(spec, words, duration):
    n = len(spec["prompts"])
    if not 1 <= n <= 5:
        raise StudioError("A prompt pack holds one to five prompts.")


def render(ctx):
    from slides.shoot import file_url, record, shoot
    from studio_engine import brand
    G = _garden()
    spec = ctx.spec
    ctx.w, ctx.h = W, H
    ctx.layout.data["format"].update(w=W, h=H, fps=FPS)
    n = len(spec["prompts"])
    stones = G.stones_for(n)
    has_voice = bool(ctx.passage.get("voice"))
    t_rings, t_lines = schedule(ctx) if has_voice else ((0.15, 3.55), (3.55, 11.75))
    ctx.say("Raking the garden.")
    with heavy.lock("prompt-pack garden still"):
        g2 = G.Garden(stones, t_rings, t_lines, SS_STILL)
        flat = g2.frame(99.0, 1.0)
        del g2
    final = G.film_grain(flat, 1)
    img = {}
    for name, arr in [("cover", final), ("close", flat * 0.55)] + [(f"band-{k}", b) for k, b in
                                                                 enumerate(bands(flat, stones), 1)]:
        p = ctx.work / f"{name}.png"
        save_png(arr, p)
        img[name] = file_url(p)
    img["brush-a"], img["brush-b"] = file_url(brand.brush("red-a")), file_url(brand.brush("red-b"))
    html_pages, names, clear = pages(spec, img)
    out = ctx.out / "slides"
    layers = ctx.work / "layers"
    shots = shoot(html_pages, ctx.work / "shots", W, H, ctx.work, names, transparent=clear)
    out.mkdir(parents=True, exist_ok=True)
    slides = []
    for s in shots:
        if s["name"].startswith("L-"):
            layers.mkdir(exist_ok=True)
            s["file"].replace(layers / s["file"].name)
        else:
            s["file"] = s["file"].replace(out / s["file"].name)
            slides.append(s)
    over = [t for s in slides for t in s["overflow"]]
    if over or any(e["box"][1] + e["box"][3] > H - 60 for s in slides for e in s["elements"] if e["role"]):
        raise StudioError("A prompt is too long for its slide. Trim the prompt, its line or its tip.")
    kinds = {0: "cover", len(slides) - 1: "close"}
    record(ctx.layout, slides, {k: kinds.get(k, "prompt") for k in range(len(slides))})
    if has_voice:
        cover_clip(ctx, stones, t_rings, t_lines, layers, n, out)
    else:
        ctx.say("No voice line was picked, so the cover is a still picture (slide 1).")
    ctx.layout.save(ctx.out / "layout.json")
    return {"output": "slides"}


def cover_clip(ctx, stones, t_rings, t_lines, layers, n, out):
    G = _garden()
    from studio_engine import sound
    dur = round(max(ctx.duration, t_lines[1]) + TAIL, 2)
    title = load_rgba(layers / "L-title.png")
    per_stone = (t_rings[1] - t_rings[0]) / n
    tags = [(load_rgba(layers / f"L-t{k}.png"), t_rings[0] + k * per_stone) for k in range(1, n + 1)]
    nf = int(round(dur * FPS))
    enc = Encoder(ctx.work / "cover-picture.mp4", W, H, FPS, crf=16, tune="grain")
    with heavy.lock("prompt-pack cover frames"):
        g = G.Garden(stones, t_rings, t_lines, SS_FRAMES)
        for i in range(nf):
            t = i / FPS
            u = t / dur
            frame = G.film_grain(g.frame(t, 1.0 + PUSH * (u * u * (3 - 2 * u))), 1000 + i)[..., ::-1]
            frame = frame * (1 - title[1]) + title[0] * title[1]
            for (rgb, al), t0 in tags:
                k = float(np.clip((t - t0) / 0.45, 0, 1))
                k = k * k * (3 - 2 * k)
                if k > 0:
                    frame = frame * (1 - al * k) + rgb * al * k
            enc.write((np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8))
            if i % (FPS * 2) == 0:
                ctx.say(f"Drawing the moving cover: {int(100 * i / nf)} percent")
        enc.close()
    # sound: a struck bowl at the start, a lower bowl on his last word, a low drone, one rake stroke per stroke
    N = int(dur * sound.SR)
    bed = np.zeros((N, 2), np.float64)
    sound.place(bed, sound.drone_bed(dur), 0.0, gain_db=-6.0)
    sound.place(bed, sound.bowl(9.0, 196.0), 0.0)
    sound.place(bed, sound.bowl(max(1.5, dur - t_lines[1]), 146.83), t_lines[1], gain_db=-2.0)
    sfx = []
    per_stroke = (t_rings[1] - t_rings[0]) / (n * G.RING_STROKES)
    for k in range(n * G.RING_STROKES):
        sfx.append({"array": sound.sand(per_stroke * 1.02, 100 + k), "t": t_rings[0] + k * per_stroke,
                    "under_db": RAKE_UNDER})
    nb = int(np.ceil((G.H0 + 2 * G.MARGIN) / G.BAND))
    per_band = (t_lines[1] - t_lines[0]) / nb
    for b in range(nb):
        sfx.append({"array": sound.sand(per_band * 1.04, 500 + b), "t": t_lines[0] + b * per_band, "under_db": RAKE_UNDER})
    ctx.say("Mixing his voice with the garden sound.")
    sound.mix(ctx.voice(), dur, ctx.out / "mix.wav", bed=bed, sfx=sfx, work=ctx.work)
    mux(ctx.work / "cover-picture.mp4", ctx.out / "mix.wav", out / "cover.mp4")


def check_mark_one_line(layout):
    """Each red underline sits on one line of the prompt (a phrase that wraps draws two red pieces)."""
    bad = [{"slide": b.get("slide"), "box": m["box"]} for b in layout["beats"] for m in b["marks"]
           if m.get("what") == "underline" and m["box"][3] > MARK_ONE_LINE]
    return {"pass": not bad, "wrapped": bad}


def qa_extra(project, vdir, layout):
    from slides import captions
    files = sorted((vdir / "slides").glob("*.png"))
    return {"no_old_captions": captions.check(project, vdir, layout, files),
            "underline_one_line": check_mark_one_line(layout)}
