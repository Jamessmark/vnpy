#!/bin/bash

# session-find.sh - 通过模糊名字查找 Session 并返回工作空间信息
# 用法: ./session-find.sh <search_pattern>
# 参数:
#   search_pattern: 模糊搜索模式（必填）
# 
# 功能:
#   1. 获取所有工作空间
#   2. 获取每个工作空间下的 Session 列表
#   3. 模糊匹配 Session 名称
#   4. 返回匹配的 Session 及其所属工作空间信息
# 
# 返回:
#   - 成功: {"success": true, "matches": [{session: {...}, workspace: {...}}, ...]}
#   - 失败: {"success": false, "error": "..."}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo '{"success": false, "error": "search_pattern is required"}' >&2
    exit 1
fi

SEARCH_PATTERN="$1"

# 1. 获取所有工作空间
workspaces_response=$(curl -s -X GET "${BASE_URL}/api/workspaces" \
    -H "Content-Type: application/json")

# 2. 获取 Session 列表（当前工作空间）
sessions_response=$(curl -s -X GET "${BASE_URL}/api/sessions" \
    -H "Content-Type: application/json")

# 3. 搜索匹配的 Session
result=$(python3 -c "
import sys
import json

# 解析参数
search_pattern = '$SEARCH_PATTERN'.lower()

# 解析工作空间数据
try:
    workspaces_data = json.loads('''$workspaces_response''')
    workspaces = workspaces_data.get('data', {}).get('workspaces', [])
    current_workspace_id = workspaces_data.get('data', {}).get('currentWorkspaceId', '')
except:
    workspaces = []
    current_workspace_id = ''

# 解析 Session 数据
try:
    sessions_data = json.loads('''$sessions_response''')
    sessions = sessions_data.get('data', {}).get('sessionList', [])
except:
    sessions = []

# 查找匹配的 Session
matches = []
for session in sessions:
    session_name = session.get('sessionName', '').lower()
    session_id = session.get('sessionId', '').lower()
    
    # 检查是否匹配
    if search_pattern in session_name or search_pattern in session_id:
        # 找到所属工作空间
        workspace = None
        for ws in workspaces:
            if ws.get('workspaceId') == current_workspace_id:
                workspace = ws
                break
        
        matches.append({
            'session': session,
            'workspace': workspace
        })

if matches:
    print(json.dumps({
        'success': True,
        'matches': matches,
        'count': len(matches),
        'searchPattern': '$SEARCH_PATTERN'
    }))
else:
    print(json.dumps({
        'success': False,
        'error': 'No session matching \"' + '$SEARCH_PATTERN' + '\" found',
        'searchPattern': '$SEARCH_PATTERN',
        'totalSessions': len(sessions)
    }))
" 2>/dev/null)

if [ -z "$result" ]; then
    echo '{"success": false, "error": "Failed to parse response"}'
    exit 1
fi

echo "$result"
