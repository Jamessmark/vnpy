#!/bin/bash

# session-delete.sh - 删除 Session
# 用法: ./session-delete.sh <session_id>
# 参数:
#   session_id: Session ID（必填）
# 返回: 删除结果的 JSON 数据

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo '{"success": false, "error": "session_id is required"}' >&2
    exit 1
fi

SESSION_ID="$1"

response=$(curl -s -X DELETE "${BASE_URL}/api/sessions/${SESSION_ID}" \
    -H "Content-Type: application/json")

echo "$response"
