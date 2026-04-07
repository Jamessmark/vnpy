#!/bin/bash

# workspace-list.sh - 获取工作空间列表
# 用法: ./workspace-list.sh

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

response=$(curl -s -X GET "${BASE_URL}/api/workspaces" \
    -H "Content-Type: application/json")

echo "$response"
