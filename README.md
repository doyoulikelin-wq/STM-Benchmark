# STM Benchmark 与 Au(111) Skill

仓库分成两个独立目录，实验结果、模拟评测和技能规程分别标注来源。

| 目录 | 内容 | 入口 |
|---|---|---|
| `benchmark/` | 可运行 synthetic / Nanonis Demo 环境、测试、历史结果及精选实机证据 | [运行说明](benchmark/README.md) |
| `skill/stm-au111-tip-conditioning/` | Au(111) 图像诊断、动作记录与功能验证技能；不包含通用实机驱动 | [Skill 入口](skill/stm-au111-tip-conditioning/SKILL.md) |

[2026-11-02 前置实验证据包](benchmark/results/au111_five_sessions_20261102/README.md)记录：S01完成一次完整修前—动作—修后尝试，严格成功闭环为0；S02完成慢扫199、快扫200和一次脉冲，但返回阶段发生中断，该时段已有其他实验员操作确认，缺修后完整图，不计第二次完整流程。总体为 **1/5完整尝试，0成功，余4**。这不等于五次流程已经完成，也不并入 synthetic / Demo 分数。

用户后来确认20:47有其他实验员操作。新证据注记与当时“原因未知”的原始审计同时保留；具体手动命令与全部物理变化仍未提供。

运行 benchmark（Python 3.11+）：

```powershell
Set-Location benchmark
.\scripts\initialize.ps1
.\.venv\Scripts\python.exe -m stm_bench run --scenario nominal --seed 0 --policy rule
```

安装 Skill 时复制整个 `skill/stm-au111-tip-conditioning/` 文件夹，包括 `references`、`scripts`、`assets`、`agents`。独立运行所需脚本／模板都在该Skill目录内，历史实测证据链接则指向仓库的benchmark证据包。本地规程中的设备经验不是通用安全上限；实际硬件操作须使用当前已经核验的适配器与明确授权。

精选证据包使用相对链接，可离线查看完整图层。GB级原生DataLog/TCP逐包档案保留在原本地档案，包内提供逐文件SHA、采样规模、来源定位与省略说明。发布记录不包含厂商程序、手册或Python运行环境。
