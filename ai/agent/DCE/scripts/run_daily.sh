#!/bin/zsh
# DCE 每日决策系统 - launchd 包装脚本
# 由 ~/Library/LaunchAgents/com.vnpy.dce.daily.plist 每天 16:00 调用

set -euo pipefail

# ── 路径配置 ───────────────────────────────────────────────────────────────
VNPY_DIR="/Users/lishengkun/MyDocuments/Duke/stock/vnpy"
UV_BIN="/Users/lishengkun/.local/bin/uv"
LOG_DIR="${VNPY_DIR}/ai/agent/DCE/logs"

# ── 准备日志目录 ────────────────────────────────────────────────────────────
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/daily_$(date +%Y%m%d_%H%M%S).log"

# ── 运行 ──────────────────────────────────────────────────────────────────
echo "===== DCE 日报任务启动: $(date '+%Y-%m-%d %H:%M:%S') =====" | tee "${LOG_FILE}"

cd "${VNPY_DIR}"
"${UV_BIN}" run python ai/agent/DCE/run.py 2>&1 | tee -a "${LOG_FILE}"

echo "===== DCE 日报任务结束: $(date '+%Y-%m-%d %H:%M:%S') =====" | tee -a "${LOG_FILE}"
