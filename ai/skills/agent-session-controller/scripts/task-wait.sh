#!/bin/bash

# task-wait.sh - 等待 AI 任务完成
# 用法: ./task-wait.sh <session_id> [timeout_seconds] [poll_interval]
# 参数:
#   session_id: Session ID（必填）
#   timeout_seconds: 超时时间，单位秒（默认: 120）
#   poll_interval: 轮询间隔，单位秒（默认: 2）
# 
# 输出:
#   - 实时打印状态指示: "." 表示等待中，"s" 表示正在流式输出
#   - 完成后返回最终状态的 JSON
# 
# 退出码:
#   0 - 任务成功完成
#   1 - 任务失败（有错误）
#   2 - 超时

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo '{"success": false, "error": "session_id is required"}' >&2
    exit 1
fi

SESSION_ID="$1"
TIMEOUT="${2:-120}"
POLL_INTERVAL="${3:-2}"

start_time=$(date +%s)
last_ts=0
streaming=false

echo "Waiting for task completion (timeout: ${TIMEOUT}s)..." >&2

while true; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    
    # 检查超时
    if [ $elapsed -ge $TIMEOUT ]; then
        echo "" >&2
        echo "Timeout after ${TIMEOUT} seconds" >&2
        echo '{"success": false, "error": "timeout", "elapsed": '$elapsed'}'
        exit 2
    fi
    
    # 获取状态
    status_response=$(curl -s -X GET "${BASE_URL}/api/sessions/${SESSION_ID}/status" \
        -H "Content-Type: application/json")
    
    # 解析状态
    is_running=$(echo "$status_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('isRunning', True))" 2>/dev/null || echo "true")
    last_say=$(echo "$status_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('lastMessageSay', ''))" 2>/dev/null || echo "")
    waiting_input=$(echo "$status_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('waitingForUserInput', False))" 2>/dev/null || echo "false")
    
    # 检查是否等待用户输入
    if [ "$waiting_input" = "True" ] || [ "$waiting_input" = "true" ]; then
        echo "" >&2
        echo "Task waiting for user input" >&2
        echo "$status_response"
        exit 0
    fi
    
    # 检查是否完成
    if [ "$is_running" = "False" ] || [ "$is_running" = "false" ]; then
        echo "" >&2
        
        # 检查是否有错误
        if [ "$last_say" = "error" ]; then
            echo "Task completed with error" >&2
            echo "$status_response"
            exit 1
        else
            echo "Task completed successfully" >&2
            echo "$status_response"
            exit 0
        fi
    fi
    
    # 打印状态指示
    if [ "$last_say" = "text" ] || [ "$last_say" = "thinking" ]; then
        echo -n "s" >&2
    else
        echo -n "." >&2
    fi
    
    sleep $POLL_INTERVAL
done
