#!/bin/bash

# Secret Extraction Examples Script
# Demonstrates different ways to extract secrets from Kubernetes

set -e

NAMESPACE="nevada"
SECRET_NAME="rabbitmq"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Kubernetes Secret Extraction Examples ===${NC}"
echo -e "${CYAN}Secret: $SECRET_NAME in namespace: $NAMESPACE${NC}"
echo ""

# Check if secret exists
if ! kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" >/dev/null 2>&1; then
    echo -e "${RED}Error: Secret '$SECRET_NAME' not found in namespace '$NAMESPACE'${NC}"
    exit 1
fi

echo -e "${YELLOW}1. Show the complete secret (base64 encoded):${NC}"
echo -e "${GREEN}Command:${NC} kubectl get secret -n $NAMESPACE $SECRET_NAME -o yaml"
kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" -o yaml
echo ""

echo -e "${YELLOW}2. Extract specific field with jsonpath (base64 encoded):${NC}"
echo -e "${GREEN}Command:${NC} kubectl get secret -n $NAMESPACE $SECRET_NAME -o jsonpath='{.data.rabbitmq-password}'"
PASSWORD_B64=$(kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" -o jsonpath='{.data.rabbitmq-password}')
echo "$PASSWORD_B64"
echo ""

echo -e "${YELLOW}3. Extract and decode in one command:${NC}"
echo -e "${GREEN}Command:${NC} kubectl get secret -n $NAMESPACE $SECRET_NAME -o jsonpath='{.data.rabbitmq-password}' | base64 -d"
PASSWORD_DECODED=$(kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" -o jsonpath='{.data.rabbitmq-password}' | base64 -d)
echo "$PASSWORD_DECODED"
echo ""

echo -e "${YELLOW}4. Using JSON output with jq (if available):${NC}"
if command -v jq >/dev/null 2>&1; then
    echo -e "${GREEN}Command:${NC} kubectl get secret -n $NAMESPACE $SECRET_NAME -o json | jq -r '.data[\"rabbitmq-password\"]' | base64 -d"
    kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" -o json | jq -r '.data["rabbitmq-password"]' | base64 -d
else
    echo -e "${RED}jq not installed - skipping this example${NC}"
fi
echo ""

echo -e "${YELLOW}5. Extract all data fields:${NC}"
echo -e "${GREEN}Command:${NC} kubectl get secret -n $NAMESPACE $SECRET_NAME -o jsonpath='{.data}'"
kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" -o jsonpath='{.data}'
echo ""
echo ""

echo -e "${YELLOW}6. Extract and decode all fields:${NC}"
echo -e "${GREEN}Password:${NC}"
echo "  Base64: $(kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" -o jsonpath='{.data.rabbitmq-password}')"
echo "  Decoded: $(kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" -o jsonpath='{.data.rabbitmq-password}' | base64 -d)"
echo ""
echo -e "${GREEN}Erlang Cookie:${NC}"
echo "  Base64: $(kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" -o jsonpath='{.data.rabbitmq-erlang-cookie}')"
echo "  Decoded: $(kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" -o jsonpath='{.data.rabbitmq-erlang-cookie}' | base64 -d)"
echo ""

echo -e "${YELLOW}7. Using kubectl get secret with --template (alternative):${NC}"
echo -e "${GREEN}Command:${NC} kubectl get secret -n $NAMESPACE $SECRET_NAME --template='{{index .data \"rabbitmq-password\"}}' | base64 -d"
echo -e "${CYAN}Note: Field names with hyphens need 'index' function in Go templates${NC}"
kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" --template='{{index .data "rabbitmq-password"}}' | base64 -d
echo ""
echo ""

echo -e "${YELLOW}8. Safe extraction with error handling:${NC}"
echo -e "${GREEN}Command:${NC} kubectl get secret -n $NAMESPACE $SECRET_NAME -o jsonpath='{.data.rabbitmq-password}' | base64 -d 2>/dev/null || echo 'Failed to decode'"
kubectl get secret -n "$NAMESPACE" "$SECRET_NAME" -o jsonpath='{.data.rabbitmq-password}' | base64 -d 2>/dev/null || echo 'Failed to decode'
echo ""

echo -e "${BLUE}=== Summary ===${NC}"
echo -e "${GREEN}Most common and reliable method:${NC}"
echo "kubectl get secret -n $NAMESPACE $SECRET_NAME -o jsonpath='{.data.rabbitmq-password}' | base64 -d"
echo ""
echo -e "${GREEN}With error handling (used in scripts):${NC}"
echo "kubectl get secret -n $NAMESPACE $SECRET_NAME -o jsonpath='{.data.rabbitmq-password}' | base64 -d 2>/dev/null || echo 'Check secret manually'"
