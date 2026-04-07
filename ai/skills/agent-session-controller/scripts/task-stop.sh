#!/bin/bash

# task-stop.sh - 停止任务
# 用法: ./task-stop.sh <session_id>
# 参数:
#   session_id: Session ID（必填）
# 返回: 停止结果的 JSON 数据，包含:
#   - success: 操作是否成功
#   - message: 结果消息
#   - wasRunning: 是否有任务在运行

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo '{"success": false, "error": "session_id is required"}' >&2
    exit 1
fi

SESSION_ID="$1"

response=$(curl -s -X POST "${BASE_URL}/api/sessions/${SESSION_ID}/tasks/stop" \
    -H "Content-Type: application/json")

echo "$response"
