#!/usr/bin/env bash
# list-registry.sh
# Usage: ./list-registry.sh [REGISTRY_HOST]
# Example: ./list-registry.sh localhost:5000

set -euo pipefail

REGISTRY="${1:-localhost:5000}"

# Get list of repositories
repos=$(curl -s "http://$REGISTRY/v2/_catalog" | jq -r '.repositories[]')

for repo in $repos; do
    echo "Repository: $repo"
    tags=$(curl -s "http://$REGISTRY/v2/$repo/tags/list" | jq -r '.tags[]?' || true)

    if [[ -z "$tags" ]]; then
        echo "  (no tags)"
    else
        for tag in $tags; do
            echo "  Tag: $tag"
        done
    fi
    echo
done
