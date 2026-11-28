#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p artifacts
dc=(docker compose --env-file .staging/compose.env -f docker-compose.staging.yml)
"${dc[@]}" ps --format json > artifacts/containers.json
"${dc[@]}" logs --no-color --tail=200 ingestion api > artifacts/runtime.log
"${dc[@]}" exec -T timescaledb psql -U postgres -d pccom_staging -P pager=off -c "
 SELECT j.job_id,j.hypertable_name,j.schedule_interval,j.scheduled,s.last_run_status,s.next_start
 FROM timescaledb_information.jobs j LEFT JOIN timescaledb_information.job_stats s USING(job_id)
 WHERE j.proc_name='policy_refresh_continuous_aggregate';" > artifacts/aggregate-jobs.txt
echo "Saved actual evidence under artifacts/. Inspect before sharing."
