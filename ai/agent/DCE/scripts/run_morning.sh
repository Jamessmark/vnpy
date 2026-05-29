#!/bin/zsh
# DCE 早盘分析 - launchd 包装脚本
# 由 ~/Library/LaunchAgents/com.vnpy.dce.morning.plist 每天 08:30 调用
# 不拉取 API 数据，直接用数据库最新数据 + 新闻分析生成报告

set -euo pipefail

VNPY_DIR="/Users/lishengkun/MyDocuments/Duke/stock/vnpy"
UV_BIN="/Users/lishengkun/.local/bin/uv"
LOG_DIR="${VNPY_DIR}/ai/agent/DCE/logs/auto"

mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/morning_$(date +%Y%m%d_%H%M%S).log"

echo "===== DCE 早盘分析启动: $(date '+%Y-%m-%d %H:%M:%S') =====" | tee "${LOG_FILE}"

# 等待网络就绪（最多等 60 秒）
echo "等待网络就绪..." | tee -a "${LOG_FILE}"
for i in $(seq 1 12); do
    if ping -c 1 -t 3 223.5.5.5 &>/dev/null; then
        echo "✅ 网络已就绪（第 ${i} 次检测）" | tee -a "${LOG_FILE}"
        break
    fi
    echo "  第 ${i} 次等待网络（5s）..." | tee -a "${LOG_FILE}"
    sleep 5
done

cd "${VNPY_DIR}"
"${UV_BIN}" run python ai/agent/DCE/run.py --mode morning --no-fetch 2>&1 | tee -a "${LOG_FILE}"

echo "===== DCE 早盘分析结束: $(date '+%Y-%m-%d %H:%M:%S') =====" | tee -a "${LOG_FILE}"
