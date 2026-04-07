#!/bin/bash

# system-info.sh - 获取系统信息
# 用法: ./system-info.sh
# 返回: 系统信息的 JSON 数据，包含:
#   - coordinatorPort: WebSocket 服务端口
#   - httpApiPort: HTTP API 服务端口
#   - registeredWorkspaces: 已注册的工作空间列表
#   - defaultWorkspaceId: 默认工作空间 ID
#   - workspaceCount: 工作空间数量
#   - wsConnections: WebSocket 连接数
#   - handlers: 支持的 Handler 列表
#   - uptime: 服务运行时长

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

response=$(curl -s -X GET "${BASE_URL}/api/system/info" \
    -H "Content-Type: application/json")

echo "$response"
