#!/usr/bin/env bash
set -euo pipefail

: "${TARGET_ENV:?Missing GitHub environment}" "${AWS_REGION:?Missing AWS region}"
: "${AWS_ACCOUNT_ID:?Missing AWS account}" "${ECS_CLUSTER:?Missing ECS cluster}"
: "${ECS_SERVICE:?Missing ECS service}"
case "$TARGET_ENV" in dev|staging) ;; *) exit 2 ;; esac
[[ "$AWS_ACCOUNT_ID" =~ ^[0-9]{12}$ ]] || exit 2
[[ "$AWS_REGION" =~ ^[a-z]{2}(-[a-z]+)+-[0-9]+$ ]] || exit 2

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
revision="$(< "releases/$TARGET_ENV.task-arn")"
family="arn:aws:ecs:$AWS_REGION:$AWS_ACCOUNT_ID:task-definition/pccom-core-$TARGET_ENV:"
if [[ "$revision" != "$family"* || ! "${revision#"$family"}" =~ ^[1-9][0-9]*$ ]]; then
  printf '%s\n' "Expected a pre-registered task definition in $family" >&2
  exit 2
fi

selector=(--cluster "$ECS_CLUSTER" --service "$ECS_SERVICE")
aws ecs update-service "${selector[@]}" --task-definition "$revision" \
  --query 'service.{service:serviceName,task:taskDefinition}' --output json
aws ecs wait services-stable --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE"
primary="$(aws ecs describe-services --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" \
  --query 'services[0].deployments[?status==`PRIMARY`].[taskDefinition,rolloutState] | [0]' \
  --output text)"
IFS=$'\t' read -r actual state <<< "$primary"
if [[ "$actual" != "$revision" || "$state" != COMPLETED ]]; then
  printf 'Deployment did not complete on the requested revision. Current: %s\n' "$primary" >&2
  exit 1
fi
printf 'Deployment completed: %s\n' "$revision"
