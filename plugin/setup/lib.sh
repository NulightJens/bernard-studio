# Shared by doctor.sh and install.sh. Pure bash plus tools every Mac has
# (sysctl, sw_vers, df, shasum, curl, osascript, security). Never call python3 here:
# on a fresh Mac it is a stub that pops up an install dialog.

SETUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
STUDIO_ROOT="${STUDIO_ROOT:-$(cd "$SETUP_DIR/.." && pwd -P)}"
STUDIO_HOME="${STUDIO_HOME:-$HOME/Library/Application Support/Bernard Studio}"
STUDIO_USER="${STUDIO_USER:-$HOME/Movies/Bernard Studio}"
export STUDIO_ROOT STUDIO_HOME STUDIO_USER

COMPONENTS_JSON="$SETUP_DIR/components.json"
STATE_JSON="$STUDIO_HOME/state.json"
REQ_DIR="$SETUP_DIR/requirements"
VENV="$STUDIO_HOME/venv"
MODELS="$STUDIO_HOME/models"
export PLAYWRIGHT_BROWSERS_PATH="$STUDIO_HOME/ms-playwright"
USER_FOLDERS=("Drop footage here" "My photos" "Projects" "Finished" ".settings")
ALL_COMPONENTS=(homebrew base slides remotion matte blender links auphonic)
KEYCHAIN_SERVICE="BERNARD_STUDIO_AUPHONIC"

# Homebrew lives in /opt/homebrew on Apple silicon and /usr/local on Intel.
if [ "$(uname -m)" = "arm64" ]; then BREW_PREFIX="/opt/homebrew"; else BREW_PREFIX="/usr/local"; fi
BREW="$BREW_PREFIX/bin/brew"
export PATH="$STUDIO_HOME/bin:$BREW_PREFIX/bin:$BREW_PREFIX/sbin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOMEBREW_NO_ENV_HINTS=1 HOMEBREW_NO_INSTALL_CLEANUP=1

# ---------- JSON (osascript JavaScript) ----------
json() { /usr/bin/osascript -l JavaScript "$SETUP_DIR/json.js" "$@" 2>/dev/null; }
# pin <path>: a value from the pins section; a path with "/" is for keys that contain dots.
pin() {
  local v
  case "$1" in */*) v="$(json get "$COMPONENTS_JSON" "pins/$1")" ;; *) v="$(json get "$COMPONENTS_JSON" "pins.$1")" ;; esac
  [ -n "$v" ] || { echo "Setup list is missing pins.$1" >&2; return 1; }
  printf '%s\n' "$v"
}

# A JSON string literal for bash values.
json_str() {
  local s="$1"
  s="${s//\\/\\\\}"; s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"; s="${s//$'\r'/\\r}"; s="${s//$'\t'/\\t}"
  printf '"%s"' "$s"
}

state_set() {  # state_set <dotted.path> <json value>
  mkdir -p "$STUDIO_HOME"
  json set "$STATE_JSON" "$1" "$2" >/dev/null || { echo "Could not write $STATE_JSON." >&2; return 1; }
}
state_get() { json get "$STATE_JSON" "$1"; }

now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
cap() { printf '%s%s' "$(printf %s "${1:0:1}" | tr '[:lower:]' '[:upper:]')" "${1:1}"; }
sha256_of() { /usr/bin/shasum -a 256 "$1" | cut -c1-64; }

# ---------- this Mac ----------
mac_chip() { sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "unknown"; }
mac_apple_silicon() { [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; }
mac_memory_gb() {
  if [ -n "${STUDIO_TEST_MEMORY_GB:-}" ]; then echo "$STUDIO_TEST_MEMORY_GB"; return; fi
  echo $(( ($(sysctl -n hw.memsize) + 536870912) / 1073741824 ))
}
mac_disk_free_gb() {
  if [ -n "${STUDIO_TEST_DISK_GB:-}" ]; then echo "$STUDIO_TEST_DISK_GB"; return; fi
  local d="$STUDIO_HOME"
  while [ ! -d "$d" ]; do d="$(dirname "$d")"; done
  df -k "$d" | awk 'NR==2 {printf "%d\n", $4/1048576}'
}
mac_os() { sw_vers -productVersion; }
mac_is_admin() { /usr/sbin/dseditgroup -o checkmember -m "$USER" admin >/dev/null 2>&1; }

# Does this Mac meet a component's needs? Prints "ok" or one plain reason.
mac_fit() {
  local c="$1" need_mem need_disk need_as mem disk
  need_as="$(json get "$COMPONENTS_JSON" "components.$c.mac.apple_silicon")"
  need_mem="$(json get "$COMPONENTS_JSON" "components.$c.mac.memory_gb")"
  need_disk="$(json get "$COMPONENTS_JSON" "components.$c.disk_gb")"
  mem="$(mac_memory_gb)"; disk="$(mac_disk_free_gb)"
  if [ "$need_as" = "true" ] && ! mac_apple_silicon; then
    echo "needs a Mac with an Apple chip (M1 or newer); this Mac has an Intel chip"; return
  fi
  if [ -n "$need_mem" ] && [ "$mem" -lt "$need_mem" ]; then
    echo "needs at least $need_mem GB of memory; this Mac has $mem GB"; return
  fi
  if [ -n "$need_disk" ] && [ "$disk" -lt $(( need_disk + 5 )) ]; then
    echo "needs about $need_disk GB of free space plus room to work; this Mac has $disk GB free"; return
  fi
  echo "ok"
}

# ---------- component checks: print a short detail, return 0 when installed ----------
venv_py() { "$VENV/bin/python" "$@"; }
req_hash() { [ -f "$REQ_DIR/$1.txt" ] && sha256_of "$REQ_DIR/$1.txt" | cut -c1-12; }
lock_hash() { [ -f "$STUDIO_ROOT/engine/remotion/package-lock.json" ] && sha256_of "$STUDIO_ROOT/engine/remotion/package-lock.json" | cut -c1-12; }

check_homebrew() {
  [ -x "$BREW" ] && "$BREW" --version >/dev/null 2>&1 || return 1
  "$BREW" --version | head -1
}

check_base() {
  local missing=() f size want
  for t in ffmpeg whisper-cli uv; do [ -x "$BREW_PREFIX/bin/$t" ] || missing+=("$t"); done
  [ -x "$VENV/bin/python" ] || missing+=("python environment")
  f="$MODELS/$(pin whisper_model.file)"
  want="$(pin whisper_model.bytes)"
  size="$(stat -L -f %z "$f" 2>/dev/null || echo 0)"
  [ "$size" = "$want" ] || missing+=("speech model")
  for d in "${USER_FOLDERS[@]}"; do [ -d "$STUDIO_USER/$d" ] || { missing+=("your folders"); break; }; done
  if [ ${#missing[@]} -gt 0 ]; then local IFS=,; echo "missing: ${missing[*]}" | sed 's/,/, /g'; return 1; fi
  if [ -f "$REQ_DIR/base.txt" ] && [ "$(state_get components.base.requirements)" != "$(req_hash base)" ]; then
    echo "an update to the Python parts is waiting"; return 2
  fi
  echo "ffmpeg, whisper.cpp, Python $(venv_py -c 'import platform;print(platform.python_version())' 2>/dev/null)"
}

check_slides() {
  [ -x "$VENV/bin/python" ] || { echo "needs the base tools first"; return 1; }
  ls -d "$VENV"/lib/python3.*/site-packages/playwright >/dev/null 2>&1 || { echo "missing: slide browser library"; return 1; }
  ls -d "$PLAYWRIGHT_BROWSERS_PATH"/chromium* >/dev/null 2>&1 || { echo "missing: slide browser"; return 1; }
  if [ "$(state_get components.slides.requirements)" != "$(req_hash slides)" ]; then echo "an update is waiting"; return 2; fi
  echo "Playwright $(state_get components.slides.version)"
}

check_remotion() {
  local h dir
  [ -x "$STUDIO_HOME/bin/node" ] && "$STUDIO_HOME/bin/node" --version >/dev/null 2>&1 || { echo "missing: Node"; return 1; }
  h="$(lock_hash)"
  [ -n "$h" ] || { echo "the motion graphics files are not in this version of the plugin"; return 1; }
  dir="$STUDIO_HOME/remotion/$h"
  [ -x "$dir/node_modules/.bin/remotion" ] || { echo "missing: Remotion packages"; return 1; }
  [ "$(state_get components.remotion.path)" = "$dir" ] && [ "$(state_get components.remotion.browser)" = "ok" ] \
    || { echo "missing: Remotion browser"; return 1; }
  echo "Node $("$STUDIO_HOME/bin/node" --version), Remotion in $h"
}

check_matte() {
  local folder f want size
  [ -x "$VENV/bin/python" ] || { echo "needs the base tools first"; return 1; }
  ls -d "$VENV"/lib/python3.*/site-packages/torch >/dev/null 2>&1 || { echo "missing: cutout libraries"; return 1; }
  folder="$MODELS/$(pin birefnet_hr.folder)"
  want="$(pin birefnet_hr.weights_bytes)"
  size="$(stat -L -f %z "$folder/model.safetensors" 2>/dev/null || echo 0)"
  [ "$size" = "$want" ] || { echo "missing: cutout model"; return 1; }
  if [ -f "$REQ_DIR/matte.txt" ] && [ "$(state_get components.matte.requirements)" != "$(req_hash matte)" ]; then
    echo "an update is waiting"; return 2
  fi
  echo "BiRefNet HR, device $(state_get components.matte.device)"
}

blender_app() { echo "/Applications/Blender.app/Contents/MacOS/Blender"; }
check_blender() {
  [ -x "$(blender_app)" ] || return 1
  local v; v="$(state_get components.blender.version)"
  echo "Blender${v:+ $v}"
}

check_links() {
  [ -x "$BREW_PREFIX/bin/yt-dlp" ] || return 1
  echo "yt-dlp $("$BREW_PREFIX/bin/yt-dlp" --version 2>/dev/null)"
}

# Never prints the key: find-generic-password without -w shows only the item's attributes.
check_auphonic() {
  /usr/bin/security find-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" >/dev/null 2>&1 || return 1
  echo "key saved in your Keychain"
}

check() {  # check <component>: prints detail, returns 0 installed, 1 missing, 2 needs update
  "check_$1"
}

component_name() { json get "$COMPONENTS_JSON" "components.$1.name"; }

# ---------- tested versions ----------
# installed_version <tool>: the version Homebrew installed, read from its own folders (no brew call, so it is fast):
# the linked formula in opt/, else the newest cask folder. Prints nothing when the tool is not installed.
installed_version() {
  local prefix="${STUDIO_TEST_BREW_PREFIX:-$BREW_PREFIX}" v=""
  if [ -L "$prefix/opt/$1" ]; then
    v="$(basename "$(readlink "$prefix/opt/$1")")"
  elif [ -d "$prefix/Caskroom/$1" ]; then
    v="$(ls -1 "$prefix/Caskroom/$1" 2>/dev/null | grep -v '^\.' | sort -t. -k1,1n -k2,2n -k3,3n | tail -1)"
  fi
  printf %s "${v%%_*}"
}

# major_of <version>: the part that signals breaking changes: the first number, or the first two for 0.x.
major_of() {
  local a="${1%%.*}" rest="${1#*.}"
  [ "$a" = 0 ] && [ "$rest" != "$1" ] && a="0.${rest%%.*}"
  printf %s "$a"
}

# version_warnings: one line per installed tool whose major version differs from the tested one: tool<TAB>installed<TAB>tested
version_warnings() {
  local t tested inst
  while IFS= read -r t; do
    [ -n "$t" ] || continue
    json items "$COMPONENTS_JSON" "pins.brew.date_versioned" | grep -qx "$t" && continue
    tested="$(json get "$COMPONENTS_JSON" "pins/brew/tested/$t")"; inst="$(installed_version "$t")"
    [ -n "$inst" ] && [ -n "$tested" ] || continue
    [ "$(major_of "$inst")" = "$(major_of "$tested")" ] || printf '%s\t%s\t%s\n' "$t" "$inst" "$tested"
  done < <(json keys "$COMPONENTS_JSON" "pins.brew.tested")
}
