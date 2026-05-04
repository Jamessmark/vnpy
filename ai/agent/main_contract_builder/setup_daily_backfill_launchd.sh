#!/bin/zsh
set -euo pipefail

# macOS launchd 安装脚本（更原生）
#
# 用法：
#   sh ai/agent/main_contract_builder/setup_daily_backfill_launchd.sh
#   sh ai/agent/main_contract_builder/setup_daily_backfill_launchd.sh --remove
#   sh ai/agent/main_contract_builder/setup_daily_backfill_launchd.sh --status

LABEL="com.vnpy.dailybackfill"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
LOG_DIR="${ROOT_DIR}/ai/agent/main_contract_builder/reports"
OUT_LOG="${LOG_DIR}/daily_backfill.launchd.out.log"
ERR_LOG="${LOG_DIR}/daily_backfill.launchd.err.log"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "${LOG_DIR}"

create_plist() {
  cat > "${PLIST_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd ${ROOT_DIR} && uv run python ai/agent/main_contract_builder/daily_backfill.py --all --report ai/agent/main_contract_builder/reports/daily_backfill_latest.json</string>
  </array>

  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>16</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>16</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>16</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>16</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>16</integer><key>Minute</key><integer>0</integer></dict>
  </array>

  <key>StandardOutPath</key>
  <string>${OUT_LOG}</string>
  <key>StandardErrorPath</key>
  <string>${ERR_LOG}</string>

  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
EOF
}

remove_job() {
  launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
  rm -f "${PLIST_PATH}"
  echo "已移除 launchd 任务: ${LABEL}"
}

status_job() {
  echo "plist: ${PLIST_PATH}"
  if [[ -f "${PLIST_PATH}" ]]; then
    echo "状态: 已安装"
  else
    echo "状态: 未安装"
  fi
  launchctl print "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 && echo "launchctl: 已加载" || echo "launchctl: 未加载"
}

case "${1:-}" in
  --remove)
    remove_job
    ;;
  --status)
    status_job
    ;;
  *)
    remove_job >/dev/null 2>&1 || true
    create_plist
    launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}"
    launchctl enable "gui/$(id -u)/${LABEL}" || true
    echo "已安装 launchd 任务: ${LABEL}"
    echo "执行时间: 工作日 16:00"
    echo "命令: uv run python ai/agent/main_contract_builder/daily_backfill.py --all"
    echo "输出日志: ${OUT_LOG}"
    echo "错误日志: ${ERR_LOG}"
    ;;
esac
