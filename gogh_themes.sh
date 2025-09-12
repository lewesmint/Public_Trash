#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${HOME}/.gogh-min"
mkdir -p "${WORKDIR}"
cd "${WORKDIR}"

command -v wget >/dev/null 2>&1 || { echo "Please install wget"; exit 1; }
command -v gsettings >/dev/null 2>&1 || { echo "gsettings not found"; exit 1; }

# Download apply script once
if [ ! -f "./apply-colors.sh" ]; then
  wget -q https://github.com/Gogh-Co/Gogh/raw/master/apply-colors.sh -O apply-colors.sh
  chmod +x apply-colors.sh
fi

export GOGH_APPLY_SCRIPT="${WORKDIR}/apply-colors.sh"
export TERMINAL=gnome-terminal

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

# --- helpers ---

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

# --- install themes ---

for theme in "${THEMES[@]}"; do
  if [ ! -f "$theme" ]; then
    echo "Downloading $theme"
    wget -q "https://github.com/Gogh-Co/Gogh/raw/master/installs/$theme" -O "$theme"
    chmod +x "$theme"
  fi
  echo "Applying $theme"
  TERMINAL=gnome-terminal bash "./$theme"
done

# --- handle 'Unnamed' profile ---
UUIDS=$(gsettings get org.gnome.Terminal.ProfilesList list | grep -oE "[0-9a-f-]{36}" || true)
for u in $UUIDS; do
  raw=$(gsettings get "org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:$u/" visible-name)
  name="${raw#\'}"; name="${name%\'}"
  if [ "$name" = "Unnamed" ]; then
    echo "Renaming profile 'Unnamed' to 'Default'"
    gsettings set "org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles/:$u/" visible-name 'Default'
  fi
done

# --- set VS Code Dark as default ---
VS_UUID=$(profile_uuid_for_name "VS Code Dark")
if [ -n "${VS_UUID:-}" ]; then
  echo "Setting 'VS Code Dark' as the default GNOME Terminal profile"
  gsettings set org.gnome.Terminal.ProfilesList default "$VS_UUID"
else
  echo "Warning: 'VS Code Dark' profile not found; default not changed"
fi

echo "Done. The 'Unnamed' profile was renamed to 'Default', and new terminals will default to VS Code Dark."
