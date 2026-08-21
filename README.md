# clean-computer · 引导式电脑清理 Skill

跨平台（macOS / Windows）、可分发到各 AI agent 平台的电脑清理技能。
**交互引导 · 数据准确性 · 安全边界** —— 不是一键自动清理器，是"引导式清理副驾"：
只读分析 → 逐品类确认 → 送回收站（可逆）→ manifest 可回滚。

## 快速开始

```bash
cd .workbuddy/skills/clean-computer/scripts

./cc.sh scan          # 只读扫描磁盘占用
./cc.sh report        # 生成 HTML 可视化报告（自动打开）
./cc.sh clean caches  # 预览待清理项（不删除）
./cc.sh clean caches --confirm   # 确认后送废纸篓（可恢复）
./cc.sh restore       # 预览可回滚项
./cc.sh restore --all # 一键恢复
./cc.sh snapshot / compare       # 清理前后对比，核验释放量
./cc.sh status        # 查看 manifest / 快照 / 状态
```

安全设计：`clean`/`restore` 默认仅预览，必须显式 `--confirm`/`--all` 才执行；仅处理白名单安全子路径，删除走回收站，单批≤10。

## 能力全景

| 层 | 能力 | 文件 |
|---|---|---|
| 引擎 | 重复文件检测（采样哈希+全量确认）、僵尸缓存（atime 判断）、可回收预测、JSON Schema v1 | `analyze.py` |
| 数据 | HTML 可视化报告（磁盘占比/大文件/重复组）、快照/对比（核验释放量） | `report.py` |
| 安全 | manifest 清理日志、一键回滚、程序化风险门禁、幂等 | `clean_*.sh/ps1` `restore_*.sh/ps1` |
| 质量 | 测试套件（单元+集成+性能基准，沙箱隔离） | `tests/` |
| 入口 | 统一命令 `cc.sh`（自动检测 OS） | `cc.sh` |

## 目录

```
clean-computer/
├── SKILL.md            # 技能定义（兼容 WorkBuddy 与 Claude Agent Skills）
├── README.md           # 分发安装 + 用户调取执行手册（详见 skill 包内）
├── CHANGELOG.md        # 版本历史（v1.0 → v1.6）
├── scripts/            # 引擎/报告/清理/回滚/统一入口
├── tests/              # 测试套件
└── docs/samples/       # 实测报告样例与性能基准
```

## 使用方式

- **终端**：`./cc.sh scan`（唯一依赖 python3，macOS 自带）
- **AI agent 对话**：安装后说"清理电脑 / 看磁盘空间"即触发，走完整引导流程
- **定时扫描**：`cc.sh scan` 只读安全，可挂 cron/launchd 低频巡检

## 文档

- 详细设计（skill vs MCP 选型、路径稳定性/TCC 结论）：[docs/DESIGN.md](docs/DESIGN.md)
- 分发安装与用户手册：[.workbuddy/skills/clean-computer/README.md](.workbuddy/skills/clean-computer/README.md)

## 协议

MIT License
