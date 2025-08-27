#!/usr/bin/env bash
set -euo pipefail

echo "🧹 Cleaning up Bitnami cache and Docker images..."

# Remove cached files
if [[ -d "./bitnami_cache" ]]; then
  echo "Removing ./bitnami_cache directory..."
  rm -rf ./bitnami_cache
  echo "✅ Cache directory removed"
else
  echo "ℹ️  No cache directory found"
fi

# Remove Docker images (if Docker is available)
if command -v docker >/dev/null 2>&1; then
  echo "Removing Docker images..."
  
  # Remove Bitnami images
  docker images --format "table {{.Repository}}:{{.Tag}}" | grep "bitnami/" | while read -r image; do
    if [[ -n "$image" && "$image" != "REPOSITORY:TAG" ]]; then
      echo "Removing: $image"
      docker rmi "$image" 2>/dev/null || echo "  (already removed or in use)"
    fi
  done
  
  echo "✅ Docker images cleaned"
else
  echo "ℹ️  Docker not found, skipping image cleanup"
fi

# Remove Helm repo
if command -v helm >/dev/null 2>&1; then
  echo "Removing Bitnami Helm repository..."
  helm repo remove bitnami 2>/dev/null || echo "ℹ️  Bitnami repo not found"
  echo "✅ Helm repo cleaned"
else
  echo "ℹ️  Helm not found, skipping repo cleanup"
fi

# Clean up any downloaded Helm installer
if [[ -f "./get_helm.sh" ]]; then
  echo "Removing Helm installer script..."
  rm -f ./get_helm.sh
  echo "✅ Helm installer removed"
fi

echo ""
echo "🎉 Cleanup complete! You can now run cache_bitnami.sh from scratch."
echo ""
echo "Note: This script does NOT uninstall Docker or Helm themselves."
echo "To completely start over, you would also need to:"
echo "  - Remove Docker: sudo snap remove docker"
echo "  - Remove Helm: sudo snap remove helm"
