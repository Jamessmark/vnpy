#!/bin/bash

# workspace-open.sh - 打开新工作空间
# 用法: ./workspace-open.sh <folder_path>
# 参数:
#   folder_path: 要打开的文件夹路径

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

if [ -z "$1" ]; then
    echo "Error: folder_path is required"
    echo "Usage: ./workspace-open.sh <folder_path>"
    exit 1
fi

FOLDER_PATH="$1"

response=$(curl -s -X POST "${BASE_URL}/api/workspaces" \
    -H "Content-Type: application/json" \
    -d "{\"folderPath\": \"${FOLDER_PATH}\"}")

echo "$response"
