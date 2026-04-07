#!/bin/bash

# workspace-close.sh - 关闭工作空间
# 用法: ./workspace-close.sh <workspace_id>
# 参数:
#   workspace_id: 要关闭的工作空间 ID

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo "Error: workspace_id is required"
    echo "Usage: ./workspace-close.sh <workspace_id>"
    exit 1
fi

WORKSPACE_ID="$1"

response=$(curl -s -X DELETE "${BASE_URL}/api/workspaces/${WORKSPACE_ID}" \
    -H "Content-Type: application/json")

echo "$response"
