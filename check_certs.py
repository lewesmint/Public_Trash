#!/usr/bin/env bash
set -euo pipefail

ROOT="/usr/local/share/ca-certificates"

# Find all .crt files recursively
mapfile -d '' FILES < <(find "$ROOT" -type f -name '*.crt' -print0 2>/dev/null || true)

if [ ${#FILES[@]} -eq 0 ]; then
  echo "No .crt files found under $ROOT"
  exit 0
fi

now_epoch=$(date +%s)

# Storage
# Key = "SUBJECT||ISSUER"  Value = "end_epoch|path"
declare -A newest_valid_by_pair
declare -A newest_any_by_pair
declare -A expired_list

canon() {
  # Canonicalise whitespace
  sed -E 's/[[:space:]]+/ /g' | sed -E 's/^ //; s/ $//'
}

for f in "${FILES[@]}"; do
  # Skip non-PEM or unreadable files gracefully
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
    # Expired
    expired_list["$f"]="$key|$end_epoch|$end_human|$subj_val|$issr_val"
  fi
done

if [ ${#expired_list[@]} -eq 0 ]; then
  echo "No expired certificates found under $ROOT"
  exit 0
fi

echo "Expired certificates and possible replacements:"
echo

for f in "${!expired_list[@]}"; do
  IFS='|' read -r key end_epoch end_human subj_val issr_val <<<"${expired_list[$f]}"

  repl="${newest_valid_by_pair[$key]:-}"
  newest_any="${newest_any_by_pair[$key]:-}"

  echo "Expired: $f"
  echo "  Subject: $subj_val"
  echo "  Issuer : $issr_val"
  echo "  Expired: $end_human"

  if [ -n "$repl" ]; then
    IFS='|' read -r rep_epoch rep_path rep_human <<<"$repl"
    echo "  Superseded by (valid): $rep_path"
    echo "    Expires: $rep_human"
  else
    if [ -n "$newest_any" ]; then
      IFS='|' read -r any_epoch any_path any_human <<<"$newest_any"
      if [ "$any_epoch" -gt "$end_epoch" ]; then
        echo "  Note: A newer cert exists for the same Subject+Issuer but it is not currently valid."
        echo "        Newest found: $any_path  (expires $any_human)"
      else
        echo "  No newer cert found for the same Subject+Issuer."
      fi
    else
      echo "  No newer cert found for the same Subject+Issuer."
    fi
  fi
  echo
done
