#!/usr/bin/env bash
# Offline checks for the fork's preconditioning additions. No Home Assistant
# install needed: tests/stub.py fabricates the homeassistant modules the code
# imports. Run this after every merge with upstream.
set -u
cd "$(dirname "$0")"
fail=0
for t in test_*.py; do
    out=$(python3 "$t" 2>&1)
    if [ $? -eq 0 ] && [ "$(echo "$out" | tail -1)" = "ALL OK" ]; then
        printf '  ok    %s\n' "$t"
    else
        printf '  FAIL  %s\n' "$t"
        echo "$out" | sed 's/^/          /'
        fail=1
    fi
done
if [ "$fail" -eq 0 ]; then
    echo "all offline checks passed"
else
    echo "offline checks failed"
fi
exit "$fail"
