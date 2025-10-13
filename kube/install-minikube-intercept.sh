#!/bin/bash
# Install a bash function in ~/.bashrc to intercept 'minikube start' and update registry hosts in the VM

BASHRC="$HOME/.bashrc"

if [ ! -f "$BASHRC" ]; then
  echo "[ERROR] $BASHRC does not exist. Aborting." >&2
  exit 2
fi

minikube() {
  if [ "$1" = "start" ]; then
    command minikube "$@"
    echo "Configuring registry hostname in minikube VM..."
    REGISTRY_IP=$(getent hosts registry | awk '{print $1}' | head -n1)
    if [ -n "$REGISTRY_IP" ]; then
      CURRENT_MAPPING=$(minikube ssh "grep -E '^[0-9.]+[[:space:]]+registry([[:space:]]|$)' /etc/hosts 2>/dev/null | awk '{print \\$1}' | head -n1" || echo "")
      if [ "$CURRENT_MAPPING" = "$REGISTRY_IP" ]; then
        echo "Registry already configured: registry -> $REGISTRY_IP"
      else
        echo "Updating registry: registry -> $REGISTRY_IP"
        minikube ssh "sudo awk '(\$2!=\"registry\"){print}' /etc/hosts > /tmp/hosts.new; echo \"$REGISTRY_IP registry\" >> /tmp/hosts.new; sudo cp /tmp/hosts.new /etc/hosts"
      fi
    fi
  else
    command minikube "$@"
  fi
}

FUNC_DEF="$(declare -f minikube)"

if ! grep -E -q "(^|[[:space:]])minikube\(\)" "$BASHRC"; then
  printf '\n# Intercept minikube start to update registry hosts\n' >> "$BASHRC"
  printf '%s\n' "$FUNC_DEF" >> "$BASHRC"
  echo "Added minikube function to $BASHRC. Source it or open a new terminal."
else
  echo "minikube function already in $BASHRC."
fi
