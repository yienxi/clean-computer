# 电脑清理工作流 · 设计说明与沉淀

> 来源：WorkBuddy 分享链接 `https://workbuddy.link/p/PxIEQwuard0Tc2NVbVcVSc`
> 主题：设计电脑清理工作流并封装为 skill（Mac / Windows）
> 沉淀日期：2026-08-20 ｜ 项目空间：Clean Computer

---

## 一、对分享内容的本源理解

分享链接内是一段**规划式对话**。原对话中你提出：

> "先讨论，针对电脑 mac windows 是否可以设计一个工作流 包装为 skill 来解决日常电脑清理方向的功能。目前市场上有很多这类开源项目，是否可以实现包装呢"

上一轮 WorkBuddy 的结论要点（已对齐吸收）：
- **方向可行**：电脑清理工作流完全能封装成 skill。
- **但形态必须是"引导式清理副驾"，不是"一键自动清理器"**。
- **核心矛盾**：清理天然想删东西，而本运行时的"个人目录安全框架"对 Desktop/Downloads/Documents/Home 根/系统根做了极严格限制（禁递归删除、删除走回收站、批量≤10、先备份/先确认）。
- 这既是合规约束，也是**正确的产品形态**——自动删个人文件本就危险。

本仓库已据此矛盾把方案落成可加载的 skill（见 `.workbuddy/skills/clean-computer/`）。

---

## 二、设计框架（已封装）

### 工作流（6 步）
1. 检测 OS（macOS / Windows）
2. 只读扫描（磁盘占用、缓存、日志、临时、派生数据、大文件）
3. 生成报告（路径 + 大小 + 风险）
4. 逐品类确认（绝不默认全清）
5. 安全执行（仅 `--confirm` 后，送回收站，单批≤10）
6. 核验汇总（估算释放空间，提示清空回收站不可逆）

### 安全目标清单（仅这些可逆子路径）
| 系统 | 可清理路径 |
|---|---|
| macOS | `~/Library/Caches`、`/Library/Caches`、`~/Library/Logs`、`~/Library/Developer/Xcode/DerivedData`、`~/Library/Caches/Homebrew`、`~/.npm/_cacache`、`~/Library/Containers`、`~/.Trash` |
| Windows | `%LOCALAPPDATA%\Temp`、`C:\Windows\Temp`、Edge/Chrome 缓存、微信缓存、`C:\Windows\SoftwareDistribution\Download` |

### 硬规则（写入 SKILL.md，不可绕过）
只读优先 · 仅安全子路径 · 回收站非 rm · 批量≤10 · 先预览后确认 · 不污染用户环境 · 不写非 ASCII 路径的 ps1/bat。

### 包装开源项目的判断
- BleachBit / ncdu / dupeGuru 可被调用，但**非必要**。
- 优先用系统内置命令实现"安全子集"，避免全局安装包污染用户环境。
- 仅当用户已自装 dupeGuru/ncdu 时作只读辅助；BleachBit 激进，默认不启用。

---

## 三、Skill vs MCP 方向对比（含本场景选型）

### 概念
- **Skill**：一份 `SKILL.md` + 可选脚本/参考，被加载进对话上下文，作为"操作指引"驱动智能体调用工具执行。本质是**流程/知识封装**。
- **MCP（Model Context Protocol）**：一个独立 server 进程，通过标准协议向任意兼容客户端暴露 tools/resources/prompts。本质是**能力/服务封装**。

### 对比表
| 维度 | Skill | MCP |
|---|---|---|
| 形态 | Markdown + 脚本，随上下文加载 | 独立进程（stdio/HTTP），常驻 |
| 部署成本 | 极低：一个文件夹，git 管理 | 较高：需运行时、安装、mcp.json 配置 |
| 状态 | 无状态（跨轮靠文件/记忆） | 可有状态：连接、缓存、后台任务 |
| 工具可靠性 | 提示驱动，复杂分支可能漂移 | 强类型 schema，执行更稳 |
| 跨客户端 | 仅 WorkBuddy 体系 | 任何 MCP 兼容客户端可用 |
| 触发 | 语义匹配用户意图 | 客户端连接后按需调用 |
| 适合 | 工作流/流程/知识 | 系统对接/长驻/多客户端共用 |
| 调试 | 在对话内，直观 | 跨进程，较难 |
| 调度自治 | 需借助 automation 层 | server 本身可常驻/监控 |

### 优缺点精炼
- **Skill 优点**：轻、可移植、随对话走、易分享（本分享链接文化即如此）、无需基建；**缺点**：无状态、复杂逻辑靠 LLM 遵循、难被非智能体客户端复用。
- **MCP 优点**：标准协议、可常驻、强类型、可集中做审计/权限；**缺点**：重、需部署运维、对本场景杀鸡用牛刀。

### 本清理场景的选型建议
- **主力用 Skill**：清理是"一套本地工作流"，由智能体经 Bash 直接跑本机命令即可，无需常驻 server，且最易按分享链接方式沉淀/复用。
- **何时才值得上 MCP**：仅当满足以下任一时——① 要在多台机器/多客户端间共用同一套"清理引擎"；② 需要常驻监控/定时守护（如磁盘水位告警）；③ 要把"扫描/回收站"等原语做成强类型工具供其他非 WorkBuddy 程序调用；④ 审计/权限需集中在 server 端。单机个人清理，YAGNI（暂时不需要）。
- **折中（未来可选）**：Skill 做编排层 + 一个可选 MCP server 暴露"安全原语（scan/trash）"供复用。当前不实现。

---

## 四、已落地产物
- `.workbuddy/skills/clean-computer/SKILL.md` — 技能主体（含安全约束与 6 步工作流）
- `.workbuddy/skills/clean-computer/scripts/scan_macos.sh` — macOS 只读扫描
- `.workbuddy/skills/clean-computer/scripts/clean_macos.sh` — macOS 引导式清理（dry-run 默认，--confirm 才删）
- `.workbuddy/skills/clean-computer/scripts/scan_windows.ps1` — Windows 只读扫描
- `.workbuddy/skills/clean-computer/scripts/clean_windows.ps1` — Windows 引导式清理（WhatIf 默认，-Confirm 才删）

## 五、方向调整记录（2026-08-20 10:30）
用户拍板：**第一版转攻 skill，做成可分发到各 AI agent 平台的版本**；设计原则锁定为
**交互引导 + 数据准确性 + 安全边界**。上架由用户后续自行完成。
- 已据此把 `SKILL.md` 升级为 **v1.0.0 可分发版**：显式写入三条设计原则、强化 OS 检测与品类映射、
  固化"路径稳定性 / TCC 完全磁盘访问"结论；frontmatter 标 `portable: true`，同时兼容 WorkBuddy 与
  Anthropic Claude Agent Skills（均读 name/description）。
- 新增 `clean-computer/README.md`：WorkBuddy / Claude 安装方式与跨平台上架说明。
- 客户端/轻客户端路线**暂缓**（用户认为 skill 先上架验证更广覆盖更直接）；若未来要做客户端，
  引擎仍复用本 skill 的确定性脚本，客户端用系统 API 解析目录 + 引导授予 FDA。

## 六、路径稳定性 / TCC 结论（已固化进 SKILL.md）
- 所选路径遵循 Apple/微软目录规范，十多年稳定；Apple Silicon/Intel 一致；`du`/`find`/`osascript`/PowerShell 均系统自带，无依赖风险 → **固定脚本不会"执行错误"，最多某些品类在新系统显示为空（覆盖度，非崩溃）**。
- 真正会"变"的是：① TCC 权限（macOS 10.14+ 对 `~/Library` 子目录收权，未授 FDA 时 `du` 报权限不足→脚本 `2>/dev/null` 静默少算，不报错）；② 现代 macOS 日志大量迁到统一日志，`~/Library/Logs` 偏小。
- 根治：客户端用 `FileManager.url(for:.cachesDirectory)` 等系统 API 解析目录而非硬编码；skill 脚本保持"约定路径+防御式"已够稳。
- 固定脚本最大准确性风险是"误删范围过宽"而非路径变化 → "送回收站、不 rm"为底线。

## 七、v1 待办（用户上架前可继续完善）
1. Windows 脚本在真机/虚拟机实跑验证（当前 Darwin 环境无法跑 .ps1）。
2. 是否补"重复文件报告（仅只读、不自动清）"作为可选品类。
3. 是否加 WorkBuddy 内"每 3 天只读扫描"的 automation（低频调度验证）。
4. 上架前再统一走一遍各平台 frontmatter 字段校验。

## 八、v1.1 落地：核心分析引擎（2026-08-20 10:49）
用户指出 v1"没有技术含量"（脚本本质是 du/find/mv 薄封装），拍板执行 P0 引擎层优化。已落地：
- **新增 `scripts/analyze.py`**（纯 Python 标准库、mac/win 一套代码、零第三方依赖，python3.8+）：
  - 磁盘画像（各品类大小/文件数/最后访问天数/僵尸字节）+ 大文件 Top-N（默认 >500MB，排除个人文档）
  - 重复文件检测：采样哈希（头/中/尾 3×64KB+大小）预筛 → 同组全量 SHA-256 确认，避免误报；**只读报告不清理**
  - 僵尸缓存：按 atime 判断超过 N 天（默认 180）未访问的死缓存 → 可回收字节
  - 可回收预测：每品类建议 + 合计；回收站按全量估算（清空不可逆须单独确认）
  - `--json` 输出 Schema v1（categories[]/large_files[]/duplicates[]/prediction{}），供任意 agent 渲染
  - 权限兜底：PermissionError 静默跳过单文件，不中断（契合 TCC 未授权场景）
- **SKILL.md 升级 v1.1**：工作流第 2 步改用引擎，无 python3 时回退 scan_*.sh/ps1；新增"核心分析引擎"专节；frontmatter 加 `engine` 字段。
- **实测验证（本机）**：fixtures 构造重复/僵尸/大文件，断言 12 项全 PASS；真实目录跑全 mode 无崩溃，
  并检出 30 份重复 Cache.db（可省 1.4MB）。修 3 个 bug：`global` 声明顺序、report 阈值字段引用错误、
  采样哈希未捕获 PermissionError。
- **上架优势**：JSON Schema 让各 agent 平台只需"翻译 JSON → 界面"，重复/僵尸/预测是差异化卖点。
- 待办继承：Windows 端 analyze.py 需真机验证（脚本内 Windows 品类映射已写，未实跑）。

## 九、v1.2 落地：可视化报告 + 快照对比（2026-08-20 11:08）
用户拍板继续 P1 数据层，**macOS 平台优先落地**。已落地：
- **`analyze.py` 新增**：
  - `dir_stats` 一次 walk 顺带聚合 Top 子目录（不额外扫盘）→ 磁盘画像
  - `--snapshot [--tag <名>]`：基线快照存 `~/.clean-computer/`（该目录不在任何清理品类内，不会被误删）
  - `--compare [--tag <名>]`：对比最近基线，输出每品类 Δ（负数=释放）+ 总量释放
- **新增 `scripts/report.py`**：纯标准库生成自包含 HTML（无 JS 无外链），含磁盘占比条形图、
  风险标记、大文件 Top、重复文件组、可回收预测、清理前后对比；agent 平台可直接预览。
- **实测（本机）**：快照→篡改基线模拟清理（caches+500MB/logs+10MB）→ compare 精确捕获 510MB 释放；
  两份 HTML（主报告/对比报告）生成成功并存入 `docs/samples/`。
- **SKILL.md → v1.2.0**：工作流第 3 步报告改走 report.py HTML（macOS 优先，Windows 同引擎），
  第 6 步增加 snapshot/compare 可核验闭环；新增"可视化报告与快照"专节。
- **对"数据准确性"的兑现**：预测释放量（predict）→ 实际释放量（compare）形成闭环，可向用户展示核验结果。
- 待办：Windows 端 analyze.py + report.py 真机验证；Linux 品类映射仍为扩展点。

## 十、v1.3 落地：安全层（manifest + 回滚 + 门禁 + 幂等，macOS 优先）（2026-08-20 11:21）
用户拍板继续 P2 安全层，**macOS 系统端优先落地**。已落地：
- **`clean_macos.sh` 升级**：
  - manifest 清理日志：每次实际清理写 `~/.clean-computer/manifest.jsonl`
    `{ts, category, src, dest, size_bytes, status}`，status ∈ moved / emptied(清空废纸篓,不可逆) / restored
  - 程序化风险门禁：仅接受白名单精确路径（caches/logs/xcode/homebrew/npm/containers/system 固定路径），
    未知品类/非白名单路径直接拒绝退出——安全边界由代码强制，不再依赖 LLM 记忆
  - 幂等：manifest 已有记录且路径不存在的品类，二次执行安全跳过
- **新增 `scripts/restore_macos.sh`**：读 manifest，把废纸篓中 moved 项移回原路径；
  原路径已存在则跳过防覆盖；恢复后标记 restored（审计保留）；清空废纸篓（emptied）仅审计展示不可恢复。
- **实测（沙箱 HOME 隔离）**：6 项断言全过——门禁(dry-run) / 真实清理+manifest / 幂等跳过 /
  restore 预览 / 真实回滚(文件回原路径+manifest 标记 restored) / 废纸篓清空。
- **SKILL.md → v1.3.0**：工作流第 5 步加 manifest+门禁说明，第 6 步加回滚步骤；
  硬规则扩至 10 条（新增门禁/manifest+回滚/幂等）；新增"安全层"专节。
- **安全闭环**：扫描(只读) → 门禁(代码强制) → 确认(逐品类) → 废纸篓(可逆) → manifest(可回滚) → 对比(可核验)。
- 待办：Windows 端 manifest/回滚扩展（当前依赖回收站 COM 可逆，无 manifest）；Windows 全链路真机验证。

## 十一、v1.4 落地：质量层（测试套件 + 性能基准）（2026-08-20 11:26）
用户拍板继续 P3 质量层。已落地：
- **`tests/test_analyze.py`（单元 11 项）**：fixtures 动态构造（重复/僵尸/大文件，临时目录不碰真实环境），
  覆盖 analyze.py 全部核心函数 + 快照/对比 + JSON Schema + report.py HTML 流水线。
- **`tests/test_cli.sh`（集成 15 项）**：沙箱 HOME 隔离，覆盖 clean 门禁/dry-run/真实清理+manifest/幂等 +
  restore 预览/回滚/防覆盖 + analyze CLI 各 mode 退出码。
- **`tests/run_all.sh`**：一键跑 单元+集成+性能基准；基准记录 docs/samples/benchmark.txt。
- **本机基准**：scan 只读 7.29s（阈值 <120s）。
- **新增 CHANGELOG.md**：v1.0→v1.4 版本历史。
- **SKILL.md → v1.4.0**：新增"质量层"专节，README 验证部分指向 run_all.sh。
- **意义**：把"数据准确性"从文档承诺变成可重复验证的测试断言；分发前 `bash tests/run_all.sh` 全绿即可上架。
- 测试中发现并修正：测试数据缺 `os` 字段（引擎契约明确）、human() 单位边界断言（1000 B 非 1.0 KB）。
- 待办：Windows 端真机全链路验证；若上架到多平台，测试套件可接入 CI（GitHub Actions）。

## 十二、v1.5 落地：Windows 端对齐（2026-08-20 11:31）
用户指令"完善 windows 系统内的内容"。已落地：
- **`clean_windows.ps1` 升级**：补齐 manifest 日志（`%USERPROFILE%\.clean-computer\manifest.jsonl`）、
  程序化风险门禁（未知品类直接拒绝）、幂等（已清理且路径不存在则跳过）、单批≤10——对齐 macOS 端。
- **新增 `scripts/restore_windows.ps1`**：从 manifest 一键回滚——回收站 COM 枚举
  `System.Recycle.DeletedFrom` 匹配原路径后 `InvokeVerb("restore")`；原路径已存在跳过；恢复后标记 restored。
- **`analyze.py` 修复**：Windows 回收站 `$Recycle.Bin` 非可 stat 路径（os.path.exists 恒 False），
  新增 `_win_recycle_stats()` 用 PowerShell 只读统计项数/大小，失败回退零值；
  补 `category_map("windows")` 映射断言 + 回收站回退单测 → 全量单元测试 13 项通过。
- **SKILL.md → v1.5.0**：安全层专节改"双平台"；README/CHANGELOG 同步。
- **双平台四层对齐**：引擎/数据/安全/质量层 macOS 与 Windows 能力一致。
- **唯一遗留**：Windows 端 .ps1 与 PowerShell 统计需真机/虚拟机实跑验证（Darwin 无法执行）。
- 上架清单（v1.5 就绪）：run_all.sh 全绿（macOS 实测）+ Windows 真机验证后即可分发各 agent 平台。

## 十三、v1.6 落地：用户入口（cc.sh + 调取手册，macOS 实测）（2026-08-20 11:37）
用户指令"mac 端直接执行 包括用户如何调取执行 完善下"。已落地：
- **新增 `scripts/cc.sh` 统一入口**（POSIX sh，自动检测 OS）：
  `scan / report / clean <品类> [--confirm] / restore [--all] / snapshot / compare / status / help`；
  clean/restore 默认仅预览，显式 `--confirm`/`--all` 才执行——安全边界在入口层同样强制。
  Windows 分支自动转调 clean_windows.ps1 / restore_windows.ps1。
- **macOS 全链路实测（真实本机，全部只读安全）**：
  `cc.sh scan`（4.2GB 应用缓存等）✓ / `cc.sh status` ✓ / `cc.sh report`（HTML 生成并打开）✓ /
  `cc.sh clean caches`（DRY-RUN 预览，未删）✓ / `cc.sh snapshot`（存基线）✓ /
  `cc.sh compare`（基线 vs 当前）✓ / `cc.sh restore`（无 manifest 时正确提示）✓。
  演示产生的真实基线快照保留在 `~/.clean-computer/`（即快照设计用途）。
- **README 新增"用户如何调取执行"手册**：方式 A 终端 cc.sh（最简，仅依赖 python3）/
  方式 B AI agent 对话触发 / 方式 C 定时只读扫描（可 cron/launchd）。
- **SKILL.md → v1.6.0**：新增"用户如何调取执行"节；工作流第 2 步首选 cc.sh；
  明确 agent 代跑清理须先展示预览并逐品类征得用户同意。
- **修复**：cc.sh report 对不存在目录自动 mkdir。
- 意义：从"开发者的 skill 包"变成"用户能直接执行的工具"——`./cc.sh scan` 一条命令即可上手。
- 待办继承：Windows 端真机验证；cron/launchd 定时扫描示例可后续补（用户此前提过"每 3 天"）。
