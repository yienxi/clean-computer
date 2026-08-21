# clean-computer Changelog

## v1.6.0（2026-08-20）— 用户入口（macOS 实测）
- 新增 `scripts/cc.sh` 统一入口：自动检测 OS，收拢 7 个子命令
  `scan / report / clean / restore / snapshot / compare / status`；clean/restore 默认仅预览，
  必须显式 `--confirm` / `--all` 才执行。
- README 新增"用户如何调取执行"手册（方式 A 终端 cc.sh / 方式 B agent 对话触发 / 方式 C 定时扫描）。
- macOS 全链路实测：scan / status / report（HTML 自动打开）/ clean 预览 / snapshot / compare / restore 预览 全部通过。
- `report` 命令自动创建输出目录；修复相对路径调用时目录不存在报错。
- SKILL.md → v1.6.0；工作流第 2 步与"用户如何调取执行"节接入 cc.sh。

## v1.5.0（2026-08-20）— Windows 端对齐
- `clean_windows.ps1`：补齐 manifest 日志（`%USERPROFILE%\.clean-computer\manifest.jsonl`）、
  程序化风险门禁（白名单精确路径）、幂等、单批≤10——对齐 macOS 端安全机制。
- 新增 `scripts/restore_windows.ps1`：从 manifest 一键回滚（回收站 COM 枚举
  `System.Recycle.DeletedFrom` 匹配原路径 → `InvokeVerb("restore")`；预览 → `-All`/`-Category`）。
- `analyze.py`：修复 Windows 回收站统计（`$Recycle.Bin` 非可 stat 路径，改用 PowerShell 只读统计
  项数与大小）；新增 `category_map("windows")` 与回收站回退单元测试（全量单元 13 项通过）。
- SKILL.md → v1.5.0；Windows 端与 macOS 端能力对齐（引擎/数据/安全/质量四层双平台覆盖）。
- 待办：Windows 端脚本真机/虚拟机实跑验证（当前 Darwin 环境无法执行 .ps1 与 PowerShell）。
## v1.4.0（2026-08-20）— 质量层：测试套件 + 性能基准
- 新增 `tests/test_analyze.py`：引擎单元测试 11 项（dir_stats/sample_hash/find_duplicates/scan_large_files/predict/快照/对比/JSON Schema/HTML 报告），fixtures 动态构造，不碰真实环境。
- 新增 `tests/test_cli.sh`：shell 集成测试 15 项（clean 门禁/dry-run/真实清理+manifest/幂等 + restore 预览/回滚/防覆盖 + analyze CLI 各 mode），沙箱 HOME 隔离。
- 新增 `tests/run_all.sh`：一键跑 单元 + 集成 + 性能基准（真实目录只读扫描计时，写入 `docs/samples/benchmark.txt`）。
- 本机基准：`scan` 只读耗时 7.29s（阈值 <120s 通过）。

## v1.3.0（2026-08-20）— 安全层（macOS 优先）
- `clean_macos.sh`：manifest 清理日志（`~/.clean-computer/manifest.jsonl`，status: moved/emptied/restored）、
  程序化风险门禁（白名单精确路径，代码强制拒绝）、幂等（已清理且路径不存在则安全跳过）。
- 新增 `scripts/restore_macos.sh`：从 manifest 一键回滚（预览 → `--all`/`--category`），原路径已存在跳过防覆盖，恢复后标记 restored 保留审计。
- SKILL.md 硬规则 7 → 10 条。

## v1.2.0（2026-08-20）— 数据层（macOS 优先）
- `analyze.py`：Top 子目录聚合（磁盘画像）、`--snapshot`（基线存 `~/.clean-computer/`）、`--compare`（每品类 Δ + 总量释放）。
- 新增 `scripts/report.py`：纯标准库生成自包含 HTML 报告（磁盘占比条形图/风险标记/大文件/重复组/预测/前后对比），无 JS 无外链。

## v1.1.0（2026-08-20）— 引擎层
- 新增 `scripts/analyze.py`：纯 Python 标准库、mac/win 一套代码、零依赖。
  - 磁盘画像 + 大文件 Top-N；重复文件检测（采样哈希预筛 → 全量 SHA-256 确认，只读不清理）；
  - 僵尸缓存（atime > 180 天）；可回收预测；`--json` 输出 Schema v1。
  - 权限兜底：PermissionError 静默跳过单文件不中断。
- SKILL.md 工作流改用引擎，无 python3 回退 scan_*.sh/ps1。

## v1.0.0（2026-08-20）— 可分发首版
- SKILL.md 显式三条设计原则（交互引导 / 数据准确性 / 安全边界），兼容 WorkBuddy 与 Claude Agent Skills。
- 跨平台脚本：scan/clean（macOS sh + Windows PowerShell），回收站可逆、逐品类确认、单批≤10。
- 新增 README（安装/上架说明）。
