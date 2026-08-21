#!/bin/sh
# restore_macos.sh — 从 manifest 一键回滚清理动作（v1.3）
# 读取 ~/.clean-computer/manifest.jsonl，把记录中"已移入废纸篓"的项移回原路径。
# 安全约束：
#   1) 仅恢复 manifest 中 status=moved 的记录；status=emptied（清空废纸篓）不可恢复，仅展示。
#   2) 目标原路径已存在时跳过（避免覆盖现有文件）。
#   3) 恢复后把该记录标记 status=restored（重建 manifest，保留审计）。
# 用法:
#   restore_macos.sh                  # 预览所有可恢复项
#   restore_macos.sh --all            # 恢复所有可恢复项
#   restore_macos.sh --category <品类> --all   # 仅恢复某品类
#   restore_macos.sh --dry-run        # 仅预览不恢复
set -u

MANIFEST="${HOME}/.clean-computer/manifest.jsonl"
ALL=0
CATEGORY=""
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --all) ALL=1; shift;;
    --category) CATEGORY="$2"; shift 2;;
    --dry-run|-n) DRY=1; shift;;
    -h|--help) printf '用法: restore_macos.sh [--all | --category <品类>] [--dry-run]\n从 manifest 恢复已移入废纸篓的清理项。\n'; exit 0;;
    *) shift;;
  esac
done

[ -f "$MANIFEST" ] || { echo "无 manifest（${MANIFEST}），没有可恢复的清理记录。"; exit 0; }

field() { echo "$1" | sed "s/.*\"$2\":\"\([^\"]*\)\".*/\1/"; }

TMPLINES=$(mktemp /tmp/restore_lines.XXXXXX)
TMPLOOP=$(mktemp /tmp/restore_loop.XXXXXX)
grep -h '"status":"moved"\|"status":"emptied"' "$MANIFEST" > "$TMPLINES"

echo "=== 可恢复项（status=moved）==="
while IFS= read -r line; do
  [ -z "$line" ] && continue
  case "$line" in
    *'"status":"emptied"'*)
      ts=$(field "$line" ts)
      echo "  (审计) $ts 清空废纸篓 —— 不可恢复"
      continue
      ;;
  esac
  cat=$(field "$line" category)
  src=$(field "$line" src)
  dest=$(field "$line" dest)
  [ -n "$CATEGORY" ] && [ "$cat" != "$CATEGORY" ] && continue
  if [ -e "$dest" ]; then
    echo "  [$cat] $src"
    echo "        ← $dest"
  else
    echo "  [$cat] $src  （废纸篓项已不存在，跳过）"
  fi
done < "$TMPLINES"

if [ "$DRY" -eq 1 ] || [ "$ALL" -ne 1 ]; then
  echo ""
  echo "以上为预览。真正恢复请加 --all（或 --category <品类> --all）。"
  rm -f "$TMPLINES" "$TMPLOOP"
  exit 0
fi

echo ""
echo "=== 开始恢复（原路径已存在则跳过，避免覆盖）==="
restored=0
while IFS= read -r line; do
  [ -z "$line" ] && continue
  case "$line" in
    *'"status":"emptied"'*) continue;;
  esac
  cat=$(field "$line" category)
  src=$(field "$line" src)
  dest=$(field "$line" dest)
  if [ -n "$CATEGORY" ] && [ "$cat" != "$CATEGORY" ]; then
    echo "$line" >> "$TMPLOOP"
    continue
  fi
  if [ -e "$src" ]; then
    echo "  ✗ 跳过（原路径已存在）: $src"
    echo "$line" >> "$TMPLOOP"
    continue
  fi
  if [ -e "$dest" ]; then
    mkdir -p "$(dirname "$src")" 2>/dev/null
    if mv -f "$dest" "$src" 2>/dev/null; then
      echo "  ✓ 已恢复: $src"
      echo "$line" | sed 's/"status":"moved"/"status":"restored"/' >> "$TMPLOOP"
      restored=$((restored+1))
    else
      echo "  ✗ 恢复失败: $dest → $src"
      echo "$line" >> "$TMPLOOP"
    fi
  else
    echo "  (废纸篓项已不存在，标记 restored) $src"
    echo "$line" | sed 's/"status":"moved"/"status":"restored"/' >> "$TMPLOOP"
  fi
done < "$TMPLINES"

# 保留 manifest 中不在本次处理范围（其他品类、非 moved/emptied 的行），与处理结果合并重建
grep -v '"status":"moved"\|"status":"emptied"' "$MANIFEST" > "$TMPLOOP.keep" 2>/dev/null || true
cat "$TMPLOOP.keep" "$TMPLOOP" | sed '/^$/d' > "$MANIFEST.tmp" 2>/dev/null
if [ -s "$MANIFEST.tmp" ]; then
  mv "$MANIFEST.tmp" "$MANIFEST"
else
  rm -f "$MANIFEST.tmp" "$MANIFEST"
fi
rm -f "$TMPLINES" "$TMPLOOP" "$TMPLOOP.keep"
echo "  完成: 恢复 $restored 项。"
echo "=== 恢复完成。manifest 已标记 status=restored（审计保留）==="
