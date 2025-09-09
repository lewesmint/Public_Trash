#!/usr/bin/env bash
set -euo pipefail

# Idempotent Docker install for Ubuntu
# Installs: docker-ce, docker-ce-cli, containerd.io, docker-buildx-plugin, docker-compose-plugin

# 0) Prereqs
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg

# 1) Keyring (idempotent)
sudo install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
fi

# 2) Repo (idempotent, uses your Ubuntu codename)
source /etc/os-release
ARCH="$(dpkg --print-architecture)"
LIST=/etc/apt/sources.list.d/docker.list
LINE="deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable"

if [ ! -f "$LIST" ] || ! grep -qF "$LINE" "$LIST"; then
  echo "$LINE" | sudo tee "$LIST" >/dev/null
fi

# 3) Install or upgrade Docker packages
sudo apt-get update -y
sudo apt-get install -y \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4) Enable and start Docker (idempotent)
sudo systemctl enable --now docker

# 5) Optional: add current user to docker group to run without sudo
if id -nG "$USER" | grep -qvw docker; then
  sudo usermod -aG docker "$USER"
  ADDED_GROUP=1
fi

# 6) Show versions
docker --version || true
containerd --version || true
docker compose version || true

echo "Docker install finished."
if [ "${ADDED_GROUP:-0}" = "1" ]; then
  echo "You were added to the 'docker' group. Open a new shell to use 'docker' without sudo."
fi
