#!/bin/bash

# workspace-reload.sh - 重载工作空间（类似 VSCode Reload Window）
# 用法: ./workspace-reload.sh <workspace_id> [--force]
# 参数:
#   workspace_id: 要重载的工作空间 ID
#   --force: 强制重载（即使是 Coordinator 也会重载）
# 
# 功能说明:
#   重新加载指定工作空间，效果等同于 VSCode 的 "Developer: Reload Window" 命令。
#   适用于需要刷新扩展状态或应用配置更改的场景。
#
# 注意事项:
#   - 默认不能重载 Coordinator 自身的工作空间（会返回错误）
#   - 使用 --force 可以强制重载 Coordinator，但服务会中断
#   - 强制重载 Coordinator 时，不要关注返回结果（响应可能无法送达）
#   - 重载过程中该工作空间会暂时断开连接，完成后自动重新注册

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo "Error: workspace_id is required"
    echo "Usage: ./workspace-reload.sh <workspace_id> [--force]"
    exit 1
fi

WORKSPACE_ID="$1"
FORCE=false

# 检查是否有 --force 参数
if [ "$2" = "--force" ] || [ "$2" = "-f" ]; then
    FORCE=true
fi

if [ "$FORCE" = true ]; then
    # 强制重载模式：不等待响应，因为服务可能会立即中断
    echo "Warning: Force reloading workspace (service may be interrupted)..."
    curl -s -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/reload" \
        -H "Content-Type: application/json" \
        -d '{"force": true}' \
        --max-time 2 || echo '{"note": "Request sent, response may not be received as service is restarting"}'
else
    # 普通重载模式
    response=$(curl -s -X POST "${BASE_URL}/api/workspaces/${WORKSPACE_ID}/reload" \
        -H "Content-Type: application/json")
    echo "$response"
fi
