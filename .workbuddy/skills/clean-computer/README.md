# clean-computer · 引导式电脑清理 Skill

跨平台（macOS / Windows）、可分发到各 AI agent 平台的电脑清理技能。
原则：**交互引导 · 数据准确性 · 安全边界（可回收站、不 rm）**。

## 目录
```
clean-computer/
├── SKILL.md              # 技能定义（frontmatter 兼容 WorkBuddy 与 Claude Agent Skills）
├── README.md             # 本文件：分发与安装说明 + 用户调取执行手册
├── CHANGELOG.md          # ★ v1.5 版本历史
├── docs/samples/         # macOS 实测生成的 HTML 报告样例 + 性能基准记录
├── tests/                # 测试套件（run_all.sh / test_analyze.py / test_cli.sh）
└── scripts/
    ├── cc.sh             # ★ 统一入口：scan/report/clean/restore/snapshot/compare/status
    ├── analyze.py        # ★ v1.1 核心分析引擎（Python 标准库，跨平台零依赖）
    ├── report.py         # ★ v1.2 HTML 可视化报告生成器（磁盘画像/清理前后对比）
    ├── clean_macos.sh    # ★ v1.3 引导式清理（dry-run 默认 + manifest 日志 + 风险门禁 + 幂等）
    ├── restore_macos.sh  # ★ v1.3 一键回滚（从 manifest 恢复废纸篓中清理项）
    ├── scan_macos.sh     # macOS 只读扫描（python3 缺失时的回退）
    ├── scan_windows.ps1  # Windows 只读扫描（python3 缺失时的回退）
    ├── clean_windows.ps1 # ★ v1.5 引导式清理（WhatIf 默认 + manifest 日志 + 风险门禁 + 幂等）
    └── restore_windows.ps1 # ★ v1.5 一键回滚（从 manifest 恢复回收站中清理项）
```

## 用户如何调取执行（macOS 实测可用）

**方式 A：终端直接调用（最简单，无需装任何东西）**
```bash
# 进入 skill 目录，或把 scripts/ 加入 PATH
cd <clean-computer>/scripts

./cc.sh scan          # 1. 只读扫描，看磁盘占用报告
./cc.sh report        # 2. 生成 HTML 可视化报告（自动用浏览器打开）
./cc.sh clean caches  # 3. 预览待清理项（不删除！）
./cc.sh clean caches --confirm   # 4. 确认后送废纸篓（可恢复，写 manifest）
./cc.sh restore       # 5. 预览可回滚项
./cc.sh restore --all # 6. 一键恢复（原路径已存在则跳过）
./cc.sh snapshot      # 7. 清理前存基线
./cc.sh compare       # 8. 清理后对比，输出实际释放量
./cc.sh status        # 9. 查看 manifest/快照/执行状态
```
- 唯一依赖：`python3`（macOS 自带 /usr/bin/python3 即可）。
- `clean`/`restore` 默认只预览，必须显式 `--confirm`/`--all` 才真正执行——安全边界代码强制。

**方式 B：在 AI agent（WorkBuddy / Claude）对话中触发**
安装后（见下），对话里说"帮我清理电脑 / 看看磁盘空间 / 清一下缓存"即可触发。
助手会走完整流程：扫描 → 报告 → 逐品类确认 → 送废纸篓 → 对比核验。

**方式 C：配合自动化定时扫描（可选）**
每 3 天只读扫描告警：`cc.sh scan` 是只读安全的，可放入 cron/launchd，不删除任何文件。

## 核心引擎与报告（v1.1 / v1.2）
`scripts/analyze.py` 是主分析入口（mac/win 一套代码，仅需 python3.8+）：
- `python3 scripts/analyze.py` → 全量分析（磁盘画像 + 重复文件 + 僵尸缓存 + 可回收预测）
- `python3 scripts/analyze.py --mode scan|dupes|zombie|predict --zombie-days 180`
- `python3 scripts/analyze.py --json` → 结构化 JSON（Schema v1），供各 agent 渲染界面
- `python3 scripts/analyze.py --snapshot` / `--compare` → 清理前后基线对比（可核验释放量）
- `python3 scripts/analyze.py --mode all --json | python3 scripts/report.py -o report.html` → HTML 报告
- 无 python3 时回退 `scan_macos.sh` / `scan_windows.ps1`（仅基础品类大小）。

## 安装到 WorkBuddy
把整个 `clean-computer/` 目录放入以下任一位置：
- 用户级：`~/.workbuddy/skills/clean-computer/`
- 项目级：`<项目>/.workbuddy/skills/clean-computer/`

对话中提到"清理电脑/释放空间/清缓存"等即会被语义触发。

## 安装到 Claude Agent Skills（Anthropic 格式）
Claude 读取 `SKILL.md` 的 `name` + `description` 做触发。直接把 `clean-computer/` 放进
Claude 的 skills 目录即可；本文件 frontmatter 已同时兼容两平台（`description` 写明触发场景）。

## 上架到其他 agent 平台
保留 `name` / `description` / `version` 三个字段不变即可；`description` 已包含触发关键词，
便于各平台语义匹配。脚本用相对路径 `scripts/...` 引用，跨平台拷贝即用。

## 安全承诺
- 只读优先，删除前必预览 + 逐品类 `y/N` 确认。
- 仅清理可恢复的安全子路径，删除走回收站（可逆），单批≤10。
- 绝不递归删除桌面/下载/文档/用户目录根/系统根。
- 双平台：程序化风险门禁（白名单精确路径，代码强制）+ manifest 清理日志 + 一键回滚 + 幂等。

## 验证
- 全量测试（分发前必跑）：`bash tests/run_all.sh`（单元 + 集成 + 性能基准，沙箱隔离）。
- 用户入口自检：`./scripts/cc.sh scan`（只读）+ `./scripts/cc.sh status`。
- macOS：`python3 scripts/analyze.py`（只读，可安全在本机运行）；或 `bash scripts/scan_macos.sh`。
- Windows：`python3 scripts/analyze.py` 或 PowerShell `.\scripts\scan_windows.ps1`（只读）。
- 清理动作默认不执行，必须显式 `--confirm` / `-Confirm` 才会送回收站。
- 回滚：macOS `bash scripts/restore_macos.sh --all`；Windows `.\scripts\restore_windows.ps1 -All`（先不加 -All 预览）。
