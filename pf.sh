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

# If set to 1, will try to start minikube if it is stopped
AUTO_START_MINIKUBE="${AUTO_START_MINIKUBE:-0}"

# ---- REQUIREMENTS ----
have_cmd() { command -v "$1" >/dev/null 2>&1; }
need_cmds() {
  for c in kubectl grep awk pgrep pkill nohup sed; do
    have_cmd "$c" || { echo "Missing command: $c"; exit 1; }
  done
}

# ---- CLUSTER CHECK ----
check_cluster() {
  local ctx cur is_mk mk_ok=0
  cur="$(kubectl config current-context 2>/dev/null || true)"
  is_mk=0
  if have_cmd minikube && [ "${cur}" = "minikube" ]; then
    is_mk=1
    # Quick status check without waiting
    if minikube status --wait=false 2>/dev/null | grep -qi "Running"; then
      mk_ok=1
    fi
    if [ $mk_ok -eq 0 ]; then
      if [ "${AUTO_START_MINIKUBE}" = "1" ]; then
        echo "Minikube is not running. Starting it now..."
        minikube start
      else
        echo "Minikube context detected but it is not running."
        echo "Start it with: minikube start"
        echo "Or set AUTO_START_MINIKUBE=1 and rerun."
        exit 1
      fi
    fi
  fi

  # Verify API is reachable (covers non-Minikube contexts too)
  if ! kubectl version --request-timeout=3s >/dev/null 2>&1; then
    echo "Kubernetes API is not reachable for context '${cur}'."
    echo "Check your kubeconfig or start your cluster, then retry."
    [ $is_mk -eq 1 ] && echo "(If you meant to use Minikube, run 'minikube start'.)"
    exit 1
  fi
}

# ---- PROCESS DETECTORS ----
is_running_pg()  { pgrep -f "kubectl port-forward.*svc/${PG_SVC}.* ${PG_LOCAL_PORT}:${PG_LOCAL_PORT}" >/dev/null; }
is_running_rmq() { pgrep -f "kubectl port-forward.*svc/${RMQ_SVC}.* ${RMQ_UI_LOCAL}:${RMQ_UI_LOCAL}" >/dev/null; }

# ---- TARGET RESOLUTION AND WAIT ----
wait_ready_dynamic() {
  local name="$1"
  local tried=""

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
  is_running_pg && echo "PostgreSQL forward started. Log: ${PG_LOG}" || { echo "Failed to start PostgreSQL forward. See log: ${PG_LOG}"; return 1; }
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
  is_running_rmq && echo "RabbitMQ forward started. Log: ${RMQ_LOG}" || { echo "Failed to start RabbitMQ forward. See log: ${RMQ_LOG}"; return 1; }
}

# ---- STOPPERS ----
stop_pg()  { is_running_pg  && { echo "Stopping PostgreSQL forward..."; pkill -f "kubectl port-forward.*svc/${PG_SVC}.* ${PG_LOCAL_PORT}:${PG_LOCAL_PORT}" || true; } || echo "PostgreSQL forward not running."; }
stop_rmq() { is_running_rmq && { echo "Stopping RabbitMQ forward...";  pkill -f "kubectl port-forward.*svc/${RMQ_SVC}.* ${RMQ_UI_LOCAL}:${RMQ_UI_LOCAL}" || true; }  || echo "RabbitMQ forward not running."; }

# ---- STATUS / FLOWS ----
status() {
  echo "Namespace: ${NS}"
  is_running_pg  && echo "PostgreSQL: RUNNING on localhost:${PG_LOCAL_PORT} (log: ${PG_LOG})" || echo "PostgreSQL: STOPPED"
  is_running_rmq && echo "RabbitMQ UI: RUNNING on http://localhost:${RMQ_UI_LOCAL} (log: ${RMQ_LOG})" || echo "RabbitMQ UI: STOPPED"
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
check_cluster

case "${1:-auto}" in
  start)   start_missing ;;
  stop)    stop_all ;;
  restart) restart_all ;;
  status)  status ;;
  auto)    auto_toggle ;;
  *) echo "Usage: $0 {start|stop|restart|status|auto}"; exit 1 ;;
esac
