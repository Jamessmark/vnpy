#!/bin/zsh
# DCE 早盘分析 - launchd 包装脚本
# 由 ~/Library/LaunchAgents/com.vnpy.dce.morning.plist 每天 08:30 调用
# 不拉取 API 数据，直接用数据库最新数据 + 新闻分析生成报告

set -euo pipefail

VNPY_DIR="/Users/lishengkun/MyDocuments/Duke/stock/vnpy"
UV_BIN="/Users/lishengkun/.local/bin/uv"
LOG_DIR="${VNPY_DIR}/ai/agent/DCE/logs"

mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/morning_$(date +%Y%m%d_%H%M%S).log"

echo "===== DCE 早盘分析启动: $(date '+%Y-%m-%d %H:%M:%S') =====" | tee "${LOG_FILE}"

cd "${VNPY_DIR}"
"${UV_BIN}" run python ai/agent/DCE/run.py --no-fetch 2>&1 | tee -a "${LOG_FILE}"

echo "===== DCE 早盘分析结束: $(date '+%Y-%m-%d %H:%M:%S') =====" | tee -a "${LOG_FILE}"
