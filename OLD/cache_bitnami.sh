#!/usr/bin/env bash
set -euo pipefail

# ================================================
# Setup validation and guidance
# ================================================
check_and_setup_prerequisites() {
  local needs_setup=false
  
  echo "Checking prerequisites..."
  
  # Check Helm
  if ! command -v helm >/dev/null 2>&1; then
    echo "❌ Helm not found. Install with:"
    echo "   curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3"
    echo "   chmod 700 get_helm.sh && ./get_helm.sh"
    echo "   OR: sudo snap install helm --classic"
    needs_setup=true
  else
    echo "✅ Helm found: $(helm version --short)"
  fi
  
  # Check Docker/Podman
  if ! command -v docker >/dev/null 2>&1 && ! command -v podman >/dev/null 2>&1; then
    echo "❌ Neither Docker nor Podman found. Install Docker with:"
    echo "   sudo snap install docker"
    echo "   OR follow: https://docs.docker.com/engine/install/"
    needs_setup=true
  else
    # Test Docker permissions
    if command -v docker >/dev/null 2>&1; then
      if ! docker ps >/dev/null 2>&1; then
        echo "❌ Docker found but permission denied. Fix with:"
        echo "   sudo groupadd docker"
        echo "   sudo usermod -aG docker \$USER"
        echo "   sudo chown root:docker /var/run/docker.sock"
        echo "   sudo chmod 660 /var/run/docker.sock"
        echo "   newgrp docker"
        echo "   OR: sudo chmod 666 /var/run/docker.sock (quick fix)"
        needs_setup=true
      else
        echo "✅ Docker working properly"
      fi
    else
      echo "✅ Podman found: $(podman --version)"
    fi
  fi
  
  if [[ "$needs_setup" == "true" ]]; then
    echo ""
    echo "Please install missing prerequisites and run the script again."
    exit 1
  fi
  
  echo "✅ All prerequisites met!"
  echo ""
}

# Run prerequisite check
check_and_setup_prerequisites

# ================================================
# Bitnami Helm Chart & Image Caching Script
#
# This script downloads (caches) Helm charts and
# their container images for offline installation.
#
# Charts handled:
#   - bitnami/keycloak
#   - bitnami/redis
#   - bitnami/postgresql
#   - bitnami/rabbitmq
#
# Requirements:
#   - helm installed
#   - docker OR podman installed
#
# Outputs:
#   ./bitnami_cache/charts   -> Helm chart .tgz archives
#   ./bitnami_cache/images   -> Saved container images (.tar files)
#   ./bitnami_cache/logs     -> Image lists per chart
#
# Usage:
#   chmod +x cache_bitnami.sh
#   ./cache_bitnami.sh
#
# Later (offline):
#   docker load -i images/<image>.tar   # load into local runtime
#   helm install <name> charts/<chart>.tgz -n <namespace>
# ================================================

# Optionally pin chart versions here (leave blank for latest)
KEYCLOAK_VER=""
REDIS_VER=""
POSTGRESQL_VER=""
RABBITMQ_VER=""

# Choose container tool (defaults to docker if available)
CONTAINER_BIN="${CONTAINER_BIN:-}"
if [[ -z "${CONTAINER_BIN}" ]]; then
  if command -v docker >/dev/null 2>&1; then
    CONTAINER_BIN="docker"
  elif command -v podman >/dev/null 2>&1; then
    CONTAINER_BIN="podman"
  else
    echo "Error: neither docker nor podman found in PATH." >&2
    exit 1
  fi
fi

# Add helm validation after the container tool check
if ! command -v helm >/dev/null 2>&1; then
  echo "Error: helm not found in PATH." >&2
  exit 1
fi

# Make sure the Bitnami Helm repo is added
if ! helm repo list | grep -qE '(^|[[:space:]])bitnami([[:space:]]|$)'; then
  helm repo add bitnami https://charts.bitnami.com/bitnami
fi
helm repo update

# Define output directories
ROOT_DIR="$(pwd)"
OUT_DIR="${ROOT_DIR}/bitnami_cache"
CHART_DIR="${OUT_DIR}/charts"
IMG_DIR="${OUT_DIR}/images"
LOG_DIR="${OUT_DIR}/logs"
mkdir -p "${CHART_DIR}" "${IMG_DIR}" "${LOG_DIR}"

# Check available disk space (recommend 3GB minimum)
REQUIRED_SPACE_GB=3
AVAILABLE_SPACE_KB=$(df --output=avail "${ROOT_DIR}" | tail -n1)
AVAILABLE_SPACE_GB=$((AVAILABLE_SPACE_KB / 1024 / 1024))

echo "Available disk space: ${AVAILABLE_SPACE_GB}GB"
if [[ ${AVAILABLE_SPACE_GB} -lt ${REQUIRED_SPACE_GB} ]]; then
  echo "Warning: Less than ${REQUIRED_SPACE_GB}GB available. Consider freeing up space." >&2
  echo "Estimated space needed: ~2GB for images + charts" >&2
  read -p "Continue anyway? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi

# ------------------------------------------------
# Pull a chart (optionally by version)
# ------------------------------------------------
pull_chart() {
  local chart_ref="$1"
  local chart_ver="${2:-}"
  local chart_name="$(basename "${chart_ref}")"
  
  # Check if chart already exists
  if ls "${CHART_DIR}/${chart_name}"-*.tgz >/dev/null 2>&1; then
    echo "Chart ${chart_ref} already cached, skipping download..."
    return
  fi
  
  if [[ -n "${chart_ver}" ]]; then
    echo "Pulling ${chart_ref} version ${chart_ver}..."
    helm pull "${chart_ref}" --version "${chart_ver}" --destination "${CHART_DIR}"
  else
    echo "Pulling latest ${chart_ref}..."
    helm pull "${chart_ref}" --destination "${CHART_DIR}"
  fi
}

# ------------------------------------------------
# Render a chart to extract image references
# ------------------------------------------------
render_and_list_images() {
  local release="$1"
  local tgz_path="$2"

  helm template "${release}" "${tgz_path}"     | grep -E '^[[:space:]]*image:[[:space:]]*'     | sed -E 's/^[[:space:]]*image:[[:space:]]*"?([^"]+)"?.*/\1/'     | sed -E 's/[[:space:]]+$//'     | sort -u
}

# ------------------------------------------------
# Pull and save an image to .tar
# ------------------------------------------------
save_image() {
  local image_ref="$1"
  local safe_name
  # replace / and : with underscores for file name
  safe_name="$(echo "${image_ref}" | tr '/:' '__')"
  local tar_path="${IMG_DIR}/${safe_name}.tar"

  if [[ -f "${tar_path}" ]]; then
    echo "Already saved: ${image_ref}"
    return
  fi

  echo "Pulling: ${image_ref}"
  "${CONTAINER_BIN}" pull "${image_ref}"

  echo "Saving: ${image_ref} -> ${tar_path}"
  "${CONTAINER_BIN}" save -o "${tar_path}" "${image_ref}"
}

# ------------------------------------------------
# Process one chart
# ------------------------------------------------
process_chart() {
  local name="$1"
  local chart_ref="$2"
  local chart_ver="$3"

  echo "============================================="
  echo "Chart: ${chart_ref} (${chart_ver:-latest})"

  pull_chart "${chart_ref}" "${chart_ver}"

  # find the newest pulled tgz file for this chart
  local tgz_path
  tgz_path="$(ls -1t "${CHART_DIR}"/"$(basename "${chart_ref}")"-*.tgz | head -n1)"

  # extract image list
  local img_list_file="${LOG_DIR}/${name}_images.txt"
  render_and_list_images "${name}" "${tgz_path}" | tee "${img_list_file}"

  # save each image
  while IFS= read -r img; do
    [[ -z "${img}" ]] && continue
    save_image "${img}"
  done < "${img_list_file}"

  echo "Done: ${name}"
  echo "Chart archive:    ${tgz_path}"
  echo "Image list:       ${img_list_file}"
  echo "Images saved in:  ${IMG_DIR}"
}

# ------------------------------------------------
# Run for all four charts
# ------------------------------------------------
process_chart "keycloak"   "bitnami/keycloak"   "${KEYCLOAK_VER}"
process_chart "redis"      "bitnami/redis"      "${REDIS_VER}"
process_chart "postgresql" "bitnami/postgresql" "${POSTGRESQL_VER}"
process_chart "rabbitmq"   "bitnami/rabbitmq"   "${RABBITMQ_VER}"

echo ""
echo "All done. Outputs under: ${OUT_DIR}"
echo "To install later without internet:"
echo "  1) Load images: ${CONTAINER_BIN} load -i ./bitnami_cache/images/<file>.tar"
echo "  2) Install chart: helm install <name> ./bitnami_cache/charts/<chart>.tgz -n <namespace>"
