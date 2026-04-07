#!/bin/bash

# session-create.sh - 创建新 Session
# 用法: ./session-create.sh [session_name] [agent_mode]
# 参数:
#   session_name: Session 名称（默认: "New Session"）
#   agent_mode: 模式 "agent" 或 "ask"（默认: "agent"）
# 返回: 创建结果的 JSON 数据，包含 sessionId

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

SESSION_NAME="${1:-New Session}"
AGENT_MODE="${2:-agent}"

# 生成 UUID
SESSION_ID=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c "import uuid; print(uuid.uuid4())")

response=$(curl -s -X POST "${BASE_URL}/api/sessions" \
    -H "Content-Type: application/json" \
    -d "{
        \"sessionId\": \"${SESSION_ID}\",
        \"sessionName\": \"${SESSION_NAME}\",
        \"isComposer\": true,
        \"agentMode\": \"${AGENT_MODE}\"
    }")

# 将 sessionId 添加到返回结果中
echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'data' not in data:
        data['data'] = {}
    data['data']['sessionId'] = '${SESSION_ID}'
    data['data']['sessionName'] = '${SESSION_NAME}'
    print(json.dumps(data))
except:
    print('{\"success\": false, \"error\": \"Failed to parse response\", \"sessionId\": \"${SESSION_ID}\"}')"
