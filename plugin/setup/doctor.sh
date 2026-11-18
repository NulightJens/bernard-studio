#!/bin/bash
# Checks this Mac and what Bernard Studio has installed. Changes nothing.
#
#   doctor.sh [--json]               the Mac, each part installed or missing, the user folder
#   doctor.sh needs <style> [--json] the parts that style still needs, and whether this Mac can run it
#   doctor.sh needs --all [--json]   every style and what it still needs (setup's "what's left")
#
# Plain lines by default; with --json, one JSON object on the last line.
# For testing a weaker Mac: STUDIO_TEST_MEMORY_GB=8 or STUDIO_TEST_DISK_GB=10.

set -u
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib.sh"

JSON=0; MODE=all; STYLE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1 ;;
    --all) [ "$MODE" = needs ] && MODE=needs_all ;;
    needs) MODE=needs; case "${2:-}" in ""|-*) ;; *) STYLE="$2"; shift ;; esac ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "I don't know \"$1\". Try: studio doctor, studio needs <style>, or studio needs --all." >&2; exit 2 ;;
  esac
  shift
done

status_of() {  # sets STATUS and DETAIL for one component
  local rc
  DETAIL="$(check "$1" 2>/dev/null)"; rc=$?
  case $rc in 0) STATUS=installed ;; 2) STATUS=update ;; *) STATUS=missing ;; esac
}

mac_json() {
  printf '{"chip":%s,"apple_silicon":%s,"memory_gb":%s,"disk_free_gb":%s,"macos":%s,"admin":%s,"test_override":%s}' \
    "$(json_str "$(mac_chip)")" "$(mac_apple_silicon && echo true || echo false)" "$(mac_memory_gb)" \
    "$(mac_disk_free_gb)" "$(json_str "$(mac_os)")" "$(mac_is_admin && echo true || echo false)" \
    "$([ -n "${STUDIO_TEST_MEMORY_GB:-}${STUDIO_TEST_DISK_GB:-}" ] && echo true || echo false)"
}

disk_gb() { json get "$COMPONENTS_JSON" "components.$1.disk_gb" || echo 0; }

# ---------- studio needs --all ----------
if [ "$MODE" = needs_all ]; then
  declare_status=""; comp_entries=""
  for c in "${ALL_COMPONENTS[@]}"; do
    status_of "$c"; fit="$(mac_fit "$c")"
    eval "ST_$c=\$STATUS; FIT_$c=\$fit"
    comp_entries+="${comp_entries:+,}$(json_str "$c"):{\"name\":$(json_str "$(component_name "$c")"),\"status\":\"$STATUS\",\"disk_gb\":$(disk_gb "$c"),\"mac\":$(json_str "$fit")}"
  done
  style_entries=""; plain=()
  while IFS= read -r st; do
    [ -n "$st" ] || continue
    miss=""; missing_names=""; weak=""; gb=0
    while IFS= read -r c; do
      [ -n "$c" ] || continue
      s_var="ST_$c"; f_var="FIT_$c"
      if [ "${!s_var}" != installed ]; then
        miss+="${miss:+,}$(json_str "$c")"; missing_names+="${missing_names:+, }$(component_name "$c")"
        gb=$(( gb + $(disk_gb "$c") ))
      fi
      [ "${!f_var}" = ok ] || weak+="${weak:+; }$(component_name "$c") ${!f_var}"
    done < <(json items "$COMPONENTS_JSON" "styles.$st.needs")
    ready=false; [ -z "$miss" ] && [ -z "$weak" ] && ready=true
    style_entries+="${style_entries:+,}$(json_str "$st"):{\"ready\":$ready,\"mac_ok\":$([ -z "$weak" ] && echo true || echo false),\"missing\":[$miss],\"missing_disk_gb\":$gb,\"mac\":$(json_str "${weak:-ok}")}"
    if [ -n "$weak" ]; then plain+=("$st: this Mac is too weak for it ($weak)")
    elif [ -n "$miss" ]; then plain+=("$st: needs $missing_names (about $gb GB)")
    else plain+=("$st: ready"); fi
  done < <(json keys "$COMPONENTS_JSON" "styles")
  if [ $JSON = 1 ]; then
    printf '{"styles":{%s},"components":{%s}}\n' "$style_entries" "$comp_entries"
  else
    for l in "${plain[@]}"; do echo "$l"; done
  fi
  exit 0
fi

# ---------- studio needs <style> ----------
if [ "$MODE" = needs ]; then
  if [ -z "$STYLE" ] || ! json get "$COMPONENTS_JSON" "styles.$STYLE" >/dev/null; then
    echo "There is no style called \"$STYLE\". Type /studio-styles to see the list." >&2; exit 2
  fi
  missing=(); weak=(); comps=()
  while IFS= read -r c; do [ -n "$c" ] && comps+=("$c"); done < <(json items "$COMPONENTS_JSON" "styles.$STYLE.needs")
  entries=""
  for c in "${comps[@]}"; do
    status_of "$c"; fit="$(mac_fit "$c")"
    [ "$STATUS" = installed ] || missing+=("$c")
    [ "$fit" = ok ] || weak+=("$c: $fit")
    entries+="${entries:+,}{\"component\":$(json_str "$c"),\"name\":$(json_str "$(component_name "$c")"),\"status\":\"$STATUS\",\"mac\":$(json_str "$fit")}"
  done
  optional="$(json get "$COMPONENTS_JSON" "styles.$STYLE.optional" || echo '{}')"
  if [ $JSON = 1 ]; then
    miss=""; for c in "${missing[@]+"${missing[@]}"}"; do miss+="${miss:+,}$(json_str "$c")"; done
    printf '{"style":%s,"ready":%s,"mac_ok":%s,"missing":[%s],"components":[%s],"optional":%s}\n' \
      "$(json_str "$STYLE")" "$([ ${#missing[@]} = 0 ] && [ ${#weak[@]} = 0 ] && echo true || echo false)" \
      "$([ ${#weak[@]} = 0 ] && echo true || echo false)" "$miss" "$entries" "$optional"
  else
    if [ ${#weak[@]} -gt 0 ]; then
      for w in "${weak[@]}"; do echo "This style needs a stronger Mac. $(component_name "${w%%:*}") ${w#*: }."; done
    elif [ ${#missing[@]} = 0 ]; then
      echo "Everything this style needs is installed."
    else
      echo "This style still needs:"
      for c in "${missing[@]}"; do echo "  $(component_name "$c"): $(json get "$COMPONENTS_JSON" "components.$c.what") (about $(json get "$COMPONENTS_JSON" "components.$c.disk_gb") GB)"; done
    fi
  fi
  [ ${#weak[@]} = 0 ] && [ ${#missing[@]} = 0 ]; exit $?
fi

# ---------- studio doctor ----------
entries=""; setup_missing=""; setup_gb=0
plain=()
for c in "${ALL_COMPONENTS[@]}"; do
  status_of "$c"; fit="$(mac_fit "$c")"
  entries+="${entries:+,}$(json_str "$c"):{\"name\":$(json_str "$(component_name "$c")"),\"status\":\"$STATUS\",\"detail\":$(json_str "$DETAIL"),\"mac\":$(json_str "$fit"),\"disk_gb\":$(disk_gb "$c")}"
  case "$c" in homebrew|base)
    if [ "$STATUS" != installed ]; then setup_missing+="${setup_missing:+,}$(json_str "$c")"; setup_gb=$(( setup_gb + $(disk_gb "$c") )); fi ;;
  esac
  case "$STATUS" in
    installed) line="installed${DETAIL:+ ($DETAIL)}" ;;
    update) line="installed, $DETAIL" ;;
    *) line="not installed${DETAIL:+ ($DETAIL)}" ;;
  esac
  [ "$fit" = ok ] || line+=". This Mac is too weak for it: it $fit"
  plain+=("$(component_name "$c"): $line")
done

vwarn=""; vplain=()
while IFS=$'\t' read -r tool inst tested; do
  [ -n "$tool" ] || continue
  vwarn+="${vwarn:+,}{\"tool\":$(json_str "$tool"),\"installed\":$(json_str "$inst"),\"tested\":$(json_str "$tested")}"
  vplain+=("$tool on your Mac is version $inst; the studio was tested with $tested. It will most likely still work. If a step fails, mention this.")
done < <(version_warnings)

folders=""; folder_ok=true
for d in "${USER_FOLDERS[@]}"; do
  if [ -d "$STUDIO_USER/$d" ]; then folders+="${folders:+,}$(json_str "$d")"; else folder_ok=false; fi
done
footage=0
[ -d "$STUDIO_USER/Drop footage here" ] && footage="$(find "$STUDIO_USER/Drop footage here" -type f ! -name '.*' 2>/dev/null | wc -l | tr -d ' ')"

if [ $JSON = 1 ]; then
  printf '{"mac":%s,"components":{%s},"setup":{"missing":[%s],"disk_gb":%s},"user_folder":{"path":%s,"ready":%s,"present":[%s],"footage_files":%s},"studio_home":%s,"version_warnings":[%s]}\n' \
    "$(mac_json)" "$entries" "$setup_missing" "$setup_gb" "$(json_str "$STUDIO_USER")" "$folder_ok" "$folders" "$footage" "$(json_str "$STUDIO_HOME")" "$vwarn"
else
  echo "Your Mac: $(mac_chip), $(mac_memory_gb) GB memory, $(mac_disk_free_gb) GB free, macOS $(mac_os)"
  mac_is_admin || echo "Your Mac account is not an administrator, so Homebrew cannot be installed from it."
  for l in "${plain[@]}"; do echo "$l"; done
  [ ${#vplain[@]} -gt 0 ] && for l in "${vplain[@]}"; do echo "$l"; done
  [ "$setup_gb" -gt 0 ] && echo "The one-time setup still needs about $setup_gb GB."
  if [ "$folder_ok" = true ]; then
    echo "Your folder: $STUDIO_USER (ready, $footage file(s) in Drop footage here)"
  else
    echo "Your folder: $STUDIO_USER (not made yet; the base tools step makes it)"
  fi
fi
exit 0
