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

# 用 caffeinate 阻止任务运行期间系统睡眠，并触发网络接口激活
caffeinate -i -s -t 3600 &
CAFFEINATE_PID=$!
trap "kill ${CAFFEINATE_PID} 2>/dev/null" EXIT

# 等待网络就绪（最多等 180 秒，验证 DNS 可用，兼容唤醒后网络延迟）
echo "等待网络就绪..." | tee -a "${LOG_FILE}"
for i in $(seq 1 36); do
    # 直接测试 DNS 解析 + HTTP 可达，比 scutil/ping 更严格
    if curl -sf --max-time 4 --dns-timeout 3 https://www.baidu.com -o /dev/null 2>/dev/null; then
        echo "✅ 网络已就绪（第 ${i} 次检测，DNS+HTTP）" | tee -a "${LOG_FILE}"
        break
    fi
    echo "  第 ${i} 次等待网络（5s）..." | tee -a "${LOG_FILE}"
    sleep 5
done

cd "${VNPY_DIR}"
"${UV_BIN}" run python ai/agent/DCE/run.py --mode daily 2>&1 | tee -a "${LOG_FILE}"

echo "===== DCE 日报任务结束: $(date '+%Y-%m-%d %H:%M:%S') =====" | tee -a "${LOG_FILE}"
