#!/usr/bin/env bash
set -euo pipefail

# This script:
# 1) Creates an initial GNOME Terminal profile "Default" if none exist
# 2) Installs a set of Gogh colour schemes non-interactively (idempotent)
# 3) Sets "VS Code Dark" as the default profile

# ---------- prerequisites ----------
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1"; exit 1; }; }
need gsettings
need dconf
need wget
need grep
need sed
need tr

# Try to ensure we have a user D-Bus (needed by dconf/gsettings in some contexts)
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
  if command -v dbus-launch >/dev/null 2>&1; then
    # shellcheck disable=SC2046
    export $(dbus-launch)
  fi
fi

BASE="/org/gnome/terminal/legacy/profiles:/"

# ---------- helper functions ----------
profiles_list() {
  dconf read "${BASE}list" 2>/dev/null || echo "[]"
}

profiles_default() {
  dconf read "${BASE}default" 2>/dev/null || echo ""
}

list_profile_uuids() {
  # Yields zero or more UUIDs
  gsettings get org.gnome.Terminal.ProfilesList list 2>/dev/null | grep -oE "[0-9a-f-]{36}" || true
}

profile_uuid_for_name() {
  # $1 = visible-name to find
  local want="$1"
  for u in $(list_profile_uuids); do
    local raw name
    raw=$(gsettings get "org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles/:${u}/" visible-name 2>/dev/null || echo "''")
    name="${raw#\'}"; name="${name%\'}"
    name="${name% (Gogh)}"; name="${name% [Gogh]}"; name="${name% - Gogh}"
    if [ "$name" = "$want" ]; then
      echo "$u"
      return 0
    fi
  done
  return 1
}

profile_exists_name() {
  [ -n "$(profile_uuid_for_name "$1" || true)" ]
}

extract_profile_name() {
  # Reads PROFILE_NAME from a Gogh installer script, else falls back to filename
  local file="$1"
  local line
  line=$(grep -m1 -E '^[[:space:]]*PROFILE_NAME=' "$file" || true)
  if [ -n "$line" ]; then
    line="${line#*=}"
    line="${line%\"}"; line="${line#\"}"
    echo "$line"
  else
    echo "${file%.sh}" | tr '-' ' '
  fi
}

make_uuid() {
  # No uuid-runtime needed
  if [ -r /proc/sys/kernel/random/uuid ]; then
    cat /proc/sys/kernel/random/uuid
  else
    # Very unlikely path; cheap fallback
    date +%s%N | md5sum | sed 's/^\(........\)\(....\)\(....\)\(....\)\(............\).*$/\1-\2-\3-\4-\5/'
  fi
}

# ---------- 1) Ensure there is at least one profile called "Default" ----------
if [ "$(profiles_list)" = "[]" ] || [ -z "$(list_profile_uuids)" ]; then
  echo "No GNOME Terminal profiles found. Creating 'Default'..."
  NEW_UUID="$(make_uuid)"

  dconf load "${BASE}" <<EOF
[/]
list=['${NEW_UUID}']
default='${NEW_UUID}'

[:${NEW_UUID}/]
visible-name='Default'
use-theme-colors=true
foreground-color='rgb(255,255,255)'
background-color='rgb(0,0,0)'
bold-is-bright=true
EOF
  echo "Created 'Default' (${NEW_UUID}) and set as default."
else
  if ! profile_exists_name "Default"; then
    # If profiles exist but no "Default", rename the first one to "Default"
    FIRST_UUID="$(list_profile_uuids | head -n1 || true)"
    if [ -n "$FIRST_UUID" ]; then
      echo "Renaming first profile to 'Default'..."
      gsettings set "org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles/:${FIRST_UUID}/" visible-name 'Default'
      gsettings set org.gnome.Terminal.ProfilesList default "$FIRST_UUID"
    fi
  else
    DEF_UUID="$(profile_uuid_for_name 'Default')"
    # Ensure default points at "Default"
    [ -n "$DEF_UUID" ] && gsettings set org.gnome.Terminal.ProfilesList default "$DEF_UUID"
  fi
fi

# ---------- 2) Prepare Gogh apply script ----------
WORKDIR="${HOME}/.gogh-min"
mkdir -p "${WORKDIR}"
cd "${WORKDIR}"

if [ ! -f "./apply-colors.sh" ]; then
  wget -q https://github.com/Gogh-Co/Gogh/raw/master/apply-colors.sh -O apply-colors.sh
  chmod +x apply-colors.sh
fi
export GOGH_APPLY_SCRIPT="${WORKDIR}/apply-colors.sh"
export TERMINAL=gnome-terminal
# If you want the newly applied theme to become active immediately during install, you can:
# export GOGH_USE_NEW_THEME=1

# Your themes
THEMES=(
  3024-day.sh
  dracula.sh
  arc-dark.sh
  atelier-forest.sh
  breath-darker.sh
  brogrammer.sh
  homebrew.sh
  hipster-green.sh
  bluloco-zsh-light.sh
  cobalt-neon.sh
  elio.sh
  misterioso.sh
  nightlion-v2.sh
  novel.sh
  one-light.sh
  tempus-day.sh
  vs-code-dark.sh
  vs-code-light.sh
)

# Idempotent apply: skip if profile already present
for theme in "${THEMES[@]}"; do
  if [ ! -f "$theme" ]; then
    echo "Downloading $theme"
    wget -q "https://github.com/Gogh-Co/Gogh/raw/master/installs/$theme" -O "$theme"
    chmod +x "$theme"
  fi
  prof_name="$(extract_profile_name "$theme")"
  if profile_exists_name "$prof_name"; then
    echo "Skipping $theme (profile '$prof_name' already exists)"
  else
    echo "Applying $theme (creates profile '$prof_name')"
    TERMINAL=gnome-terminal bash "./$theme"
  fi
done

# ---------- 3) Set VS Code Dark as the default for new terminals ----------
VS_UUID="$(profile_uuid_for_name 'VS Code Dark' || true)"
if [ -n "$VS_UUID" ]; then
  echo "Setting 'VS Code Dark' as the default GNOME Terminal profile"
  gsettings set org.gnome.Terminal.ProfilesList default "$VS_UUID"
else
  echo "Warning: 'VS Code Dark' profile not found. Default unchanged."
fi

echo "Done. A 'Default' profile now exists, themes are installed idempotently, and new terminals will open with VS Code Dark."
