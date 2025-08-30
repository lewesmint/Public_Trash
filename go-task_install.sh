#!/usr/bin/env bash
set -euo pipefail

# Add signing key (skip certificate checks)
sudo mkdir -p /etc/apt/keyrings
wget --no-check-certificate -qO /etc/apt/keyrings/go-task.asc https://repo.gotask.io/gpg.key
sudo chmod 0644 /etc/apt/keyrings/go-task.asc

# Add repo (idempotent overwrite)
echo "deb [signed-by=/etc/apt/keyrings/go-task.asc] https://repo.gotask.io/ /" | \
  sudo tee /etc/apt/sources.list.d/go-task.list >/dev/null

# Install Task
sudo apt-get update
sudo apt-get install -y go-task

# Verify
task --version
