#!/usr/bin/env bash
set -euo pipefail

# Requirements: helm, kubectl, curl, jq
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1"; exit 1; }; }
need helm; need kubectl; need curl; need jq

NS="nevada"
OCI_BASE="oci://registry-1.docker.io/bitnamicharts"

# Create namespace if it does not exist
kubectl get ns "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

# Helper to fetch the latest chart version from ArtifactHub
latest_ver() {
  # $1 = package name on ArtifactHub, e.g. redis, postgresql, rabbitmq, keycloak
  curl -fsSL "https://artifacthub.io/api/v1/packages/helm/bitnami/$1" | jq -r '.version'
}

echo "Resolving latest chart versions from ArtifactHub..."
REDIS_VER=$(latest_ver redis)
POSTGRES_VER=$(latest_ver postgresql)
RABBIT_VER=$(latest_ver rabbitmq)
KEYCLOAK_VER=$(latest_ver keycloak)

echo "Redis chart:        $REDIS_VER"
echo "PostgreSQL chart:   $POSTGRES_VER"
echo "RabbitMQ chart:     $RABBIT_VER"
echo "Keycloak chart:     $KEYCLOAK_VER"

echo
echo "Installing charts from Bitnami OCI registry into namespace '$NS'..."

# Redis
helm install redis "$OCI_BASE/redis" \
  --version "$REDIS_VER" \
  -n "$NS" --create-namespace

# PostgreSQL
helm install postgresql "$OCI_BASE/postgresql" \
  --version "$POSTGRES_VER" \
  -n "$NS"

# RabbitMQ
helm install rabbitmq "$OCI_BASE/rabbitmq" \
  --version "$RABBIT_VER" \
  -n "$NS"

# Keycloak
helm install keycloak "$OCI_BASE/keycloak" \
  --version "$KEYCLOAK_VER" \
  -n "$NS"

echo
echo "Done. Checking status..."
helm list -n "$NS"
kubectl get pods,svc -n "$NS"
