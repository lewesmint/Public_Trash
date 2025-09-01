#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Checking for expired certificates under /usr/local/share/ca-certificates/..."

found=0
while IFS= read -r -d '' c; do
    end=$(openssl x509 -in "$c" -noout -enddate | cut -d= -f2)
    end_epoch=$(date -d "$end" +%s)
    now_epoch=$(date +%s)

    if [ "$end_epoch" -lt "$now_epoch" ]; then
        echo "❌ Expired: $c  (expired on $end)"
        found=$((found+1))
    fi
done < <(find /usr/local/share/ca-certificates/ -type f -name "*.crt" -print0)

if [ $found -eq 0 ]; then
    echo "✅ No expired certificates found."
fi
