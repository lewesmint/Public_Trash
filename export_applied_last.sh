#!/usr/bin/env bash
set -euo pipefail

# Namespace to export (default: nevada)
NS="${1:-nevada}"

# Output folder
OUT="export-$NS"
mkdir -p "$OUT"

# ---- Dependency checks -------------------------------------------------------
need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: '$1' not found in PATH" >&2
    exit 1
  }
}
need kubectl
need yq

# Ensure Mike Farah yq v4+
if ! yq --version 2>/dev/null | grep -qE 'yq \(https://github.com/mikefarah/yq\) version 4\.'; then
  echo "error: this script requires Mike Farah yq v4.x" >&2
  echo "       see https://github.com/mikefarah/yq" >&2
  exit 1
fi

# ---- 00: Namespace manifest --------------------------------------------------
# Include a clear label to mark cloned namespaces. You can add annotations if you prefer.
cat > "$OUT/00-namespace.yaml" <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: $NS
  labels:
    cloned: "true"
EOF

# ---- Kinds to export (namespaced only) ---------------------------------------
KINDS=(
  deployment
  statefulset
  daemonset
  cronjob
  job
  service
  ingress
  configmap
  secret
  serviceaccount
  role
  rolebinding
  hpa
  pdb
  networkpolicy
  resourcequota
  limitrange
  pvc
)

# ---- Clean-up filter for live exported objects -------------------------------
# This is a yq (v4) expression. It deletes noisy/cluster-specific fields and
# handles kind-specific tweaks so re-apply works cleanly on a new cluster.
clean_filter='
  # Generic cleanup
  del(
    .metadata.annotations."kubectl.kubernetes.io/last-applied-configuration",
    .metadata.annotations."deployment.kubernetes.io/revision",
    .metadata.annotations."pv.kubernetes.io/bind-completed",
    .metadata.annotations."pv.kubernetes.io/bound-by-controller",
    .metadata.creationTimestamp,
    .metadata.resourceVersion,
    .metadata.uid,
    .metadata.generation,
    .metadata.managedFields,
    .status
  )
  |
  # Services: drop allocated IPs and nodePorts so the new cluster can allocate
  (if .kind == "Service" then
      .spec |= (
        del(.clusterIP, .clusterIPs, .healthCheckNodePort)
        | (if has("ports") then .ports |= map(del(.nodePort)) else . end)
        # Uncomment the next line if you want to strip any old external IPs as well
        # | del(.externalIPs)
      )
    else . end)
  |
  # PVCs: drop binding to old PVs and controller marks
  (if .kind == "PersistentVolumeClaim" then
      .metadata.annotations |= with_entries(select(.key | startswith("pv.kubernetes.io/") | not))
      | del(.spec.volumeName)
    else . end)
  |
  # Jobs: drop defaulted selectors that can conflict on re-apply
  (if .kind == "Job" then
      del(.spec.selector, .spec.manualSelector)
    else . end)
'

# ---- Export loop -------------------------------------------------------------
i=10

for kind in "${KINDS[@]}"; do
  # List object names for this kind (may be empty)
  mapfile -t objs < <(kubectl get "$kind" -n "$NS" -o name 2>/dev/null || true)
  ((${#objs[@]}==0)) && continue

  for obj in "${objs[@]}"; do
    base="${obj#*/}"                               # kind/name -> name
    file="$OUT/$(printf "%02d" "$i")-$kind.$base.yaml"

    # Skip auto-generated SA token Secrets entirely
    if [[ "$kind" == "secret" ]]; then
      stype="$(kubectl get -n "$NS" "$obj" -o jsonpath='{.type}' 2>/dev/null || true)"
      if [[ "$stype" == "kubernetes.io/service-account-token" ]]; then
        echo "skip SA token -> $obj"
        i=$((i+1))
        continue
      fi
    fi

    # Try to prefer the user's last-applied configuration (best for intent)
    if kubectl apply view-last-applied -n "$NS" "$obj" -o yaml > "$file" 2>/dev/null; then
      {
        echo "# source: last-applied"
        cat "$file"
      } > "$file.tmp" && mv "$file.tmp" "$file"
      echo "wrote last-applied -> $file"
    else
      # Fallback to cleaned live spec
      {
        echo "# source: live-export (no last-applied annotation)"
        kubectl get -n "$NS" "$obj" -o yaml --show-managed-fields=false | yq eval "$clean_filter" -
      } > "$file"
      echo "wrote live spec -> $file"
    fi

    # For Secrets with stringData omitted in last-applied, ensure stable output
    if [[ "$kind" == "secret" ]]; then
      # No-op guard: secrets might be base64 data only; we leave as-is.
      :
    fi

    i=$((i+1))
  done
done

# ---- Optional: write a kustomization.yaml for easy apply ---------------------
# This lets you do: kubectl apply -k "$OUT"
# We include 00-namespace.yaml explicitly first, then the rest in lexical order.
{
  echo "apiVersion: kustomize.config.k8s.io/v1beta1"
  echo "kind: Kustomization"
  echo "namespace: $NS"
  echo "resources:"
  echo "  - 00-namespace.yaml"
  # shellcheck disable=SC2012
  for f in $(ls -1 "$OUT"/*.yaml | sed 's#.*/##' | grep -v '^kustomization\.yaml$' | grep -v '^00-namespace\.yaml$'); do
    echo "  - $f"
  done
} > "$OUT/kustomization.yaml"

# ---- Summary and next steps --------------------------------------------------
echo
echo "Export complete in: $OUT"
echo
echo "Recreate with either:"
echo "  kubectl apply -f $OUT/00-namespace.yaml && kubectl apply -f $OUT"
echo "or"
echo "  kubectl apply -k $OUT"
