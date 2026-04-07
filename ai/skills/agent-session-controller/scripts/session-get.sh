#!/bin/bash

# session-get.sh - 获取单个 Session 详情
# 用法: ./session-get.sh <session_id>
# 参数:
#   session_id: Session ID（必填）
# 返回: Session 详情的 JSON 数据

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo '{"success": false, "error": "session_id is required"}' >&2
    exit 1
fi

SESSION_ID="$1"

response=$(curl -s -X GET "${BASE_URL}/api/sessions/${SESSION_ID}" \
    -H "Content-Type: application/json")

echo "$response"
