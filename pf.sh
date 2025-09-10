#!/usr/bin/env bash
# pf.sh - manage kubectl port-forwards for PostgreSQL and RabbitMQ (UI only)
# Usage:
#   ./pf.sh start
#   ./pf.sh stop
#   ./pf.sh restart
#   ./pf.sh status
#   ./pf.sh auto      # default if no arg given

set -euo pipefail

# ---- CONFIG ----
NS="xxx"                       # Kubernetes namespace
PG_SVC="postgresql"            # Service name for Postgres
RMQ_SVC="rabbitmq"             # Service name for RabbitMQ

PG_LOCAL_PORT=5432
RMQ_UI_LOCAL=15672

LOG_DIR="/tmp"
PG_LOG="${LOG_DIR}/pg-portfwd.log"
RMQ_LOG="${LOG_DIR}/rabbitmq-portfwd.log"

# ---- REQUIREMENTS ----
have_cmd() { command -v "$1" >/dev/null 2>&1; }
need_cmds() {
  for c in kubectl grep awk pkill pgrep nohup sed; do
    have_cmd "$c" || { echo "Missing command: $c"; exit 1; }
  done
}

# ---- PROCESS DETECTORS ----
is_running_pg()  { pgrep -f "kubectl port-forward.*svc/${PG_SVC}.* ${PG_LOCAL_PORT}:${PG_LOCAL_PORT}" >/dev/null; }
is_running_rmq() { pgrep -f "kubectl port-forward.*svc/${RMQ_SVC}.* ${RMQ_UI_LOCAL}:${RMQ_UI_LOCAL}" >/dev/null; }

# ---- TARGET RESOLUTION AND WAIT ----
wait_ready_dynamic() {
  local name="$1"   # logical app name, e.g. postgresql or rabbitmq
  local tried=""

  echo "Waiting for '${name}' pods in namespace '${NS}' to be Ready..."

  # Try modern label
  if kubectl get pods -n "${NS}" -l "app.kubernetes.io/name=${name}" --no-headers 2>/dev/null | grep -q .; then
    tried="${tried}[label app.kubernetes.io/name=${name}] "
    kubectl wait -n "${NS}" --for=condition=ready pod -l "app.kubernetes.io/name=${name}" --timeout=180s && return 0
  fi

  # Try legacy label
  if kubectl get pods -n "${NS}" -l "app=${name}" --no-headers 2>/dev/null | grep -q .; then
    tried="${tried}[label app=${name}] "
    kubectl wait -n "${NS}" --for=condition=ready pod -l "app=${name}" --timeout=180s && return 0
  fi

  # Fall back to pod name grep
  local pod
  pod="$(kubectl get pods -n "${NS}" -o name 2>/dev/null | grep -Ei "pod/.+${name}" | head -n1 || true)"
  if [ -n "${pod}" ]; then
    tried="${tried}[name match ${pod}] "
    kubectl wait -n "${NS}" --for=condition=ready "${pod}" --timeout=180s && return 0
  fi

  echo "Could not find a Ready pod for '${name}'. Tried: ${tried}"
  return 1
}

# ---- STARTERS ----
start_pg() {
  if is_running_pg; then
    echo "PostgreSQL forward already running on localhost:${PG_LOCAL_PORT}"
    return 0
  fi
  wait_ready_dynamic "postgresql"
  echo "Starting PostgreSQL forward svc/${PG_SVC} -> localhost:${PG_LOCAL_PORT}"
  nohup kubectl port-forward -n "${NS}" "svc/${PG_SVC}" "${PG_LOCAL_PORT}:${PG_LOCAL_PORT}" >"${PG_LOG}" 2>&1 &
  disown || true
  sleep 0.7
  if is_running_pg; then
    echo "PostgreSQL forward started. Log: ${PG_LOG}"
  else
    echo "Failed to start PostgreSQL forward. See log: ${PG_LOG}"
    return 1
  fi
}

start_rmq() {
  if is_running_rmq; then
    echo "RabbitMQ UI forward already running on localhost:${RMQ_UI_LOCAL}"
    return 0
  fi
  wait_ready_dynamic "rabbitmq"
  echo "Starting RabbitMQ forward svc/${RMQ_SVC} -> localhost:${RMQ_UI_LOCAL}"
  nohup kubectl port-forward -n "${NS}" "svc/${RMQ_SVC}" "${RMQ_UI_LOCAL}:${RMQ_UI_LOCAL}" >"${RMQ_LOG}" 2>&1 &
  disown || true
  sleep 0.7
  if is_running_rmq; then
    echo "RabbitMQ forward started. Log: ${RMQ_LOG}"
  else
    echo "Failed to start RabbitMQ forward. See log: ${RMQ_LOG}"
    return 1
  fi
}

# ---- STOPPERS ----
stop_pg() {
  if is_running_pg; then
    echo "Stopping PostgreSQL forward..."
    pkill -f "kubectl port-forward.*svc/${PG_SVC}.* ${PG_LOCAL_PORT}:${PG_LOCAL_PORT}" || true
  else
    echo "PostgreSQL forward not running."
  fi
}

stop_rmq() {
  if is_running_rmq; then
    echo "Stopping RabbitMQ forward..."
    pkill -f "kubectl port-forward.*svc/${RMQ_SVC}.* ${RMQ_UI_LOCAL}:${RMQ_UI_LOCAL}" || true
  else
    echo "RabbitMQ forward not running."
  fi
}

# ---- STATUS / FLOWS ----
status() {
  echo "Namespace: ${NS}"
  if is_running_pg; then
    echo "PostgreSQL: RUNNING on localhost:${PG_LOCAL_PORT} (log: ${PG_LOG})"
  else
    echo "PostgreSQL: STOPPED"
  fi
  if is_running_rmq; then
    echo "RabbitMQ UI: RUNNING on http://localhost:${RMQ_UI_LOCAL} (log: ${RMQ_LOG})"
  else
    echo "RabbitMQ UI: STOPPED"
  fi
}

start_missing() { start_pg; start_rmq; status; }
stop_all()      { stop_pg; stop_rmq; status; }
restart_all()   { echo "Restarting all port-forwards..."; stop_all; start_missing; }

auto_toggle() {
  if is_running_pg && is_running_rmq; then
    echo "Both forwards are running. Stopping them..."
    stop_all
  else
    echo "Starting any missing forwards..."
    start_missing
  fi
}

# ---- MAIN ----
need_cmds

case "${1:-auto}" in
  start)   start_missing ;;
  stop)    stop_all ;;
  restart) restart_all ;;
  status)  status ;;
  auto)    auto_toggle ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|auto}"
    exit 1
    ;;
esac
