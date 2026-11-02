# STM-Benchmark · v0.2.0

这是一个可运行、可复核的 STM 自主实验环境，覆盖 **进针 → 稳定隧穿确认 → 概览扫描 → ROI 选区定位 → 局部扫图与复扫 → 判图与接受/退出**。Python 包名为 `stm_bench`。

环境提供两种后端：`synthetic` 是可复现的软件任务生成器；`nanonis_demo` 通过本机 TCP 实际控制 Nanonis Demo 并读取扫描数据。两种来源在记录中明确区分。当前评分衡量工作流、测量证据和数值控制能力；原子识别、材料鉴定、科学目标定位准确率尚未建立标注与验收标准。

## v0.2：宽松标准与多次实验

新增独立的 `relaxed-v1`，同时保留默认 `strict-v1`。两者使用相同身份、过流、超时、新鲜性及双窗口/双帧检查。每回合记录实际 profile 和阈值，不修改旧结果。

5 次实际 Nanonis Demo 参数试验全部走通全流程，取得 **15 张新扫描图**，配置恢复全部通过。

720 回合配对测试中，规则基线在正常/可恢复任务的完成数由 **31/40 增至 40/40**；故障误接受也由 **14/140 增至 25/140**。这表示验收容忍度变化，不能当成 Agent 能力提升。详见 [本轮实验报告](docs/RELAXED_TRIALS.md) 和 [可移植证据](results/v0.2.0/README.md)。

完成下方初始化后，可运行：

```powershell
.\.venv\Scripts\python.exe -m stm_bench run --profile relaxed-v1 --scenario noisy
.\.venv\Scripts\python.exe -m stm_bench compare --seeds 20 --seed-offset 100
.\.venv\Scripts\python.exe -m stm_bench demo-series --profile relaxed-v1 --repeats 5
```

最后一条会实际控制已核验的本机 Nanonis Demo，执行五个预先定义的参数组合。纯离线 CI 不连接设备。

## Au(111) 针尖调理经验与技能

[实机经验总结](docs/AU111_TIP_CONDITIONING_LESSONS.md) 区分诱导尝试、研究员示范、人工干预混杂与已验证修复闭环；这些观察不计入当前 synthetic / Demo 成绩。完整可移植 [技能包](../skill/stm-au111-tip-conditioning/SKILL.md) 包含物理依据、本地经验、记录模板和离线校验工具；它不提供通用实机驱动，也不改变 Simulator 身份保护。

[技能审查与确认记录](docs/TIP_SKILL_REVIEW.md) 列出 A–F 修订，以及用户确认的脉冲预算、策略复核、SafeTip 和图文参数澄清。安装时复制整个 `../skill/stm-au111-tip-conditioning/` 文件夹（包括 references、scripts、assets、agents），保留 `SKILL.md` 文件名。

## 开始运行

需要 Python 3.11 或更高版本。所有命令在仓库的 `benchmark/` 目录执行，不依赖历史实验目录中的 Python 环境。

```powershell
git clone https://github.com/doyoulikelin-wq/STM-Benchmark.git
Set-Location STM-Benchmark/benchmark
.\scripts\initialize.ps1
.\.venv\Scripts\python.exe -m stm_bench run --scenario nominal --seed 0 --policy rule
.\.venv\Scripts\python.exe -m stm_bench evaluate --split test --seeds 3 --policies rule random
```

初始化脚本建立本工程的 `.venv` 并安装依赖。也可手动执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

默认输出写入新建的 `runs/<命令>_<北京时间戳>/`。每次实验使用新目录，已有目录不会被覆盖。打开该目录的 `report.html` 可查看结果和 Z 图预览；`summary.json` 保存机器可读结果。

便捷入口为 `scripts/run_benchmark.ps1` 和 `scripts/run_demo.ps1`；前者默认宽松模式、每场景 5 个 seeds，可使用 `-Profile strict-v1 -Split dev -Seeds 3` 调整，后者可用 `-ReadOnly` 执行只读探测。另有 `scripts/run_comparison.ps1` 和 `scripts/run_demo_series.ps1`。CLI 参数及完整评测定义见 [BENCHMARK.md](docs/BENCHMARK.md)。

## Nanonis Demo 实验

打开本机 Nanonis STM Simulator 及 Programming Interface，使扫描和自动进针处于停止状态，并释放其他 PI 客户端连接，然后运行：

```powershell
.\.venv\Scripts\python.exe -m stm_bench demo --port 6501 --pixels 64
```

该命令会实际写入已核验的本机 Demo：先保存配置、撤回并设置任务起点，再自动进针、采集稳定窗口、扫描概览、移动 ROI、独立复扫、判图，最后撤回并恢复记录的配置。每次写入前重新核验 Nanonis/Sim-Engine 进程及本机连接关系；不存在真机模式或跳过身份检查的参数。CLI 允许端口 `6501/6502/6503`、分辨率 `64/128`。

配置恢复不等于恢复原来的针尖位置。Demo 清理记录明确保留 `z_position_restored=false`。第一次实际 Demo 试验在约 **140.14 秒** 内，以 **11 个动作、3 次新扫描、21 次设备写入** 完成流程，得分 **98.9**，两张局部图相关系数为 **0.999353**，配置恢复检查通过；结束时 Z 位于撤回端点。该结果来自一个本机会话。公开证据摘要位于 [demo_pilot_001](results/v0.1.0/demo_pilot_001/summary.json)，后续冻结验证与汇总见 [VALIDATION.md](docs/VALIDATION.md)。

## 接入自己的 Agent

Python 接口采用 `reset/step/close`，每步返回观测、奖励、结束标记和评测信息。以下例子可直接运行；替换 `policy.act` 即可接入自己的策略。

```python
from stm_bench.env import STMEnv
from stm_bench.policies import RulePolicy

env = STMEnv(max_steps=48)
policy = RulePolicy(seed=0)
try:
    obs, info = env.reset(seed=0, options={"scenario": "nominal"})
    while True:
        action = policy.act(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break
finally:
    env.close()
print(env.summary())
```

观测包含合法动作 `action_mask`、配置快照、Current/Z 测量指标、原始正反扫数组及剩余动作预算。策略不直接获得场景名称或图像验收标签。动作示例为 `{"type":"observe"}`、`{"type":"configure","params":{"line_time_s":0.256}}`、`{"type":"judge","label":"good"}`。判图还可声明独立的 `diagnosis` 假设，如 `double_tip` 或 `drift`；该假设不等于已验证的科学诊断。

其他语言或 Agent 框架可启动持久 JSONL 服务：

```powershell
.\.venv\Scripts\python.exe -m stm_bench stdio
```

服务支持 `reset/step/summary/close`，当前只连接 synthetic 后端。请求与响应格式、日志职责见 [接入说明](docs/BENCHMARK.md#外部-agent-接入)。

## 当前评测内容

九种软件场景为 `nominal`、`noisy`、`drift`、`double_tip`、`no_tunnel`、`current_spike`、`scan_timeout`、`flat`、`stale_frame`。内置 `rule` 数值规则基线和 `random` 合法动作随机基线；当前工程没有训练新的模型。

成功必须同时具备两段独立稳定窗口、通过门禁的概览图、有效 ROI、两张同设置且不同数据的局部图、重复性确认，以及针对最新图的 `judge=good` 和 `accept`。改参数或移动 ROI 会使旧稳定性和图像确认失效。故障场景通过率另外统计，必须有相应测量证据；提前放弃、程序错误或耗尽预算不自动算识别故障成功。

## 验证与记录

发布版本通过126项测试及171项子测试；[核验记录](results/verification_v0.2.0/README.md)保留只读收尾状态和完整性结果。

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m stm_bench audit .\runs\你的运行目录
```

记录包含逐步 JSONL、原始扫描 NPZ、Demo TCP 原始请求/响应、清理结果、运行时源代码快照和 SHA-256 文件清单。`audit` 只读核验文件完整性；它不替代科学判读或对结果进行独立重新评分。

公开仓库包含独立工程与精选实验记录；完整原始采集保留在本地。厂商程序、手册、Python 环境及其他历史实验目录不包含在仓库中。
