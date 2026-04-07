#!/bin/bash

# task-send.sh - 发送 AI 任务
# 用法: ./task-send.sh <session_id> <task_content> [agent_mode]
#       ./task-send.sh <session_id> --file <task_file> [agent_mode]
# 参数:
#   session_id: Session ID（必填）
#   task_content: 任务内容（必填）
#   --file: 从文件读取任务内容
#   task_file: 包含任务内容的文件路径
#   agent_mode: 模式 "agent" 或 "ask"（默认: "agent"）
# 返回: 发送结果的 JSON 数据，包含 chatId

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo '{"success": false, "error": "session_id is required"}' >&2
    exit 1
fi

SESSION_ID="$1"
shift

# 检查是否使用 --file 选项
if [ "$1" = "--file" ]; then
    shift
    if [ -z "$1" ]; then
        echo '{"success": false, "error": "task_file is required when using --file"}' >&2
        exit 1
    fi
    TASK_FILE="$1"
    if [ ! -f "$TASK_FILE" ]; then
        echo "{\"success\": false, \"error\": \"File not found: $TASK_FILE\"}" >&2
        exit 1
    fi
    TASK_CONTENT=$(cat "$TASK_FILE")
    shift
    AGENT_MODE="${1:-agent}"
else
    if [ -z "$1" ]; then
        echo '{"success": false, "error": "task_content is required"}' >&2
        exit 1
    fi
    TASK_CONTENT="$1"
    AGENT_MODE="${2:-agent}"
fi

# 转义 JSON 特殊字符
TASK_CONTENT_ESCAPED=$(echo -n "$TASK_CONTENT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" | sed 's/^"//;s/"$//')

response=$(curl -s -X POST "${BASE_URL}/api/sessions/${SESSION_ID}/tasks" \
    -H "Content-Type: application/json" \
    -d "{
        \"taskContent\": \"${TASK_CONTENT_ESCAPED}\",
        \"agentMode\": \"${AGENT_MODE}\",
        \"isAskMode\": false
    }")

echo "$response"
