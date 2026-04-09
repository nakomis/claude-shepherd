#!/usr/bin/env bash
# Claude Code statusline script — displays rate limit usage and saves resets_at to disk.
#
# Install: add to ~/.claude/settings.json under "statusline":
#   "statusline": "/path/to/rate-limit-statusline.sh"
#
# Reads JSON from stdin (Claude Code statusline protocol).
# Writes ~/.claude/rate-limit-state.json so claude-resume can read resets_at.
# Outputs a short status string for display in the terminal titlebar / tmux.

STATE_FILE="${HOME}/.claude/rate-limit-state.json"

input=$(cat)

five_pct=$(echo "$input"   | jq -r '.rate_limits.five_hour.used_percentage  // empty' 2>/dev/null)
five_at=$(echo "$input"    | jq -r '.rate_limits.five_hour.resets_at         // empty' 2>/dev/null)
seven_pct=$(echo "$input"  | jq -r '.rate_limits.seven_day.used_percentage   // empty' 2>/dev/null)
seven_at=$(echo "$input"   | jq -r '.rate_limits.seven_day.resets_at         // empty' 2>/dev/null)
ctx_pct=$(echo "$input"    | jq -r '.context_window.used_percentage          // empty' 2>/dev/null)

# Persist rate limit state for claude-resume to read
if [[ -n "$five_at" ]]; then
    jq -n \
        --argjson five_pct  "${five_pct:-0}"  \
        --argjson five_at   "${five_at:-0}"   \
        --argjson seven_pct "${seven_pct:-0}" \
        --argjson seven_at  "${seven_at:-0}"  \
        --argjson written   "$(date +%s)"     \
        '{
            five_hour:  { used_percentage: $five_pct,  resets_at: $five_at  },
            seven_day:  { used_percentage: $seven_pct, resets_at: $seven_at },
            written_at: $written
        }' > "$STATE_FILE"
fi

# Build display string
parts=()
[[ -n "$five_pct"  ]] && parts+=("5h: ${five_pct}%")
[[ -n "$seven_pct" ]] && parts+=("7d: ${seven_pct}%")
[[ -n "$ctx_pct"   ]] && parts+=("ctx: ${ctx_pct}%")

if [[ ${#parts[@]} -gt 0 ]]; then
    out="${parts[0]}"
    for part in "${parts[@]:1}"; do
        out+=" | ${part}"
    done
    printf '%s' "$out"
fi
