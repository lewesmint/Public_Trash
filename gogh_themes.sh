#!/usr/bin/env bash
set -euo pipefail

command -v gsettings >/dev/null 2>&1 || { echo "gsettings not found"; exit 1; }
command -v wget >/dev/null 2>&1 || { echo "Please install wget"; exit 1; }

WORKDIR="${HOME}/.gogh-min"
mkdir -p "${WORKDIR}"
cd "${WORKDIR}"

# --- helpers ---

# Return the UUID of the first profile with this visible-name (after stripping common suffixes)
profile_uuid_for_name() {
  local want="$1"
  gsettings get org.gnome.Terminal.ProfilesList list \
  | grep -oE "[0-9a-f-]{36}" \
  | while read -r u; do
      local raw name
      raw=$(gsettings get "org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:${u}/" visible-name)
      name="${raw#\'}"; name="${name%\'}"
      name="${name% (Gogh)}"; name="${name% [Gogh]}"; name="${name% - Gogh}"
      if [ "$name" = "$want" ]; then
        echo "$u"
        return 0
      fi
    done
}

# Return 0 if a profile with this visible-name exists
profile_exists_name() {
  local n="$1"
  [ -n "$(profile_uuid_for_name "$n")" ]
}

# Extract PROFILE_NAME from a Gogh installer script, else fall back to filename
extract_profile_name() {
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

# --- 1) Rename fresh Unnamed to Default, first ---

if ! profile_exists_name "Default"; then
  # find any Unnamed and rename it to Default; if none, rename the first profile
  FIRST_UUID=$(gsettings get org.gnome.Terminal.ProfilesList list | grep -oE "[0-9a-f-]{36}" | head -n1 || true)
  if [ -n "$FIRST_UUID" ]; then
    RAW_NAME=$(gsettings get "org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:${FIRST_UUID}/" visible-name || echo "'Unnamed'")
    NAME="${RAW_NAME#\'}"; NAME="${NAME%\'}"
    if [ "$NAME" = "Unnamed" ] || [ -z "$NAME" ]; then
      echo "Renaming profile 'Unnamed' to 'Default'"
    else
      echo "No 'Default' found. Renaming first profile '$NAME' to 'Default'"
    fi
    gsettings set "org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:${FIRST_UUID}/" visible-name 'Default'
  else
    echo "No GNOME Terminal profiles found. Aborting."
    exit 1
  fi
else
  echo "Profile 'Default' already exists. No rename needed."
fi

# Ensure the current default points at Default
DEF_UUID="$(profile_uuid_for_name 'Default' || true)"
if [ -n "$DEF_UUID" ]; then
  echo "Setting 'Default' as the default profile UUID"
  gsettings set org.gnome.Terminal.ProfilesList default "$DEF_UUID"
fi

# --- 2) Prepare Gogh apply script ---

if [ ! -f "./apply-colors.sh" ]; then
  wget -q https://github.com/Gogh-Co/Gogh/raw/master/apply-colors.sh -O apply-colors.sh
  chmod +x apply-colors.sh
fi
export GOGH_APPLY_SCRIPT="${WORKDIR}/apply-colors.sh"
export TERMINAL=gnome-terminal
# If you want each applied theme to take effect immediately in the applying process, uncomment:
# export GOGH_USE_NEW_THEME=1

# --- 3) Themes to install, idempotently ---

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

# Check if a profile with the final visible-name already exists
profile_exists_for_installer() {
  local installer="$1"
  local pname
  pname="$(extract_profile_name "$installer")"
  profile_exists_name "$pname"
}

for theme in "${THEMES[@]}"; do
  if [ ! -f "$theme" ]; then
    echo "Downloading $theme"
    wget -q "https://github.com/Gogh-Co/Gogh/raw/master/installs/$theme" -O "$theme"
    chmod +x "$theme"
  fi
  if profile_exists_for_installer "$theme"; then
    echo "Skipping $theme (profile already present)"
  else
    echo "Applying $theme"
    TERMINAL=gnome-terminal bash "./$theme"
  fi
done

# --- 4) Set VS Code Dark as the default for new terminals ---

VS_UUID="$(profile_uuid_for_name 'VS Code Dark' || true)"
if [ -n "$VS_UUID" ]; then
  echo "Setting 'VS Code Dark' as the default GNOME Terminal profile"
  gsettings set org.gnome.Terminal.ProfilesList default "$VS_UUID"
else
  echo "Warning: 'VS Code Dark' profile not found. Default unchanged."
fi

echo "Done. The fresh profile was renamed to 'Default' first. New terminals will open with 'VS Code Dark'."
