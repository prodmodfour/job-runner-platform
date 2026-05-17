#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/build-loop.sh [options]

Runs autonomous pi build cycles for job-runner-platform.

Each cycle:
- reads AGENTS.md, BUILD_TICKETS.md, and BUILD_NOTES.md
- selects the lowest-numbered TODO/IN_PROGRESS ticket
- implements only that ticket
- runs quality gates
- updates BUILD_NOTES.md and BUILD_TICKETS.md
- commits the completed work
- leaves the working tree clean

Options:
  --max-cycles N      Number of cycles to run. Default: 1.
  --sleep SECONDS     Pause between successful cycles. Default: 0.
  --push              Push after each successful cycle.
  --allow-ahead       Allow starting a cycle when the branch is already ahead of upstream.
  -h, --help          Show this help.

This script intentionally does not pass a model or thinking level to pi.
It relies on the existing pi configuration.
USAGE
}

MAX_CYCLES=1
SLEEP_SECONDS=0
PUSH_AFTER=0
ALLOW_AHEAD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --max-cycles)
      MAX_CYCLES="$2"
      shift 2
      ;;
    --sleep)
      SLEEP_SECONDS="$2"
      shift 2
      ;;
    --push)
      PUSH_AFTER=1
      shift
      ;;
    --allow-ahead)
      ALLOW_AHEAD=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$MAX_CYCLES" =~ ^[0-9]+$ ]] || [[ "$MAX_CYCLES" -lt 1 ]]; then
  echo "--max-cycles must be a positive integer" >&2
  exit 2
fi

if ! [[ "$SLEEP_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "--sleep must be a non-negative integer" >&2
  exit 2
fi

REQUIRED_FILES=(
  AGENTS.md
  BUILD_TICKETS.md
  BUILD_NOTES.md
  scripts/quality-gate.sh
)

LOG_DIR=".pi/logs/build-loop"
LOCK_DIR=".pi/build-loop.lock"

PROMPT=$(cat <<'PROMPT_EOF'
You are continuing the autonomous build of job-runner-platform.

Read AGENTS.md, BUILD_TICKETS.md, and BUILD_NOTES.md.

Your task in this run:

- Select the lowest-numbered TODO or IN_PROGRESS ticket from BUILD_TICKETS.md.
- Implement only that ticket.
- Do not start future tickets.
- Do not broaden scope.
- Respect all architecture, reliability, and public-safety rules in AGENTS.md.
- Do not implement arbitrary shell command execution.
- Jobs must be safe allowlisted demo handlers only.
- Apply SOLID principles through the required architecture boundaries:
  routes -> schemas -> services -> repositories -> database/queue.
- Add or update meaningful tests.
- Update documentation if the ticket changes setup, architecture, API behaviour, data model, observability, operations, or limitations.
- Run scripts/quality-gate.sh.
- Update BUILD_TICKETS.md with ticket status.
- Update BUILD_NOTES.md with:
  - what changed
  - quality gates run
  - any limitations
  - next recommended ticket
- Commit the completed ticket with a conventional commit message.
- Leave the working tree clean.

If you cannot safely complete the ticket:

- explain the blocker in BUILD_NOTES.md
- mark the ticket BLOCKED if appropriate
- do not mark it DONE
- do not commit partial broken work
- leave the working tree clean if possible
PROMPT_EOF
)

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 127
  fi
}

require_clean_tree() {
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree is dirty; refusing to start." >&2
    git status --short >&2
    exit 1
  fi
}

get_upstream_ref() {
  git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true
}

sync_before_cycle() {
  local upstream_ref
  local counts
  local behind_count
  local ahead_count

  require_clean_tree

  upstream_ref="$(get_upstream_ref)"
  CYCLE_UPSTREAM_REF="$upstream_ref"
  CYCLE_UPSTREAM_HEAD=""

  if [[ -z "$upstream_ref" ]]; then
    echo "No upstream configured; skipping remote sync checks."
    return 0
  fi

  git pull --ff-only
  require_clean_tree

  CYCLE_UPSTREAM_HEAD="$(git rev-parse "$upstream_ref")"
  counts="$(git rev-list --left-right --count "${upstream_ref}...HEAD")"
  read -r behind_count ahead_count <<< "$counts"

  if (( behind_count > 0 )); then
    echo "Branch is behind upstream after git pull --ff-only; refusing to start." >&2
    exit 1
  fi

  if (( ahead_count > 0 && ALLOW_AHEAD != 1 )); then
    echo "Branch is ahead of upstream by ${ahead_count} commit(s); refusing to start." >&2
    echo "Push first, or rerun with --allow-ahead." >&2
    exit 1
  fi
}

refuse_if_remote_advanced() {
  local upstream_ref="$1"
  local expected_upstream_head="$2"
  local current_upstream_head

  if [[ -z "$upstream_ref" || -z "$expected_upstream_head" ]]; then
    return 0
  fi

  git fetch --quiet
  current_upstream_head="$(git rev-parse "$upstream_ref")"

  if [[ "$current_upstream_head" != "$expected_upstream_head" ]]; then
    echo "Upstream $upstream_ref advanced during the cycle; refusing to continue." >&2
    echo "Expected upstream: $expected_upstream_head" >&2
    echo "Current upstream:  $current_upstream_head" >&2
    exit 1
  fi
}

acquire_lock() {
  mkdir -p "$(dirname "$LOCK_DIR")" "$LOG_DIR"

  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "Another build loop appears to be running: $LOCK_DIR" >&2
    exit 1
  fi

  echo "$$" > "$LOCK_DIR/pid"
  trap 'rm -rf "$LOCK_DIR"' EXIT
}

require_command git
require_command pi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not inside a git work tree." >&2
  exit 1
fi

for file in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Required file missing: $file" >&2
    exit 1
  fi
done

acquire_lock

cycle=0

while (( cycle < MAX_CYCLES )); do
  cycle=$((cycle + 1))
  echo "=== pi build cycle $cycle/$MAX_CYCLES ==="

  sync_before_cycle

  before_head="$(git rev-parse HEAD)"
  log_file="$LOG_DIR/cycle-$(date +%Y%m%d-%H%M%S)-$cycle.log"

  echo "Logging to $log_file"

  if ! pi --no-session -p @AGENTS.md @BUILD_TICKETS.md @BUILD_NOTES.md "$PROMPT" 2>&1 | tee "$log_file"; then
    echo "pi failed during cycle $cycle; stopping. See $log_file" >&2
    exit 1
  fi

  if [[ -n "$(git status --porcelain)" ]]; then
    echo "pi left a dirty working tree; stopping for manual review." >&2
    git status --short >&2
    exit 1
  fi

  refuse_if_remote_advanced "$CYCLE_UPSTREAM_REF" "$CYCLE_UPSTREAM_HEAD"

  after_head="$(git rev-parse HEAD)"

  if [[ "$after_head" == "$before_head" ]]; then
    echo "Cycle completed without a new commit; stopping." >&2
    exit 1
  fi

  if (( PUSH_AFTER == 1 )); then
    git push
  fi

  automation_status="$(
    awk -F: '
      /^AUTOMATION_STATUS:/ {
        status=$2
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", status)
        print status
        exit
      }
    ' BUILD_TICKETS.md
  )"

  if [[ "$automation_status" == "DONE" ]]; then
    echo "Build tickets marked done."
    exit 0
  fi

  if (( SLEEP_SECONDS > 0 )); then
    sleep "$SLEEP_SECONDS"
  fi
done
