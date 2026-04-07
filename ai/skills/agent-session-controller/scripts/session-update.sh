#!/bin/bash

# session-update.sh - 更新 Session 名称
# 用法: ./session-update.sh <session_id> <new_name>
# 参数:
#   session_id: Session ID（必填）
#   new_name: 新的 Session 名称（必填）
# 返回: 更新结果的 JSON 数据

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ] || [ -z "$2" ]; then
    echo '{"success": false, "error": "session_id and new_name are required"}' >&2
    exit 1
fi

SESSION_ID="$1"
NEW_NAME="$2"

response=$(curl -s -X PUT "${BASE_URL}/api/sessions/${SESSION_ID}" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"${NEW_NAME}\"}")

echo "$response"
