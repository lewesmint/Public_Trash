#!/usr/bin/env bash
# Standalone Keycloak installer for Minikube with HTTPS (TLS) options
#
# TLS modes provided by this script:
#   - mkcert      : HTTPS using a certificate signed by a local developer CA from mkcert.
#                   Browsers will trust it on machines where you ran `mkcert -install`.
#   - self-signed : HTTPS with a self-signed certificate. Encrypted, but browsers warn
#                   because it is not signed by a trusted CA (safe for local/dev).
#   - none        : Plain HTTP only. Easiest, but no encryption.
#
# Separation of phases:
#   - Install: ensures namespace, generates TLS secret (if any), writes Helm values,
#              and runs `helm upgrade --install`.
#   - Verify (optional): port-forwards ingress-nginx and curls a Keycloak endpoint to
#              confirm it is up. Disable with --no-verify.
#
# Requirements: kubectl, helm, curl; plus mkcert (mkcert mode) or openssl (self-signed).
#
# Example: ./scripts/install-keycloak-standalone.sh --mode mkcert --fresh

set -euo pipefail
set -o errtrace

# Defaults
MODE="mkcert"
HOST="auth.minikube"
SECRET_NAME="auth.minikube-tls"
NAMESPACE="keycloak"
CHART_VERSION="25.2.0"   # Helm chart version pinned; app image tag is set in values.yaml
FRESH=0
VERIFY=1
RETRIES=24      # ~2 minutes
RETRY_SLEEP_SECONDS=5

# Resolve locations
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# usage
# Prints CLI usage information and example invocations.
# Reads $0 for script name.
usage() {
  cat <<EOF
Usage: $0 [--mode mkcert|self-signed|none] [--host HOST] [--secret SECRET] [--namespace NS] [--chart-version VER] [--fresh] [--no-verify]

Examples:
  $0 --mode mkcert           # HTTPS with mkcert (default)
  $0 --mode self-signed      # HTTPS with OpenSSL self-signed
  $0 --mode none             # HTTP only
  $0 --mode mkcert --fresh   # Delete ns first, then install with mkcert
EOF
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    --secret) SECRET_NAME="$2"; shift 2;;
    --namespace) NAMESPACE="$2"; shift 2;;
    --chart-version) CHART_VERSION="$2"; shift 2;;
    --fresh) FRESH=1; shift;;
    --no-verify) VERIFY=0; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

# Compute derived paths after args are parsed (handles --host changes)
GEN_DIR="$ROOT_DIR/generated/standalone"
mkdir -p "$GEN_DIR"
CRT_PATH="$GEN_DIR/${HOST}.crt"
KEY_PATH="$GEN_DIR/${HOST}.key"
VALUES_FILE="$GEN_DIR/keycloak-values.yaml"

# abort
# Prints an error message and exits the script with non-zero status.
# Parameters:
#   $1..$N - message parts to print to stderr.
# Output: error message to stderr.
# Exit: always exits 1.
abort() {
  echo "Error: $*" >&2
  exit 1
}

# ensure_ingress_ready
# Verifies that the ingress-nginx namespace and controller service exist.
# Useful before attempting port-forward verification.
# Parameters: none.
# Output: human-readable hints if missing.
# Exit: exits non-zero via abort on failure.
ensure_ingress_ready() {
  # Verifies ingress-nginx essentials exist
  if ! kubectl get ns ingress-nginx >/dev/null 2>&1; then
    abort "Namespace 'ingress-nginx' not found. On Minikube run: minikube addons enable ingress"
  fi
  # common service names across different ingress-nginx deployments
  if ! kubectl -n ingress-nginx get svc ingress-nginx-controller >/dev/null 2>&1 && \
     ! kubectl -n ingress-nginx get svc nginx-ingress-ingress-nginx-controller >/dev/null 2>&1; then
    abort "ingress-nginx controller Service not found in namespace 'ingress-nginx' (tried: 'ingress-nginx-controller', 'nginx-ingress-ingress-nginx-controller'). If using Minikube: minikube addons enable ingress"
  fi
}

pf_pid=""

# pf_start
# Starts a kubectl port-forward to a given Service in the background.
# Stores the background process id in global variable pf_pid.
# Parameters:
#   $1 - namespace
#   $2 - service name
#   $3 - local port
#   $4 - target port on the Service
# Output: logs redirected to /tmp/keycloak-pf.log
# Exit: continues on success. On failure, kubectl will return non-zero.
pf_start() {
  # Starts a port-forward in the background and records its PID
  local ns="$1" svc="$2" lport="$3" tport="$4"
  kubectl -n "$ns" port-forward "svc/$svc" "${lport}:${tport}" >/tmp/keycloak-pf.log 2>&1 &
  pf_pid=$!
  sleep 2
}

# pf_stop
# Stops a previously started port-forward if pf_pid is set.
# Parameters: none.
pf_stop() {
  # Stops the port-forward if running
  if [[ -n "${pf_pid:-}" ]]; then
    kill "$pf_pid" >/dev/null 2>&1 || true
  fi
}

# print_admin_password
# Prints the Bitnami generated Keycloak admin password from Secret keycloak/admin-password.
# Parameters:
#   $1 - namespace where the chart is installed.
# Output: password to stdout if available, otherwise a note.
# Exit: always continues.
print_admin_password() {
  # Prints the Bitnami-generated admin password if present
  local ns="$1"
  local secret="keycloak"
  local key="admin-password"
  if kubectl -n "$ns" get secret "$secret" >/dev/null 2>&1; then
    echo "Keycloak admin password:"
    kubectl -n "$ns" get secret "$secret" -o jsonpath="{.data.${key}}" | base64 -d; echo
  else
    echo "Admin password secret '$secret' not found in namespace '$ns' (not fatal)."
  fi
}

# Always clean up the port-forward on exit or interruption
trap 'pf_stop' EXIT INT TERM


apt_updated=0

# apt_install
# Best effort install of packages using apt-get where available.
# Safe to call on non-Debian systems where apt-get is absent.
# Parameters:
#   $@ - package names to install.
# Output: apt output or nothing if apt-get is not present.
# Exit: continues even if apt commands fail.
apt_install() {
  if command -v apt-get >/dev/null 2>&1; then
    if [[ $apt_updated -eq 0 ]]; then
      sudo apt-get update -y || true
      apt_updated=1
    fi
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$@" || true
  fi
}

# ensure_binary
# Ensures a required binary is available. Attempts light-touch install via apt,
# and for mkcert also tries a local download into ~/.local/bin on Linux.
# Parameters:
#   $1 - binary name to check.
# Output: human-readable messages about what is being installed.
# Exit: exits non-zero if the binary cannot be ensured.
ensure_binary() {
  local bin="$1"; shift || true
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Missing dependency: $bin"
    case "$bin" in
      mkcert)
        echo "Attempting to install mkcert..."
        apt_install mkcert libnss3-tools
        if ! command -v mkcert >/dev/null 2>&1; then
          # Fallback: local download to ~/.local/bin on Linux x86_64 only (pinned)
          if [[ "$(uname -s)" == "Linux" ]]; then
            arch="$(uname -m)"
            if [[ "$arch" == "x86_64" || "$arch" == "amd64" ]]; then
              mkdir -p "$HOME/.local/bin"
              local URL="https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64"
              curl -fsSL "$URL" -o "$HOME/.local/bin/mkcert" && chmod +x "$HOME/.local/bin/mkcert"
              export PATH="$HOME/.local/bin:$PATH"
            else
              echo "mkcert fallback binary not available for arch '$arch'. Please install mkcert manually: https://github.com/FiloSottile/mkcert" >&2
            fi
          else
            echo "mkcert fallback is only implemented for Linux x86_64. Please install mkcert manually: https://github.com/FiloSottile/mkcert" >&2
          fi
        fi
        ;;

      openssl)
        echo "Attempting to install openssl..."
        apt_install openssl
        ;;

      curl)
        echo "Attempting to install curl..."
        apt_install curl
        ;;
      *) ;;
    esac
  fi
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Error: required command '$bin' still not found" >&2
    exit 1
  fi
}

# ensure_namespace
# Idempotently creates a Kubernetes namespace if it does not exist.
# Parameters:
#   $1 - namespace name.
# Output: none on success.
# Exit: always continues.
ensure_namespace() {
  local ns="$1"
  kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1 || true
}

# ensure_tls_and_secret
# Creates or reuses TLS certificate files and ensures a kubernetes TLS Secret.
# For mkcert or self-signed, writes cert and key under gen_dir and applies Secret.
# Parameters:
#   $1 - mode: mkcert | self-signed | none
#   $2 - host name for the cert CN and SAN
#   $3 - Secret name
#   $4 - namespace for the Secret
#   $5 - directory for generated cert files
# Output: prints "true" if TLS is enabled, "false" otherwise. Caller captures this.
ensure_tls_and_secret() {
  local mode="$1" host="$2" secret="$3" ns="$4" gen_dir="$5"
  local crt="$gen_dir/${host}.crt"
  local key="$gen_dir/${host}.key"
  mkdir -p "$gen_dir"
  case "$mode" in
    mkcert)
      echo "Generating or reusing mkcert certificate for $host" >&2
      if [[ ! -f "$crt" || ! -f "$key" ]]; then
        mkcert -cert-file "$crt" -key-file "$key" "$host"
      else
        echo "Using existing cert files: $crt, $key" >&2
      fi
      kubectl -n "$ns" create secret tls "$secret" --cert="$crt" --key="$key" \
        --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1 || true
      echo "true"
      ;;

    self-signed)
      echo "Generating or reusing self-signed certificate for $host" >&2
      if [[ ! -f "$crt" || ! -f "$key" ]]; then
        openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
          -keyout "$key" -out "$crt" \
          -subj "/CN=$host" -addext "subjectAltName = DNS:$host" >/dev/null 2>&1
      else
        echo "Using existing cert files: $crt, $key" >&2
      fi
      kubectl -n "$ns" create secret tls "$secret" --cert="$crt" --key="$key" \
        --dry-run=client -o yaml | kubectl apply -f - >/dev/null 2>&1 || true
      echo "true"
      ;;

    none)
      echo "false"
      ;;
    *)
      abort "Invalid mode: $mode"
      ;;
  esac
}

# write_values_file
# Writes a Helm values YAML file for the Bitnami Keycloak chart.
# When tls_enabled is true, appends an extraTls section to bind the provided Secret.
# Parameters:
#   $1 - host name for ingress
#   $2 - tls_enabled flag string "true" or "false"
#   $3 - secret name for TLS
#   $4 - file path to write
# Output: the YAML file at the provided path.
write_values_file() {
  local host="$1" tls_enabled="$2" secret="$3" values_file="$4"
  if [[ "$tls_enabled" == "true" ]]; then
    cat > "$values_file" <<EOF
# Autogenerated by installer. Edit with care.
# Bitnami global dev setting: allow using images that may not meet stricter policies (local/dev only)
global:
  security:
    allowInsecureImages: true

image:
  # Using bitnamilegacy registry/tag known to work locally; update as desired
  repository: bitnamilegacy/keycloak
  tag: "26.3.3-debian-12-r0"

auth:
  adminUser: admin

postgresql:
  enabled: true
  image:
    registry: docker.io
    repository: bitnamilegacy/postgresql
    tag: "latest"
  metrics:
    image:
      registry: docker.io
      repository: bitnamilegacy/postgres-exporter
      tag: "latest"
  auth:
    username: keycloak_user
    database: keycloak_db

ingress:
  enabled: true
  ingressClassName: nginx
  hostname: "$host"
  tls: false  # keep false; we bind our explicit secret via extraTls below
  selfSigned: false
  extraTls:
    - hosts:
      - "$host"
      secretName: "$secret"

# Keycloak proxy settings suitable for use behind ingress-nginx
# Use /auth/ path for compatibility behind ingress-nginx and certain defaults
httpRelativePath: "/auth/"
proxyHeaders: "xforwarded"
hostnameStrict: true
EOF
  else
    cat > "$values_file" <<EOF
# Autogenerated by installer. Edit with care.
# Bitnami global dev setting: allow using images that may not meet stricter policies (local/dev only)
global:
  security:
    allowInsecureImages: true

image:
  # Using bitnamilegacy registry/tag known to work locally; update as desired
  repository: bitnamilegacy/keycloak
  tag: "26.3.3-debian-12-r0"

auth:
  adminUser: admin

postgresql:
  enabled: true
  image:
    registry: docker.io
    repository: bitnamilegacy/postgresql
    tag: "latest"
  metrics:
    image:
      registry: docker.io
      repository: bitnamilegacy/postgres-exporter
      tag: "latest"
  auth:
    username: keycloak_user
    database: keycloak_db

ingress:
  enabled: true
  ingressClassName: nginx
  hostname: "$host"
  tls: false  # keep false; we bind our explicit secret via extraTls below
  selfSigned: false

# Keycloak proxy settings suitable for use behind ingress-nginx
# Use /auth/ path for compatibility behind ingress-nginx and certain defaults
httpRelativePath: "/auth/"
proxyHeaders: "xforwarded"
hostnameStrict: true
EOF
  fi
}

# helm_install_release
# Installs or upgrades the Bitnami Keycloak chart with the provided values file.
# Parameters:
#   $1 - namespace to install into
#   $2 - chart version
#   $3 - path to values.yaml
#   $4 - host name (only used for human-readable logging)
#   $5 - mode string for logging
helm_install_release() {
  local ns="$1" chart_version="$2" values_file="$3" host="$4" mode="$5"
  echo "Installing or upgrading Keycloak (mode=$mode, namespace=$ns, host=$host)..."
  helm upgrade --install keycloak oci://registry-1.docker.io/bitnamicharts/keycloak \
    --version "$chart_version" \
    --namespace "$ns" \
    --create-namespace \
    --values "$values_file" \
    --reset-values \
    --timeout 15m \
    --wait
  echo "Keycloak install or upgrade complete."
}

# verify_deployment
# Verifies the deployment by port-forwarding the ingress controller and
# requesting the master realm OpenID configuration endpoint until it returns 200.
# Parameters:
#   $1 - namespace where Keycloak is installed
#   $2 - host name to send in Host header
#   $3 - tls_enabled string "true" or "false"
#   $4 - number of retries
#   $5 - sleep seconds between retries
# Output: prints HTTP code and a warning if not 200.
verify_deployment() {
  local ns="$1" host="$2" tls_enabled="$3" retries="$4" sleep_secs="$5"
  kubectl -n "$ns" get pods,ingress -o wide || true
  local proto="https"; local lport=8443; local tport=443
  if [[ "$tls_enabled" != "true" ]]; then
    proto="http"; lport=8080; tport=80
  fi
  echo "Testing ${proto} via port-forward to ingress-nginx (Host: $host)..."
  ensure_ingress_ready
  local svc_name="ingress-nginx-controller"
  # Support both Minikube addon and Helm-based naming conventions
  if ! kubectl -n ingress-nginx get svc "$svc_name" >/dev/null 2>&1; then
    svc_name="nginx-ingress-ingress-nginx-controller"
  fi
  pf_start "ingress-nginx" "$svc_name" "$lport" "$tport"
  local test_url="${proto}://127.0.0.1:${lport}/auth/realms/master/.well-known/openid-configuration"
  local code="000"
  for _ in $(seq 1 "$retries"); do
    # Note: for HTTPS we use -k to ignore certificate trust warnings (mkcert/self-signed)
    if [[ "$proto" == "https" ]]; then
      code=$(curl -sk -o /dev/null -w "%{http_code}" "$test_url" -H "Host: $host")
    else
      code=$(curl -s -o /dev/null -w "%{http_code}" "$test_url" -H "Host: $host")
    fi
    if [[ "$code" == "200" ]]; then break; fi
    sleep "$sleep_secs"
  done
  pf_stop
  echo "Ingress check HTTP code: $code"
  if [[ "$code" != "200" ]]; then
    echo "Warning: expected 200 from $test_url but got $code" >&2
  fi
}

# main
# Entry point. Ensures dependencies, prepares namespace and TLS,
# writes values, installs Keycloak, prints admin password,
# and optionally verifies the ingress endpoint.
# Parameters: uses globals set by arg parsing.
main() {
  # Dependencies
  ensure_binary helm
  ensure_binary kubectl
  ensure_binary curl
  case "$MODE" in
    mkcert) ensure_binary mkcert;;
    self-signed) ensure_binary openssl;;
    none) ;;
    *) abort "Invalid --mode: $MODE";;
  esac

  echo "kubectl context: $(kubectl config current-context)"

  # Fresh start
  if [[ "$FRESH" -eq 1 ]]; then
    echo "Deleting namespace $NAMESPACE..."
    kubectl delete namespace "$NAMESPACE" --ignore-not-found --wait=true
  fi

  ensure_namespace "$NAMESPACE"

  # Capture TLS enabled flag ("true"/"false") from ensure_tls_and_secret
  local tls_enabled
  tls_enabled=$(ensure_tls_and_secret "$MODE" "$HOST" "$SECRET_NAME" "$NAMESPACE" "$GEN_DIR")

  write_values_file "$HOST" "$tls_enabled" "$SECRET_NAME" "$VALUES_FILE"

  helm_install_release "$NAMESPACE" "$CHART_VERSION" "$VALUES_FILE" "$HOST" "$MODE"

  print_admin_password "$NAMESPACE" || true

  if [[ "$VERIFY" -eq 1 ]]; then
    verify_deployment "$NAMESPACE" "$HOST" "$tls_enabled" "$RETRIES" "$RETRY_SLEEP_SECONDS"
  fi

  echo "Done."
}

main "$@"
