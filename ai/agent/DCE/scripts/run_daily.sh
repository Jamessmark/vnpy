#!/bin/zsh
# DCE 每日决策系统 - launchd 包装脚本
# 由 ~/Library/LaunchAgents/com.vnpy.dce.daily.plist 每天 16:00 调用

set -euo pipefail

# ── 路径配置 ───────────────────────────────────────────────────────────────
VNPY_DIR="/Users/lishengkun/MyDocuments/Duke/stock/vnpy"
UV_BIN="/Users/lishengkun/.local/bin/uv"
LOG_DIR="${VNPY_DIR}/ai/agent/DCE/logs/auto"

# ── 准备日志目录 ────────────────────────────────────────────────────────────
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/daily_$(date +%Y%m%d_%H%M%S).log"

# ── 运行 ──────────────────────────────────────────────────────────────────
echo "===== DCE 日报任务启动: $(date '+%Y-%m-%d %H:%M:%S') =====" | tee "${LOG_FILE}"

# 等待网络就绪（最多等 180 秒，兼容 hibernatemode=3 冷启动）
echo "等待网络就绪..." | tee -a "${LOG_FILE}"
for i in $(seq 1 36); do
    if scutil --nwi 2>/dev/null | grep -q "IPv4 network reachable\|Reachable"; then
        echo "✅ 网络已就绪（第 ${i} 次检测，scutil）" | tee -a "${LOG_FILE}"
        break
    fi
    if ping -c 1 -t 2 223.5.5.5 &>/dev/null; then
        echo "✅ 网络已就绪（第 ${i} 次检测，ping）" | tee -a "${LOG_FILE}"
        break
    fi
    echo "  第 ${i} 次等待网络（5s）..." | tee -a "${LOG_FILE}"
    sleep 5
done

cd "${VNPY_DIR}"
"${UV_BIN}" run python ai/agent/DCE/run.py --mode daily 2>&1 | tee -a "${LOG_FILE}"

echo "===== DCE 日报任务结束: $(date '+%Y-%m-%d %H:%M:%S') =====" | tee -a "${LOG_FILE}"
