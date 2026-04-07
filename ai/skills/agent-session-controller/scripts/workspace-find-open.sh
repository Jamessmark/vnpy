#!/bin/bash

# workspace-find-open.sh - 模糊匹配目录并打开工作空间
# 用法: ./workspace-find-open.sh <search_pattern> [base_path]
# 参数:
#   search_pattern: 模糊搜索模式（必填）
#   base_path: 搜索的基础路径（默认: ~）
# 
# 功能:
#   1. 首先检查是否已有匹配的工作空间打开
#   2. 如果有，返回已存在的工作空间信息
#   3. 如果没有，在文件系统中搜索匹配的目录
#   4. 找到后打开该工作空间
# 
# 返回:
#   - 成功: {"success": true, "action": "opened|existing", "workspace": {...}}
#   - 失败: {"success": false, "error": "..."}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo '{"success": false, "error": "search_pattern is required"}' >&2
    exit 1
fi

SEARCH_PATTERN="$1"
BASE_PATH="${2:-$HOME}"

# 1. 获取已打开的工作空间列表
workspaces_response=$(curl -s -X GET "${BASE_URL}/api/workspaces" \
    -H "Content-Type: application/json")

# 检查是否有匹配的已打开工作空间
existing_workspace=$(echo "$workspaces_response" | python3 -c "
import sys
import json
import re

try:
    data = json.load(sys.stdin)
    workspaces = data.get('data', {}).get('workspaces', [])
    pattern = '$SEARCH_PATTERN'.lower()
    
    for ws in workspaces:
        name = ws.get('name', '').lower()
        path = ws.get('path', '').lower()
        
        # 检查名称或路径是否包含搜索模式
        if pattern in name or pattern in path:
            print(json.dumps({
                'success': True,
                'action': 'existing',
                'workspace': ws,
                'message': 'Workspace already opened'
            }))
            sys.exit(0)
    
    print('null')
except Exception as e:
    print('null')
" 2>/dev/null)

if [ "$existing_workspace" != "null" ] && [ -n "$existing_workspace" ]; then
    echo "$existing_workspace"
    exit 0
fi

# 2. 在文件系统中搜索匹配的目录
# 使用 find 命令搜索目录（限制深度和时间）
found_dir=$(find "$BASE_PATH" -maxdepth 4 -type d -name "*${SEARCH_PATTERN}*" 2>/dev/null | head -1)

if [ -z "$found_dir" ]; then
    # 尝试更宽松的搜索（忽略大小写）
    found_dir=$(find "$BASE_PATH" -maxdepth 4 -type d -iname "*${SEARCH_PATTERN}*" 2>/dev/null | head -1)
fi

if [ -z "$found_dir" ]; then
    echo "{\"success\": false, \"error\": \"No directory matching '${SEARCH_PATTERN}' found in ${BASE_PATH}\"}"
    exit 1
fi

# 3. 打开找到的目录作为工作空间
open_response=$(curl -s -X POST "${BASE_URL}/api/workspaces" \
    -H "Content-Type: application/json" \
    -d "{\"folderPath\": \"${found_dir}\"}")

# 检查是否成功
success=$(echo "$open_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('success', False))" 2>/dev/null || echo "false")

if [ "$success" = "True" ] || [ "$success" = "true" ]; then
    workspace_id=$(echo "$open_response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('workspaceId', ''))" 2>/dev/null)
    echo "{\"success\": true, \"action\": \"opened\", \"foundPath\": \"${found_dir}\", \"workspaceId\": \"${workspace_id}\", \"message\": \"Workspace opened successfully\"}"
    exit 0
else
    echo "{\"success\": false, \"error\": \"Failed to open workspace\", \"foundPath\": \"${found_dir}\", \"response\": ${open_response}}"
    exit 1
fi
