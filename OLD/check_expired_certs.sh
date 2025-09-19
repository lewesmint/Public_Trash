#!/usr/bin/env bash
set -euo pipefail

ROOT="/usr/local/share/ca-certificates"

echo "🔍 Checking for expired certificates under $ROOT ..."

now_epoch=$(date +%s)

# Track certs
declare -A newest_valid_by_pair
declare -A newest_any_by_pair
declare -A expired_list

canon() {
  sed -E 's/[[:space:]]+/ /g' | sed -E 's/^ //; s/ $//'
}

while IFS= read -r -d '' f; do
  if ! subj=$(openssl x509 -in "$f" -noout -subject 2>/dev/null); then continue; fi
  if ! issr=$(openssl x509 -in "$f" -noout -issuer  2>/dev/null);  then continue; fi
  if ! endd=$(openssl x509 -in "$f" -noout -enddate 2>/dev/null);  then continue; fi

  subj_val=$(echo "${subj#subject=}" | canon)
  issr_val=$(echo "${issr#issuer=}"  | canon)
  end_human=${endd#notAfter=}
  end_epoch=$(date -d "$end_human" +%s 2>/dev/null || echo 0)

  key="$subj_val||$issr_val"

  # Track newest any
  prev_any="${newest_any_by_pair[$key]:-}"
  if [ -z "$prev_any" ] || [ "$end_epoch" -gt "${prev_any%%|*}" ]; then
    newest_any_by_pair[$key]="$end_epoch|$f|$end_human"
  fi

  # Track newest valid
  if [ "$end_epoch" -gt "$now_epoch" ]; then
    prev_val="${newest_valid_by_pair[$key]:-}"
    if [ -z "$prev_val" ] || [ "$end_epoch" -gt "${prev_val%%|*}" ]; then
      newest_valid_by_pair[$key]="$end_epoch|$f|$end_human"
    fi
  else
    expired_list["$f"]="$key|$end_epoch|$end_human|$subj_val|$issr_val"
  fi
done < <(find "$ROOT" -type f -name '*.crt' -print0 2>/dev/null || true)

if [ ${#expired_list[@]} -eq 0 ]; then
  echo "✅ No expired certificates found."
  exit 0
fi

echo
echo "❌ Expired certificates:"
echo

for f in "${!expired_list[@]}"; do
  IFS='|' read -r key end_epoch end_human subj_val issr_val <<<"${expired_list[$f]}"

  repl="${newest_valid_by_pair[$key]:-}"

  echo "File   : $f"
  echo "Subject: $subj_val"
  echo "Issuer : $issr_val"
  echo "Expired: $end_human"

  if [ -n "$repl" ]; then
    IFS='|' read -r rep_epoch rep_path rep_human <<<"$repl"
    echo "→ Superseded by valid: $rep_path (expires $rep_human)"
  fi
  echo
done
