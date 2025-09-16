# 1. Query ArtifactHub for the most recent chart version
LATEST=$(curl -fsSL "https://artifacthub.io/api/v1/packages/helm/bitnami/redis" | jq -r '.version')
echo "Latest chart version: $LATEST"

# 2. Install directly from the OCI registry using that version
helm install redis oci://registry-1.docker.io/bitnamicharts/redis \
  --version "$LATEST" \
  -n nevada --create-namespace
