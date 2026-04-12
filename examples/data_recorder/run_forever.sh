#!/bin/bash
# =============================================================================
# VeighNa 行情录制守护脚本
#
# 加执行权限（只需一次）
# chmod +x examples/data_recorder/run_forever.sh
# 
# 使用方法（后台启动，关闭终端也不会停止）：
#   nohup bash examples/data_recorder/run_forever.sh > examples/data_recorder/log/recorder.log 2>&1 &
#
# 查看日志：
#   tail -f examples/data_recorder/log/recorder.log
#
# 停止录制：
: <<'STOP_COMMANDS'

PID=$(cat examples/data_recorder/log/recorder.pid) && kill $PID
pkill -f "examples/data_recorder/data_recorder.py"
pkill -f "examples/data_recorder/run_forever.sh"

STOP_COMMANDS
# =============================================================================

# 脚本所在目录（自动推断项目根目录，不依赖当前工作目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/log"
PID_FILE="$LOG_DIR/recorder.pid"

# uv 可执行文件路径
UV_BIN="$HOME/.local/bin/uv"

# 创建 log 目录
mkdir -p "$LOG_DIR"

# 记录守护脚本本身的 PID
echo $$ > "$PID_FILE"

echo "============================================"
echo "  VeighNa 行情录制守护脚本启动"
echo "  项目目录: $PROJECT_DIR"
echo "  日志目录: $LOG_DIR"
echo "  守护进程 PID: $$（已写入 $PID_FILE）"
echo "  启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  停止命令: PID=\$(cat $PID_FILE) && kill \$PID"
echo "============================================"

# 切换到项目目录（uv run 需要在项目根目录执行才能找到 .venv）
cd "$PROJECT_DIR" || {
    echo "[ERROR] 无法切换到项目目录: $PROJECT_DIR"
    exit 1
}

# 检查 uv 是否存在
if [ ! -f "$UV_BIN" ]; then
    UV_BIN=$(which uv 2>/dev/null)
    if [ -z "$UV_BIN" ]; then
        echo "[ERROR] 找不到 uv，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

echo "[INFO] 使用 uv: $UV_BIN"

# 捕获 SIGTERM/SIGINT 信号，优雅退出
trap 'echo "[$(date "+%Y-%m-%d %H:%M:%S")] 收到停止信号，退出守护脚本"; rm -f "$PID_FILE"; exit 0' SIGTERM SIGINT

# 重启计数器
RESTART_COUNT=0

while true; do
    RESTART_COUNT=$((RESTART_COUNT + 1))
    echo ""
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 第 $RESTART_COUNT 次启动 data_recorder.py ..."

    # 使用 uv run 启动（自动使用 .venv，无需手动 source activate）
    "$UV_BIN" run python examples/data_recorder/data_recorder.py

    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 程序退出，退出码: $EXIT_CODE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 10 秒后自动重启..."
    sleep 10
done
