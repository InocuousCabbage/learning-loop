#!/usr/bin/env bash
# Surface skills whose open-issue backlog has crossed the rewrite threshold.
# Read-only. Used by morning-review and the skill-capture cron to decide which
# skills learning-loop APPLY should be pointed at. The rewrite itself is never
# automatic - this only names the candidates for a human GO.
set -uo pipefail
MIN="${1:-3}"
T="$HOME/.claude/skills/learning-loop/scripts/tracker.py"
if ! python3 "$T" ping >/dev/null 2>&1; then
  echo "SKILL-TRACKER: connection not configured (SUPABASE_DB_URL) -- cannot surface"; exit 2
fi
ROWS=$(python3 "$T" skills --min "$MIN" 2>/dev/null)
if [ -z "$ROWS" ]; then
  echo "SKILL-TRACKER: no skill has >= ${MIN} open issues (nothing to work)"; exit 0
fi
echo "SKILL-TRACKER: skills at/over ${MIN} open issues -- candidates for learning-loop APPLY (human GO required):"
echo "$ROWS" | while IFS=$'\t' read -r name open stage; do
  printf "  %-28s %s open\n" "$name" "$open"
done
