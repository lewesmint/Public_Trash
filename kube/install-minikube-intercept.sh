#!/bin/bash
# Install a bash function in ~/.bashrc to intercept 'minikube start' and run ~/bin/update-registry-hosts.sh after

BASHRC="$HOME/.bashrc"
FUNC_NAME="minikube"
SCRIPT="$HOME/bin/update-registry-hosts.sh"

if [ ! -f "$BASHRC" ]; then
  echo "[ERROR] $BASHRC does not exist. Aborting." >&2
  exit 2
fi

if [ ! -f "$HOME/bin/update-registry-hosts.sh" ]; then
  mkdir -p "$HOME/bin"
  printf '%s\n' '#!/bin/sh' \
    '# Update /etc/hosts to map registry to host gateway' \
    'GATEWAY=$(ip route | awk "/default/ {print \\$3}" | head -n1)' \
    'if [ -n "$GATEWAY" ]; then' \
    '  echo "Using host gateway: $GATEWAY"' \
    '  sudo awk '\''($2!="registry"){print}'\'' /etc/hosts > /tmp/hosts.new' \
    '  echo "$GATEWAY registry" >> /tmp/hosts.new' \
    '  sudo cp /tmp/hosts.new /etc/hosts' \
    '  echo "Registry hostname configured: registry -> $GATEWAY"' \
    '  touch "$HOME/.registry-hosts-updated"' \
    'else' \
    '  echo "Could not determine host gateway; skipping registry hostname mapping"' \
    'fi' \
    > "$HOME/bin/update-registry-hosts.sh"
  chmod +x "$HOME/bin/update-registry-hosts.sh"
fi

# Function will ene up in ~/.bashrc
minikube() {
  if [ "$1" = "start" ]; then
    command minikube "$@"
    if [ -f "$HOME/bin/update-registry-hosts.sh" ]; then
      if [ ! -x "$HOME/bin/update-registry-hosts.sh" ]; then
        chmod +x "$HOME/bin/update-registry-hosts.sh"
      fi
      "$HOME/bin/update-registry-hosts.sh"
      echo minikube hosts file updated via ~/.bashrc
    fi
  else
    command minikube "$@"
  fi
}

# Extract the function definition as a string
FUNC_DEF="$(declare -f minikube)"

# Only add if not already present
if ! grep -E -q "(^|[[:space:]])minikube\(\)" "$BASHRC"; then
  printf '\n# Intercept minikube start to update registry hosts\n' >> "$BASHRC"
  printf '%s\n' "$FUNC_DEF" >> "$BASHRC"
  echo "Added minikube intercept function to $BASHRC. You must source it or open a new terminal for it to take effect."
else
  echo "minikube intercept function already present in $BASHRC. No changes made."
fi
