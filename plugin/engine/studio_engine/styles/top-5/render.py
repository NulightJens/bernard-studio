"""Top 5: a countdown list with his real screens at 1080 x 1440, one item per slide (see SPEC.md).

Cover: a photo of him fading into black, a small kicker line, "TOP 5" set huge, his title, "(#1 will surprise you)"
with a red mark. The big "TOP 5" stays off his face: the cover photo is checked for faces (Apple Vision) and, when his
head sits where the number goes, the number moves to the other side, up or down, or gets smaller, in that order.
Items: counted down (05 to 01): the big number with a red bar, the item's title and a small line, a picture of his
screen or footage (the best still moment of a stretch: sharp and never mid-scroll), where it came from, his quote.
Item 01 has a red number and the save-and-follow line.
"""
from html import escape as esc

from studio_engine.errors import StudioError

KIND = "carousel"
W, H = 1080, 1440
NAME = "Bernard Ablola"
KICKERS = ["Ranked", "Countdown", "My list", "Ranked · from my own build"]   # the kicker's fixed choices
KICKER = "Ranked"            # the kicker when the spec does not set one ("" for none)
NUM_TOP = 470                # the cover number's top, as he picked it
LABELS = (["TOP", NAME, "→", "(#1 will surprise you)", "Save this · Follow @bernardablola"] + KICKERS
          + [f"{n}" for n in range(3, 11)] + [f"{i:02d}" for i in range(1, 11)]
          + [f"Top {n} · {i:02d}" for n in range(3, 11) for i in range(1, n + 1)])

CSS = """
.dk { background: radial-gradient(120% 80% at 50% 30%, #161514 0%, #0d0d0d 55%, #090909 100%); }
.cv-photo { position: absolute; left: 0; top: 0; width: 1080px; height: 1000px; background-size: cover; background-repeat: no-repeat; -webkit-mask-image: linear-gradient(180deg, #000 0%, #000 62%, transparent 100%); mask-image: linear-gradient(180deg, #000 0%, #000 62%, transparent 100%); }
.cv-photo::after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(9,9,9,.55) 0%, rgba(9,9,9,0) 22%); }
.kick { position: absolute; left: 80px; top: 96px; font-family: var(--arch); font-size: 30px; letter-spacing: .14em; color: rgba(238,233,223,.85); text-transform: uppercase; }
.cv-num { position: absolute; right: 80px; top: 470px; font-family: var(--display); font-weight: 600; font-size: 420px; line-height: .8; color: #F3EEE4; letter-spacing: -.04em; }
.cv-num i { font-style: normal; font-family: var(--body); font-weight: 800; font-size: 54px; letter-spacing: .2em; vertical-align: top; position: relative; top: 26px; margin-right: 14px; color: rgba(238,233,223,.75); }
.cv-t { position: absolute; left: 80px; right: 80px; top: 905px; font-family: var(--body); font-weight: 800; font-size: 84px; line-height: 1.0; letter-spacing: .01em; text-transform: uppercase; color: #F3EEE4; }
.cv-s { position: absolute; z-index: 1; left: 80px; top: 1112px; font-family: var(--display); font-style: italic; font-weight: 500; font-size: 58px; color: rgba(238,233,223,.86); }
.cv-s b { font-weight: 600; color: #F3EEE4; position: relative; }
.cv-s b::after { content: ""; position: absolute; left: -4px; right: -6px; bottom: 6px; height: 7px; background: var(--red-footage); z-index: -1; }
.cv-s span { position: relative; z-index: 1; }
.no { position: absolute; left: 80px; top: 128px; font-family: var(--display); font-weight: 600; font-size: 250px; line-height: .8; letter-spacing: -.04em; color: #F3EEE4; }
.redbar { position: absolute; left: 96px; top: 352px; width: 64px; height: 7px; background: var(--red-footage); }
.it { position: absolute; left: 380px; right: 80px; top: 150px; font-family: var(--body); font-weight: 800; font-size: 58px; line-height: 1.04; text-transform: uppercase; color: #F3EEE4; }
.it small { display: block; margin-top: 18px; font-family: var(--arch); font-weight: 400; font-size: 26px; letter-spacing: .12em; color: rgba(238,233,223,.6); text-transform: uppercase; }
.media { position: absolute; left: 80px; right: 80px; top: 430px; height: 640px; border-radius: 6px; overflow: hidden; background-size: cover; background-position: center; box-shadow: 0 0 0 1px rgba(238,233,223,.14), 0 30px 60px rgba(0,0,0,.6); }
.q { position: absolute; left: 126px; right: 80px; top: 1134px; font-family: var(--display); font-weight: 500; font-style: italic; font-size: 54px; line-height: 1.14; color: #F3EEE4; }
.q::before { content: "\\201C"; position: absolute; left: -46px; top: -4px; color: rgba(238,233,223,.45); }
.by { position: absolute; left: 80px; right: 80px; bottom: 84px; display: flex; justify-content: space-between; font-family: var(--body); font-weight: 700; font-size: 22px; letter-spacing: .26em; text-transform: uppercase; color: rgba(238,233,223,.45); }
.src { position: absolute; left: 80px; right: 80px; top: 1084px; font-family: var(--arch); font-size: 22px; letter-spacing: .08em; color: rgba(238,233,223,.45); }
"""
MEDIA = (80, 430, 920, 640)          # x, y, w, h of the item picture
COVER = (0, 0, 1080, 1000)


def kicker_html(text, right=False):
    if not text:
        return ""
    role = "label" if text in KICKERS else "words"          # anything else must be his words
    side = ' style="left:auto;right:80px"' if right else ""
    return f'<div class="kick" data-role="{role}"{side}>{esc(text).replace("·", "&middot;")}</div>'


def num_style(place):
    """CSS for the cover number when it has to move off his face: side, top and scale."""
    if not place:
        return ""
    side = "left:80px;right:auto;transform-origin:left top" if place["side"] == "left" else "transform-origin:right top"
    return f' style="{side};top:{place["top"]:.0f}px;transform:scale({place["scale"]:.2f})"'


def cover_page(spec, url, kit_head, n, place=None, kick_right=False):
    c = spec["cover"]
    return (kit_head(CSS, W, H) + '<article class="slide dk grain">'
            f'<div class="cv-photo" style="background-image:url(\'{url}\'); background-position:center"></div>'
            + kicker_html(c.get("kicker", KICKER), kick_right) +
            f'<div class="cv-num"{num_style(place)}><i data-role="label">TOP</i><span data-role="label">{n}</span></div>'
            f'<div class="cv-t" data-role="words" data-text="{esc(c["title"].replace(chr(10), " "))}">'
            f'{"<br>".join(esc(x) for x in c["title"].split(chr(10)))}</div>'
            '<div class="cv-s" data-role="label" data-text="(#1 will surprise you)">(<b data-mark="underline" data-red="1">'
            '<span>#1</span></b> will surprise you)</div>'
            f'<div class="by"><span data-role="label">{NAME}</span><span data-role="label">&rarr;</span></div></article>'
            # a title on three lines pushes the "(#1 will surprise you)" line down, never under it
            "<script>document.fonts.ready.then(()=>{const t=document.querySelector('.cv-t'),s=document.querySelector('.cv-s');"
            "const gap=t.getBoundingClientRect().bottom+28-s.getBoundingClientRect().top;"
            "if(gap>0)s.style.top=(parseFloat(getComputedStyle(s).top)+gap)+'px';});</script></body></html>")


def pages(spec, urls, kit_head, place=None):
    head = kit_head(CSS, W, H)
    items = spec["items"]
    n = len(items)
    out = [cover_page(spec, urls[0], kit_head, n, place)]
    for k, it in enumerate(items):
        num = n - k
        last = num == 1
        small = f'<small data-role="words">{esc(it["small"])}</small>' if it.get("small") else ""
        src = f'<div class="src" data-role="words">{esc(it["from"])}</div>' if it.get("from") else ""
        foot = ('<span data-role="label">Save this &middot; Follow @bernardablola</span>' if last
                else f'<span data-role="label">{NAME}</span>')
        out.append(head + '<article class="slide dk grain">'
                   + (f'<div class="no" data-role="label" data-red="1" style="color:var(--red-footage)">{num:02d}</div>' if last
                      else f'<div class="no" data-role="label">{num:02d}</div><div class="redbar" data-mark="bar" data-red="1"></div>')
                   + f'<div class="it"><span data-role="words">{esc(it["title"])}</span>{small}</div>'
                   f'<div class="media" style="background-image:url(\'{urls[k + 1]}\')"></div>' + src
                   + f'<div class="q" data-role="words" style="top:{1110 if last else 1134}px">{esc(it["quote"])}</div>'
                   f'<div class="by">{foot}<span data-role="label">Top {n} &middot; {num:02d}</span></div>'
                   '</article></body></html>')
    return out


# ----------------------------------------------------------------------------------------------- his face on the cover
def union(boxes):
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[0] + b[2] for b in boxes), max(b[1] + b[3] for b in boxes)
    return (x0, y0, x1 - x0, y1 - y0)


def cover_boxes(shot, n):
    """The big number's box ("TOP" and the count) and every other text box on the cover, as measured."""
    els = [e for e in shot["elements"] if e["role"]]
    num = [e["box"] for e in els if e["text"] in ("TOP", str(n)) and e["box"][1] > 300]
    rest = [e for e in els if not (e["text"] in ("TOP", str(n)) and e["box"][1] > 300)]
    return (union(num) if num else None), rest


def place_number(num, heads, floor, ceiling=160):
    """Where the cover number goes to stay off his head: the same size on the other side first, then moved up or down
    (between the kicker and the title), then smaller (down to half size). `num` is its box as he picked it (right
    side, top 470). Returns {"side", "top", "scale"} or None when nothing fits."""
    from slides.faces import overlap
    x, y, w, h = num
    dy = y - NUM_TOP
    for k in range(20, 9, -1):
        sc = k / 20
        for side in ("right", "left"):
            bx = (x + w - w * sc) if side == "right" else 80.0
            lo, hi = ceiling - dy * sc, floor - h * sc - dy * sc
            tops = sorted(range(int(lo), int(hi) + 1, 10), key=lambda t: abs(t - NUM_TOP))
            for top in tops:
                box = (bx, top + dy * sc, w * sc, h * sc)
                if not any(overlap(box, hb) for hb in heads):
                    return {"side": side, "top": top, "scale": sc}
    return None


def validate(spec, words, duration):
    if not 3 <= len(spec["items"]) <= 10:
        raise StudioError("A countdown holds three to ten items.")


def render(ctx):
    from slides import pictures
    from slides.shoot import file_url, kit_head, record, shoot
    spec = ctx.spec
    ctx.layout.data["format"].update(w=W, h=H)
    urls, crops = [], []
    specs = [(spec["cover"]["photo"], COVER)] + [(it["photo"], MEDIA) for it in spec["items"]]
    for k, (ph, (x, y, w, h)) in enumerate(specs):
        ctx.say(f"Picking picture {k + 1} of {len(specs)}.")
        pic, box = pictures.picture(ctx.project, ph, w, h)
        f = ctx.work / f"pic-{k:02d}.jpg"
        pic.convert("RGB").save(f, quality=92)
        urls.append(file_url(f))
        crops.append((f"slide-{k + 1:02d}.png", [x, y, w, h], ph, box))
    html_pages = pages(spec, urls, kit_head)
    shots = shoot(html_pages, ctx.out / "slides", W, H, ctx.work)
    shots[0] = keep_number_off_face(ctx, spec, urls, shots[0], kit_head, shoot)
    over = [t for s in shots for t in s["overflow"]]
    if over:
        raise StudioError(f'This text runs off its slide: "{over[0]}". Make it shorter.')
    for s in shots[1:]:
        q = [e for e in s["elements"] if e["role"] == "words" and e["box"][1] > 1100]
        if any(e["box"][1] + e["box"][3] > H - 120 for e in q):
            raise StudioError(f'A quote is too long for its slide ("{q[0]["text"][:50]}..."). Use a shorter line of his.')
    record(ctx.layout, shots, {0: "cover", **{k: "item" for k in range(1, len(shots))}})
    for name, box, ph, crop in crops:
        pictures.note(ctx.layout, name, box, ph, crop)
    ctx.layout.save(ctx.out / "layout.json")
    return {"output": "slides"}


def keep_number_off_face(ctx, spec, urls, shot, kit_head, shoot):
    """Find his face on the cover photo; when his head sits under the big number, move the number and shoot the cover
    again. The face boxes go into layout.json for the cover_face_clear check."""
    from PIL import Image
    from slides import faces
    n = len(spec["items"])
    pic = Image.open(ctx.work / "pic-00.jpg")
    found = faces.find(pic)
    sx, sy = COVER[2] / pic.size[0], COVER[3] / pic.size[1]
    found = [(f[0] * sx + COVER[0], f[1] * sy + COVER[1], f[2] * sx, f[3] * sy) for f in found]
    heads = [faces.head_box(f, W, COVER[3]) for f in found]
    ctx.layout.data["faces"] = [{"slide": shot["file"].name, "face": [round(v, 1) for v in f],
                                 "head": list(h)} for f, h in zip(found, heads)]
    num, rest = cover_boxes(shot, n)
    kick = [e["box"] for e in rest if e["box"][1] < 300]
    kick_right = any(faces.overlap(k, f) for k in kick for f in found)
    on_head = num is not None and any(faces.overlap(num, h) for h in heads)
    if not found or not (on_head or kick_right):
        return shot
    if kick_right:
        ctx.say("Moving the line at the top of the cover off his face.")
    if not on_head:
        return shoot([cover_page(spec, urls[0], kit_head, n, None, True)], ctx.out / "slides", W, H, ctx.work,
                     names=[shot["name"]])[0]
    title = [e["box"] for e in rest if e["role"] == "words"]
    floor = min(b[1] for b in title) - 24 if title else COVER[3]
    ceiling = max(b[1] + b[3] for b in kick) + 24 if kick else 120
    place = place_number(num, heads, floor, ceiling)
    if place is None:
        ctx.say("His face fills the cover where the big number goes. A cover photo with his face to one side, or "
                "higher in the frame, will read better.")
        if not kick_right:
            return shot
    else:
        ctx.say(f"Moving the big number off his face ({place['side']} side, {round(place['scale'] * 100)} percent "
                "size).")
    new = shoot([cover_page(spec, urls[0], kit_head, n, place, kick_right)], ctx.out / "slides", W, H, ctx.work,
                names=[shot["name"]])[0]
    ctx.layout.data["cover_number"] = place
    return new


def check_face_clear(layout, tol=0.01):
    """No text on the cover sits on his face (the face box: brow to chin). A sliver under 1 percent of the face
    (a letter's edge) is let through."""
    from slides.faces import overlap
    bad = []
    by_slide = {b.get("slide"): b for b in layout["beats"]}
    for f in layout.get("faces") or []:
        b = by_slide.get(f["slide"])
        if not b:
            continue
        area = f["face"][2] * f["face"][3]
        for t in b["texts"]:
            o = overlap(t["box"], f["face"])
            if area and o / area > tol:
                bad.append({"slide": f["slide"], "text": t["text"], "share_of_face": round(o / area, 3)})
    return {"pass": not bad, "faces": len(layout.get("faces") or []), "on_face": bad}


def qa_extra(project, vdir, layout):
    from slides import captions
    files = sorted((vdir / "slides").glob("*.png"))
    return {"no_old_captions": captions.check(project, vdir, layout, files), "cover_face_clear": check_face_clear(layout)}
