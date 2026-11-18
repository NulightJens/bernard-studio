"""Every folder the engine reads or writes. Nothing else in the engine builds a path to a fixed place.

Three roots (CONTRACT section 2):
  STUDIO_ROOT  the plugin folder (code and assets, read only). bin/studio sets it.
  STUDIO_HOME  ~/Library/Application Support/Bernard Studio (venv, models, locks, state.json)
  STUDIO_USER  ~/Movies/Bernard Studio (his footage, photos, projects, finished files, settings)
"""
import os
from pathlib import Path

PROJECT_DIRS = ("sources", "ingest", "passage", "logs")


def _env_path(name, default):
    v = os.environ.get(name)
    return Path(v).expanduser() if v else Path(default).expanduser()


def root() -> Path:
    # engine/studio_engine/paths.py -> plugin folder is two levels above the package
    return _env_path("STUDIO_ROOT", Path(__file__).resolve().parents[2])


def home() -> Path:
    return _env_path("STUDIO_HOME", "~/Library/Application Support/Bernard Studio")


def user() -> Path:
    return _env_path("STUDIO_USER", "~/Movies/Bernard Studio")


# ----------------------------------------------------------------------------------------------- inside STUDIO_ROOT
def engine_dir() -> Path:
    return root() / "engine"


def styles_dir() -> Path:
    return engine_dir() / "studio_engine" / "styles"


def style_dir(slug) -> Path:
    return styles_dir() / slug


def remotion_src() -> Path:
    return engine_dir() / "remotion"


def slides_dir() -> Path:
    return engine_dir() / "slides"


def brand_dir() -> Path:
    return root() / "brand"


def fonts_dir() -> Path:
    return brand_dir() / "fonts"


def brushes_dir() -> Path:
    return brand_dir() / "brushes"


def library_dir() -> Path:
    return root() / "library"


def sound_library() -> Path:
    return library_dir() / "sound"


def poses_dir() -> Path:
    return library_dir() / "poses"


def objects_dir() -> Path:
    return library_dir() / "objects"


def examples_dir() -> Path:
    return root() / "examples"


def styles_json() -> Path:
    return root() / "styles.json"


def known_styles() -> set:
    """The style slugs this copy of the studio offers: the ones listed in styles.json, nothing else."""
    import json
    try:
        data = json.loads(styles_json().read_text())
    except (OSError, ValueError):
        return set()
    rows = data.get("styles", data) if isinstance(data, dict) else data
    return {str(r.get("slug")) for r in rows if isinstance(r, dict)}


# ----------------------------------------------------------------------------------------------- inside STUDIO_HOME
def models_dir() -> Path:
    return home() / "models"


def whisper_model() -> Path:
    v = os.environ.get("STUDIO_WHISPER_MODEL")
    return Path(v).expanduser() if v else models_dir() / "ggml-medium.en.bin"


def birefnet_dir() -> Path:
    return models_dir() / "birefnet-hr"


def torch_home() -> Path:
    return models_dir() / "torch"


def mms_fa_weights() -> Path:
    return torch_home() / "hub" / "checkpoints" / "model.pt"


def locks_dir() -> Path:
    return home() / "locks"


def heavy_lock_file() -> Path:
    v = os.environ.get("STUDIO_HEAVY_LOCK")
    return Path(v).expanduser() if v else locks_dir() / "heavy.lock"


def home_logs() -> Path:
    return home() / "logs"


def remotion_home() -> Path:
    return home() / "remotion"


def playwright_browsers() -> Path:
    return home() / "ms-playwright"


# ----------------------------------------------------------------------------------------------- inside STUDIO_USER
def drop_folder() -> Path:
    return user() / "Drop footage here"


def photos_folder() -> Path:
    return user() / "My photos"


def projects_folder() -> Path:
    return user() / "Projects"


def finished_folder() -> Path:
    return user() / "Finished"


def settings_folder() -> Path:
    return user() / ".settings"


def brand_settings() -> Path:
    return settings_folder() / "brand.json"


def user_poses() -> Path:
    """His own cutout poses, added with /studio-tune (matte-photo writes here)."""
    return settings_folder() / "poses"


def ensure_user_folders():
    for p in (drop_folder(), photos_folder(), projects_folder(), finished_folder(), settings_folder()):
        p.mkdir(parents=True, exist_ok=True)


def configure_env():
    """Point model caches at STUDIO_HOME and keep every library offline at run time (downloads only in install)."""
    os.environ.setdefault("TORCH_HOME", str(torch_home()))
    os.environ.setdefault("HF_HOME", str(models_dir() / "hf"))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(playwright_browsers()))
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
