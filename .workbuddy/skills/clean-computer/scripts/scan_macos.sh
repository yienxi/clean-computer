#!/bin/sh
# scan_macos.sh — 只读扫描 macOS 可清理项（缓存/日志/临时/派生数据等）
# 安全：仅统计大小与路径，绝不删除、绝不移动。
set -u

echo "=== macOS 清理扫描报告（只读，不修改任何文件）==="

report() {
  label="$1"; path="$2"
  if [ -e "$path" ]; then
    size=$(du -sh "$path" 2>/dev/null | cut -f1)
    count=$(find "$path" -type f 2>/dev/null | wc -l | tr -d ' ')
    printf "  [%-12s] %s\n       大小: %s   文件数: %s\n" "$label" "$path" "$size" "$count"
  else
    printf "  [%-12s] %s — 不存在，跳过\n" "$label" "$path"
  fi
}

report "应用缓存"   "$HOME/Library/Caches"
report "系统缓存"   "/Library/Caches"
report "日志"       "$HOME/Library/Logs"
report "Xcode派生"   "$HOME/Library/Developer/Xcode/DerivedData"
report "Homebrew"   "$HOME/Library/Caches/Homebrew"
report "npm缓存"    "$HOME/.npm/_cacache"
report "容器缓存"   "$HOME/Library/Containers"
report "废纸篓"     "$HOME/.Trash"

echo ""
echo "=== 大文件 Top（>500M，已排除个人文档/下载/桌面根目录）==="
find "$HOME" -type f -size +500M 2>/dev/null \
  | grep -vE "/Documents/|/Downloads/|/Desktop/" \
  | head -20 \
  | while read -r f; do printf "  %s  %s\n" "$(du -h "$f" | cut -f1)" "$f"; done

echo ""
echo "=== 扫描完成。清理请用 clean_macos.sh --category <品类> 先看预览，确认后加 --confirm ==="
