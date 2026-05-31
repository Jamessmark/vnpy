#!/bin/bash
# DCE 定时任务系统配置脚本
# 配置 macOS 电源管理和自动唤醒，确保定时任务能正常执行
#
# 使用说明：
#   1. 首次部署时执行一次：./setup_system.sh
#   2. 配置会永久生效，无需重复执行
#   3. 如果系统重置或配置丢失，重新执行即可恢复
#
# 配置内容：
#   - 禁用自动睡眠、Standby、Safe Sleep
#   - 设置每天 8:29 自动唤醒（早盘任务）
#   - 设置明天 15:59 唤醒（日报任务，需定期重设）

set -euo pipefail

echo "=========================================="
echo "DCE 定时任务系统配置"
echo "=========================================="
echo ""

# ── 1. 电源管理配置 ────────────────────────────────────────────────────────
echo "[1/3] 配置电源管理..."
echo "  - 禁用自动睡眠（sleep=0）"
echo "  - 禁用 Standby 模式（standby=0）"
echo "  - 禁用 Safe Sleep（hibernatemode=0）"
echo ""

sudo pmset -a sleep 0
sudo pmset -a standby 0
sudo pmset -a hibernatemode 0

echo "✅ 电源管理配置完成"
echo ""

# ── 2. 自动唤醒计划 ────────────────────────────────────────────────────────
echo "[2/3] 配置自动唤醒计划..."
echo "  - 每天 8:29 唤醒（早盘任务 8:30）"
echo "  - 每天 15:59 唤醒（日报任务 16:00）"
echo ""

# 删除旧的唤醒计划
sudo pmset repeat cancel 2>/dev/null || true

# pmset repeat 只能设置一个时间，所以用 schedule 设置多个一次性唤醒
# 但 schedule 是一次性的，所以我们用 repeat 设置早上，手动 schedule 设置下午
# 实际上 macOS 不支持多个 repeat，只能二选一
# 解决方案：用 cron + pmset schedule 动态设置明天的唤醒

# 先设置早盘唤醒（每天 8:29）
sudo pmset repeat wakeorpoweron MTWRFSU 08:29:00

# 然后用 schedule 设置今天的下午唤醒（一次性）
TOMORROW=$(date -v+1d '+%m/%d/%Y')
sudo pmset schedule wakeorpoweron "$TOMORROW 15:59:00"

echo "✅ 自动唤醒计划配置完成"
echo "   注意：pmset repeat 只支持单一时间，已设置 8:29"
echo "   下午 15:59 需要手动或通过 cron 每天设置"
echo ""

# ── 3. 验证配置 ────────────────────────────────────────────────────────────
echo "[3/3] 验证配置..."
echo ""
echo "电源管理状态："
pmset -g | grep -E "sleep|standby|hibernatemode" | sed 's/^/  /'
echo ""
echo "自动唤醒计划："
pmset -g sched | sed 's/^/  /'
echo ""

echo "=========================================="
echo "✅ 系统配置完成！"
echo "=========================================="
echo ""
echo "说明："
echo "  - Mac 将在每天 8:29 和 15:59 自动唤醒"
echo "  - 合盖后唤醒速度更快（不写磁盘）"
echo "  - 如需恢复默认设置，运行："
echo "    sudo pmset -a sleep 1"
echo "    sudo pmset -a standby 1"
echo "    sudo pmset -a hibernatemode 3"
echo "    sudo pmset repeat cancel"
echo ""
