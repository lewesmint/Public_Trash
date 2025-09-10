#!/usr/bin/env bash
# pf.sh - manage kubectl port-forwards for PostgreSQL and RabbitMQ (UI only)

set -euo pipefail

# ---- CONFIG ----
NS="xxx"
PG_SVC="postgresql"
RMQ_SVC="rabbitmq"

PG_LOCAL_PORT=5432
RMQ_UI_LOCAL=15672

LOG_DIR="/tmp"
PG_LOG="${LOG_DIR}/pg-portfwd.log"
RMQ_LOG="${LOG_DIR}/rabbitmq-portfwd.log"

# Behaviour controls
AUTO_START_MINIKUBE="${AUTO_START_MINIKUBE:-0}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-300}"
WAIT_INTERVAL="${WAIT_INTERVAL:-5}"

# ---- REQUIREMENTS ----
have_cmd() { command -v "$1" >/dev/null 2>&1; }
need_cmds() {
  for c in kubectl grep awk pgrep pkill nohup sed date; do
    have_cmd "$c" || { echo "Missing command: $c"; exit 1; }
  done
  if have_cmd minikube; then :; else echo "Warning: minikube not found in PATH."; fi
}

# ---- CLUSTER WAIT LOOP ----
wait_for_cluster() {
  local ctx cur start now elapsed
  cur="$(kubectl config current-context 2>/dev/null || true)"
  start="$(date +%s)"

  # If current context is minikube, ensure it is running
  if [ "$cur" = "minikube" ] && have_cmd minikube; then
    while true; do
      if minikube status --wait=false 2>/dev/null | grep -qi "Running"; then
        # Check API
        if kubectl version --request-timeout=3s >/dev/null 2>&1; then
          return 0
        fi
      else
        if [ "$AUTO_START_MINIKUBE" = "1" ]; then
          echo "Minikube not running. Starting..."
          minikube start || true
        fi
      fi
      now="$(date +%s)"; elapsed=$(( now - start ))
      if [ "$elapsed" -ge "$WAIT_TIMEOUT" ]; then
        echo "Timed out waiting for Minikube and API (context: $cur)."
        echo "Start it manually with: minikube start"
        exit 1
      fi
      sleep "$WAIT_INTERVAL"
    done
  fi

  # Non-minikube context: just wait for API
  start="$(date +%s)"
  while true; do
    if kubectl version --request-timeout=3s >/dev/null 2>&1; then
      return 0
    fi
    now="$(date +%s)"; elapsed=$(( now - start ))
    if [ "$elapsed" -ge "$WAIT_TIMEOUT" ]; then
      echo "Timed out waiting for Kubernetes API (context: $cur)."
      echo "Check your kubeconfig or cluster status."
      exit 1
    fi
    sleep "$WAIT_INTERVAL"
  done
}

# ---- PROCESS DETECTORS ----
is_running_pg()  { pgrep -f "kubectl port-forward.*svc/${PG_SVC}.* ${PG_LOCAL_PORT}:${PG_LOCAL_PORT}" >/dev/null; }
is_running_rmq() { pgrep -f "kubectl port-forward.*svc/${RMQ_SVC}.* ${RMQ_UI_LOCAL}:${RMQ_UI_LOCAL}" >/dev/null; }

# ---- POD READY HELPERS ----
wait_ready_dynamic() {
  local name="$1" tried=""

  echo "Waiting for '${name}' pods in namespace '${NS}' to be Ready..."

  if kubectl get pods -n "${NS}" -l "app.kubernetes.io/name=${name}" --no-headers 2>/dev/null | grep -q .; then
    tried="${tried}[label app.kubernetes.io/name=${name}] "
    kubectl wait -n "${NS}" --for=condition=ready pod -l "app.kubernetes.io/name=${name}" --timeout=180s && return 0
  fi
  if kubectl get pods -n "${NS}" -l "app=${name}" --no-headers 2>/dev/null | grep -q .; then
    tried="${tried}[label app=${name}] "
    kubectl wait -n "${NS}" --for=condition=ready pod -l "app=${name}" --timeout=180s && return 0
  fi
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
stop_pg()  { is_running_pg  && { echo "Stopping PostgreSQL forward..."; pkill -f "kubectl port-forward.*svc/${PG_SVC}.* ${PG_LOCAL_PORT}:${PG_LOCAL_PORT}" || true; } || echo "PostgreSQL forward not running."; }
stop_rmq() { is_running_rmq && { echo "Stopping RabbitMQ forward...";  pkill -f "kubectl port-forward.*svc/${RMQ_SVC}.* ${RMQ_UI_LOCAL}:${RMQ_UI_LOCAL}" || true; }  || echo "RabbitMQ forward not running."; }

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
wait_for_cluster

case "${1:-auto}" in
  start)   start_missing ;;
  stop)    stop_all ;;
  restart) restart_all ;;
  status)  status ;;
  auto)    auto_toggle ;;
  *) echo "Usage: $0 {start|stop|restart|status|auto}"; exit 1 ;;
esac
