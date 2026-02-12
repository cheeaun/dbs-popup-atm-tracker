#!/usr/bin/env bash
set -euo pipefail

URL="https://docs.google.com/spreadsheets/d/e/2PACX-1vRf5HEUI66UBlEo3ESVN5J1pcSKN8_-euPFp9n6Ic4svlqlz1iwrtfUoyuXPjj92eskbWmjIO21Dzll/pub?gid=795957248&single=true&output=csv"
DATA_DIR="${DATA_DIR:-./data}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-60}"
COLLECT_TZ="${COLLECT_TZ:-Asia/Singapore}"
MODE="loop"

usage() {
  cat <<'EOF'
Usage: ./fetch_csv.sh [--once]

Modes:
  (default)    Loop forever and fetch periodically.
  --once       Attempt a single fetch and exit.
EOF
}

if [[ "${1:-}" == "--once" ]]; then
  MODE="once"
  shift
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  usage
  exit 1
fi

in_window() {
  local today="$1"
  local now_hm_num="$2"

  if [[ "$today" > "2026-02-02" && "$today" < "2026-02-16" ]]; then
    # Feb 3-15, 2026: 10:00-22:00
    [[ "$now_hm_num" -ge 1000 && "$now_hm_num" -lt 2200 ]]
    return
  elif [[ "$today" == "2026-02-16" ]]; then
    # Feb 16, 2026: 10:00-13:00
    [[ "$now_hm_num" -ge 1000 && "$now_hm_num" -lt 1300 ]]
    return
  fi
  return 1
}

next_sleep_seconds() {
  python3 - "$COLLECT_TZ" <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

tz = ZoneInfo(sys.argv[1])
now = datetime.now(tz)
day_start = datetime(2026, 2, 3, 9, 55, tzinfo=tz)
day_end = datetime(2026, 2, 16, 9, 55, tzinfo=tz)
today_num = now.hour * 100 + now.minute

def at_955(dt):
    return dt.replace(hour=9, minute=55, second=0, microsecond=0)

if now < day_start:
    target = day_start
elif now.date() < day_end.date():
    target = at_955(now) if today_num < 1000 else at_955(now + timedelta(days=1))
elif now.date() == day_end.date():
    target = at_955(now) if today_num < 1000 else datetime(2026, 2, 17, 9, 55, tzinfo=tz)
else:
    target = at_955(now + timedelta(days=1))

sleep_secs = max(60, int((target - now).total_seconds()))
print(sleep_secs)
print(f"Outside window. Sleeping until {target.strftime('%Y-%m-%d %H:%M')} ({tz.key}).", file=sys.stderr)
PY
}

fetch_once() {
  local tmp latest ts out ymd

  tmp="$(mktemp)"
  if ! curl -fsSL "$URL" -o "$tmp"; then
    rm -f "$tmp"
    echo "Fetch failed."
    return 0
  fi

  latest="$(ls -1t "$DATA_DIR"/*.csv 2>/dev/null | head -n 1 || true)"
  if [[ -n "$latest" ]] && cmp -s "$tmp" "$latest"; then
    rm -f "$tmp"
    echo "No changes"
  else
    ts="$(TZ="$COLLECT_TZ" date +"%Y%m%d-%H%M%S")"
    out="$DATA_DIR/$ts.csv"
    mv "$tmp" "$out"
    echo "Saved: $out"
    ymd="${ts%%-*}"
    if ! python3 ./generate_charts.py "$ymd"; then
      echo "Chart generation failed for $ymd"
    fi
  fi
  return 0
}

mkdir -p "$DATA_DIR"

while true; do
  today="$(TZ="$COLLECT_TZ" date +%F)"
  now_hm="$(TZ="$COLLECT_TZ" date +%H%M)"
  now_hm_num=$((10#$now_hm))

  if ! in_window "$today" "$now_hm_num"; then
    if [[ "$MODE" == "once" ]]; then
      echo "Outside collection window ($today $now_hm, $COLLECT_TZ). Skipping."
      exit 0
    fi
    sleep_secs="$(next_sleep_seconds || true)"
    if [[ -z "$sleep_secs" ]]; then
      sleep_secs="$INTERVAL_SECONDS"
      echo "Outside window. Sleeping for ${sleep_secs}s."
    fi
    sleep "$sleep_secs"
    continue
  fi

  fetch_once
  if [[ "$MODE" == "once" ]]; then
    exit 0
  fi
  sleep "$INTERVAL_SECONDS"
done
