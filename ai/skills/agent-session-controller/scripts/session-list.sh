#!/bin/bash

# session-list.sh - 获取 Session 列表
# 用法: ./session-list.sh
# 返回: Session 列表的 JSON 数据

set -e

BASE_URL="${DUET_API_URL:-http://localhost:3459}"

response=$(curl -s -X GET "${BASE_URL}/api/sessions" \
    -H "Content-Type: application/json")

echo "$response"
