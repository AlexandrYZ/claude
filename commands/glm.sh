#!/usr/bin/env bash
# Toggle GLM API settings in ~/.claude/settings.json
# If GLM keys are present — remove them (switch to Anthropic)
# If GLM keys are absent — add them (switch to GLM)

set -euo pipefail

SETTINGS_FILE="$HOME/.claude/settings.json"

if [[ ! -f "$SETTINGS_FILE" ]]; then
  echo "ERROR: $SETTINGS_FILE not found"
  exit 1
fi

# Validate input JSON
if ! jq empty "$SETTINGS_FILE" 2>/dev/null; then
  echo "ERROR: $SETTINGS_FILE is not valid JSON"
  exit 1
fi

CURRENT_URL=$(jq -r '.env.ANTHROPIC_BASE_URL // ""' "$SETTINGS_FILE")

if [[ "$CURRENT_URL" == "https://api.z.ai/api/anthropic" ]]; then
  # GLM is ON -> remove GLM keys
  jq '.env |= del(
    .ANTHROPIC_DEFAULT_HAIKU_MODEL,
    .ANTHROPIC_DEFAULT_SONNET_MODEL,
    .ANTHROPIC_DEFAULT_OPUS_MODEL,
    .ANTHROPIC_AUTH_TOKEN,
    .ANTHROPIC_BASE_URL,
    .API_TIMEOUT_MS
  )' "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp"
  ACTION="OFF"
else
  # GLM is OFF -> add GLM keys
  jq '.env += {
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.5-air",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-4.7",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
    "ANTHROPIC_AUTH_TOKEN": "",
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
    "API_TIMEOUT_MS": "3000000"
  }' "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp"
  ACTION="ON"
fi

# Validate output JSON before replacing
if ! jq empty "${SETTINGS_FILE}.tmp" 2>/dev/null; then
  echo "ERROR: resulting JSON is invalid, aborting"
  rm -f "${SETTINGS_FILE}.tmp"
  exit 1
fi

mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"

echo "GLM mode $ACTION"
echo "---"
jq '.env' "$SETTINGS_FILE"
