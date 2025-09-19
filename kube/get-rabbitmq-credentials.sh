#!/usr/bin/env bash

# Get RabbitMQ credentials
# Usage: ./get-rabbitmq-credentials.sh [namespace]

NAMESPACE="${1:-default}"

# Get username from StatefulSet
USERNAME=$(kubectl get statefulset -n "$NAMESPACE" rabbitmq -o json | \
  jq -r '.spec.template.spec.containers[0].env[] |
         select(.name=="RABBITMQ_USERNAME") |
         .value' 2>/dev/null || echo "user")

# Get password from Secret using jq
PASSWORD=$(kubectl get secret -n "$NAMESPACE" rabbitmq -o json | \
  jq -r '.data["rabbitmq-password"]' | \
  base64 -d)

echo "Username: $USERNAME"
echo "Password: $PASSWORD"
