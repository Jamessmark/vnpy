#!/bin/bash

# health-check.sh - 健康检查
# 用法: ./health-check.sh
# 返回: 服务健康状态的 JSON 数据

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

response=$(curl -s -X GET "${BASE_URL}/api/health" \
    -H "Content-Type: application/json")

echo "$response"
