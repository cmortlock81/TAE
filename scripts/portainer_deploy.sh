#!/usr/bin/env bash
set -euo pipefail

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

require_var PORTAINER_URL
require_var PORTAINER_STACK_ID
require_var PORTAINER_ENDPOINT_ID
require_var IMAGE_TAG

auth_header=()
if [[ -n "${PORTAINER_API_KEY:-}" ]]; then
  auth_header=("X-API-Key: ${PORTAINER_API_KEY}")
elif [[ -n "${PORTAINER_USERNAME:-}" && -n "${PORTAINER_PASSWORD:-}" ]]; then
  auth_response=$(curl -sS -w "\n%{http_code}" -X POST "${PORTAINER_URL}/api/auth" \
    -H "Content-Type: application/json" \
    -d "{\"Username\":\"${PORTAINER_USERNAME}\",\"Password\":\"${PORTAINER_PASSWORD}\"}")
  auth_body=$(echo "$auth_response" | head -n 1)
  auth_code=$(echo "$auth_response" | tail -n 1)
  if [[ "$auth_code" != "200" ]]; then
    echo "Portainer auth failed with status ${auth_code}" >&2
    exit 1
  fi
  jwt=$(echo "$auth_body" | jq -r '.jwt')
  if [[ -z "$jwt" || "$jwt" == "null" ]]; then
    echo "Portainer auth response missing jwt" >&2
    exit 1
  fi
  auth_header=("Authorization: Bearer ${jwt}")
else
  echo "Provide PORTAINER_API_KEY or PORTAINER_USERNAME/PORTAINER_PASSWORD" >&2
  exit 1
fi

stack_response=$(curl -sS -w "\n%{http_code}" "${PORTAINER_URL}/api/stacks/${PORTAINER_STACK_ID}" \
  -H "${auth_header[0]}")
stack_body=$(echo "$stack_response" | head -n 1)
stack_code=$(echo "$stack_response" | tail -n 1)
if [[ ! "$stack_code" =~ ^2 ]]; then
  echo "Failed to fetch stack details (status ${stack_code})" >&2
  exit 1
fi
env_payload=$(echo "$stack_body" | jq -c '.Env // []')

file_response=$(curl -sS -w "\n%{http_code}" "${PORTAINER_URL}/api/stacks/${PORTAINER_STACK_ID}/file?endpointId=${PORTAINER_ENDPOINT_ID}" \
  -H "${auth_header[0]}")
file_body=$(echo "$file_response" | head -n 1)
file_code=$(echo "$file_response" | tail -n 1)
if [[ ! "$file_code" =~ ^2 ]]; then
  echo "Failed to fetch stack file (status ${file_code})" >&2
  exit 1
fi
stack_file=$(echo "$file_body" | jq -r '.StackFileContent')
if [[ -z "$stack_file" || "$stack_file" == "null" ]]; then
  echo "Portainer returned empty stack file" >&2
  exit 1
fi

updated_stack=$(STACK_FILE="$stack_file" IMAGE_TAG="$IMAGE_TAG" python - <<'PY'
import os
import re
import sys

content = os.environ["STACK_FILE"]
image_tag = os.environ["IMAGE_TAG"]
pattern = r"^\s*image:\s*ghcr\.io/cmortlock81/tae:.*$"
if not re.search(pattern, content, flags=re.M):
    sys.stderr.write("Could not find ghcr.io/cmortlock81/tae image line to replace\n")
    sys.exit(1)
updated = re.sub(pattern, f"  image: {image_tag}", content, flags=re.M)
print(updated)
PY
)

update_payload=$(jq -n \
  --arg content "$updated_stack" \
  --argjson env "$env_payload" \
  '{stackFileContent: $content, env: $env, prune: true, pullImage: true}')

update_response=$(curl -sS -w "\n%{http_code}" -X PUT \
  "${PORTAINER_URL}/api/stacks/${PORTAINER_STACK_ID}?endpointId=${PORTAINER_ENDPOINT_ID}" \
  -H "Content-Type: application/json" \
  -H "${auth_header[0]}" \
  -d "$update_payload")
update_code=$(echo "$update_response" | tail -n 1)
if [[ ! "$update_code" =~ ^2 ]]; then
  echo "Portainer stack update failed (status ${update_code})" >&2
  exit 1
fi

echo "Portainer stack updated successfully."
