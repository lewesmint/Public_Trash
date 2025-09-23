#!/usr/bin/env bash

# Get credentials for RabbitMQ and Graylog services
# Usage: ./get-all-credentials.sh [rabbitmq-namespace] [graylog-namespace] [keycloak-namespace]

RABBITMQ_NAMESPACE="${1:-nevada}"
GRAYLOG_NAMESPACE="${2:-graylog}"
KEYCLOAK_NAMESPACE="${3:-nevada}"

echo "=== Service Credentials ==="
echo ""

echo "RabbitMQ (namespace: $RABBITMQ_NAMESPACE)"
echo "----------------------------------------"

# Get RabbitMQ username from StatefulSet environment variables
RABBITMQ_USERNAME=$(kubectl get statefulset -n "$RABBITMQ_NAMESPACE" rabbitmq -o json | \
  jq -r '.spec.template.spec.containers[0].env[] | 
         select(.name=="RABBITMQ_USERNAME") | 
         .value' 2>/dev/null || echo "user")

# Get RabbitMQ password from Secret
RABBITMQ_PASSWORD=$(kubectl get secret -n "$RABBITMQ_NAMESPACE" rabbitmq \
  -o jsonpath='{.data.rabbitmq-password}' | \
  base64 -d 2>/dev/null || echo "Check secret manually")

echo "Username: $RABBITMQ_USERNAME"
echo "Password: $RABBITMQ_PASSWORD"
echo ""

echo "Graylog (namespace: $GRAYLOG_NAMESPACE)"
echo "----------------------------------------"

# Get Graylog username from Secret
GRAYLOG_USERNAME=$(kubectl get secret --namespace "$GRAYLOG_NAMESPACE" graylog \
  -o jsonpath="{.data.graylog-root-username}" | \
  base64 -d 2>/dev/null || echo "admin")

# Get Graylog password from Secret
GRAYLOG_PASSWORD=$(kubectl get secret --namespace "$GRAYLOG_NAMESPACE" graylog \
  -o jsonpath="{.data.graylog-password-secret}" | \
  base64 -d 2>/dev/null || echo "Check secret manually")

echo "Username: $GRAYLOG_USERNAME"
echo "Password: $GRAYLOG_PASSWORD"
echo ""

echo "Keycloak (namespace: $KEYCLOAK_NAMESPACE)"
echo "----------------------------------------"

# Keycloak username is hardcoded as admin
KEYCLOAK_USERNAME="admin"

# Get Keycloak password from Secret
KEYCLOAK_PASSWORD=$(kubectl get secret -n "$KEYCLOAK_NAMESPACE" keycloak \
  -o jsonpath='{.data.admin-password}' | \
  base64 -d 2>/dev/null || echo "Check secret manually")

# Get Keycloak PostgreSQL password (from the main postgresql secret)
KEYCLOAK_DB_PASSWORD=$(kubectl get secret -n "$KEYCLOAK_NAMESPACE" postgresql \
  -o jsonpath='{.data.postgres-password}' | \
  base64 -d 2>/dev/null || echo "Check secret manually")

echo "Username: $KEYCLOAK_USERNAME"
echo "Password: $KEYCLOAK_PASSWORD"
echo "Database Password: $KEYCLOAK_DB_PASSWORD"
echo ""

echo "Access Information"
echo "----------------------------------------"
echo "RabbitMQ Management UI:"
echo "  kubectl port-forward -n $RABBITMQ_NAMESPACE svc/rabbitmq 15672:15672"
echo "  Then open: http://localhost:15672"
echo ""
echo "Graylog Web UI:"
echo "  http://graylog.nevada.local (if ingress configured)"
echo "  Or: kubectl port-forward -n $GRAYLOG_NAMESPACE svc/graylog 9000:9000"
echo "  Then open: http://localhost:9000"
echo ""
echo "Keycloak Web UI:"
echo "  User UI: http://auth.minikube/auth/"
echo "  Admin UI: http://admin.auth.minikube/auth/admin/"
echo "  Or: kubectl port-forward -n $RABBITMQ_NAMESPACE svc/keycloak 8080:80"
echo "  Then open: http://localhost:8080/auth/"
echo ""
echo "RabbitMQ AMQP:"
echo "  External: $(minikube ip):5672 (if ingress TCP configured)"
echo "  Internal: rabbitmq.$RABBITMQ_NAMESPACE.svc.cluster.local:5672"
