"""Field notes: his build diary on cream paper at 1080 x 1440 (see SPEC.md).

Typewritten entries (Special Elite), taped photo prints of his screen and of him, and a red Permanent Marker note:
at most three in a carousel, never two on a slide. Slide kinds: cover (title, a big print, a marker note and an arrow),
step (step label, title, typed lines, an optional short list, a print, a marker note), close (a wide print, his closing
line with a red underline, follow line). Every position has a default per kind; a spec may set them by hand.
"""
from html import escape as esc

from studio_engine.errors import StudioError

KIND = "carousel"
W, H = 1080, 1440
HANDLE = "@bernardablola"
MARKER_MAX = 3
LABELS = (["FIELD NOTES", HANDLE, "swipe →", "→", f"Follow {HANDLE}"]
          + [f"{i:02d} / {n:02d}" for n in range(2, 13) for i in range(1, n + 1)] + [f"STEP {i}" for i in range(1, 13)])

CSS = """
:root { --paper:#F1EBDF; --ink:#1c1a17; --red:#B91C1C; }
.s { width:1080px; height:1440px; position:relative; overflow:hidden; background:var(--paper);
     color:var(--ink); font-family:"Special Elite", monospace; }
.s::before { content:""; position:absolute; inset:0; z-index:1; pointer-events:none; mix-blend-mode:multiply;
  background-image:
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='700' height='700'><filter id='f'><feTurbulence type='fractalNoise' baseFrequency='.011 .45' numOctaves='2' seed='7'/><feColorMatrix values='0 0 0 0 .45  0 0 0 0 .38  0 0 0 0 .28  0 0 0 .22 0'/></filter><rect width='100%' height='100%' filter='url(%23f)'/></svg>"),
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='500' height='500'><filter id='g'><feTurbulence type='fractalNoise' baseFrequency='.6' numOctaves='2' seed='3'/><feColorMatrix values='0 0 0 0 .4  0 0 0 0 .35  0 0 0 0 .3  0 0 0 .12 0'/></filter><rect width='100%' height='100%' filter='url(%23g)'/></svg>"),
    radial-gradient(120% 95% at 45% 40%, transparent 50%, rgba(90,66,36,.22) 100%); }
.z { position:absolute; z-index:5; }
.head { left:80px; right:80px; top:70px; display:flex; justify-content:space-between; font-size:26px; letter-spacing:.2em; color:#6f675b; }
.rule { left:80px; right:80px; top:116px; height:2px; background:#1c1a17; opacity:.75; }
.rule2 { left:80px; right:80px; top:122px; height:1px; background:#1c1a17; opacity:.5; }
.typed { font-size:40px; line-height:1.48; text-shadow: 0 0 .6px rgba(28,26,23,.6); }
.typed .dim { color:#5d574e; }
.step { font-size:30px; letter-spacing:.2em; color:#6f675b; }
.title { font-size:74px; line-height:1.18; letter-spacing:-.01em; text-shadow:0 0 .8px rgba(28,26,23,.7); }
.print { position:absolute; z-index:4; background:#fbf9f4; padding:20px 20px 64px; box-shadow: 0 2px 2px rgba(0,0,0,.18), 0 18px 40px rgba(40,28,10,.28); }
.print img { display:block; width:100%; height:100%; object-fit:cover; filter:contrast(1.04) saturate(.9); }
.print .cap { position:absolute; left:22px; bottom:18px; font-size:22px; color:#6f675b; letter-spacing:.05em; }
.tape { position:absolute; z-index:6; width:170px; height:46px; background:rgba(226,214,186,.78);
        box-shadow:0 1px 2px rgba(0,0,0,.08);
        clip-path: polygon(2% 8%, 8% 0, 15% 6%, 24% 0, 33% 7%, 44% 1%, 55% 6%, 66% 0, 78% 7%, 88% 1%, 98% 6%, 100% 92%, 92% 100%, 82% 94%, 70% 100%, 58% 93%, 46% 100%, 34% 94%, 22% 100%, 10% 93%, 0 98%); }
.marker { position:absolute; z-index:7; font-family:"Permanent Marker"; color:var(--red); font-size:52px; line-height:1.05; }
.foot { left:80px; right:80px; bottom:64px; display:flex; justify-content:space-between; font-size:24px; color:#7a7266; letter-spacing:.06em; }
"""
ARROW = ('<svg data-mark="arrow" data-red="1" style="position:absolute; left:{x}px; top:calc(100% + {y}px)" '
         'width="300" height="200" viewBox="0 0 300 200">'
         '<path d="M20 10 C 40 120, 140 170, 250 150" fill="none" stroke="#B91C1C" stroke-width="7" stroke-linecap="round"/>'
         '<path d="M222 122 L 254 150 L 216 172" fill="none" stroke="#B91C1C" stroke-width="7" stroke-linecap="round" '
         'stroke-linejoin="round"/></svg>')

# the closing underline: a hand-drawn stroke 8 px past each end of the underlined words. Drawn at 340 px, then
# redrawn once the fonts are in to the width the browser measures for the words (round one's 340 px suited "you
# direct." at 62 px; a fixed width ran short under a long phrase and past a short one)
UNDERLINE = ('<svg id="ul" data-mark="underline" data-red="1" style="position:absolute; left:-8px; bottom:-18px" '
             'width="{w}" height="30" viewBox="0 0 {w} 30"><path d="M4 18 C 90 6, 200 26, 334 10" fill="none" '
             'stroke="#B91C1C" stroke-width="8" stroke-linecap="round"/></svg>')
# the same curve stretched to the measured width w: M4 18 C (90/340 w) 6, (200/340 w) 26, (w - 6) 10
UNDERLINE_FIT = ("<script>document.fonts.ready.then(()=>{const s=document.getElementById('ulw'),"
                 "u=document.getElementById('ul');if(!s||!u)return;const w=Math.round(s.getBoundingClientRect().width+16);"
                 "u.setAttribute('width',w);u.setAttribute('viewBox','0 0 '+w+' 30');"
                 "u.firstChild.setAttribute('d','M4 18 C '+(w*90/340).toFixed(1)+' 6, '+(w*200/340).toFixed(1)+' 26, '"
                 "+(w-6).toFixed(1)+' 10');});</script>")

# defaults per kind (the round-one positions): print box [x, y, w, h] and turn, tapes [x, y, turn], marker [x, y, w]
DEFAULTS = {
    "cover": {"print": [420, 520, 520, 770, 3.2], "tapes": [[600, 494, -4]], "marker": [92, 760, 330, 52, -5],
              "arrow": [58, 26]},          # the arrow hangs from the note: left offset, gap under it
    "step": {"print": [90, 880, 620, 400, -2.4], "tapes": [[104, 862, -14], [580, 850, 9]],
             "marker": [736, 1000, 260, 44, -6], "typed_top": 430, "title_size": 66},
    "step-right": {"print": [372, 860, 640, 420, 2.6], "tapes": [[590, 836, -3]], "marker": [80, 960, 250, 46, -5]},
    "step-list": {"print": [610, 620, 400, 560, 3.4], "tapes": [[730, 596, 4]], "marker": [84, 1010, 520, 50, -3]},
    "close": {"print": [80, 190, 920, 560, -1.4], "tapes": [[150, 170, -8], [790, 166, 7]], "title_top": 860,
              "title_size": 62},
}


def lines_html(text):
    return "<br>".join(esc(x) for x in text.split("\n"))


def page(slide, k, n, img_url, kit_head):
    kind = slide["kind"]
    lay = slide.get("layout") or ("step" if kind == "step" else kind)
    d = DEFAULTS[lay if lay in DEFAULTS else kind]
    o = [kit_head(CSS, W, H) + '<section class="s">',
         f'<div class="z head"><span data-role="label">FIELD NOTES</span><span data-role="label">{k:02d} / {n:02d}</span></div>',
         '<div class="z rule"></div><div class="z rule2"></div>']
    pr = slide.get("print")
    if pr:
        x, y, w, h, rot = pr.get("box", d["print"][:4]) + [pr.get("rotate", d["print"][4])]
        cap = (f'<div class="cap" data-role="words">{esc(pr["caption"])}</div>') if pr.get("caption") else ""
        o.append(f'<div class="print" style="left:{x}px; top:{y}px; width:{w}px; height:{h}px; transform:rotate({rot}deg)">'
                 f'<img src="{img_url}">{cap}</div>')
        for tx, ty, tr in pr.get("tapes", d["tapes"]):
            o.append(f'<div class="tape" style="left:{tx}px; top:{ty}px; transform:rotate({tr}deg)"></div>')
    if kind == "cover":
        o.append(f'<div class="z title" data-role="words" data-text="{esc(slide["title"].replace(chr(10), " "))}" '
                 f'style="left:80px; right:80px; top:176px">{lines_html(slide["title"])}</div>')
    elif kind == "step":
        top = slide.get("typed_top", d.get("typed_top", DEFAULTS["step"]["typed_top"]))
        if slide.get("step") is not None:          # optional: a step slide without a number has no label
            o.append(f'<div class="z step" data-role="label" style="left:80px; top:170px">STEP {slide["step"]}</div>')
        o.append(f'<div class="z title" id="ttl" data-role="words" style="left:80px; right:80px; top:216px; font-size:'
                 f'{slide.get("title_size", 66)}px">{esc(slide["title"])}</div>')
        typed = "<br>".join(f'<span data-role="words" data-text="{esc(t.replace(chr(10), " "))}">{lines_html(t)}</span>'
                            for t in slide.get("typed", []))
        dim = "<br>".join(f'<span class="dim" data-role="words" data-text="{esc(t.replace(chr(10), " "))}">'
                          f'{lines_html(t)}</span>' for t in slide.get("dim", []))
        o.append(f'<div class="z typed" id="typ" style="left:80px; right:80px; top:{top}px">{typed}{"<br>" if typed and dim else ""}{dim}</div>')
        # a title that wraps to two lines pushes the typed entry down, never under it
        o.append("<script>document.fonts.ready.then(()=>{const t=document.getElementById('ttl'),y=document.getElementById('typ');"
                 "const gap=t.getBoundingClientRect().bottom+34-y.getBoundingClientRect().top;"
                 "if(gap>0)y.style.top=(parseFloat(y.style.top)+gap)+'px';});</script>")
        if slide.get("list"):
            lx, ly, lw = slide.get("list_box", [80, 640, 520])
            items = "<br>".join(f'&mdash; <span data-role="words">{esc(t)}</span>' for t in slide["list"])
            o.append(f'<div class="z typed" style="left:{lx}px; width:{lw}px; top:{ly}px; font-size:34px; line-height:1.5">'
                     f'<span class="step" data-role="words" style="font-size:26px">{esc(slide.get("list_title", ""))}</span><br>{items}</div>')
    else:
        top = slide.get("title_top", d["title_top"])
        title = esc(slide["title"]).replace("\n", "<br>")
        ul = slide.get("underline")
        if ul:
            if esc(ul) not in title:
                raise StudioError(f'The words to underline, "{ul}", are not in the closing line word for word.')
            i = title.rindex(esc(ul))
            title = (title[:i] + '<span id="ulw" style="position:relative; white-space:nowrap">' + esc(ul)
                     + UNDERLINE.format(w=340) + '</span>' + title[i + len(esc(ul)):])
            o.append(UNDERLINE_FIT)
        o.append(f'<div class="z title" data-role="words" data-text="{esc(slide["title"].replace(chr(10), " "))}" '
                 f'style="left:80px; right:80px; top:{top}px; font-size:{slide.get("title_size", d["title_size"])}px; '
                 f'line-height:1.25">{title}</div>')
        o.append(f'<div class="z typed" data-role="label" style="left:80px; top:{top + 350}px; font-size:34px">Follow {HANDLE}</div>')
    m = slide.get("marker")
    if m:
        mx, my, mw, ms, mr = (m.get("box", d["marker"][:3]) + [m.get("size", d["marker"][3]), m.get("rotate", d["marker"][4])])
        arrow = ""
        if kind == "cover" and slide.get("arrow", True):
            ax, ay = slide.get("arrow_at", d["arrow"])
            arrow = ARROW.format(x=ax, y=ay)
        o.append(f'<div class="marker" data-red="1" style="left:{mx}px; top:{my}px; width:{mw}px; '
                 f'font-size:{ms}px; transform:rotate({mr}deg)"><span data-role="words" data-red="1">{esc(m["text"])}</span>'
                 f'{arrow}</div>')
    if kind == "close":
        o.append(f'<div class="z foot"><span data-role="words">{esc(slide.get("foot", ""))}</span><span></span></div>')
    else:
        o.append(f'<div class="z foot"><span data-role="label">{HANDLE}</span><span data-role="label">'
                 f'{"swipe &rarr;" if kind == "cover" else "&rarr;"}</span></div>')
    o.append("</section></body></html>")
    return "".join(o)


def validate(spec, words, duration):
    marks = [k for k, s in enumerate(spec["slides"]) if s.get("marker")]
    if len(marks) > MARKER_MAX:
        raise StudioError(f"The red marker notes are on {len(marks)} slides; keep them to {MARKER_MAX} at most, "
                          "so they still stand out.")


def render(ctx):
    from slides import pictures
    from slides.shoot import file_url, kit_head, record, shoot
    spec = ctx.spec
    ctx.layout.data["format"].update(w=W, h=H)
    n = len(spec["slides"])
    pages, crops = [], {}
    for k, s in enumerate(spec["slides"], 1):
        url = ""
        pr = s.get("print")
        if pr:
            d = DEFAULTS[s.get("layout") or s["kind"]]
            bw, bh = pr.get("box", d["print"][:4])[2:]
            iw, ih = bw - 40, bh - 84                      # the picture inside the white border
            pic, box = pictures.picture(ctx.project, pr["photo"], iw * 2, ih * 2)
            f = ctx.work / f"print-{k:02d}.jpg"
            pic.convert("RGB").save(f, quality=92)
            url = file_url(f)
            x, y = pr.get("box", d["print"][:4])[:2]
            crops[k] = ([x + 20, y + 20, iw, ih], pr["photo"], box)
        pages.append(page(s, k, n, url, kit_head))
    ctx.say(f"Drawing {n} slides.")
    shots = shoot(pages, ctx.out / "slides", W, H, ctx.work)
    over = [t for s in shots for t in s["overflow"]]
    if over:
        raise StudioError(f'This text runs off its slide: "{over[0]}". Make it shorter.')
    for s in shots:
        for e in s["elements"]:
            if e["role"] and e["box"][1] + e["box"][3] > H - 100 and "foot" not in (e["text"] or ""):
                if e["box"][1] < H - 110:
                    raise StudioError(f'This text runs into the bottom of its slide: "{e["text"][:60]}". Make it shorter.')
    record(ctx.layout, shots, {k: spec["slides"][k]["kind"] for k in range(n)})
    for k, (box, ph, crop) in crops.items():
        pictures.note(ctx.layout, f"slide-{k:02d}.png", box, ph, crop)
    ctx.layout.save(ctx.out / "layout.json")
    return {"output": "slides"}


def qa_extra(project, vdir, layout):
    from slides import captions
    files = sorted((vdir / "slides").glob("*.png"))
    hands = sum(1 for b in layout["beats"] for t in b["texts"] if t.get("red") and t["role"] == "words")
    per_slide = [b["slide"] for b in layout["beats"] if sum(1 for t in b["texts"] if t.get("red")) > 1]
    return {"no_old_captions": captions.check(project, vdir, layout, files),
            "marker_notes": {"pass": hands <= MARKER_MAX and not per_slide, "count": hands, "max": MARKER_MAX,
                             "slides_with_two": per_slide}}
