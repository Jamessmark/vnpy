#!/bin/bash

# session-status.sh - 获取 Session 任务运行状态
# 用法: ./session-status.sh <session_id>
# 参数:
#   session_id: Session ID（必填）
# 返回: Session 状态的 JSON 数据，包含:
#   - isRunning: 是否有任务正在运行
#   - currentChatId: 当前执行的对话 ID
#   - lastMessageTs: 最后消息时间戳
#   - lastMessageType: 最后消息类型
#   - lastMessageSay: 最后消息的 say 类型
#   - waitingForUserInput: 是否等待用户输入

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo '{"success": false, "error": "session_id is required"}' >&2
    exit 1
fi

SESSION_ID="$1"

response=$(curl -s -X GET "${BASE_URL}/api/sessions/${SESSION_ID}/status" \
    -H "Content-Type: application/json")

echo "$response"
