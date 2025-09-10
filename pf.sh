#!/usr/bin/env bash
# pf.sh - manage kubectl port-forwards for PostgreSQL and RabbitMQ
# Usage:
#   ./pf.sh start    # start any missing forwards
#   ./pf.sh stop     # stop any running forwards
#   ./pf.sh status   # show state
#   ./pf.sh restart  # stop and then start them again
#   ./pf.sh auto     # if all running -> stop; otherwise start missing

set -euo pipefail

# ---- CONFIG ----
NS="xxx"                       # Kubernetes namespace
PG_SVC="postgresql"            # Service name for Postgres
RMQ_SVC="rabbitmq"             # Service name for RabbitMQ
PG_LOCAL_PORT=5432
RMQ_AMQP_LOCAL=5672
RMQ_UI_LOCAL=15672
LOG_DIR="/tmp"
PG_LOG="${LOG_DIR}/pg-portfwd.log"
RMQ_LOG="${LOG_DIR}/rabbitmq-portfwd.log"

# Pod label selectors (adjust if your charts use different labels)
PG_SELECTOR="app=postgresql"
RMQ_SELECTOR="app=rabbitmq"

# ---- HELPERS ----
have_cmd() { command -v "$1" >/dev/null 2>&1; }

need_cmds() {
  for c in kubectl grep awk pkill pgrep nohup; do
    have_cmd "$c" || { echo "Missing command: $c"; exit 1; }
  done
}

is_running_pg()   { pgrep -f "kubectl port-forward.*svc/${PG_SVC}.* ${PG_LOCAL_PORT}:${PG_LOCAL_PORT}" >/dev/null; }
is_running_rmq()  { pgrep -f "kubectl port-forward.*svc/${RMQ_SVC}.* ${RMQ_AMQP_LOCAL}:${RMQ_AMQP_LOCAL} .* ${RMQ_UI_LOCAL}:${RMQ_UI_LOCAL}" >/dev/null; }

wait_ready() {
  local selector="$1"
  echo "Waiting for pods with selector '${selector}' in namespace '${NS}' to be Ready..."
  kubectl wait -n "${NS}" --for=condition=ready pod -l "${selector}" --timeout=120s
}

start_pg() {
  if is_running_pg; then
    echo "PostgreSQL forward already running on localhost:${PG_LOCAL_PORT}"
    return 0
  fi
  wait_ready "${PG_SELECTOR}"
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
    echo "RabbitMQ forward already running on localhost:${RMQ_AMQP_LOCAL} and :${RMQ_UI_LOCAL}"
    return 0
  fi
  wait_ready "${RMQ_SELECTOR}"
  echo "Starting RabbitMQ forward svc/${RMQ_SVC} -> localhost:${RMQ_AMQP_LOCAL} and :${RMQ_UI_LOCAL}"
  nohup kubectl port-forward -n "${NS}" "svc/${RMQ_SVC}" \
    "${RMQ_AMQP_LOCAL}:${RMQ_AMQP_LOCAL}" "${RMQ_UI_LOCAL}:${RMQ_UI_LOCAL}" >"${RMQ_LOG}" 2>&1 &
  disown || true
  sleep 0.7
  if is_running_rmq; then
    echo "RabbitMQ forward started. Log: ${RMQ_LOG}"
  else
    echo "Failed to start RabbitMQ forward. See log: ${RMQ_LOG}"
    return 1
  fi
}

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
    pkill -f "kubectl port-forward.*svc/${RMQ_SVC}.* ${RMQ_AMQP_LOCAL}:${RMQ_AMQP_LOCAL} .* ${RMQ_UI_LOCAL}:${RMQ_UI_LOCAL}" || true
  else
    echo "RabbitMQ forward not running."
  fi
}

status() {
  echo "Namespace: ${NS}"
  if is_running_pg; then
    echo "PostgreSQL: RUNNING on localhost:${PG_LOCAL_PORT}"
  else
    echo "PostgreSQL: STOPPED"
  fi
  if is_running_rmq; then
    echo "RabbitMQ:   RUNNING on localhost:${RMQ_AMQP_LOCAL}, http://localhost:${RMQ_UI_LOCAL}"
  else
    echo "RabbitMQ:   STOPPED"
  fi
}

start_missing() {
  start_pg
  start_rmq
  status
}

stop_all() {
  stop_pg
  stop_rmq
  status
}

restart_all() {
  echo "Restarting all port-forwards..."
  stop_all
  start_missing
}

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
