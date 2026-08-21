#!/bin/sh
# run_all.sh — clean-computer 统一测试入口（v1.4）
#   1. 引擎单元测试（Python unittest，fixtures 动态构造）
#   2. shell 脚本集成测试（沙箱 HOME 隔离）
#   3. 性能基准：真实目录扫描计时（只读），记录到 docs/samples/benchmark.txt
# 用法: bash tests/run_all.sh
set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
SKILL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
PY="${PYTHON:-python3}"
START=$(date +%s)

echo "=============================================="
echo "clean-computer 测试套件（v1.4）"
echo "=============================================="

echo ""
echo "== [1/3] 引擎单元测试 =="
(cd "$SKILL_DIR" && "$PY" -m unittest tests/test_analyze.py -v 2>&1 | tail -5) || exit 1

echo ""
echo "== [2/3] shell 集成测试（沙箱隔离）=="
"$SCRIPT_DIR/test_cli.sh" || exit 1

echo ""
echo "== [3/3] 性能基准（真实目录只读扫描）=="
BENCH="$SKILL_DIR/docs/samples/benchmark.txt"
mkdir -p "$SKILL_DIR/docs/samples"
/usr/bin/time -p "$PY" "$SKILL_DIR/scripts/analyze.py" --mode scan --zombie-days 180 >/dev/null 2>"$BENCH.tmp"
REAL=$(grep real "$BENCH.tmp" | awk '{print $2}')
printf 'clean-computer 性能基准\n日期: %s\nscan(只读) 耗时: %s s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)" "$REAL" > "$BENCH"
rm -f "$BENCH.tmp"
echo "  scan 耗时: ${REAL}s → 已记录 $BENCH"
case "$REAL" in
  *.*) SECS=$(echo "$REAL" | awk -F. '{print $1}');;
  *) SECS=$(echo "$REAL" | awk '{print int($1)}');;
esac
[ "${SECS:-0}" -lt 120 ] && echo "  [PASS] 扫描耗时 < 120s" || echo "  [WARN] 扫描耗时超 120s（大数据量机器属正常）"

END=$(date +%s)
echo ""
echo "=============================================="
echo "全部完成，用时 $((END-START))s。基准记录见 docs/samples/benchmark.txt"
echo "=============================================="
