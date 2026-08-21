#!/bin/sh
# clean_macos.sh — 引导式 macOS 清理（默认 dry-run 仅预览；删除需显式 --confirm）
# v1.3 安全机制（写入 skill 的硬规则）：
#   1) 仅处理"可恢复的安全子路径"，绝不含 Desktop/Downloads/Documents/Home 根/系统根。
#   2) 移入废纸篓(~/.Trash)而非 rm，删除可逆。
#   3) 单批最多 10 项，超出需再次运行。
#   4) 任何删除前先预览路径与大小，并要求 y/N 确认。
#   5) manifest 清理日志（~/.clean-computer/manifest.jsonl），支持一键回滚 restore_macos.sh。
#   6) 程序化风险门禁：仅接受白名单精确路径，通配符/父路径直接拒绝。
#   7) 幂等：已清理路径二次执行安全跳过，不重复误删新产生内容（同路径会再次记录）。
set -u

CATEGORY=""
CONFIRM=0
MANIFEST_DIR="${HOME}/.clean-computer"
MANIFEST="${MANIFEST_DIR}/manifest.jsonl"

# 白名单：品类 → 精确路径（程序化风险门禁的基础，禁止任何其他路径）
targets_for() {
  case "$1" in
    caches)    echo "$HOME/Library/Caches";;
    logs)      echo "$HOME/Library/Logs";;
    xcode)     echo "$HOME/Library/Developer/Xcode/DerivedData";;
    homebrew)  echo "$HOME/Library/Caches/Homebrew";;
    npm)       echo "$HOME/.npm/_cacache";;
    containers) echo "$HOME/Library/Containers";;
    system)    echo "/Library/Caches";;
    trash)     echo "$HOME/.Trash";;
    *) echo "";;
  esac
}

# 风险门禁：路径必须是白名单的精确匹配（或废纸篓品类），否则拒绝
gate_path() {
  p="$1"
  for c in caches logs xcode homebrew npm containers system; do
    [ "$p" = "$(targets_for $c)" ] && return 0
  done
  return 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --category) CATEGORY="$2"; shift 2;;
    --confirm)  CONFIRM=1; shift;;
    --dry-run|-n) shift;;
    -h|--help) printf '用法: clean_macos.sh --category <caches|logs|xcode|homebrew|npm|containers|system|trash> [--confirm]\n默认 dry-run 仅预览，不删除。\n'; exit 0;;
    *) shift;;
  esac
done

[ -z "$CATEGORY" ] && { echo "请指定 --category。可选: caches logs xcode homebrew npm containers system trash"; exit 1; }

# 程序化风险门禁：目标路径必须精确命中白名单
TARGET=$(targets_for "$CATEGORY")
if [ -z "$TARGET" ]; then
  echo "✗ 风险门禁拒绝：未知品类 '$CATEGORY'。"
  exit 1
fi
if [ "$CATEGORY" != "trash" ] && ! gate_path "$TARGET"; then
  echo "✗ 风险门禁拒绝：路径不在安全白名单内 → $TARGET"
  exit 1
fi

TRASH_DIR="$HOME/.Trash"

# 幂等检查：该品类目标是否已在 manifest 有"已移入"记录且路径不存在
already_cleaned() {
  [ -f "$MANIFEST" ] || return 1
  grep -q "\"category\":\"$1\"" "$MANIFEST" 2>/dev/null && [ ! -e "$(targets_for $1)" ]
}

# 写 manifest 一行
log_manifest() {
  [ -d "$MANIFEST_DIR" ] || mkdir -p "$MANIFEST_DIR"
  ts=$(date +%Y-%m-%dT%H:%M:%S%z)
  printf '{"ts":"%s","category":"%s","src":"%s","dest":"%s","size_bytes":%s,"status":"moved"}\n' \
    "$ts" "$CATEGORY" "$1" "$2" "$3" >> "$MANIFEST"
}

# 移入废纸篓（可逆）。若跨卷 mv 失败，提示不改 rm。
to_trash() {
  src="$1"; [ -e "$src" ] || return 0
  ts=$(date +%Y%m%d%H%M%S)
  base=$(basename "$src")
  dest="$TRASH_DIR/${base}.cleaned-${ts}"
  sz=$(du -sk "$src" 2>/dev/null | awk '{print $1*1024}')
  [ -z "$sz" ] && sz=0
  if mv -f "$src" "$dest" 2>/dev/null; then
    echo "  ✓ 已移入废纸篓(可恢复): $dest"
    log_manifest "$src" "$dest" "$sz"
  else
    echo "  ✗ 移动失败(可能跨卷)，已跳过，未删除: $src"
  fi
}

if [ "$CONFIRM" -ne 1 ]; then
  echo "=== DRY-RUN 预览：将被处理（不删除）==="
  echo "  [风险门禁] 目标须精确命中白名单：$TARGET"
  if [ -e "$TARGET" ]; then
    sz=$(du -sh "$TARGET" 2>/dev/null | cut -f1)
    echo "  [$CATEGORY] $TARGET  ($sz)"
  else
    echo "  [$CATEGORY] $TARGET — 不存在"
  fi
  echo "确认清理请加 --confirm（移入废纸篓，可恢复；记录于 manifest 支持回滚）。"
  exit 0
fi

# 幂等：若已清理过且路径不存在，直接提示并退出
if [ "$CATEGORY" != "trash" ] && already_cleaned "$CATEGORY"; then
  echo "  幂等提示: '$CATEGORY' 已按 manifest 记录清理过，且路径不存在。若为新产生的缓存，重新运行即可（会再次记录）。"
fi

echo "⚠️ 即将把以下目标移入废纸篓（可恢复，非永久删除）："
n=0
[ -e "$TARGET" ] && { echo "  - $TARGET"; n=$((n+1)); }
[ "$CATEGORY" = "trash" ] && echo "  （清空废纸篓=永久删除已丢弃文件，不可恢复，已单独警告）"
[ "$n" -eq 0 ] && { echo "无目标可处理。"; exit 0; }

printf "确认执行？(y/N) "; read -r ans
[ "$ans" = "y" ] || { echo "已取消。"; exit 0; }

i=0
if [ "$CATEGORY" = "trash" ]; then
  # 清空废纸篓前先记录（不可逆操作，仅记状态供审计）
  ts=$(date +%Y-%m-%dT%H:%M:%S%z)
  [ -d "$MANIFEST_DIR" ] || mkdir -p "$MANIFEST_DIR"
  printf '{"ts":"%s","category":"trash","src":"~/.Trash","dest":"(emptied)","size_bytes":0,"status":"emptied"}\n' \
    "$ts" >> "$MANIFEST"
  osascript -e 'tell application "Finder" to empty trash' 2>/dev/null && echo "  ✓ 废纸篓已清空（不可恢复）"
else
  to_trash "$TARGET"
  i=$((i+1))
  [ "$i" -ge 10 ] && { echo "  已达单批上限 10 项，剩余请再次运行。"; }
fi
echo "=== 完成。回滚请运行: restore_macos.sh [--category $CATEGORY] ==="
