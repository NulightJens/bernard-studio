#!/bin/bash
# Installs one part of Bernard Studio. Safe to run again: it only does what is missing,
# then checks the part by running it, and records success in state.json.
#
#   install.sh <component> [--json]
#   components: homebrew base slides remotion matte blender links auphonic
#
# Exit codes: 0 done, 1 failed, 3 another part is needed first, 4 this Mac is too weak,
# 75 still waiting for a Terminal window (run the same command again to keep waiting).
# Tool output goes to the log in $STUDIO_HOME/logs/, Bernard sees short plain lines.
#
# Testing: STUDIO_WAIT_SECS (how long to wait for a Terminal window, default 540),
# STUDIO_FORCE=1 (skip the Mac strength check), install.sh auphonic --stdin (key on stdin).

set -u
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib.sh"

C=""; JSON=0; FROM_STDIN=0
for a in "$@"; do
  case "$a" in
    --json) JSON=1 ;;
    --stdin) FROM_STDIN=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) C="$a" ;;
  esac
done

case " ${ALL_COMPONENTS[*]} " in
  *" $C "*) ;;
  *) echo "Tell me which part to install: ${ALL_COMPONENTS[*]}." >&2; exit 2 ;;
esac

mkdir -p "$STUDIO_HOME/logs"
LOG="$STUDIO_HOME/logs/install-$C.log"
echo "=== $(now_iso) install $C" >> "$LOG"

say() { echo "$*"; echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }
logrun() { echo "\$ $*" >> "$LOG"; "$@" >> "$LOG" 2>&1; }

finish() {  # finish <exit code> <one plain sentence>
  local code="$1" msg="$2" status
  echo "[$(date +%H:%M:%S)] exit $code: $msg" >> "$LOG"
  case "$code" in 0) status=done ;; 3) status=needs_first ;; 4) status=mac_too_weak ;; 75) status=waiting ;; *) status=failed ;; esac
  echo "$msg"
  if [ $JSON = 1 ]; then
    printf '{"component":%s,"ok":%s,"status":"%s","message":%s,"log":%s}\n' "$(json_str "$C")" \
      "$([ "$code" = 0 ] && echo true || echo false)" "$status" "$(json_str "$msg")" "$(json_str "$LOG")"
  fi
  exit "$code"
}
fail() { finish 1 "$1"; }

need() {  # need <component>: stop if a required part is missing
  check "$1" >/dev/null 2>&1 && return 0
  finish 3 "$(component_name "$1") needs to be installed first. Run the setup step for it, then this one again."
}

mac_ok_or_stop() {
  local fit; fit="$(mac_fit "$C")"
  [ "$fit" = ok ] || [ "${STUDIO_FORCE:-}" = 1 ] && return 0
  finish 4 "$(component_name "$C") $fit, so it is better not to install it on this Mac."
}

record() {  # record <json object of extra fields>
  local extra="$1"
  state_set "components.$C" "{\"installed_at\":\"$(now_iso)\"${extra:+,$extra}}" || fail "I could not save the setup record in $STUDIO_HOME. Check that your disk is not full, then run this step again."
}

# download <url> <destination> <sha256> <bytes> <label shown to Bernard>
download() {
  local url="$1" dest="$2" sha="$3" bytes="$4" label="$5" part="$2.part" pid size pct last=-1
  [ ${#sha} = 64 ] && [ -n "$bytes" ] || return 3
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ] && [ "$(stat -L -f %z "$dest")" = "$bytes" ]; then
    [ "$(sha256_of "$dest")" = "$sha" ] && { say "Already here: $label."; return 0; }
    rm -f "$dest"
  fi
  say "Downloading $label ($(( bytes / 1000000 )) MB)."
  if [ "$(stat -L -f %z "$part" 2>/dev/null || echo 0)" != "$bytes" ]; then
    curl -fL --retry 5 --retry-delay 3 --connect-timeout 20 -C - -s -o "$part" "$url" >> "$LOG" 2>&1 &
    pid=$!
    while kill -0 "$pid" 2>/dev/null; do
      sleep 10
      size="$(stat -L -f %z "$part" 2>/dev/null || echo 0)"
      pct=$(( size * 100 / bytes ))
      if [ $(( pct / 10 )) -ne $(( last / 10 )) ] && [ "$pct" -lt 100 ]; then say "Downloading $label: $pct percent"; last=$pct; fi
    done
    wait "$pid" || { echo "curl failed for $url" >> "$LOG"; return 1; }
  fi
  say "Checking $label."
  if [ "$(sha256_of "$part")" != "$sha" ]; then
    rm -f "$part"
    echo "checksum mismatch for $url" >> "$LOG"
    return 2
  fi
  mv -f "$part" "$dest"
}

download_or_fail() {
  download "$@"; case $? in
    0) ;;
    3) fail "This version of Bernard Studio has a broken setup list. Update the plugin, then run this step again." ;;
    2) fail "The download of $5 did not match its checksum, so I threw it away. Run this step again; if it happens twice, tell the person who set up your studio." ;;
    *) fail "I could not download $5. Check your internet connection, then run this step again (it picks up where it stopped)." ;;
  esac
}

brew_install() {  # brew_install <formula> <plain label>
  if "$BREW" list --versions "$1" >/dev/null 2>&1; then say "Already installed: $2."; return 0; fi
  say "Installing $2."
  logrun "$BREW" install "$1" || fail "Homebrew could not install $2. Check your internet connection and run this step again; the details are in $LOG."
}

pip_install() {  # pip_install <requirement files...>
  local args=() f hashed=0
  for f in "$@"; do
    [ -f "$REQ_DIR/$f.txt" ] || fail "This version of Bernard Studio is missing its $f package list. Update the plugin, then run this step again."
    args+=(-r "$REQ_DIR/$f.txt")
    grep -q -- '--hash=' "$REQ_DIR/$f.txt" && hashed=1
  done
  [ $hashed = 1 ] && args+=(--require-hashes)
  logrun "$BREW_PREFIX/bin/uv" pip install --python "$VENV/bin/python" "${args[@]}" \
    || fail "The Python packages did not install. Check your internet connection and run this step again; the details are in $LOG."
}

# ---------- a Terminal window for the steps only Bernard can type ----------
# term_step <name> <script body>: writes $STUDIO_HOME/setup/<name>.command, opens it in Terminal,
# then waits for it to write "done" or "failed:<reason>" to $STUDIO_HOME/setup/<name>.status.
term_status() { cat "$STUDIO_HOME/setup/$1.status" 2>/dev/null; }
term_open() {
  local name="$1" body="$2" cmd="$STUDIO_HOME/setup/$1.command" st="$STUDIO_HOME/setup/$1.status"
  mkdir -p "$STUDIO_HOME/setup"
  {
    echo '#!/bin/bash'
    echo "STATUS=$(printf %q "$st")"
    echo 'echo "running $$" > "$STATUS"'
    echo 'clear'
    echo "$body"
  } > "$cmd"
  chmod 700 "$cmd"
  rm -f "$st"
  /usr/bin/open -a Terminal "$cmd" || fail "I could not open a Terminal window. Open the Terminal app once, then run this step again."
}
term_wait() {  # term_wait <name> <label>
  local name="$1" label="$2" waited=0 limit="${STUDIO_WAIT_SECS:-540}" s
  while :; do
    s="$(term_status "$name")"
    case "$s" in
      done) return 0 ;;
      failed:*) return 1 ;;
      running*)
        if ! kill -0 "${s#running }" 2>/dev/null; then echo "failed:closed" > "$STUDIO_HOME/setup/$name.status"; return 1; fi ;;
    esac
    if [ "$waited" -ge "$limit" ]; then
      finish 75 "Still working on $label in the Terminal window. Run this step again to keep waiting."
    fi
    [ $(( waited % 60 )) = 0 ] && say "Waiting for $label to finish in the Terminal window."
    sleep 5; waited=$(( waited + 5 ))
  done
}

# ---------- components ----------

brew_profile() {  # add brew to the shell profile the way Homebrew's own installer says to
  local suffix rc
  case "${SHELL:-/bin/zsh}" in
    */bash*) suffix=" bash"; rc="$HOME/.bash_profile" ;;
    */zsh*) suffix=" zsh"; rc="${ZDOTDIR:-$HOME}/.zprofile" ;;
    */fish*) suffix=" fish"; rc="$HOME/.config/fish/config.fish" ;;
    *) suffix=""; rc="${ENV:-$HOME/.profile}" ;;
  esac
  if ! grep -qs "eval \"\$($BREW_PREFIX/bin/brew shellenv[^\"]*)\"" "$rc"; then
    echo >> "$rc"
    echo "eval \"\$($BREW_PREFIX/bin/brew shellenv$suffix)\"" >> "$rc"
    say "Added Homebrew to $rc."
  fi
}

install_homebrew() {
  local s url sha
  if check_homebrew >/dev/null; then
    brew_profile
    record "\"version\":$(json_str "$("$BREW" --version | head -1)")"
    finish 0 "Homebrew is installed and working."
  fi
  mac_is_admin || fail "Your Mac account is not an administrator, so Homebrew cannot be installed from it. Sign in to an administrator account (or ask whoever manages this Mac to make yours one), then run setup again."
  s="$(term_status homebrew)"
  if [ "${s%% *}" = running ] && kill -0 "${s#running }" 2>/dev/null; then
    say "The Homebrew window is still open."
  else
    url="$(pin homebrew_installer.url)"; sha="$(pin homebrew_installer.sha256)"
    say "Opening a Terminal window for Homebrew. Type your Mac password there when it asks."
    term_open homebrew "$(cat <<EOF
URL=$(printf %q "$url")
SHA=$sha
TMP="\$(mktemp -d)/install.sh"
echo "Bernard Studio: installing Homebrew"
echo
echo "Homebrew is the standard free installer for Mac tools."
echo "Your Mac will ask for your password once. Type it and press Return."
echo "(Nothing shows while you type. That is normal.)"
echo
if ! /usr/bin/sudo -v; then echo "failed:password" > "\$STATUS"; echo; echo "The password was not accepted. Close this window and ask Claude to try again."; exit 1; fi
( while /bin/kill -0 \$\$ 2>/dev/null; do /usr/bin/sudo -n true 2>/dev/null; sleep 50; done ) &
echo
echo "Thank you. Installing now. This window shows Homebrew's own progress."
echo
if ! /usr/bin/curl -fsSL "\$URL" -o "\$TMP"; then echo "failed:download" > "\$STATUS"; echo "Could not download the Homebrew installer. Check the internet connection."; exit 1; fi
if [ "\$(/usr/bin/shasum -a 256 "\$TMP" | cut -c1-64)" != "\$SHA" ]; then echo "failed:checksum" > "\$STATUS"; echo "The Homebrew installer did not match its checksum, so it was not run."; exit 1; fi
if NONINTERACTIVE=1 /bin/bash "\$TMP"; then
  echo done > "\$STATUS"
  echo
  echo "All done. You can close this window and go back to Claude."
else
  echo "failed:installer" > "\$STATUS"
  echo
  echo "Homebrew did not finish. Go back to Claude; it will tell you what to do."
fi
/usr/bin/sudo -k
EOF
)"
  fi
  term_wait homebrew "Homebrew" || {
    case "$(term_status homebrew)" in
      failed:password) fail "The Mac password was not accepted in the Terminal window. Run this step again and type the password you use to log in to this Mac." ;;
      failed:closed) fail "The Terminal window closed before Homebrew finished. Run this step again." ;;
      failed:download) fail "The Homebrew installer could not be downloaded. Check your internet connection, then run this step again." ;;
      *) fail "Homebrew did not finish installing. Run this step again; if it fails twice, send a screenshot of the Terminal window to the person who set up your studio." ;;
    esac
  }
  check_homebrew >/dev/null || fail "Homebrew says it finished, but I cannot run it. Restart your Mac, then run this step again."
  brew_profile
  record "\"version\":$(json_str "$("$BREW" --version | head -1)")"
  finish 0 "Homebrew is installed and working."
}

install_base() {
  local py pyv f tmp out
  need homebrew; mac_ok_or_stop
  for f in $(json items "$COMPONENTS_JSON" pins.brew.base); do
    case "$f" in ffmpeg) brew_install ffmpeg "ffmpeg (video tools)" ;; whisper-cpp) brew_install whisper-cpp "whisper.cpp (speech to text)" ;; uv) brew_install uv "uv (Python manager)" ;; *) brew_install "$f" "$f" ;; esac
  done
  pyv="$(pin python)"
  export UV_PYTHON_INSTALL_DIR="$STUDIO_HOME/python"
  if [ "$(venv_py -c 'import platform;print(platform.python_version())' 2>/dev/null)" != "$pyv" ]; then
    say "Setting up Python $pyv."
    logrun "$BREW_PREFIX/bin/uv" python install --python-preference only-managed "$pyv" || fail "Python $pyv did not install. Check your internet connection and run this step again."
    rm -rf "$VENV"
    logrun "$BREW_PREFIX/bin/uv" venv --python-preference only-managed --python "$pyv" "$VENV" || fail "The Python environment could not be made. Run this step again; the details are in $LOG."
  fi
  if [ "$(state_get components.base.requirements)" != "$(req_hash base)" ] || ! check_base >/dev/null 2>&1; then
    say "Installing the Python packages."
    pip_install base
  fi
  download_or_fail "$(pin whisper_model.url)" "$MODELS/$(pin whisper_model.file)" "$(pin whisper_model.sha256)" \
    "$(pin whisper_model.bytes)" "the speech model"
  for f in "${USER_FOLDERS[@]}"; do mkdir -p "$STUDIO_USER/$f" || fail "I could not make your folder $STUDIO_USER. Check the Movies folder exists, then run this step again."; done
  say "Your folder is ready: $STUDIO_USER"

  say "Checking the base tools."
  tmp="$(mktemp -d)"
  logrun "$BREW_PREFIX/bin/ffmpeg" -v error -f lavfi -i "sine=frequency=440:duration=2" -ar 16000 -ac 1 "$tmp/t.wav" \
    || fail "ffmpeg is installed but does not run. Run this step again; if it fails twice, tell the person who set up your studio."
  logrun "$BREW_PREFIX/bin/whisper-cli" -m "$MODELS/$(pin whisper_model.file)" -f "$tmp/t.wav" -np -nt \
    || fail "The speech-to-text tool does not run. Run this step again; if it fails twice, tell the person who set up your studio."
  logrun venv_py -c "import sys; assert sys.version_info[:2] == (3, 12)" \
    || fail "The Python environment does not run. Run this step again."
  rm -rf "$tmp"
  record "\"python\":\"$pyv\",\"requirements\":\"$(req_hash base)\",\"ffmpeg\":$(json_str "$("$BREW_PREFIX/bin/ffmpeg" -version | head -1 | awk '{print $3}')"),\"whisper_cpp\":$(json_str "$("$BREW" list --versions whisper-cpp | awk '{print $2}')"),\"model_sha256\":\"$(pin whisper_model.sha256)\""
  finish 0 "The base tools are installed and working."
}

install_slides() {
  local v tmp
  need base; mac_ok_or_stop
  say "Installing the slide maker."
  pip_install slides
  say "Downloading the slide browser."
  logrun venv_py -m playwright install --only-shell "$(pin playwright_browser)" \
    || fail "The slide browser did not download. Check your internet connection, then run this step again."
  say "Checking the slide maker."
  tmp="$(mktemp -d)"
  logrun venv_py - "$tmp/check.png" <<'PY' || fail "The slide maker is installed but could not draw a test slide. Run this step again; the details are in the log."
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1350})
    pg.set_content("<body style='margin:0;background:#B91C1C'><h1 style='color:white'>Slide check</h1></body>")
    pg.screenshot(path=sys.argv[1])
    b.close()
PY
  [ -s "$tmp/check.png" ] || fail "The slide maker could not draw a test slide. Run this step again."
  v="$(venv_py -c 'import importlib.metadata as m;print(m.version("playwright"))')"
  rm -rf "$tmp"
  record "\"version\":\"$v\",\"requirements\":\"$(req_hash slides)\",\"browsers\":$(json_str "$PLAYWRIGHT_BROWSERS_PATH")"
  finish 0 "The slide maker is installed and working."
}

install_remotion() {
  local node_f h src dir nodebin d
  need base; mac_ok_or_stop
  node_f="$(json items "$COMPONENTS_JSON" pins.brew.remotion | head -1)"
  brew_install "$node_f" "Node (runs the motion graphics)"
  nodebin="$BREW_PREFIX/opt/$node_f/bin"
  mkdir -p "$STUDIO_HOME/bin"
  for t in node npm npx; do ln -sfn "$nodebin/$t" "$STUDIO_HOME/bin/$t"; done
  "$STUDIO_HOME/bin/node" --version >/dev/null 2>&1 || fail "Node is installed but does not run. Run this step again."
  src="$STUDIO_ROOT/engine/remotion"
  h="$(lock_hash)"
  [ -n "$h" ] && [ -f "$src/package.json" ] || fail "This version of Bernard Studio is missing its motion graphics files. Update the plugin, then run this step again."
  dir="$STUDIO_HOME/remotion/$h"
  if [ ! -x "$dir/node_modules/.bin/remotion" ]; then
    say "Installing Remotion (this downloads a few hundred MB)."
    rm -rf "$dir"; mkdir -p "$dir"
    /usr/bin/rsync -a --exclude node_modules --exclude out "$src/" "$dir/" || fail "I could not copy the motion graphics files. Check your disk space, then run this step again."
    (cd "$dir" && logrun "$STUDIO_HOME/bin/npm" ci --no-audit --no-fund) \
      || { rm -rf "$dir"; fail "Remotion did not install. Check your internet connection and run this step again; the details are in $LOG."; }
  else
    say "Remotion is already installed."
  fi
  say "Getting Remotion's browser."
  (cd "$dir" && logrun "$STUDIO_HOME/bin/npx" --no-install remotion browser ensure) \
    || fail "Remotion's browser did not download. Check your internet connection, then run this step again."
  say "Checking Remotion."
  (cd "$dir" && logrun "$STUDIO_HOME/bin/npx" --no-install remotion versions) \
    || fail "Remotion is installed but does not run. Run this step again; the details are in $LOG."
  # older copies from earlier plugin versions
  for d in "$STUDIO_HOME/remotion"/*; do
    case "$(basename "$d")" in "$h") ;; [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) rm -rf "$d" ;; esac
  done
  record "\"path\":$(json_str "$dir"),\"lock\":\"$h\",\"node\":\"$("$STUDIO_HOME/bin/node" --version)\",\"browser\":\"ok\""
  finish 0 "Motion graphics are installed and working."
}

install_matte() {
  local folder repo rev f out device secs lockfile
  need base; mac_ok_or_stop
  say "Installing the cutout libraries (about 1 GB)."
  if [ "$(state_get components.matte.requirements)" != "$(req_hash matte)" ] || ! ls -d "$VENV"/lib/python3.*/site-packages/torch >/dev/null 2>&1; then
    pip_install base matte
  fi
  folder="$MODELS/$(pin birefnet_hr.folder)"; repo="$(pin birefnet_hr.repo)"; rev="$(pin birefnet_hr.revision)"
  for f in $(json keys "$COMPONENTS_JSON" pins.birefnet_hr.files); do
    local bytes=0 want
    want="$(pin "birefnet_hr/files/$f")" || fail "This version of Bernard Studio has a broken setup list. Update the plugin, then run this step again."
    [ "$f" = model.safetensors ] && bytes="$(pin birefnet_hr.weights_bytes)"
    if [ "$bytes" = 0 ]; then  # small code and config files
      if [ "$(sha256_of "$folder/$f" 2>/dev/null)" != "$want" ]; then
        mkdir -p "$folder"
        curl -fsSL --retry 5 -o "$folder/$f" "https://huggingface.co/$repo/resolve/$rev/$f" >> "$LOG" 2>&1 \
          || fail "I could not download the cutout model. Check your internet connection, then run this step again."
        [ "$(sha256_of "$folder/$f")" = "$want" ] \
          || { rm -f "$folder/$f"; fail "Part of the cutout model did not match its checksum, so I threw it away. Run this step again."; }
      fi
    else
      download_or_fail "https://huggingface.co/$repo/resolve/$rev/$f" "$folder/$f" "$want" "$bytes" "the cutout model"
    fi
  done
  download_or_fail "$(pin alignment_model.url)" "$MODELS/$(pin alignment_model.file)" "$(pin alignment_model.sha256)" \
    "$(pin alignment_model.bytes)" "the word timing model"

  say "Checking the cutout model on one test picture."
  lockfile="${STUDIO_HEAVY_LOCK:-$STUDIO_HOME/locks/heavy.lock}"; mkdir -p "$(dirname "$lockfile")"
  out="$(/usr/bin/lockf -k "$lockfile" "$VENV/bin/python" - "$folder" 2>>"$LOG" <<'PY'
import sys, time, warnings
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModelForImageSegmentation
dev = "mps" if torch.backends.mps.is_available() else "cpu"
dtype = torch.float16 if dev == "mps" else torch.float32
t0 = time.time()
net = AutoModelForImageSegmentation.from_pretrained(sys.argv[1], trust_remote_code=True, local_files_only=True)
net = net.to(dev).eval().to(dtype)
load = time.time() - t0
x = torch.rand(1, 3, 2048, 2048, device=dev, dtype=dtype)
with torch.no_grad():
    t1 = time.time(); y = net(x)[-1].sigmoid()
    if dev == "mps": torch.mps.synchronize()
    first = time.time() - t1
    t2 = time.time(); y = net(x)[-1].sigmoid()
    if dev == "mps": torch.mps.synchronize()
    second = time.time() - t2
assert y.shape[-1] == 2048
print(f"{dev} {load:.1f} {first:.2f} {second:.2f}")
PY
)" || fail "The cutout model is installed but could not run. Restart your Mac and run this step again; the details are in $LOG."
  set -- $out; device="$1"; secs="$4"
  echo "matte check: device $1, load $2 s, first frame $3 s, second frame $4 s" >> "$LOG"
  say "The cutout model runs on the $([ "$device" = mps ] && echo "Mac's graphics chip" || echo "processor") at about $secs seconds a frame."
  record "\"requirements\":\"$(req_hash matte)\",\"device\":\"$device\",\"seconds_per_frame\":$secs,\"load_seconds\":$2,\"revision\":\"$rev\""
  finish 0 "The cutout model is installed and working."
}

install_blender() {
  local v
  mac_ok_or_stop
  need homebrew
  if [ ! -x "$(blender_app)" ]; then
    say "Installing Blender (about 1 GB)."
    logrun "$BREW" install --cask "$(pin brew.blender_cask)" \
      || fail "Blender did not install. Check your internet connection and run this step again; the details are in $LOG."
  else
    say "Blender is already installed."
  fi
  say "Checking Blender."
  v="$("$(blender_app)" --background --factory-startup --version 2>/dev/null | head -1 | awk '{print $2}')"
  [ -n "$v" ] || fail "Blender is installed but does not start. Open it once from Applications, then run this step again."
  record "\"version\":\"$v\""
  finish 0 "Blender $v is installed and working."
}

install_links() {
  local v
  need homebrew
  brew_install yt-dlp "the link downloader"
  v="$("$BREW_PREFIX/bin/yt-dlp" --version 2>>"$LOG")" || fail "The link downloader is installed but does not run. Run this step again."
  record "\"version\":\"$v\""
  finish 0 "The link downloader is installed and working."
}

auphonic_verify() {  # reads the key from the Keychain at use; it never touches argv, a file or the screen
  local code
  code="$( { printf 'Authorization: bearer '; /usr/bin/security find-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" -w 2>/dev/null; } \
    | curl -s -o /dev/null -w '%{http_code}' -H @- https://auphonic.com/api/user.json 2>>"$LOG")"
  echo "auphonic check: http $code" >> "$LOG"
  case "$code" in 200) return 0 ;; 401|403) return 1 ;; *) return 2 ;; esac
}

install_auphonic() {
  local key s
  if [ $FROM_STDIN = 1 ]; then
    IFS= read -r key || true
    key="${key//[[:space:]]/}"
    [ -n "$key" ] || fail "No key came through. Run this step again."
    printf 'add-generic-password -U -a "%s" -s "%s" -w "%s"\n' "$USER" "$KEYCHAIN_SERVICE" "$key" | /usr/bin/security -i >> "$LOG" 2>&1
    key=""
  elif ! check_auphonic >/dev/null; then
    s="$(term_status auphonic)"
    if ! { [ "${s%% *}" = running ] && kill -0 "${s#running }" 2>/dev/null; }; then
      say "Opening a Terminal window. Paste your Auphonic key there and press Return."
      term_open auphonic "$(cat <<EOF
SERVICE=$KEYCHAIN_SERVICE
echo "Bernard Studio: save your Auphonic key"
echo
echo "1. In your web browser, open https://auphonic.com/accounts/settings/ and copy your API key."
echo "2. Paste it here and press Return. (Nothing shows while you paste. That is normal.)"
echo
IFS= read -rs KEY
KEY="\${KEY//[[:space:]]/}"
if [ -z "\$KEY" ]; then echo "failed:empty" > "\$STATUS"; echo "No key was pasted. Close this window and ask Claude to try again."; exit 1; fi
printf 'add-generic-password -U -a "%s" -s "%s" -w "%s"\n' "\$USER" "\$SERVICE" "\$KEY" | /usr/bin/security -i >/dev/null 2>&1
KEY=""
if /usr/bin/security find-generic-password -a "\$USER" -s "\$SERVICE" >/dev/null 2>&1; then
  echo done > "\$STATUS"; echo; echo "Saved in your Mac's Keychain. You can close this window and go back to Claude."
else
  echo "failed:keychain" > "\$STATUS"; echo "The key could not be saved in your Keychain. Go back to Claude."
fi
EOF
)"
    fi
    term_wait auphonic "your Auphonic key" || fail "The key was not saved. Run this step again and paste the key into the Terminal window."
  fi
  check_auphonic >/dev/null || fail "Your Auphonic key is not in your Keychain. Run this step again."
  say "Checking your key with Auphonic."
  auphonic_verify; case $? in
    0) record "\"keychain_service\":\"$KEYCHAIN_SERVICE\",\"verified\":true"
       finish 0 "Auphonic accepted your key. Voice clean-up will use your Auphonic account from now on." ;;
    1) /usr/bin/security delete-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" >/dev/null 2>&1
       fail "Auphonic did not accept that key, so I removed it. Copy the key again from your Auphonic account settings and run this step again." ;;
    *) record "\"keychain_service\":\"$KEYCHAIN_SERVICE\",\"verified\":false"
       finish 0 "Your key is saved, but I could not reach Auphonic to check it. It will be checked the first time it is used." ;;
  esac
}

"install_$C"
