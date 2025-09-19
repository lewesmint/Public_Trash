#!/usr/bin/env bash
# build-local.sh - safe Maven install that never pushes

set -euo pipefail

# Generate a unique dev tag (username + timestamp)
DEV_TAG="dev-$(whoami)-$(date +%Y%m%d%H%M)"

echo ">>> Building with safe local tag: $DEV_TAG"

mvn clean install -DskipTests \
  -Dquarkus.container-image.build=true \
  -Dquarkus.container-image.push=false \
  -Dquarkus.container-image.tag="$DEV_TAG" \
  "$@"

echo ">>> Build complete. Image tagged as: $DEV_TAG"
echo ">>> No push was attempted."
