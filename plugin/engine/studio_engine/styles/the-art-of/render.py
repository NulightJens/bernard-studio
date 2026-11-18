"""The art of: an object-grid carousel at 1080 x 1350 (see SPEC.md).

Slide 1: "The art of" + his topic, ringed by five objects, with two cutouts of him and a plus between them.
Slides 2 to 9: one idea per slide, its name in the centre, six objects around it, each with a short line of his.
Last slide: a full-bleed photo of him with "Welcome to my account." and his closing lines.
Layout measured 1:1 from the reference format: grey #E5E5E5, Inter, the six slot positions, the cover boxes.
"""
import html
import json

import numpy as np

from studio_engine import paths
from studio_engine.errors import StudioError

KIND = "carousel"
LABELS = ["The art of", "Welcome to my account."]
W, H = 1080, 1350
BG = "#e5e5e5"

# section slots measured from the reference (centre x, band top, band bottom, max w, max h, caption width)
SLOTS = [(299, 18, 470, 330, 318, 340), (779, 18, 470, 330, 318, 340),
         (185, 500, 862, 250, 262, 330), (893, 500, 862, 250, 262, 330),
         (299, 885, 1336, 330, 318, 340), (779, 885, 1336, 330, 318, 340)]
# cover object boxes (x0, y0, x1, y1): top left, top centre, top right, middle left, middle right
COVER = [(31, 119, 367, 401), (446, 64, 633, 436), (742, 110, 1026, 430), (13, 500, 236, 740), (834, 520, 1074, 730)]
# default cutout placement: x0, width; the picture bleeds off the bottom (its bottom edge at y 1360)
POSE_SLOT = {"left": (-65, 517), "right": (572, 509)}
POSE_BOTTOM = 1360
CAPTION_LINES = 4      # the round-one carousel has one four-line caption; more would crowd the next row
SIDE = 80              # carousel side margin; the reference ran captions and the last-slide text to 70 px
LAST_X = 80


def _head():
    from slides.shoot import font_css
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{font_css()}
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:{BG}}}
body{{position:relative;font-family:Inter;font-variation-settings:'opsz' 14;color:#000;-webkit-font-smoothing:antialiased}}
.slot{{position:absolute;display:flex;flex-direction:column;align-items:center;justify-content:center}}
.ob{{position:relative;flex:none}} .ob img{{position:absolute;display:block}}
.cap{{margin-top:23px;font-weight:600;font-size:34px;line-height:38px;text-align:center;letter-spacing:-0.1px}}
.word{{position:absolute;left:0;width:{W}px;text-align:center;font-weight:800;line-height:.98;letter-spacing:-0.5px}}
.abs{{position:absolute;display:block}}
</style></head><body>"""


# ----------------------------------------------------------------------------------------------- library
def _tags():
    f = paths.objects_dir() / "tags.json"
    return json.loads(f.read_text())["objects"] if f.exists() else {}


def object_file(project, oid):
    """An object picture: the project's own objects/ folder first (new ones made for him), then the library."""
    for p in (project.path("objects", f"{oid}.png"), paths.objects_dir() / f"{oid}.png"):
        if p.exists():
            return p
    raise StudioError(f'There is no object called "{oid}". The objects are listed in the library\'s tags.json.')


def pose_file(pid):
    for p in (paths.user_poses() / f"{pid}.png", paths.poses_dir() / f"{pid}.png"):
        if p.exists():
            return p
    raise StudioError(f'There is no pose called "{pid}". Poses are in the library or added with studio matte-photo.')


_ink = {}


def ink_box(p, oid):
    """The object's own box inside its picture (left, top, right, bottom) and how much of that box it fills."""
    if p not in _ink:
        from PIL import Image
        a = np.asarray(Image.open(p).convert("RGBA"))[..., 3]
        box = _tags().get(oid, {}).get("ink_box")
        if not box:
            ys, xs = np.where(a > 8)
            box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else [0, 0, a.shape[1] - 1, a.shape[0] - 1]
        x0, y0, x1, y1 = box
        _ink[p] = (box, a.shape[1], a.shape[0], float((a[y0:y1 + 1, x0:x1 + 1] > 128).mean()))
    return _ink[p]


def obj_html(project, oid, maxw, maxh, weight=True):
    from slides.shoot import file_url
    p = object_file(project, oid)
    (x0, y0, x1, y1), Wp, Hp, fill = ink_box(p, oid)
    ow, oh = x1 - x0 + 1, y1 - y0 + 1
    # visual weight: dense, compact objects (an apple, a box) shrink up to 20 percent; sparse ones keep the full box
    wt = min(1.0, max(0.8, (0.42 / max(fill, 1e-3)) ** 0.3)) if weight else 1.0
    s = min(maxw / ow, maxh / oh) * wt
    return (f'<div class="ob" style="width:{ow*s:.1f}px;height:{oh*s:.1f}px">'
            f'<img src="{file_url(p)}" style="left:{-x0*s:.1f}px;top:{-y0*s:.1f}px;width:{Wp*s:.1f}px;height:{Hp*s:.1f}px">'
            '</div>')


# ----------------------------------------------------------------------------------------------- pages
def section_page(project, sec):
    out = [_head()]
    for (cx, t, b, mw, mh, cw), it in zip(SLOTS, sec["items"]):
        out.append(f'<div class="slot" style="left:{cx-cw/2-20}px;width:{cw+40}px;top:{t}px;height:{b-t}px">'
                   f'{obj_html(project, it["object"], mw, mh)}'
                   f'<div class="cap" data-role="words" style="width:{cw}px">{html.escape(it["text"])}</div></div>')
    words = sec["name"].split(" ")
    lines = [sec["name"]] if len(words) == 1 else [" ".join(words[:len(words) // 2]), " ".join(words[len(words) // 2:])]
    out.append(f'<div class="word" id="w" data-role="words" data-text="{html.escape(sec["name"])}">'
               f'{"<br>".join(html.escape(x) for x in lines)}</div>')
    # the section word: ExtraBold caps sized so its widest line is about 290 px, at most 86 px, centred on y 682
    out.append("""<script>
const w=document.getElementById('w'); document.fonts.ready.then(()=>{
 const sp=document.createElement('span'); sp.style.cssText='font-weight:800;font-size:100px;letter-spacing:-0.5px;white-space:nowrap;position:absolute;visibility:hidden';
 document.body.appendChild(sp); let mx=0; for(const l of w.innerHTML.split('<br>')){sp.innerHTML=l; mx=Math.max(mx, sp.getBoundingClientRect().width);}
 sp.remove(); const fs=Math.min(86, 100*290/mx); w.style.fontSize=fs+'px';
 const h=w.getBoundingClientRect().height; w.style.top=(682-h/2)+'px';
 // a caption that would run into the 80 px side margin moves inward just enough (short ones stay centred)
 for (const c of document.querySelectorAll('.cap')) { const g=document.createRange(); g.selectNodeContents(c);
   const r=g.getBoundingClientRect(); const dx = r.left < SIDE ? SIDE - r.left : (r.right > WIDTH - SIDE ? WIDTH - SIDE - r.right : 0);
   if (dx) c.style.transform='translateX('+dx+'px)'; } });
</script></body></html>""".replace("SIDE", str(SIDE)).replace("WIDTH", str(W)))
    return "".join(out)


def pose_box(side, cut):
    if cut.get("box"):
        return cut["box"]
    from PIL import Image
    pw, ph = Image.open(pose_file(cut["pose"])).size
    x0, w = POSE_SLOT[side]
    h = w * ph / pw
    return [x0, round(POSE_BOTTOM - h), x0 + w, POSE_BOTTOM]


def cover_page(project, topic, c):
    from slides.shoot import file_url
    out = [_head()]
    for oid, (x0, y0, x1, y1) in zip(c["objects"], COVER):
        bw, bh = x1 - x0, y1 - y0
        out.append(f'<div class="slot" style="left:{x0}px;top:{y0}px;width:{bw}px;height:{bh}px">'
                   f'{obj_html(project, oid, bw, bh, weight=False)}</div>')
    out.append('<div data-role="label" style="position:absolute;left:0;width:1080px;top:524px;text-align:center;'
               'font-weight:800;font-size:104px;line-height:104px;letter-spacing:-1px">The art of</div>')
    out.append('<div data-role="words" style="position:absolute;left:0;width:1080px;top:634px;text-align:center;'
               f'font-weight:400;font-size:65px;line-height:70px">{html.escape(topic)}</div>')
    for side in ("left", "right"):
        cut = c.get(side)
        if not cut:
            continue
        x0, y0, x1, y1 = pose_box(side, cut)
        out.append(f'<img class="abs" src="{file_url(pose_file(cut["pose"]))}" style="left:{x0}px;top:{y0}px;'
                   f'width:{x1-x0}px;height:{y1-y0}px;filter:drop-shadow(0 10px 14px rgba(0,0,0,.09))">')
    px, py = c.get("plus", [489, 1085])
    out.append(f'<div class="abs" style="left:{px-44}px;top:{py-11}px;width:89px;height:23px;background:#000"></div>'
               f'<div class="abs" style="left:{px-11}px;top:{py-44}px;width:23px;height:89px;background:#000"></div>')
    out.append("</body></html>")
    return "".join(out)


def last_page(photo_url, L):
    lines = "<br>".join(html.escape(x) for x in L.get("line", "").split("\n"))
    return (_head() + f'<img class="abs" src="{photo_url}" style="left:0;top:0;width:1080px;height:1350px;object-fit:cover">'
            '<div class="abs" style="left:0;top:0;width:1080px;height:520px;background:linear-gradient(rgba(0,0,0,.28),rgba(0,0,0,0))"></div>'
            f'<div class="abs" style="left:{LAST_X}px;top:100px;color:#fff;text-shadow:0 2px 14px rgba(0,0,0,.35)">'
            '<div style="font-weight:700;font-size:52px;line-height:58px;letter-spacing:-.3px">'
            f'<span data-role="label">Welcome to my account.</span><br><span data-role="words">{html.escape(L["headline"])}</span></div>'
            + (f'<div data-role="words" style="font-weight:500;font-size:33px;line-height:37px;margin-top:14px">{lines}</div>'
               if lines else "")
            + "</div></body></html>")


# ----------------------------------------------------------------------------------------------- the style
def validate(spec, words, duration):
    for k, s in enumerate(spec["sections"]):
        if len(s["items"]) != 6:
            raise StudioError(f"sections[{k}] needs exactly six objects with a line each (it has {len(s['items'])}).")


def render(ctx):
    from slides import pictures
    from slides.shoot import file_url, record, shoot
    spec, project = ctx.spec, ctx.project
    pages = [cover_page(project, spec["topic"], spec["cover"])]
    pages += [section_page(project, s) for s in spec["sections"]]
    L = spec["last"]
    img, box = pictures.picture(project, L["photo"], W, H)
    ph = ctx.work / "last-photo.png"
    img.save(ph)
    pages.append(last_page(file_url(ph), L))
    ctx.say(f"Drawing {len(pages)} slides.")
    slides_dir = ctx.out / "slides"
    shots = shoot(pages, slides_dir, W, H, ctx.work)
    long, names = [], {s["name"] for s in spec["sections"]}
    for s in shots:
        for e in s["elements"]:
            if e["role"] == "words" and e["text"] not in names and e["lines"] > CAPTION_LINES:
                long.append(e["text"])
        long += [t for t in s["overflow"]]
    for e in shots[0]["elements"] + shots[-1]["elements"]:
        if e["role"] and e["box"][0] + e["box"][2] > W - 40:
            long.append(e["text"])
    if long:
        raise StudioError(f'This line is too long for its place on the slide: "{long[0]}". Trim it to fewer words.')
    kinds = {0: "cover", len(shots) - 1: "last"}
    record(ctx.layout, shots, {k: kinds.get(k, "section") for k in range(len(shots))})
    pictures.note(ctx.layout, shots[-1]["file"].name, [0, 0, W, H], L["photo"], box)
    ctx.layout.save(ctx.out / "layout.json")
    return {"output": "slides"}


def qa_extra(project, vdir, layout):
    from slides import captions
    files = sorted((vdir / "slides").glob("*.png"))
    return {"no_old_captions": captions.check(project, vdir, layout, files)}
