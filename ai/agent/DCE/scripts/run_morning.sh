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

# 等待网络就绪（最多等 180 秒，兼容 hibernatemode=3 冷启动）
echo "等待网络就绪..." | tee -a "${LOG_FILE}"
for i in $(seq 1 36); do
    # 优先用 scutil 检测系统网络状态（比 ping 更早感知到网络就绪）
    if scutil --nwi 2>/dev/null | grep -q "IPv4 network reachable\|Reachable"; then
        echo "✅ 网络已就绪（第 ${i} 次检测，scutil）" | tee -a "${LOG_FILE}"
        break
    fi
    # 备用：直接 ping 阿里 DNS
    if ping -c 1 -t 2 223.5.5.5 &>/dev/null; then
        echo "✅ 网络已就绪（第 ${i} 次检测，ping）" | tee -a "${LOG_FILE}"
        break
    fi
    echo "  第 ${i} 次等待网络（5s）..." | tee -a "${LOG_FILE}"
    sleep 5
done

cd "${VNPY_DIR}"
"${UV_BIN}" run python ai/agent/DCE/run.py --mode morning --no-fetch 2>&1 | tee -a "${LOG_FILE}"

echo "===== DCE 早盘分析结束: $(date '+%Y-%m-%d %H:%M:%S') =====" | tee -a "${LOG_FILE}"
