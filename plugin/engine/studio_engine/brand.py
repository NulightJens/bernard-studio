"""His brand: kit colours, fonts, caption and sound settings. brand/defaults.json with his own settings
(STUDIO_USER/.settings/brand.json, changed through /studio-tune) laid over it.

    from studio_engine import brand
    b = brand.load()                     # merged dict
    brand.color("red")                   # (185, 28, 28)
    brand.hex("red")                     # "#B91C1C"
    brand.font("caption", 62)            # PIL ImageFont, Raleway 800
    brand.font_path("display")           # Path to the .ttf
    brand.brush("red-a")                 # Path to a brush PNG
    brand.get("captions.size"); brand.set_value("style.documentary.grain", "0.03")
    brand.style_settings("documentary")  # his saved preferences for one style
    brand.caption_px(58, ctx.brand)      # a style's own caption size, scaled by his caption size setting
"""
import copy
import json
from functools import lru_cache

from . import paths
from .errors import StudioError
from .project import write_json


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def defaults():
    return json.loads((paths.brand_dir() / "defaults.json").read_text())


def user_settings():
    f = paths.brand_settings()
    if f.exists():
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            raise StudioError("His brand settings file is damaged. Run /studio-tune to set them again.")
    return {}


def load():
    return _merge(defaults(), user_settings())


def caption_px(native, data=None):
    """A style's caption size in pixels after his caption size setting (/studio-tune). Each style keeps its own look:
    `native` is its size at the default setting, and his setting scales it by the same ratio, so the default setting
    changes nothing and "bigger" means bigger in every style."""
    d = load() if data is None else data
    base = float(defaults()["captions"]["size"])
    try:
        size = float(d["captions"]["size"])
    except (KeyError, TypeError, ValueError):
        size = base
    if size <= 0:
        size = base
    return int(round(native * size / base))


def get(key=None, data=None):
    d = load() if data is None else data
    if not key:
        return d
    for part in key.split("."):
        if not isinstance(d, dict) or part not in d:
            raise StudioError(f'There is no brand setting called "{key}".')
        d = d[part]
    return d


def _parse(value):
    """Settings arrive as text from the command line: numbers, true/false and JSON become real values."""
    if not isinstance(value, str):
        return value
    v = value.strip()
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return value


def set_value(key, value):
    """Save one setting in his settings file. Dotted keys reach inside: captions.size, style.<slug>.<key>."""
    parts = key.split(".")
    if not all(parts):
        raise StudioError(f'"{key}" is not a setting name.')
    known_tops = set(defaults())
    if parts[0] not in known_tops:
        raise StudioError(f'There is no brand setting group called "{parts[0]}". Groups: {", ".join(sorted(known_tops))}.')
    val = _parse(value)
    if parts[0] == "colors" and isinstance(val, str):
        if not (val.startswith("#") and len(val) == 7):
            raise StudioError(f'A colour needs to look like #B91C1C, not "{value}".')
        val = val.upper()
    s = user_settings()
    d = s
    for part in parts[:-1]:
        d = d.setdefault(part, {})
        if not isinstance(d, dict):
            raise StudioError(f'"{key}" goes inside a setting that is not a group.')
    d[parts[-1]] = val
    paths.settings_folder().mkdir(parents=True, exist_ok=True)
    write_json(paths.brand_settings(), s)
    font.cache_clear()
    return val


def style_settings(slug):
    return load().get("style", {}).get(slug, {})


def hex(name):
    c = load()["colors"].get(name)
    if not c:
        raise StudioError(f'There is no kit colour called "{name}".')
    return c


def rgb_of(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def color(name):
    return rgb_of(hex(name))


def font_path(kind):
    spec = load()["fonts"].get(kind)
    if not spec:
        raise StudioError(f'There is no kit font called "{kind}".')
    p = paths.fonts_dir() / spec["file"]
    if not p.exists():
        raise StudioError(f"The font file {spec['file']} is missing from the studio. Reinstall the plugin.")
    return p


@lru_cache(None)
def font(kind, size):
    """A PIL font from the kit at a pixel size, with the kit's weight set on variable fonts."""
    from PIL import ImageFont
    spec = load()["fonts"][kind]
    f = ImageFont.truetype(str(font_path(kind)), int(size))
    if spec.get("weight"):
        try:
            f.set_variation_by_axes([spec["weight"]])
        except Exception:
            pass
    return f


def brush(name):
    """brush('red-a') -> Path of brand/brushes/brush-red-a.png. Names: red-a, red-b, white-a, white-b."""
    p = paths.brushes_dir() / f"brush-{name}.png"
    if not p.exists():
        raise StudioError(f'There is no brush called "{name}". Brushes: red-a, red-b, white-a, white-b.')
    return p


def safe():
    return load()["safe"]


def sound_settings():
    return load()["sound"]
