#!/bin/bash

# messages-search.sh - 搜索 Session 消息
# 用法: ./messages-search.sh <session_id> [options_json]
# 参数:
#   session_id: Session ID（必填）
#   options_json: 搜索选项 JSON（可选，默认只返回用户输入和agent正式输出）
# 
# 默认行为：
#   - 只返回 "text" 和 "completion_result" 类型的消息
#   - 过滤掉 tool、thinking、api_req_started 等中间 ReAct 信息
#   - 如需查看所有消息，传入空过滤器：'{}'
#
# options_json 结构:
# {
#   "filters": {
#     "role": "user" | "assistant",
#     "say": "text" | ["text", "completion_result"],
#     "contains": "关键词",
#     "chatId": "chat-uuid",
#     "partial": false,
#     "startTime": 1708300000000,
#     "endTime": 1708400000000
#   },
#   "options": {
#     "limit": 50,
#     "offset": 0,
#     "order": "desc"
#   },
#   "fields": ["ts", "role", "say", "text"],
#   "textLimits": {
#     "perMessage": 2000,
#     "total": 50000
#   }
# }
# 返回: 搜索结果的 JSON 数据

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo '{"success": false, "error": "session_id is required"}' >&2
    exit 1
fi

SESSION_ID="$1"

# 默认过滤选项：只返回用户输入和 agent 正式输出
# 过滤掉 tool、thinking、api_req_started、command 等中间 ReAct 信息
DEFAULT_OPTIONS='{
    "filters": {
        "say": ["text", "completion_result", "user_feedback"]
    },
    "options": {
        "limit": 50,
        "order": "desc"
    },
    "textLimits": {
        "perMessage": 3000,
        "total": 50000
    }
}'

# 如果用户提供了参数，使用用户参数；否则使用默认选项
if [ -n "$2" ]; then
    OPTIONS_JSON="$2"
else
    OPTIONS_JSON="$DEFAULT_OPTIONS"
fi

response=$(curl -s -X POST "${BASE_URL}/api/sessions/${SESSION_ID}/messages/search" \
    -H "Content-Type: application/json" \
    -d "$OPTIONS_JSON")

echo "$response"
