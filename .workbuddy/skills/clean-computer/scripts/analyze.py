#!/usr/bin/env python3
# analyze.py — clean-computer 核心分析引擎（v1.1，纯标准库，跨平台零依赖）
#
# 提供四类只读分析，全部不修改任何文件：
#   --mode scan     磁盘画像：各可清理品类大小/文件数/最后访问 + 大文件 Top-N
#   --mode dupes    重复文件检测（采样哈希，快于全量校验）
#   --mode zombie   僵尸缓存：按 atime 判断"很久没碰"的死缓存
#   --mode predict  可回收空间预测：结合品类属性与僵尸比例给出建议
#   --mode all      以上全部（默认）
#
# 输出：
#   默认：人读摘要（stdout）
#   --json：结构化 JSON（JSON Schema v1，供任意 AI agent 渲染）
#
# 安全边界：本脚本只读。删除/移动一律由 clean_*.sh / clean_*.ps1 在显式确认后执行。

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

SCHEMA_VERSION = "1.0"
ZOMBIE_DAYS_DEFAULT = 180   # 超过 N 天未被访问 → 视为僵尸缓存
LARGE_FILE_MIN = 500 * 1024 * 1024  # 大文件阈值 500MB
SAMPLE_SIZE = 64 * 1024      # 重复检测采样块大小（64KB）
DUP_MIN_GROUP = 2            # 至少几个文件相同才算重复组
SNAPSHOT_DIR = os.path.expanduser("~/.clean-computer")  # 基线快照目录（不在任何清理品类内）


def human(n):
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def os_family():
    s = platform.system().lower()
    if s == "darwin":
        return "macos"
    if s.startswith("win"):
        return "windows"
    return "linux"


def category_map(osf):
    home = os.path.expanduser("~")
    if osf == "macos":
        return [
            {"id": "caches",   "label": "应用缓存", "path": f"{home}/Library/Caches", "risk": "green"},
            {"id": "system",   "label": "系统缓存", "path": "/Library/Caches",         "risk": "green"},
            {"id": "logs",     "label": "日志",     "path": f"{home}/Library/Logs",    "risk": "green"},
            {"id": "xcode",    "label": "Xcode派生", "path": f"{home}/Library/Developer/Xcode/DerivedData", "risk": "green"},
            {"id": "homebrew", "label": "Homebrew", "path": f"{home}/Library/Caches/Homebrew", "risk": "green"},
            {"id": "npm",      "label": "npm缓存",  "path": f"{home}/.npm/_cacache",   "risk": "green"},
            {"id": "containers", "label": "容器缓存", "path": f"{home}/Library/Containers", "risk": "yellow"},
            {"id": "trash",    "label": "废纸篓",   "path": f"{home}/.Trash",          "risk": "yellow"},
        ]
    if osf == "windows":
        lp = os.environ.get("LOCALAPPDATA", "")
        win = os.environ.get("WINDIR", "C:\\Windows")
        return [
            {"id": "temp_user", "label": "用户临时", "path": os.path.join(lp, "Temp"), "risk": "green"},
            {"id": "temp_sys",  "label": "系统临时", "path": os.path.join(win, "Temp"), "risk": "green"},
            {"id": "edge",      "label": "Edge缓存", "path": os.path.join(lp, "Microsoft", "Edge", "User Data", "Default", "Cache"), "risk": "green"},
            {"id": "chrome",    "label": "Chrome缓存", "path": os.path.join(lp, "Google", "Chrome", "User Data", "Default", "Cache"), "risk": "green"},
            {"id": "wechat",    "label": "微信缓存", "path": os.path.join(lp, "Tencent", "WeChat"), "risk": "yellow"},
            {"id": "winupdate", "label": "更新缓存", "path": os.path.join(win, "SoftwareDistribution", "Download"), "risk": "green"},
            {"id": "trash",     "label": "回收站",   "path": "$Recycle.Bin", "risk": "yellow"},
        ]
    return []  # linux 暂未覆盖


def dir_stats(root, zombie_days, top_k=5):
    """遍历目录统计：总大小、文件数、僵尸(未访问超阈值)字节数、最后访问天数、Top 子目录。"""
    now = time.time()
    total = count = zombie = 0
    newest_access = None
    top_agg = {}  # 顶层子目录名 → 字节数（一次 walk 顺带聚合，不额外扫盘）
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ("Library", "node_modules", ".git")]
            rel = os.path.relpath(dirpath, root)
            top_key = rel.split(os.sep)[0] if rel != "." else "."
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                try:
                    st = os.lstat(fp)
                except (OSError, PermissionError):
                    continue
                total += st.st_size
                count += 1
                top_agg[top_key] = top_agg.get(top_key, 0) + st.st_size
                age_days = (now - st.st_atime) / 86400
                if age_days > zombie_days:
                    zombie += st.st_size
                if newest_access is None or st.st_atime > newest_access:
                    newest_access = st.st_atime
    except (OSError, PermissionError):
        pass
    last_days = None
    if newest_access is not None:
        last_days = max(0, int((now - newest_access) / 86400))
    top_subdirs = [{"name": k, "size_bytes": v} for k, v in
                   sorted(top_agg.items(), key=lambda x: -x[1])[:top_k]]
    return {"size_bytes": total, "file_count": count,
            "zombie_bytes": zombie, "last_access_days": last_days,
            "top_subdirs": top_subdirs}


def scan_categories(osf, zombie_days):
    cats = []
    for c in category_map(osf):
        item = dict(c)
        if osf == "windows" and c["id"] == "trash":
            # Windows 回收站无普通文件系统路径，用 PowerShell 只读统计项数与大小
            item.update(_win_recycle_stats())
            cats.append(item)
            continue
        if os.path.exists(c["path"]):
            s = dir_stats(c["path"], zombie_days)
            item.update(s)
            item["exists"] = True
            item["reclaimable_bytes"] = s["zombie_bytes"]
        else:
            item.update({"size_bytes": 0, "file_count": 0, "zombie_bytes": 0,
                         "last_access_days": None, "exists": False, "reclaimable_bytes": 0})
        cats.append(item)
    return cats


def _win_recycle_stats():
    """Windows 回收站：调用 PowerShell 只读统计项数与总大小。失败时返回零值。"""
    try:
        ps = (
            "$s=New-Object -ComObject Shell.Application;"
            "$rb=$s.Namespace(10);"
            "$items=$rb.Items();"
            "$n=0;$sz=0;"
            "foreach($i in $items){$n++;$sz+=$i.Size};"
            "Write-Output \"$n`t$sz\""
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=60)
        n, sz = r.stdout.strip().split("\t")
        return {"size_bytes": int(sz), "file_count": int(n),
                "zombie_bytes": 0, "last_access_days": None,
                "exists": int(n) > 0,
                "reclaimable_bytes": int(sz),
                "top_subdirs": []}
    except Exception:
        return {"size_bytes": 0, "file_count": 0, "zombie_bytes": 0,
                "last_access_days": None, "exists": False,
                "reclaimable_bytes": 0, "top_subdirs": []}


def scan_large_files(top_dirs, min_bytes=LARGE_FILE_MIN, exclude=("Documents", "Downloads", "Desktop"), limit=20):
    big = []
    for root in top_dirs:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ("Library", "node_modules", ".git")]
            if any(seg in exclude for seg in dirpath.split(os.sep)):
                continue
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue
                if sz >= min_bytes:
                    big.append({"path": fp, "size_bytes": sz})
    big.sort(key=lambda x: -x["size_bytes"])
    return big[:limit]


def sample_hash(fp):
    """采样哈希：大小 + 头/中/尾三块 SHA-256，快于全文件哈希，用于预筛重复。"""
    h = hashlib.sha256()
    try:
        sz = os.path.getsize(fp)
    except OSError:
        return None
    if sz == 0:
        return h.hexdigest() + ":0"
    h.update(str(sz).encode())
    try:
        with open(fp, "rb") as f:
            for pos in (0, max(0, sz // 2), max(0, sz - SAMPLE_SIZE)):
                f.seek(pos)
                h.update(f.read(SAMPLE_SIZE))
    except OSError:
        return None
    return h.hexdigest() + f":{sz}"


def find_duplicates(roots, min_group=DUP_MIN_GROUP, limit=50):
    """跨目录重复文件检测：先按(大小, 采样哈希)分组，组内再全量校验确认。"""
    buckets = {}
    for root in roots:
        if not os.path.exists(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(fp) < 1024:  # 跳过 <1KB 琐碎文件
                        continue
                except OSError:
                    continue
                sh = sample_hash(fp)
                if sh:
                    buckets.setdefault(sh, []).append(fp)
    groups = []
    for paths in buckets.values():
        if len(paths) < min_group:
            continue
        # 组内全量确认，剔除采样碰巧相同的
        full = {}
        for p in paths:
            try:
                with open(p, "rb") as f:
                    full.setdefault(hashlib.sha256(f.read()).hexdigest(), []).append(p)
            except OSError:
                continue
        for fh, plist in full.items():
            if len(plist) >= min_group:
                try:
                    sz = os.path.getsize(plist[0])
                except OSError:
                    sz = 0
                groups.append({"size_bytes": sz, "count": len(plist), "files": plist})
                if len(groups) >= limit:
                    return groups
    groups.sort(key=lambda g: -g["size_bytes"] * g["count"])
    return groups[:limit]


def predict(cats, dup_groups, large_files):
    cats_predict = []
    for c in cats:
        if not c.get("exists"):
            continue
        r = c.get("reclaimable_bytes", 0)
        if c["id"] == "trash":
            r = c.get("size_bytes", 0)  # 清空回收站可全释放（但不可逆，须单独确认）
        cats_predict.append({
            "id": c["id"], "label": c["label"], "path": c["path"],
            "size_bytes": c.get("size_bytes", 0),
            "reclaimable_bytes": r,
            "risk": c["risk"],
            "note": "建议清理" if r >= 50 * 1024 * 1024 else ("少量" if r > 0 else "无需清理"),
        })
    dup_total = sum(g["size_bytes"] * (g["count"] - 1) for g in dup_groups)
    large_hint = sum(f["size_bytes"] for f in large_files[:5])
    return {
        "reclaimable_total_bytes": sum(p["reclaimable_bytes"] for p in cats_predict),
        "dup_reclaimable_bytes": dup_total,
        "large_hint_bytes": large_hint,
        "categories": cats_predict,
    }


def build_report(osf, zombie_days, modes):
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    cats = scan_categories(osf, zombie_days) if ("scan" in modes or "all" in modes or "predict" in modes) else []
    dup_groups = []
    large = []
    if "scan" in modes or "all" in modes:
        home = os.path.expanduser("~")
        large = scan_large_files([home])
    if "dupes" in modes or "all" in modes or "predict" in modes:
        dup_roots = [c["path"] for c in cats if c.get("exists")]
        dup_groups = find_duplicates(dup_roots)
    pred = predict(cats, dup_groups, large) if ("predict" in modes or "all" in modes) else None
    return {
        "schema_version": SCHEMA_VERSION,
        "os": osf,
        "generated_at": now,
        "zombie_days_threshold": zombie_days,
        "categories": cats,
        "large_files": large,
        "duplicates": dup_groups,
        "prediction": pred,
    }


def save_snapshot(report, tag=None):
    """保存基线快照到 ~/.clean-computer/（该目录不在任何清理品类内，不会被误删）。"""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    name = f"snapshot-{report['os']}{'-' + tag if tag else ''}.json"
    path = os.path.join(SNAPSHOT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return path


def load_snapshot(osf, tag=None):
    """加载最近一次基线快照；无则返回 None。"""
    try:
        names = [n for n in os.listdir(SNAPSHOT_DIR)
                 if n.startswith(f"snapshot-{osf}") and n.endswith(".json")]
        if not names:
            return None
        names.sort(reverse=True)
        target = f"snapshot-{osf}-{tag}.json" if tag else names[0]
        if tag and target not in names:
            return None
        with open(os.path.join(SNAPSHOT_DIR, target), encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return None


def compare_reports(base, now_report):
    """对比基线 vs 当前：每品类 Δ（负数=释放），回收站单独标记。"""
    base_map = {c["id"]: c for c in base.get("categories", [])}
    rows = []
    for c in now_report.get("categories", []):
        b = base_map.get(c["id"])
        bsize = b.get("size_bytes", 0) if b else 0
        csize = c.get("size_bytes", 0)
        rows.append({
            "id": c["id"], "label": c["label"], "risk": c["risk"],
            "before_bytes": bsize, "after_bytes": csize,
            "delta_bytes": csize - bsize,
            "baseline_exists": b is not None,
        })
    before_total = sum(r["before_bytes"] for r in rows)
    after_total = sum(r["after_bytes"] for r in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "os": now_report["os"],
        "generated_at": now_report["generated_at"],
        "baseline_generated_at": base.get("generated_at"),
        "before_total_bytes": before_total,
        "after_total_bytes": after_total,
        "released_bytes": before_total - after_total,
        "categories": rows,
    }


def print_compare(c):
    print("=" * 62)
    print(f"清理前后对比  |  基线: {c['baseline_generated_at']}  →  当前: {c['generated_at']}")
    print("=" * 62)
    rel = c["released_bytes"]
    arrow = "释放" if rel >= 0 else "增长"
    print(f"\n品类合计: {human(c['before_total_bytes'])} → {human(c['after_total_bytes'])}  "
          f"({arrow} {human(abs(rel))})")
    print("\n[各品类变化]")
    for r in c["categories"]:
        if not r["baseline_exists"]:
            continue
        d = r["delta_bytes"]
        mark = "释放" if d < 0 else ("增长" if d > 0 else "不变")
        print(f"  {r['label']:<8} {human(r['before_bytes']):>9} → {human(r['after_bytes']):>9}  "
              f"{mark} {human(abs(d))}")
    print("\n提示: 对比仅覆盖品类内路径；回收站若已清空会显示为释放。")


def print_human(r):
    print("=" * 62)
    print(f"clean-computer 分析报告  |  OS: {r['os']}  |  僵尸阈值: {r['zombie_days_threshold']} 天")
    print("=" * 62)
    print("\n[1] 可清理品类")
    for c in r["categories"]:
        if not c.get("exists"):
            print(f"  {c['label']:<8} {c['path']} — 不存在")
            continue
        flag = {"green": "[安全]", "yellow": "[谨慎]"}.get(c["risk"], "")
        last = f"{c['last_access_days']} 天前" if c.get("last_access_days") is not None else "无记录"
        print(f"  {c['label']:<8} {human(c['size_bytes']):>9}  {c['file_count']} 文件  "
              f"最后访问 {last}  {flag}")
        if c.get("reclaimable_bytes", 0) > 0:
            print(f"           ≈ 可回收 {human(c['reclaimable_bytes'])}（{r['zombie_days_threshold']} 天未访问）")
    if r["duplicates"]:
        print("\n[2] 重复文件组（采样哈希+全量确认）")
        for g in r["duplicates"][:10]:
            print(f"  {g['count']} 份 × {human(g['size_bytes'])} → 可省 {human(g['size_bytes'] * (g['count'] - 1))}")
            for f in g["files"][:3]:
                print(f"      - {f}")
            if len(g["files"]) > 3:
                print(f"      ... 另 {len(g['files']) - 3} 个")
    if r["large_files"]:
        print(f"\n[3] 大文件 Top（>{human(LARGE_FILE_MIN)}）")
        for f in r["large_files"]:
            print(f"  {human(f['size_bytes']):>9}  {f['path']}")
    if r["prediction"]:
        p = r["prediction"]
        print("\n[4] 可回收预测")
        for c in p["categories"]:
            print(f"  {c['label']:<8} 可回收 {human(c['reclaimable_bytes']):>9}  {c['note']}")
        print(f"  —— 品类合计: {human(p['reclaimable_total_bytes'])}  重复文件可省: {human(p['dup_reclaimable_bytes'])}")
    print("\n提示: 本报告只读。清理请走 clean 脚本预览→确认流程；重复文件仅报告，不自动清理。")


def main():
    global LARGE_FILE_MIN
    ap = argparse.ArgumentParser(description="clean-computer 核心分析引擎（只读）")
    ap.add_argument("--mode", default="all",
                    help="scan | dupes | zombie | predict | all（默认 all）")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    ap.add_argument("--zombie-days", type=int, default=ZOMBIE_DAYS_DEFAULT,
                    help=f"僵尸缓存阈值天数（默认 {ZOMBIE_DAYS_DEFAULT}）")
    ap.add_argument("--min-large-mb", type=int, default=int(LARGE_FILE_MIN // 1024 // 1024),
                    help="大文件阈值 MB（默认 500）")
    ap.add_argument("--snapshot", action="store_true",
                    help="扫描后保存基线快照到 ~/.clean-computer/（供下次对比）")
    ap.add_argument("--tag", default=None, help="快照标签（默认 os 名，同标签会覆盖）")
    ap.add_argument("--compare", action="store_true",
                    help="对比最近一次快照，输出清理前后释放量")
    args = ap.parse_args()

    LARGE_FILE_MIN = args.min_large_mb * 1024 * 1024

    osf = os_family()
    if osf == "linux":
        print("当前 v1.1 引擎未覆盖 Linux（路径约定不同），请用 macOS/Windows。", file=sys.stderr)
        sys.exit(2)

    modes = set(args.mode.split(","))

    if args.compare:
        base = load_snapshot(osf, args.tag)
        if base is None:
            print(f"未找到基线快照。请先运行: analyze.py --snapshot [--tag <名>]",
                  file=sys.stderr)
            sys.exit(3)
        current = build_report(osf, args.zombie_days, modes)
        comp = compare_reports(base, current)
        if args.json:
            print(json.dumps(comp, ensure_ascii=False, indent=2))
        else:
            print_compare(comp)
        return

    report = build_report(osf, args.zombie_days, modes)
    if args.snapshot:
        path = save_snapshot(report, args.tag)
        print(f"[快照已保存] {path}", file=sys.stderr)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)


if __name__ == "__main__":
    main()
