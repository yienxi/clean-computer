#!/bin/sh
# cc.sh — clean-computer 统一入口（v1.5）
# 傻瓜式调用：自动检测操作系统，把 analyze.py / report.py / clean_*.sh|ps1 / restore_*.sh|ps1 收拢成 7 个子命令。
#
# 用法:
#   cc.sh scan                只读扫描 + 人读报告
#   cc.sh report [输出.html]  扫描 + 生成 HTML 可视化报告（macOS 自动打开）
#   cc.sh clean <品类>        预览待清理项（不删除）；加 --confirm 才送回收站
#   cc.sh restore             预览可回滚项；加 --all 才恢复
#   cc.sh snapshot [标签]     存基线快照（供清理后对比）
#   cc.sh compare [标签]      对比最近快照，输出释放量
#   cc.sh status              查看 manifest / 快照 / 最近执行
#   cc.sh help                帮助
#
# 安全：clean / restore 默认仅预览，必须显式 --confirm / --all 才会执行。

set -u
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PY="${PYTHON:-python3}"
ANALYZE="$SCRIPT_DIR/analyze.py"
REPORT="$SCRIPT_DIR/report.py"

# —— OS 检测 ——
OS="unknown"
case "$(uname -s 2>/dev/null)" in
  Darwin) OS="macos";;
  MINGW*|MSYS*|CYGWIN*) OS="windows";;
esac

CLEAN=""
RESTORE=""
if [ "$OS" = "macos" ]; then
  CLEAN="$SCRIPT_DIR/clean_macos.sh"
  RESTORE="$SCRIPT_DIR/restore_macos.sh"
elif [ "$OS" = "windows" ]; then
  CLEAN="$SCRIPT_DIR/clean_windows.ps1"
  RESTORE="$SCRIPT_DIR/restore_windows.ps1"
fi

usage() {
  echo "用法: cc.sh <命令> [参数]"
  echo ""
  echo "  scan                只读扫描 + 人读报告"
  echo "  report [输出.html]  扫描 + 生成 HTML 可视化报告（macOS 自动打开）"
  echo "  clean <品类>        预览待清理项（不删除）；加 --confirm 才送回收站"
  echo "  restore             预览可回滚项；加 --all 才恢复"
  echo "  snapshot [标签]     存基线快照（供清理后对比）"
  echo "  compare [标签]      对比最近快照，输出释放量"
  echo "  status              查看 manifest / 快照 / 最近执行"
  echo "  help                帮助"
  echo ""
  echo "品类: caches logs xcode homebrew npm containers system trash (macOS) | temp edge chrome wechat winupdate (Windows)"
  echo ""
  echo "安全: clean / restore 默认仅预览，必须显式 --confirm / --all 才会执行。"
}

# —— 子命令实现 ——
cmd_scan() {
  "$PY" "$ANALYZE" --mode all
}

cmd_report() {
  out="${1:-clean-report.html}"
  mkdir -p "$(dirname "$out")" 2>/dev/null || true
  "$PY" "$ANALYZE" --mode all --json | "$PY" "$REPORT" -o "$out" --title "clean-computer 分析报告"
  echo ""
  if [ "$OS" = "macos" ] && [ -f "$out" ]; then open "$out"; fi
  echo "报告已生成: $(cd "$(dirname "$out")" && pwd)/$(basename "$out")"
}

cmd_clean() {
  cat="$1"; shift
  confirm=""
  for a in "$@"; do [ "$a" = "--confirm" ] && confirm="--confirm"; done
  if [ "$OS" = "macos" ]; then
    bash "$CLEAN" --category "$cat" $confirm
  else
    if [ "$confirm" = "--confirm" ]; then
      powershell -ExecutionPolicy Bypass -File "$CLEAN" -Category "$cat" -Confirm
    else
      powershell -ExecutionPolicy Bypass -File "$CLEAN" -Category "$cat"
    fi
  fi
}

cmd_restore() {
  all=""
  for a in "$@"; do [ "$a" = "--all" ] && all="--all"; done
  if [ "$OS" = "macos" ]; then
    bash "$RESTORE" $all
  else
    if [ "$all" = "--all" ]; then
      powershell -ExecutionPolicy Bypass -File "$RESTORE" -All
    else
      powershell -ExecutionPolicy Bypass -File "$RESTORE"
    fi
  fi
}

cmd_snapshot() {
  tag="${1:-}"
  if [ -n "$tag" ]; then
    "$PY" "$ANALYZE" --mode scan --snapshot --tag "$tag"
  else
    "$PY" "$ANALYZE" --mode scan --snapshot
  fi
}

cmd_compare() {
  tag="${1:-}"
  if [ -n "$tag" ]; then
    "$PY" "$ANALYZE" --mode scan --compare --tag "$tag"
  else
    "$PY" "$ANALYZE" --mode scan --compare
  fi
}

cmd_status() {
  echo "=== clean-computer 状态 ==="
  echo "OS: $OS"
  if [ "$OS" = "macos" ]; then MF="$HOME/.clean-computer/manifest.jsonl";
  else MF="$USERPROFILE/.clean-computer/manifest.jsonl"; fi
  if [ -f "$MF" ]; then
    echo "manifest: $MF"
    echo "  总记录: $(wc -l < "$MF" | tr -d ' ') 行"
    echo "  moved(可回滚): $(grep -c '"status":"moved"' "$MF" 2>/dev/null || echo 0)"
    echo "  restored:      $(grep -c '"status":"restored"' "$MF" 2>/dev/null || echo 0)"
  else
    echo "manifest: 无（尚未执行过清理）"
  fi
  echo ""
  echo "快照: $(ls "$HOME/.clean-computer"/snapshot-*.json 2>/dev/null | wc -l | tr -d ' ') 个"
  echo ""
  echo "常用命令: cc.sh scan | cc.sh report | cc.sh clean caches | cc.sh restore"
}

# —— 主分发 ——
case "${1:-help}" in
  scan)     cmd_scan;;
  report)   cmd_report "${2:-}";;
  clean)    [ -n "${2:-}" ] && cmd_clean "$2" "${@:3}" || { echo "用法: cc.sh clean <品类> [--confirm]"; exit 1; };;
  restore)  cmd_restore "${@:2}";;
  snapshot) cmd_snapshot "${2:-}";;
  compare)  cmd_compare "${2:-}";;
  status)   cmd_status;;
  help|-h|--help) usage;;
  *) echo "未知命令: ${1:-}"; usage; exit 1;;
esac
