---
name: clean-computer
description: |
  Guided, safety-first computer cleanup skill for macOS and Windows, designed to be
  portable across AI agent platforms. Scans disk usage / caches / logs / temp /
  derived-data READ-ONLY, then cleans ONLY safe, recoverable sub-paths by moving them
  to Trash / Recycle Bin (never permanent delete) after per-category confirmation.
  Built-in principles: interactive guidance, data accuracy, reversible actions.
  Trigger when the user wants to: free disk space, clear app/system caches, empty
  trash, find large files, or do routine computer maintenance on Mac or Windows.
  This is NOT a one-click auto-cleaner — it always confirms before any destructive step.
description_zh: "引导式、安全优先的 Mac/Windows 电脑清理技能（跨平台可分发）"
description_en: "Guided safety-first Mac/Windows cleanup skill (portable across agent platforms)"
version: 1.6.0
license: MIT
metadata:
  version: "1.6.0"
  category: system-utility
  agent_created: true
  os: [macos, windows]
  portable: true
  engine: "scripts/analyze.py (Python3 stdlib, cross-platform)"
  sources:
    - Apple macOS File System Programming Guide (Library directory conventions)
    - Apple TCC / Full Disk Access documentation
    - Microsoft Windows Disk Cleanup / DISM documentation
---

# Clean Computer — 引导式电脑清理 Skill（可分发 v1.3）

把"日常电脑清理"封装成一个**工作流 skill**：先只读扫描、再按品类确认、最后送回收站（可逆）。
本 skill 面向**各 AI agent 平台**分发，因此在"交互引导、数据准确性、安全边界"三条原则上做了硬性约定。
v1.1 新增**核心分析引擎 `scripts/analyze.py`**（纯 Python 标准库、跨平台零依赖），把重复文件检测、
僵尸缓存判断、可回收空间预测、JSON 结构化输出从"规则"变成"代码能力"。
v1.2 新增**可视化报告 `scripts/report.py`**（磁盘画像 HTML + 清理前后对比），macOS 平台优先落地。
v1.3 新增**安全层**：manifest 清理日志 + 一键回滚 + 程序化风险门禁 + 幂等（macOS 优先）。
v1.4 新增**质量层**：`tests/` 测试套件（单元 + 集成，沙箱隔离）+ 性能基准 + CHANGELOG。
v1.5 **Windows 端对齐**：clean_windows.ps1 补 manifest/门禁/幂等，新增 restore_windows.ps1 一键回滚，analyze.py 修复 Windows 回收站统计。
v1.6 **用户入口**：新增 `scripts/cc.sh` 统一入口（scan/report/clean/restore/snapshot/compare/status），macOS 实测全链路可用；README 新增"用户如何调取执行"手册。

## 设计原则（上架前必须守住，不可绕开）
1. **交互引导（Interactive Guidance）**：任何删除前必须 扫描 → 报告 → 逐品类确认；绝不静默自动删、绝不默认全清。用户随时可中止。
2. **数据准确性（Data Accuracy）**：报告中的大小一律由系统命令真实计算（`du` / `Get-ChildItem`），**不靠模型猜测**；清理后建议复扫核对释放空间，给出可核验结果。
3. **安全边界（Safety Boundary）**：仅处理可恢复的安全子路径；禁止触碰个人目录禁区；删除走回收站（可逆）；单批≤10；脚本默认只读，删除须显式确认。

## 何时触发
用户提到：清理电脑 / 释放磁盘空间 / 清缓存 / 清日志 / 清临时文件 / 清废纸篓 / 找大文件 / C 盘红了 / Mac Windows 日常维护。

## 用户如何调取执行（agent 首选 `scripts/cc.sh` 统一入口）
用户在本机直接执行（终端）或由 agent 代跑，统一走 `cc.sh`（自动检测 OS，自动分发到对应脚本）：
- `cc.sh scan`：只读扫描 + 人读报告
- `cc.sh report [out.html]`：生成 HTML 可视化报告（macOS 自动打开）
- `cc.sh clean <品类>`：预览；`cc.sh clean <品类> --confirm` 才送回收站
- `cc.sh restore`：预览；`cc.sh restore --all` 才恢复
- `cc.sh snapshot` / `cc.sh compare`：清理前后基线对比（核验释放量）
- `cc.sh status`：查看 manifest / 快照 / 状态
- `cc.sh help`：帮助
安全：clean/restore 默认仅预览，必须显式 `--confirm`/`--all` 才执行。agent 若为用户代跑清理，
必须先展示预览并逐品类征得用户明确同意，再执行；不代用户确认。

## 工作流（6 步）
1. **检测 OS**：`uname -s` 输出 `Darwin` → macOS；`$env:OS` 含 `Windows` 或 PowerShell `$IsWindows` 为 `$true` → Windows。
2. **只读分析**（优先用核心引擎，mac/win 通吃）：
   - `scripts/cc.sh scan`（统一入口，推荐）或 `python3 <skill>/scripts/analyze.py --mode all`
   - 只跑某类：`--mode scan|dupes|zombie|predict`；`--zombie-days N` 调僵尸阈值（默认 180）
   - **无 python3 时回退旧脚本**：macOS `bash <skill>/scripts/scan_macos.sh`；Windows `powershell -ExecutionPolicy Bypass -File <skill>/scripts/scan_windows.ps1`
   - AI agent 若要渲染界面，用 `--json` 取结构化输出（Schema v1，见下文）
3. **生成报告**：把分析结果以两种形式回给用户：
   - **HTML 可视化报告（推荐，macOS 优先）**：
     `analyze.py --mode all --json | report.py -o clean-report.html`
     含磁盘占比条形图、风险标记、大文件 Top、重复文件组、可回收预测，任何环境可打开。
   - **人读清单**：直接用引擎的 human 输出（各品类大小/文件数/僵尸可回收量、大文件 Top、重复文件组、可回收预测），标注"可恢复"与风险等级（安全/谨慎）。
   - **建议**：在用户环境生成 HTML 报告路径并告知，同时用 2-3 行摘要复述关键结论（最大品类、可回收总量、风险项）。
4. **逐品类确认**：询问清理哪些品类（caches/logs/xcode/homebrew/npm/containers/system/trash 等），**绝不一刀切默认全清**。
5. **安全执行**（仅当用户显式 `--confirm` / `-Confirm`）：
   - macOS：`bash <skill>/scripts/clean_macos.sh --category <品类> --confirm`
   - Windows：`powershell -ExecutionPolicy Bypass -File <skill>/scripts/clean_windows.ps1 -Category <品类> -Confirm`
   - 脚本内部再次预览 + `y/N` 二次确认；单批≤10；送回收站。
   - **每次清理自动写 manifest**（macOS `~/.clean-computer/manifest.jsonl`；Windows `%USERPROFILE%\.clean-computer\manifest.jsonl`），
     供 `restore_macos.sh` / `restore_windows.ps1` 一键回滚。
   - **程序化风险门禁**：clean 脚本只接受白名单精确路径，其他路径一律拒绝（代码强制，不依赖 LLM 记忆）。
   - 注意：重复文件组只读报告，引擎不做清理；如需去重走 clean 脚本对应品类或用户自选路径，仍须逐个确认。
6. **核验汇总**：复跑 `analyze.py --mode scan` 核对释放空间，给出已送回收站路径清单；提示"如需彻底释放请手动清空废纸篓/回收站"（不可逆，需单独明确告知）。
   - **清理前建议先存基线**：`analyze.py --mode scan --snapshot [--tag <名>]`（存到 `~/.clean-computer/`，不在任何清理品类内）。
   - **清理后对比**：`analyze.py --mode scan --compare [--tag <名>]` → 输出每品类释放量；也可 `--compare --json | report.py -o compare.html` 生成对比报告。
   - **一键回滚**：macOS `restore_macos.sh`（预览 → `--all`/`--category`）；Windows `restore_windows.ps1`（预览 → `-All`/`-Category`）；原路径已存在则跳过避免覆盖。

## 系统检测与品类映射
| 系统 | 检测方式 | 可清理品类（均为可逆子路径） |
|---|---|---|
| macOS | `uname -s` == Darwin | `caches`=~/Library/Caches；`logs`=~/Library/Logs；`xcode`=~/Library/Developer/Xcode/DerivedData；`homebrew`=~/Library/Caches/Homebrew；`npm`=~/.npm/_cacache；`containers`=~/Library/Containers；`system`=/Library/Caches；`trash`=~/.Trash |
| Windows | `$env:OS` 含 Windows / `$IsWindows` | `temp`=%LOCALAPPDATA%\Temp + C:\Windows\Temp；`edge`/`chrome` 缓存；`wechat` 缓存；`winupdate`=C:\Windows\SoftwareDistribution\Download |

> Linux：当前 v1 未覆盖（路径约定不同，`~/.cache` 等），可作为扩展点，不影响 mac/win 分发。

## 硬规则（不可绕过）
1. 只读优先：清理前必先扫描/预览，列出路径+大小，绝不先删。
2. 仅安全子路径：见上表。禁区——macOS 的 ~/Desktop、~/Downloads、~/Documents、Home 根、/System；Windows 的桌面/下载/文档/用户目录根/C:\Windows（除明确列出的临时/下载缓存子路径）。
3. 废纸篓而非删除：macOS `mv` 进 `~/.Trash`；Windows 回收站 COM（`Shell.Application` NameSpace(10).MoveHere）。删除可逆。
4. 批量≤10：单次最多 10 个顶层目标，超出分次。
5. 先预览后确认：每动作前列受影响路径并 `y/N` 确认。
6. 不污染用户环境：脚本用系统内置命令（du/find/mv/osascript、PowerShell），不强制安装 brew/choco/第三方包。
7. 不写含非 ASCII 路径的 .ps1/.bat：Windows 清理一律走直接命令行调用，避免脚本文件名编码损坏。
8. **macOS 程序化风险门禁**：clean 脚本仅接受白名单精确路径（caches/logs/xcode/homebrew/npm/containers/system 的固定路径），通配符/父路径/未知品类一律拒绝——安全边界由代码强制，不依赖 LLM 记忆。
9. **macOS manifest + 回滚**：每次清理写入 `~/.clean-computer/manifest.jsonl`；`restore_macos.sh` 按记录恢复，原路径已存在则跳过（防覆盖）；清空废纸篓（status=emptied）不可恢复，仅审计展示。
10. **幂等**：已清理且路径不存在的品类，二次执行安全跳过（不重复误删新产生内容）。

## 核心分析引擎（v1.1，`scripts/analyze.py`）
纯 Python 标准库（os/hashlib/json），macOS + Windows 一套代码，**零第三方依赖**（python3 3.8+ 即可）。
- **磁盘画像（scan）**：各品类大小/文件数/最后访问天数/僵尸字节，大文件 Top-N（默认 >500MB，排除个人文档目录）。
- **重复文件检测（dupes）**：采样哈希（头/中/尾 3×64KB + 大小）预筛 → 同组内全量 SHA-256 确认，避免误报；只读报告，不清理。
- **僵尸缓存（zombie）**：按 atime 判断"超过 N 天（默认 180）未被访问"的死缓存，给出可回收字节。
- **可回收预测（predict）**：每品类建议（安全/少量/无需）+ 合计；回收站品类按全量估算（但清空不可逆，须单独确认）。
- **JSON 输出（--json）**：Schema v1，供任意 AI agent 渲染表格/图表：
  `{schema_version, os, generated_at, zombie_days_threshold, categories[], large_files[], duplicates[], prediction{}}`
  - categories[].risk ∈ green/yellow（红色禁区不进清单）；reclaimable_bytes = 僵尸字节
- **权限兜底**：遍历/哈希遇 PermissionError（如未授完全磁盘访问）静默跳过该文件，不中断；不会因单个文件失败而崩。
- **无 python3 场景**：自动回退 `scan_macos.sh` / `scan_windows.ps1`（仅基础品类大小，无重复/僵尸/预测能力）。

## 可视化报告与快照（v1.2，`scripts/report.py` + 快照对比）
- **HTML 报告（report.py）**：纯标准库生成、无 JS 无外链，任何环境可打开。含磁盘占比条形图、
  风险标记、大文件 Top、重复文件组、可回收预测、清理前后对比。
  - 主报告：`analyze.py --mode all --json | report.py -o report.html`
  - 对比报告：`analyze.py --mode scan --compare --json | report.py -o compare.html`
- **基线快照（--snapshot / --compare）**：存 `~/.clean-computer/`（不在任何清理品类内，不会被误删）。
  - 清理前 `--snapshot [--tag <名>]` 存基线；清理后 `--compare` 输出每品类 Δ（负数=释放），
    实现"数据准确性"的可核验闭环（预测释放量 → 实际释放量）。
- 样例报告见同包 `docs/samples/`（macOS 实测生成）。

## 安全层（v1.3/v1.5，双平台）
- **manifest 清理日志**：`clean_macos.sh` / `clean_windows.ps1` 每次实际清理（非 dry-run/WhatIf）自动写
  `~/.clean-computer/manifest.jsonl`（Windows 为 `%USERPROFILE%\.clean-computer\manifest.jsonl`），
  字段 `{ts, category, src, dest, size_bytes, status}`；status ∈ moved / emptied（清空回收站，不可逆）/ restored。
- **一键回滚**：
  - macOS `restore_macos.sh`：预览 → `--all` 恢复全部（或 `--category` 限定）；原路径已存在则跳过避免覆盖。
  - Windows `restore_windows.ps1`：预览 → `-All` 恢复（或 `-Category` 限定）；通过回收站 COM 枚举
    `System.Recycle.DeletedFrom` 匹配原路径后 `InvokeVerb("restore")`；原路径已存在则跳过。
  - 恢复后标记 status=restored，审计保留不删除。
- **程序化风险门禁**：clean 脚本内置白名单精确路径校验，未知品类/非白名单路径直接拒绝退出，
  不进入预览与确认流程——安全边界代码强制（macOS 与 Windows 均已实现）。
- **幂等**：manifest 已有记录且路径不存在的品类，二次执行提示后安全跳过。
- Windows 回收站统计：`analyze.py` 在 Windows 下用 PowerShell 只读统计回收站项数与大小
  （`$Recycle.Bin` 非可 stat 路径，不可用 os.path 直读）。

## 质量层（v1.4，`tests/`）
- **引擎单元测试** `tests/test_analyze.py`：11 项，fixtures 动态构造（重复/僵尸/大文件），覆盖 analyze.py 全部核心函数、JSON Schema、report.py HTML。
- **shell 集成测试** `tests/test_cli.sh`：15 项，沙箱 HOME 隔离（绝不碰真实环境），覆盖 clean 门禁/dry-run/清理+manifest/幂等 + restore 预览/回滚/防覆盖。
- **统一入口 + 性能基准** `tests/run_all.sh`：一键跑单元+集成+基准（真实目录只读扫描计时，写入 docs/samples/benchmark.txt）。
- 本机基准：scan 只读 7.29s（阈值 <120s）。分发前跑 `bash tests/run_all.sh` 确认全绿。

## 数据准确性与路径稳定性（给分发者的说明）
- 所用路径遵循 Apple/微软目录规范，十多年稳定；Apple Silicon / Intel 路径一致；`du`/`find`/`osascript`/PowerShell 均为系统自带，无依赖风险。
- 现代 macOS 把大量日志迁到**统一日志**，`~/Library/Logs` 可能偏小——属覆盖度，非错误（脚本对不存在/为空项优雅跳过）。
- 未授予"完全磁盘访问(Full Disk Access)"时，TCC 会让 `du` 对某些 `~/Library` 子目录报权限不足 → 脚本以 `2>/dev/null` 静默少算，**不报错**；如需完整扫描，引导用户授予 FDA。
- 固定脚本最大的准确性风险不是"路径变了"，而是"误删范围过宽"——因此"送回收站、不 rm"是底线。

## 包装开源项目（可选，非必要）
- BleachBit / ncdu / dupeGuru 可被调用；现状优先用系统内置命令实现"安全子集"，避免全局安装污染用户环境。
- 仅当用户已自装 dupeGuru/ncdu 时作只读辅助；BleachBit 较激进，默认不启用，须经用户确认预设后才可用。

## 跨平台 agent 兼容
- 本 `SKILL.md` 同时兼容 **WorkBuddy** 与 **Anthropic Claude Agent Skills**（均读取 `name` / `description` 做语义触发）。
- 上架其他平台时：保留 `name` / `description` / `version`；`description` 已写明触发场景，便于被语义匹配。
- 分发配套见同目录 `README.md`（WorkBuddy / Claude 安装方式）。

## 边界
- 不处理照片/文档/项目源码等个人资产；此类清理须用户明确知情并单独授权。
- 系统级清理（macOS `sudo`、Windows DISM/WinSxS）需提权，默认不做；如用户要求，单独说明风险并走提权流程。
