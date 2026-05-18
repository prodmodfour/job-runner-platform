#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL=${JOB_RUNNER_DEMO_API_BASE_URL:-http://127.0.0.1:8000}
POLL_TIMEOUT_SECONDS=${JOB_RUNNER_DEMO_POLL_TIMEOUT_SECONDS:-45}
POLL_INTERVAL_SECONDS=${JOB_RUNNER_DEMO_POLL_INTERVAL_SECONDS:-0.5}
DEMO_API_KEY=${JOB_RUNNER_DEMO_API_KEY:-}

AUTH_HEADERS=()
if [[ -n "$DEMO_API_KEY" ]]; then
  AUTH_HEADERS=(-H "X-API-Key: $DEMO_API_KEY")
fi

log() {
  printf '\n== %s ==\n' "$*" >&2
}

info() {
  printf '%s\n' "$*" >&2
}

fail() {
  printf 'demo smoke failed: %s\n' "$*" >&2
  exit 1
}

require_command() {
  local command_name=$1
  if ! command -v "$command_name" >/dev/null 2>&1; then
    fail "required command '$command_name' was not found"
  fi
}

api_url() {
  local path=$1
  printf '%s/%s' "${API_BASE_URL%/}" "${path#/}"
}

json_value() {
  local path=$1
  python3 -c '
import json
import sys

current = json.load(sys.stdin)
for part in sys.argv[1].split("."):
    if isinstance(current, dict) and part in current:
        current = current[part]
    else:
        raise SystemExit(f"missing JSON field: {sys.argv[1]}")

if current is None:
    print("")
elif isinstance(current, (dict, list)):
    print(json.dumps(current, sort_keys=True))
else:
    print(current)
' "$path"
}

get_job() {
  local job_id=$1
  curl -fsS "${AUTH_HEADERS[@]}" "$(api_url "/jobs/$job_id")"
}

create_job() {
  local label=$1
  local body=$2
  local response
  local job_id
  local status

  log "Create $label job"
  response=$(curl -fsS \
    -X POST \
    -H 'Content-Type: application/json' \
    "${AUTH_HEADERS[@]}" \
    -d "$body" \
    "$(api_url /jobs)")
  job_id=$(json_value job.id <<<"$response")
  status=$(json_value job.status <<<"$response")
  info "$label job id: $job_id (initial status: $status)"
  printf '%s\n' "$job_id"
}

wait_for_status() {
  local job_id=$1
  shift
  local expected_statuses=("$@")
  local deadline=$((SECONDS + POLL_TIMEOUT_SECONDS))
  local response=""
  local status="unknown"
  local attempts="unknown"

  while ((SECONDS <= deadline)); do
    response=$(get_job "$job_id")
    status=$(json_value status <<<"$response")
    attempts=$(json_value attempts <<<"$response")
    info "job $job_id status=$status attempts=$attempts"

    for expected_status in "${expected_statuses[@]}"; do
      if [[ "$status" == "$expected_status" ]]; then
        printf '%s\n' "$response"
        return 0
      fi
    done

    sleep "$POLL_INTERVAL_SECONDS"
  done

  fail "job $job_id did not reach status '${expected_statuses[*]}' within ${POLL_TIMEOUT_SECONDS}s; last status was $status"
}

assert_metric_present() {
  local metrics=$1
  local metric_name=$2
  if [[ "$metrics" != *"$metric_name"* ]]; then
    fail "metrics output did not include $metric_name"
  fi
}

require_command curl
require_command python3

log "Check local API health and readiness"
if ! curl -fsS "$(api_url /healthz)" >/dev/null; then
  fail "API health check failed; start the local Compose stack with 'docker compose up --build'"
fi
if ! ready_response=$(curl -fsS "$(api_url /readyz)"); then
  fail "API readiness check failed; wait for PostgreSQL and Redis, then retry"
fi
ready_status=$(json_value status <<<"$ready_response")
if [[ "$ready_status" != "ready" ]]; then
  fail "API readiness was '$ready_status'; start the local Compose stack with 'docker compose up --build'"
fi
info "API is healthy and dependencies are ready at $API_BASE_URL"

echo_job_id=$(create_job "echo" '{"job_type":"echo","payload":{"message":"hello from the smoke demo"}}')
echo_response=$(wait_for_status "$echo_job_id" succeeded)
echo_result=$(json_value result <<<"$echo_response")
info "echo result: $echo_result"

checksum_job_id=$(create_job "checksum" '{"job_type":"checksum","payload":{"text":"hello from checksum demo","algorithm":"sha256"}}')
checksum_response=$(wait_for_status "$checksum_job_id" succeeded)
checksum_digest=$(json_value result.checksum <<<"$checksum_response")
info "checksum digest: $checksum_digest"

fail_once_job_id=$(create_job "fail_once" '{"job_type":"fail_once","payload":{},"max_attempts":3}')
fail_once_response=$(wait_for_status "$fail_once_job_id" succeeded)
fail_once_attempts=$(json_value attempts <<<"$fail_once_response")
if ((fail_once_attempts < 2)); then
  fail "fail_once job succeeded without a retry; attempts=$fail_once_attempts"
fi
info "fail_once retry observed; final attempts=$fail_once_attempts"

always_fail_job_id=$(create_job "always_fail" '{"job_type":"always_fail","payload":{},"max_attempts":2}')
always_fail_response=$(wait_for_status "$always_fail_job_id" dead_lettered)
always_fail_attempts=$(json_value attempts <<<"$always_fail_response")
always_fail_error=$(json_value error_message <<<"$always_fail_response")
if [[ "$always_fail_attempts" != "2" || -z "$always_fail_error" ]]; then
  fail "always_fail did not dead-letter as expected; attempts=$always_fail_attempts error='$always_fail_error'"
fi
info "always_fail dead-letter observed; error='$always_fail_error'"

sleep_job_id=$(create_job "sleep" '{"job_type":"sleep","payload":{"seconds":5},"max_attempts":3}')
wait_for_status "$sleep_job_id" running >/dev/null
log "Cancel sleep job"
cancel_response=$(curl -fsS \
  -X POST \
  "${AUTH_HEADERS[@]}" \
  "$(api_url "/jobs/$sleep_job_id/cancel")")
cancel_status=$(json_value job.status <<<"$cancel_response")
info "sleep cancellation request accepted; API returned status=$cancel_status"
sleep_response=$(wait_for_status "$sleep_job_id" cancelled)
sleep_error=$(json_value error_message <<<"$sleep_response")
info "sleep cancellation observed; error='$sleep_error'"

log "Check Prometheus metrics"
metrics=$(curl -fsS "$(api_url /metrics)")
for metric_name in \
  jobs_created_total \
  jobs_started_total \
  jobs_succeeded_total \
  jobs_failed_total \
  jobs_retried_total \
  jobs_dead_lettered_total \
  jobs_cancelled_total \
  job_duration_seconds; do
  assert_metric_present "$metrics" "$metric_name"
done
info "metrics include required job lifecycle families"

log "Smoke demo complete"
info "Created jobs: echo=$echo_job_id checksum=$checksum_job_id fail_once=$fail_once_job_id always_fail=$always_fail_job_id sleep=$sleep_job_id"
