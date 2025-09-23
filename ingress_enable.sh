#!/bin/bash
# Start with image caching if not already running

if ! minikube status | grep -q "host: Running"; then
  minikube start --cache-images
fi

# Enable addon
echo "Enabling ingress addon..."
minikube addons enable ingress

# Wait for resources to be created
echo "Waiting for ingress resources..."
timeout 300 bash -c 'until kubectl -n ingress-nginx get deployment/ingress-nginx-controller 2>/dev/null; do sleep 2; done'

# Discover all images
echo "Discovering required images..."
IMGS=$(kubectl -n ingress-nginx get all -o jsonpath='{range .items[*]}{.spec.template.spec.containers[*].image}{"\n"}{.spec.jobTemplate.spec.template.spec.containers[*].image}{"\n"}{end}' | sort | uniq | grep -v '^$')

# Parallel preload with progress
echo "Preloading images in parallel..."
for img in $IMGS; do
  (
    if ! minikube image ls --format=table | grep -q "$(basename "$img")"; then
      echo "→ Loading $img"
      minikube image load "$img" && echo "✓ Loaded $img"
    else
      echo "✓ $img already cached"
    fi
  ) &
done
wait

echo "✓ All images preloaded, waiting for pods..."
kubectl -n ingress-nginx wait --for=condition=ready pod --all --timeout=300s
