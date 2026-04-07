#!/bin/bash

# task-respond.sh - 响应阻断性 UI
# 用法: ./task-respond.sh <session_id> <action> <ask_type> [response]
# 参数:
#   session_id: Session ID（必填）
#   action: 响应动作 "approve" | "reject" | "skip"（必填）
#   ask_type: 阻断类型 "command" | "mcp" | "plan" | "ask_user_questions"（必填）
#   response: 用户响应内容（ask_user_questions 时使用，可选）
# 返回: 响应结果的 JSON 数据，包含:
#   - success: 操作是否成功
#   - message: 结果消息
#   - action: 响应的动作
#   - askType: 阻断类型

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo '{"success": false, "error": "session_id is required"}' >&2
    exit 1
fi

if [ -z "$2" ]; then
    echo '{"success": false, "error": "action is required (approve/reject/skip)"}' >&2
    exit 1
fi

if [ -z "$3" ]; then
    echo '{"success": false, "error": "ask_type is required (command/mcp/plan/ask_user_questions)"}' >&2
    exit 1
fi

SESSION_ID="$1"
ACTION="$2"
ASK_TYPE="$3"
RESPONSE="${4:-}"

# 构建请求体
if [ -n "$RESPONSE" ]; then
    # 转义 JSON 特殊字符
    RESPONSE_ESCAPED=$(echo -n "$RESPONSE" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" | sed 's/^"//;s/"$//')
    REQUEST_BODY="{
        \"action\": \"${ACTION}\",
        \"askType\": \"${ASK_TYPE}\",
        \"response\": \"${RESPONSE_ESCAPED}\"
    }"
else
    REQUEST_BODY="{
        \"action\": \"${ACTION}\",
        \"askType\": \"${ASK_TYPE}\"
    }"
fi

response=$(curl -s -X POST "${BASE_URL}/api/sessions/${SESSION_ID}/respond" \
    -H "Content-Type: application/json" \
    -d "$REQUEST_BODY")

echo "$response"
