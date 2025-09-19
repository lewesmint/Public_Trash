#!/bin/bash

# RabbitMQ Port Forward Script
# This script sets up port forwarding for RabbitMQ services

set -e

NAMESPACE="nevada"
RABBITMQ_SERVICE="rabbitmq"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== RabbitMQ Port Forward Setup ===${NC}"

# Check if RabbitMQ service exists
if ! kubectl get svc -n "$NAMESPACE" "$RABBITMQ_SERVICE" >/dev/null 2>&1; then
    echo -e "${RED}Error: RabbitMQ service '$RABBITMQ_SERVICE' not found in namespace '$NAMESPACE'${NC}"
    echo "Available services:"
    kubectl get svc -n "$NAMESPACE"
    exit 1
fi

# Get service details
echo -e "${YELLOW}RabbitMQ Service Details:${NC}"
kubectl get svc -n "$NAMESPACE" "$RABBITMQ_SERVICE"

echo ""
echo -e "${YELLOW}Setting up port forwarding...${NC}"

# Kill any existing port forwards on these ports
echo "Cleaning up existing port forwards..."
pkill -f "kubectl.*port-forward.*rabbitmq" || true
sleep 2

# Set up port forwarding for RabbitMQ
echo -e "${GREEN}Starting RabbitMQ port forwards:${NC}"
echo "  - Management UI: http://localhost:15672"
echo "  - AMQP: localhost:5672"

# Start port forwarding in background
kubectl port-forward -n "$NAMESPACE" svc/"$RABBITMQ_SERVICE" 15672:15672 5672:5672 &
PF_PID=$!

# Wait a moment for port forward to establish
sleep 3

# Check if port forward is working
if ps -p $PF_PID > /dev/null; then
    echo -e "${GREEN}✅ Port forwarding established successfully!${NC}"
    echo ""
    echo -e "${BLUE}Access Information:${NC}"
    echo "  🌐 RabbitMQ Management UI: http://localhost:15672"
    echo "  🔌 AMQP Connection: amqp://localhost:5672"
    echo ""
    echo -e "${YELLOW}Default Credentials:${NC}"
    echo "  Username: user"
    echo "  Password: $(kubectl get secret -n "$NAMESPACE" rabbitmq -o jsonpath='{.data.rabbitmq-password}' | base64 -d 2>/dev/null || echo 'Check secret manually')"
    echo ""
    echo -e "${YELLOW}To stop port forwarding:${NC}"
    echo "  kill $PF_PID"
    echo "  or press Ctrl+C"
    echo ""
    echo "Port forwarding is running in background (PID: $PF_PID)"
    
    # Keep script running to maintain port forward
    wait $PF_PID
else
    echo -e "${RED}❌ Failed to establish port forwarding${NC}"
    exit 1
fi
