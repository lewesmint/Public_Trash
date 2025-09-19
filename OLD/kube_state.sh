#!/usr/bin/env bash
# check-everything.sh
# Combined systemd + Kubernetes health check with a concise summary and exit code.
# Usage examples:
#   ./check-everything.sh
#   ./check-everything.sh --services docker,kubelet,containerd
#   ./check-everything.sh -n nevada
#   ./check-everything.sh --all-namespaces
#   SERVICES="docker,kubelet" NAMESPACES="default,nevada" ./check-everything.sh

set -euo pipefail

# -----------------------
# Defaults and arguments
# -----------------------
SERVICES="${SERVICES:-}"                 # env override e.g. SERVICES="docker,kubelet"
NAMESPACES="${NAMESPACES:-}"             # env override e.g. NAMESPACES="default,nevada"
ALL_NS=false

print_usage() {
  cat <<'USAGE'
check-everything.sh

Options:
  -s, --services CSV     Comma-separated systemd services to check (e.g. docker,kubelet)
  -n, --namespaces CSV   Comma-separated Kubernetes namespaces to check
      --all-namespaces   Check all namespaces
  -h, --help             Show this help

You can also use env vars:
  SERVICES="docker,kubelet" NAMESPACES="default,nevada" ./check-everything.sh
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--services)    SERVICES="$2"; shift 2;;
    -n|--namespaces)  NAMESPACES="$2"; shift 2;;
    --all-namespaces) ALL_NS=true; shift;;
    -h|--help)        print_usage; exit 0;;
    *) echo "Unknown arg: $1"; print_usage; exit 2;;
  esac
done

# -----------------------
# Helpers
# -----------------------
OK=0
WARN=0
FAIL=0

green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$*"; }
plain() { printf "%s\n" "$*"; }

inc_fail(){ FAIL=$((FAIL+1)); }
inc_warn(){ WARN=$((WARN+1)); }
inc_ok(){ OK=$((OK+1)); }

have() { command -v "$1" >/dev/null 2>&1; }

# -----------------------
# Systemd checks
# -----------------------
check_systemd_services() {
  if [[ -z "${SERVICES}" ]]; then
    yellow "Systemd: no services specified (skip). Use --services or SERVICES env to enable."
    return 0
  fi
  if ! have systemctl; then
    yellow "Systemd: systemctl not found (skip)."
    return 0
  fi

  IFS=',' read -r -a SVC_ARR <<< "$SERVICES"
  plain "== System services =="
  for svc in "${SVC_ARR[@]}"; do
    svc="$(echo "$svc" | xargs)"  # trim
    if systemctl is-active --quiet "$svc"; then
      green "OK  $svc is active"
      inc_ok
    else
      red   "FAIL $svc is NOT active"
      inc_fail
    fi
  done
  echo
}

# -----------------------
# Kubernetes checks
# -----------------------
kubectl_or_skip() {
  if ! have kubectl; then
    yellow "Kubernetes: kubectl not found (skip all k8s checks)."
    return 1
  fi
  if ! kubectl version --client >/dev/null 2>&1; then
    yellow "Kubernetes: kubectl unusable (skip)."
    return 1
  fi
  return 0
}

pick_namespaces() {
  if $ALL_NS; then
    kubectl get ns -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
  elif [[ -n "${NAMESPACES}" ]]; then
    echo "$NAMESPACES" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
  else
    # default to current namespace or "default"
    ns="$(kubectl config view --minify -o jsonpath='{..namespace}' 2>/dev/null || true)"
    [[ -z "$ns" ]] && ns="default"
    echo "$ns"
  fi
}

check_nodes() {
  plain "== Cluster nodes =="
  # Any NotReady nodes are failures
  if kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.conditions[-1].type}{"="}{.status.conditions[-1].status}{"\n"}{end}' 2>/dev/null \
    | awk 'BEGIN{bad=0} {if ($2=="Ready=False" || $2=="Ready=Unknown") {print "FAIL " $1 " not Ready"; bad++}} END{exit bad}' ; then
    green "OK  all nodes Ready"
    inc_ok
  else
    inc_fail
  fi
  echo
}

check_workloads_in_ns() {
  local ns="$1"
  plain "-- Namespace: $ns --"

  # Deployments
  kubectl get deploy -n "$ns" --no-headers 2>/dev/null | awk 'BEGIN{n=0} {n++} END{if(n==0) print "No Deployments"}'
  kubectl get deploy -n "$ns" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.readyReplicas}/{.status.replicas}{"\n"}{end}' 2>/dev/null \
    | awk -v ns="$ns" '
      NF==0 { next }
      {
        split($2,a,"/"); ready=a[1]; desired=a[2];
        if (desired=="" || desired==0) {
          printf "WARN %s: desired replicas is 0\n", $1;
          warn++
        } else if (ready!=desired) {
          printf "FAIL %s: %s ready\n", $1, $2;
          fail++
        } else {
          printf "OK  %s: %s ready\n", $1, $2;
          ok++
        }
      }
      END{
        if (ok)  printf "__OK__:%d\n", ok;
        if (warn)printf "__WARN__:%d\n", warn;
        if (fail)printf "__FAIL__:%d\n", fail;
      }' \
    | while read -r line; do
        case "$line" in
          __OK__:* ) inc_ok;;
          __WARN__:* ) inc_warn;;
          __FAIL__:* ) inc_fail;;
          OK* )   green "$line";;
          WARN* ) yellow "$line";;
          FAIL* ) red "$line";;
          * )     plain "$line";;
        esac
      done

  # StatefulSets
  kubectl get sts -n "$ns" --no-headers 2>/dev/null | awk 'BEGIN{n=0} {n++} END{if(n==0) print "No StatefulSets"}'
  kubectl get sts -n "$ns" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.readyReplicas}/{.status.replicas}{"\n"}{end}' 2>/dev/null \
    | awk -v ns="$ns" '
      NF==0 { next }
      {
        split($2,a,"/"); ready=a[1]; desired=a[2];
        if (desired=="" || desired==0) {
          printf "WARN %s: desired replicas is 0\n", $1; warn++
        } else if (ready!=desired) {
          printf "FAIL %s: %s ready\n", $1, $2; fail++
        } else {
          printf "OK  %s: %s ready\n", $1, $2; ok++
        }
      }
      END{
        if (ok)  printf "__OK__:%d\n", ok;
        if (warn)printf "__WARN__:%d\n", warn;
        if (fail)printf "__FAIL__:%d\n", fail;
      }' \
    | while read -r line; do
        case "$line" in
          __OK__:* ) inc_ok;;
          __WARN__:* ) inc_warn;;
          __FAIL__:* ) inc_fail;;
          OK* )   green "$line";;
          WARN* ) yellow "$line";;
          FAIL* ) red "$line";;
          * )     plain "$line";;
        esac
      done

  # DaemonSets
  kubectl get ds -n "$ns" --no-headers 2>/dev/null | awk 'BEGIN{n=0} {n++} END{if(n==0) print "No DaemonSets"}'
  kubectl get ds -n "$ns" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.numberReady}/{.status.desiredNumberScheduled}{"\n"}{end}' 2>/dev/null \
    | awk '
      NF==0 { next }
      {
        split($2,a,"/"); ready=a[1]; desired=a[2];
        if (desired=="" || desired==0) {
          printf "WARN %s: desired scheduled is 0\n", $1; warn++
        } else if (ready!=desired) {
          printf "FAIL %s: %s ready\n", $1, $2; fail++
        } else {
          printf "OK  %s: %s ready\n", $1, $2; ok++
        }
      }
      END{
        if (ok)  printf "__OK__:%d\n", ok;
        if (warn)printf "__WARN__:%d\n", warn;
        if (fail)printf "__FAIL__:%d\n", fail;
      }' \
    | while read -r line; do
        case "$line" in
          __OK__:* ) inc_ok;;
          __WARN__:* ) inc_warn;;
          __FAIL__:* ) inc_fail;;
          OK* )   green "$line";;
          WARN* ) yellow "$line";;
          FAIL* ) red "$line";;
          * )     plain "$line";;
        esac
      done

  # Quick pod sanity: CrashLoopBackOff or ImagePullBackOff in namespace
  kubectl get pods -n "$ns" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\t"}{range .status.containerStatuses[*]}{.state.waiting.reason}{" "}{end}{"\n"}{end}' 2>/dev/null \
    | awk '
      $0 ~ /CrashLoopBackOff|ImagePullBackOff|ErrImagePull|CreateContainerConfigError/ {
        printf "FAIL pod %s: %s\n", $1, $0; fail++
      }
      END{
        if (fail) printf "__FAIL__:%d\n", fail;
      }' \
    | while read -r line; do
        case "$line" in
          __FAIL__:* ) inc_fail;;
          FAIL* ) red "$line";;
          * ) : ;;
        esac
      done

  echo
}

check_kubernetes() {
  kubectl_or_skip || return 0

  # Context info
  ctx="$(kubectl config current-context 2>/dev/null || true)"
  if [[ -n "$ctx" ]]; then
    plain "== Kubernetes context: $ctx =="
  else
    yellow "Kubernetes: no current context set."
  fi

  # Node readiness
  if kubectl get nodes >/dev/null 2>&1; then
    check_nodes
  fi

  # Namespaces to check
  mapfile -t NS_ARR < <(pick_namespaces)
  if [[ ${#NS_ARR[@]} -eq 0 ]]; then
    yellow "Kubernetes: no namespaces to check."
    return 0
  fi

  for ns in "${NS_ARR[@]}"; do
    check_workloads_in_ns "$ns"
  done
}

# -----------------------
# Run
# -----------------------
check_systemd_services
check_kubernetes

# -----------------------
# Summary + exit code
# -----------------------
plain "== Summary =="
plain "OK:   $OK"
plain "WARN: $WARN"
plain "FAIL: $FAIL"

if [[ $FAIL -gt 0 ]]; then
  red   "Overall: FAIL"
  exit 1
elif [[ $WARN -gt 0 ]]; then
  yellow "Overall: WARN"
  exit 0
else
  green "Overall: OK"
  exit 0
fi
