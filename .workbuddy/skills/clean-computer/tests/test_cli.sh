#!/bin/sh
# test_cli.sh — clean-computer shell 脚本集成测试（沙箱 HOME 隔离，绝不碰真实环境）
# 覆盖：clean_macos.sh（dry-run/门禁/真实清理+manifest/幂等）+ restore_macos.sh（预览/回滚/防覆盖）
#      + analyze.py CLI 各 mode 退出码。
# 用法: bash tests/test_cli.sh   （由 tests/run_all.sh 统一调用）

set -u
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
SKILL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
PY="${PYTHON:-python3}"
CLEAN="$SKILL_DIR/scripts/clean_macos.sh"
RESTORE="$SKILL_DIR/scripts/restore_macos.sh"
ANALYZE="$SKILL_DIR/scripts/analyze.py"

PASS=0
FAIL=0
report() {
  if [ "$1" = "ok" ]; then PASS=$((PASS+1)); echo "  [PASS] $2";
  else FAIL=$((FAIL+1)); echo "  [FAIL] $2"; fi
}

# —— 沙箱：临时 HOME，绝对干净 ——
SANDBOX=$(mktemp -d /tmp/cc-test-home.XXXXXX)
export HOME="$SANDBOX"
mkdir -p "$HOME/Library/Caches" "$HOME/.Trash" "$HOME/Library/Logs"
echo "cache-data-$RANDOM" > "$HOME/Library/Caches/test-cache.txt"
echo "log-data-$RANDOM" > "$HOME/Library/Logs/test.log"

echo "=== [集成] clean_macos.sh 门禁与 dry-run ==="
out=$(HOME="$SANDBOX" bash "$CLEAN" --category caches --dry-run 2>&1)
case "$out" in *"DRY-RUN 预览"*) report ok "dry-run 预览正常";; *) report fail "dry-run 预览异常: $out";; esac

out=$(HOME="$SANDBOX" bash "$CLEAN" --category not-a-real-cat --dry-run 2>&1)
case "$out" in *"风险门禁拒绝"*) report ok "未知品类被门禁拒绝";; *) report fail "门禁未拦截未知品类: $out";; esac

echo "=== [集成] clean_macos.sh 真实清理 + manifest ==="
out=$(printf 'y\n' | HOME="$SANDBOX" bash "$CLEAN" --category caches --confirm 2>&1)
case "$out" in *"已移入废纸篓"*) report ok "caches 已移入废纸篓";; *) report fail "清理失败: $out";; esac
if [ ! -e "$HOME/Library/Caches" ] && [ -e "$HOME/.Trash/Caches.cleaned-"* ]; then
  report ok "原路径已移走且废纸篓有实体"
else
  report fail "路径状态异常"
fi
if [ -f "$HOME/.clean-computer/manifest.jsonl" ] && grep -q '"status":"moved"' "$HOME/.clean-computer/manifest.jsonl"; then
  report ok "manifest 已写入 moved 记录"
else
  report fail "manifest 未正确写入"
fi

echo "=== [集成] 幂等（二次执行安全跳过）==="
out=$(printf 'y\n' | HOME="$SANDBOX" bash "$CLEAN" --category caches --confirm 2>&1)
case "$out" in *"无目标可处理"*) report ok "幂等：二次执行无目标安全跳过";; *) report fail "幂等异常: $out";; esac

echo "=== [集成] restore_macos.sh 预览与回滚 ==="
out=$(HOME="$SANDBOX" bash "$RESTORE" 2>&1)
case "$out" in *"以上为预览"*) report ok "restore 预览正常";; *) report fail "restore 预览异常: $out";; esac

out=$(HOME="$SANDBOX" bash "$RESTORE" --all 2>&1)
case "$out" in *"已恢复"*) report ok "回滚成功";; *) report fail "回滚失败: $out";; esac
if [ -e "$HOME/Library/Caches/test-cache.txt" ]; then
  report ok "文件已回原路径"
else
  report fail "文件未回原路径"
fi
if grep -q '"status":"restored"' "$HOME/.clean-computer/manifest.jsonl" 2>/dev/null; then
  report ok "manifest 已标记 restored"
else
  report fail "manifest 未标记 restored"
fi

echo "=== [集成] analyze.py CLI 各 mode ==="
for mode in scan dupes zombie predict all; do
  if "$PY" "$ANALYZE" --mode "$mode" --zombie-days 180 >/dev/null 2>&1; then
    report ok "--mode $mode 退出码 0"
  else
    report fail "--mode $mode 异常退出"
  fi
done

rm -rf "$SANDBOX"
echo ""
echo "集成测试: $PASS 通过, $FAIL 失败"
[ "$FAIL" -eq 0 ] || exit 1
