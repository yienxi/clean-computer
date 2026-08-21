#!/usr/bin/env python3
# report.py — clean-computer 报告生成器（v1.2，纯标准库，零依赖）
#
# 消费 analyze.py --json 输出，生成自包含 HTML 报告，供各 AI agent 平台直接预览/渲染。
#
# 用法：
#   analyze.py --mode all --json | report.py -o /tmp/clean-report.html
#   analyze.py --compare --json | report.py -o /tmp/clean-compare.html
#   report.py -i report.json -o out.html        # 或直接读 JSON 文件
#
# 输出 HTML 特性：磁盘占比条形图（纯 CSS）、风险标记、大文件 Top、重复文件组、
# 可回收预测、清理前后对比。无 JS、无外链，任何环境可打开。

import argparse
import json
import os
import sys

RISK_COLOR = {"green": "#1D9E75", "yellow": "#BA7517", "red": "#E24B4A"}
RISK_LABEL = {"green": "安全", "yellow": "谨慎", "red": "禁止"}


def human(n):
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bar(width_pct, color):
    return (f'<div style="background:{color};height:14px;border-radius:4px;'
            f'width:{min(100, max(2, width_pct)):.1f}%"></div>')


def render_categories(cats):
    total = sum(c.get("size_bytes", 0) for c in cats)
    rows = []
    for c in cats:
        if not c.get("exists"):
            rows.append(f'<tr><td>{esc(c["label"])}</td><td class="muted">不存在</td>'
                        f'<td></td><td></td><td></td><td></td></tr>')
            continue
        pct = (c.get("size_bytes", 0) / total * 100) if total else 0
        risk = RISK_LABEL.get(c.get("risk"), "")
        rcolor = RISK_COLOR.get(c.get("risk"), "#888")
        last = f"{c['last_access_days']} 天前" if c.get("last_access_days") is not None else "—"
        reclaim = c.get("reclaimable_bytes", 0)
        reclaim_txt = human(reclaim) if reclaim > 0 else "—"
        top = ""
        for t in c.get("top_subdirs", [])[:3]:
            top += f'<div class="sub">{esc(t["name"])} · {human(t["size_bytes"])}</div>'
        rows.append(
            f'<tr><td>{esc(c["label"])}</td>'
            f'<td style="color:{rcolor};font-weight:500">{risk}</td>'
            f'<td>{human(c.get("size_bytes"))}</td>'
            f'<td>{c.get("file_count", 0)}</td>'
            f'<td>{last}</td>'
            f'<td>{reclaim_txt}</td>'
            f'<td class="sub"><div class="bar-wrap">{bar(pct, rcolor)}</div>{top}</td></tr>')
    return rows


def render_large(files):
    if not files:
        return '<p class="muted">未发现超过阈值的大文件。</p>'
    rows = "".join(
        f'<tr><td>{human(f["size_bytes"])}</td><td class="p">{esc(f["path"])}</td></tr>'
        for f in files)
    return f'<table class="zebra"><tr><th>大小</th><th>路径</th></tr>{rows}</table>'


def render_dupes(groups):
    if not groups:
        return '<p class="muted">未发现重复文件。</p>'
    blocks = []
    for g in groups[:10]:
        save = human(g["size_bytes"] * (g["count"] - 1))
        files = "".join(f'<li>{esc(f)}</li>' for f in g["files"][:4])
        more = f'<li class="muted">…另 {len(g["files"]) - 4} 个</li>' if len(g["files"]) > 4 else ""
        blocks.append(
            f'<div class="dup"><span class="chip">{g["count"]} 份 × {human(g["size_bytes"])}</span>'
            f' 可省 <b style="color:#1D9E75">{save}</b><ul>{files}{more}</ul></div>')
    return "".join(blocks)


def render_prediction(pred):
    if not pred:
        return '<p class="muted">未生成预测。</p>'
    rows = "".join(
        f'<tr><td>{esc(c["label"])}</td><td>{human(c["reclaimable_bytes"])}</td>'
        f'<td class="muted">{esc(c["note"])}</td></tr>'
        for c in pred.get("categories", []))
    return (f'<table class="zebra"><tr><th>品类</th><th>可回收</th><th>建议</th></tr>{rows}</table>'
            f'<p>品类合计可回收 <b>{human(pred.get("reclaimable_total_bytes"))}</b>，'
            f'重复文件可省 <b>{human(pred.get("dup_reclaimable_bytes"))}</b>。</p>')


def render_compare(comp):
    rows = []
    for c in comp.get("categories", []):
        d = c["delta_bytes"]
        mark = f'<span style="color:#1D9E75">释放 {human(abs(d))}</span>' if d < 0 else (
            f'<span style="color:#E24B4A">增长 {human(abs(d))}</span>' if d > 0 else "不变")
        rows.append(f'<tr><td>{esc(c["label"])}</td>'
                    f'<td>{human(c["before_bytes"])}</td><td>{human(c["after_bytes"])}</td>'
                    f'<td>{mark}</td></tr>')
    rel = comp.get("released_bytes", 0)
    tone = "#1D9E75" if rel >= 0 else "#E24B4A"
    return (f'<div class="hero"><div class="hero-num" style="color:{tone}">'
            f'{"释放" if rel >= 0 else "增长"} {human(abs(rel))}</div>'
            f'<div class="hero-sub">基线 {esc(comp.get("baseline_generated_at"))} → '
            f'当前 {esc(comp.get("generated_at"))}</div></div>'
            f'<table class="zebra"><tr><th>品类</th><th>清理前</th><th>清理后</th>'
            f'<th>变化</th></tr>{"".join(rows)}</table>')


def build_html(payload, title):
    kind = "compare" if "released_bytes" in payload else "report"
    head = (f'<meta charset="utf-8"><title>{title}</title><style>'
            'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;'
            'margin:0;background:#f6f6f4;color:#222;line-height:1.55}'
            '.wrap{max-width:880px;margin:0 auto;padding:32px 20px 60px}'
            'h1{font-size:22px;font-weight:600;margin:0 0 4px}'
            'h2{font-size:16px;font-weight:600;margin:28px 0 10px;padding-bottom:6px;'
            'border-bottom:1px solid #e2e0da}'
            '.meta{color:#777;font-size:13px;margin-bottom:20px}'
            'table{width:100%;border-collapse:collapse;font-size:13px}'
            'th{text-align:left;color:#555;font-weight:500;padding:8px 10px;'
            'border-bottom:1px solid #e2e0da;font-size:12px}'
            'td{padding:9px 10px;border-bottom:1px solid #efede7;vertical-align:top}'
            '.zebra tr:nth-child(even) td{background:#faf9f6}'
            '.muted{color:#8a8882}.p{word-break:break-all}.sub{font-size:12px;color:#777}'
            '.bar-wrap{background:#eee;border-radius:4px;margin:2px 0 4px;min-width:60px}'
            '.dup{background:#faf9f6;border:1px solid #e8e5dd;border-radius:8px;'
            'padding:10px 14px;margin-bottom:10px}'
            '.chip{background:#e6f1fb;color:#185fa5;border-radius:12px;padding:2px 10px;'
            'font-size:12px;font-weight:500;margin-right:8px}'
            '.dup ul{margin:8px 0 0;padding-left:18px;font-size:12px;color:#555}'
            '.hero{background:#fff;border:1px solid #e8e5dd;border-radius:12px;'
            'padding:20px;text-align:center;margin:10px 0 18px}'
            '.hero-num{font-size:30px;font-weight:700}.hero-sub{color:#777;font-size:13px;margin-top:6px}'
            '.footer{color:#999;font-size:12px;margin-top:40px;text-align:center}</style>')

    if kind == "compare":
        body = render_compare(payload)
        section = ""
    else:
        body = render_categories(payload.get("categories", []))
        rows = "".join(body) if body else '<tr><td colspan="7">无数据</td></tr>'
        section = (f'<h2>磁盘画像与可清理品类</h2>'
                   f'<table><tr><th>品类</th><th>风险</th><th>大小</th><th>文件数</th>'
                   f'<th>最后访问</th><th>可回收</th><th>占比 / Top 子目录</th></tr>{rows}</table>'
                   f'<h2>大文件 Top</h2>{render_large(payload.get("large_files", []))}'
                   f'<h2>重复文件组（只读报告）</h2>{render_dupes(payload.get("duplicates", []))}'
                   f'<h2>可回收预测</h2>{render_prediction(payload.get("prediction"))}')

    meta = (f'<div class="meta">OS: {esc(payload.get("os", ""))} · '
            f'生成: {esc(payload.get("generated_at", ""))} · '
            f'Schema v{esc(payload.get("schema_version", ""))}'
            + (f' · 僵尸阈值 {esc(payload.get("zombie_days_threshold"))} 天'
               if "zombie_days_threshold" in payload else "") + '</div>')

    return (f'<!DOCTYPE html><html><head>{head}</head><body><div class="wrap">'
            f'<h1>{esc(title)}</h1>{meta}{section}{body}'
            f'<div class="footer">clean-computer · 只读分析报告 · '
            f'清理动作需用户逐品类确认后另行执行</div></div></body></html>')


def main():
    ap = argparse.ArgumentParser(description="clean-computer HTML 报告生成器")
    ap.add_argument("-i", "--input", default="-", help="JSON 输入（默认 stdin）")
    ap.add_argument("-o", "--output", required=True, help="输出 HTML 路径")
    ap.add_argument("--title", default="clean-computer 分析报告", help="报告标题")
    args = ap.parse_args()

    if args.input == "-":
        payload = json.load(sys.stdin)
    else:
        with open(args.input, encoding="utf-8") as f:
            payload = json.load(f)

    html = build_html(payload, args.title)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"报告已生成: {args.output}")


if __name__ == "__main__":
    main()
