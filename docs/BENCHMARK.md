# STM Agent Benchmark v0.2：任务与复核说明

本文件描述 `stm_bench` 的实际接口和评分。完整的一回合由 Agent 选择动作，由环境验证顺序和证据，再由后端执行。软件后端与 Nanonis Demo 共用环境和指标函数，各自保留数据来源。运行时的确切版本以输出目录中的 `source_snapshot/stm_bench/` 和 `protocol.json` 为准。

## 任务流程与成功条件

流程为：

```text
approach
  → observe × 2（连续且独立的稳定窗口）
  → survey（完整且符合数值门禁）
  → select_roi（在概览范围内选区、变换坐标并移动）
  → observe × 2（移动后重新确认稳定）
  → scan × 2（同设置的独立局部扫描）
  → judge("good")（针对最新图）
  → accept（再次核验当前配置）
```

在默认正常任务中，这对应 11 个动作和 3 次扫描。环境阶段名称为 `approach`、`stabilize`、`survey`、`locate`、`scan`、`judge`、`complete`、`failed`。策略应以 `action_mask` 判断可执行动作，不能仅按阶段名假设动作合法。

两段稳定窗口必须有不同的 `window_id`，时间范围有效且不重叠；窗口中的 setpoint、Z 量程和反馈状态必须符合当前配置。只有连续两段通过才开放扫描。参数变更、ROI 移动会清空稳定计数、旧图确认和复扫配对；不稳定的新观察也会使已有复扫确认失效。

每次扫描必须有新 ID、`fresh=true`、实际运行到停止的生命周期、正数采集时长、原始 Current/Z 正反扫数据及配置元数据。整回合保存已见过的扫描 ID 和数组摘要；把旧缓冲改名后再次提交也会被拒绝。环境在扫描前后核对配置，接受最终结果前再读取一次配置。双图验收要求两张局部图同配置、数据不同、各自合格、去平面后的正扫 Z 相关系数达到阈值。

`terminated=true` 表示成功、主动撤回或已确定的故障终止；`truncated=true` 表示动作预算耗尽。最后一个预算动作如果已经成功，不再标为截断。结束后必须 `reset` 才能继续 `step`。`close` 执行清理；清理失败会使 runner 的最终成功标记无效。

## 动作与观测

动作是字典，命令键可写为 `type` 或 `action`；同时提供时必须一致。

| 动作 | 参数 | 必要证据和作用 |
|---|---|---|
| `approach` | 无 | 只在初始阶段执行；完成证据与反馈开启后进入稳定确认 |
| `observe` | 无 | 获取新的 Current/Z 时间窗口；默认 32 个采样 |
| `configure` | `params` 字典 | 调整允许范围内的控制参数，随后重新确认稳定 |
| `survey` | 无 | 稳定后采集概览图；合格后允许 ROI |
| `select_roi` | `roi={x,y,size}` | 在最近概览坐标系中选区并移动；随后重新确认稳定 |
| `scan` | 无 | ROI 移动并稳定后获取新的局部扫描 |
| `judge` | `label`，可选 `diagnosis` | 对最新图声明数值质量标签及独立诊断假设 |
| `accept` | 无 | 双图确认成立且最新图已正确声明 `good` 才可接受 |
| `retract` | 无 | 主动结束本回合并撤回/关闭反馈 |

`configure` 的键为 `p_gain_m`、`time_constant_s`、`line_time_s`、`setpoint_A`。单位分别为 m、s、s、A。所有输入必须有限；参数批次不能夹带未知键。后端还会验证自身约束和回读。策略可根据可用后端的 `configuration_bounds` 获取其支持范围；最终生效范围由环境与后端验证器共同决定。

| 参数 | synthetic 范围 | Demo 后端范围 |
|---|---:|---:|
| P 增益 | 10–160 pm | 5–100 pm |
| 时间常数 | 0.5–20 ms | 0.1–10 ms |
| 单方向行时间 | 10–500 ms | 50–300 ms |
| 电流设定 | 0.05–5 nA | 0.01–10 nA |

以上是本软件的执行范围，不是物理仪器的已校准安全包络。当前环境优先采用后端声明的参数范围，未声明时采用 synthetic 范围，后端写入前再次验证。修改参数或范围后应使用新的运行目录与协议版本。

ROI 的 `x/y` 为概览图中的归一化中心，`size` 为概览宽高的共同缩放比例，范围为 0.15–0.5；整个 ROI 必须落在概览内。列增大对应局部 +X，行增大对应局部 +Y。局部偏移按扫描框角度旋转后转换到设备中心坐标，两方向图采用相同空间方向，不按“看起来更相似”而自动镜像。

`choose_roi` 参考可见图像的纹理、正反扫一致性和电流波动选择内部区域。`localization_valid` 仅表示几何与流程有效；`scientific_localization_accuracy=null`。该字段不评价是否找到了某个原子、缺陷、分子或研究目标。

Agent 观测包括：

- `stage/action_mask`：阶段及当前合法动作。
- `profile`：本环境固定使用的数值验收配置，默认 `strict-v1`。
- `snapshot`：反馈、控制设置、扫描框、Z 量程、后端名；Demo 还带当前读数。
- `latest_stability`：最新窗口的稳定性数值与门禁结果。
- `latest_image`：图像数值指标；移除了评估器的 `acceptable/label/checks/scientific_validity`。
- `latest_frame`：原始正反扫 Current/Z 数组及采集元数据。
- `stable_windows/detail_scans/repeatability`：稳定计数、当前有效局部图数、复扫证据。
- `budgets/last_error`：剩余动作数和上一动作错误。

场景名称、seed 和预期答案属于评测调度记录，不放入 Agent 观测。`info` 和 `summary` 含评测证据及判图一致性，外部评测器应将其记录为反馈/日志，并明确自己的 Agent 能看到哪些信息。这里是公开数值规则的工作流 benchmark，没有提供防读取同进程评估器的安全沙箱。

## 数值门禁

阈值集中在 `stm_bench/profiles.py::PROFILES`，每个运行协议均保存实际配置名称和阈值副本。`stm_bench/metrics.py::THRESHOLDS` 保留为默认严格配置的兼容名称。下表是 `strict-v1`，与 v0.1 规则一致：

| 指标 | 阈值 | 应用范围 |
|---|---:|---|
| 有效窗口样本数 | 至少 16 | 稳定窗口 |
| 反馈 | 必须开启 | 稳定窗口、扫描与重复性 |
| 电流均值相对设定误差 | ≤ 0.30 | 稳定窗口及图像，默认 strict-v1 |
| 电流 CV | ≤ 0.80 | 稳定窗口及图像 |
| 绝对电流峰值/设定值 | ≤ 20 | 稳定窗口及图像 |
| 绝对电流峰值 | < 1 µA | 保护门禁；达到阈值即终止 |
| 超过 5 倍设定值的电流像素比例 | ≤ 0.001 | 图像；两个方向合并 |
| Z 限位比例 | ≤ 0.01 | 窗口及两个图像方向 |
| 窗口 Z 线性漂移斜率绝对值 | ≤ 2 nm/s | 稳定窗口 |
| 去平面 Z 标准差 | ≥ 1 pm | 两个方向分别满足 |
| 去平面 Z 峰谷差 | ≥ 5 pm | 两个方向分别满足 |
| 去平面 Z 正反扫相关系数 | ≥ 0.60 | 每张图 |
| 两张局部图去平面正扫 Z 相关系数 | ≥ 0.90 | 独立复扫确认 |

电流相对误差定义为 `abs(mean(I)-setpoint)/abs(setpoint)`；CV 为标准差除以电流均值绝对值，并对零分母进行保护。Z 限位按 `abs(Z) >= 0.499*z_range` 统计。图像去平面采用二维最小二乘平面，只用于指标计算，原始数组不被改写。非有限值、尺寸不一致、缺失元数据或失真的生命周期不能成为合格证据；数据中同时存在 NaN 和过流时仍触发保护。

v0.2 起可显式选择 `--profile relaxed-v1` 或 `STMEnv(profile="relaxed-v1")`，策略 `RulePolicy(profile="relaxed-v1")` 应使用同一 profile。宽松配置仅将均值误差改为0.40、CV改为1.00、异常像素占比改为0.003、正反扫相关改为0.50、复扫相关改为0.80。默认严格配置及其他门禁不变。完整阈值、配对结果和重复 Demo 试验见 [RELAXED_TRIALS.md](RELAXED_TRIALS.md)。配置为每实例只读对象，不存在修改全局阈值影响其他环境的问题。

判图标签由数值规则产生：全部通过为 `good`；Z 限位失败为 `saturated`；纹理门禁失败为 `flat`；其余完整但不合格图为 `noisy`；不完整数据为 `incomplete`。这些标签是工程质量类别。`double_tip` 软件场景构造方向相关的重影/不一致，部分图会以 `noisy` 被拒绝，部分连贯伪影也可能通过数值门禁；概览通过而局部图失败也是允许的结果。工程未提供真实双针尖分类器或科学图像标签。

`judge` 可另带 `diagnosis="unknown"/"clean"/"double_tip"/"drift"`，默认 `unknown`。例如 `{"type":"judge","label":"good","diagnosis":"double_tip"}` 表示“数值质量合格，但 Agent 怀疑双针尖伪影”。该假设记录为 `unverified_agent_hypothesis`；声明 `double_tip/drift` 的这次 verdict 不开放 `accept`。外部视觉策略可以通过这个接口提出超出数值门禁的判断。synthetic 外层评测器可对照构造场景核对诊断并评价拒绝结果；Demo 只记录假设，不能验证真实科学诊断。

## 奖励、总分和故障通过率

阶段积分只在首次达到时获得：

| 阶段 | 积分 |
|---|---:|
| 进针完成 | 10 |
| 两个稳定窗口 | 15 |
| 合格概览 | 15 |
| 合法 ROI | 15 |
| 合格局部图 | 15 |
| 双图重复性确认 | 15 |
| 判图与数值标签一致 | 5 |
| 最终接受 | 10 |
| 合计 | 100 |

每个动作扣 0.1 分，非法动作额外扣 2 分，错误判图扣 1 分，后端或证据故障扣 5 分。阶段积分不会通过重复同一动作刷取。`summary.score` 是阶段分与惩罚之和，通常与逐步 `reward` 总和一致；它不是成功概率或图像科学质量分。最短正常流程 11 步得 98.9 分。失败回合保留已经达到的阶段分，因此比较策略应同时看成功率、故障误接受、错误数和清理结果，不能只看平均分。

`workflow_success` 表示完成整个验收流程；`task_pass` 对不同场景另作判断：`nominal/noisy` 要求工作流成功，其他场景要求有相应故障证据并合理退出。无隧穿需要未完成的 approach 证据；过流需要实际超限测量；扫描超时需要稳定后发起扫描且发生对应超时；缓存故障需要扫描尝试及缓存/重复证据。`flat` 需要平坦图像及正确判图后主动撤回；`double_tip` 可由有证据的 `noisy` 判图，或在扫描后声明与构造场景匹配的 `double_tip` 诊断再撤回通过。`drift` 可由漂移/复扫不一致等数值证据，或扫描后的匹配诊断再撤回通过。诊断匹配仅是 synthetic 的场景 oracle，不能外推为真实诊断准确率。提前撤回、实现异常和预算耗尽不自动获得故障识别分。

`evaluate` 同时报告工作流成功率、场景通过率及 Wilson 95% 区间、故障场景误接受数、平均分、平均动作数、清理失败和执行错误。区间仅描述这些生成案例，不推断实际 STM 设备可靠性。

## 两种后端

### synthetic

`SyntheticBackend` 完全离线，以 seed 决定表面、缺陷及随机测量噪声。表面、信号和图像使用独立 RNG 流，允许复现实验。P/T/行时间会影响误差，ROI 的物理坐标会改变观测图像。模拟时间随窗口与扫描推进，不需要实际等待。

| 场景 | 软件构造和期望 |
|---|---|
| `nominal` | 常规完整流程，期望成功 |
| `noisy` | 初始设置产生高噪声，有限调参后期望成功 |
| `drift` | 漂移造成独立扫描不一致，期望有证据地拒绝 |
| `double_tip` | 构造方向相关重影，不等同真实双针尖模型，期望有证据地拒绝 |
| `no_tunnel` | 有界进针尝试不能建立隧穿 |
| `current_spike` | 测量中产生超过保护阈值的电流 |
| `scan_timeout` | 有界扫描不完成 |
| `flat` | 图像无有效 Z 纹理 |
| `stale_frame` | 再次返回旧缓冲证据 |

此后端是任务生成器；参数响应曲线、缺陷分布、噪声和故障均未对真实 STM 校准。它适合测试任务顺序、恢复策略、接口和证据约束。

### nanonis_demo

`DemoBackend` 使用原始 Nanonis TCP 协议。动态识别 Current/Z 通道，避免把某个历史通道号写死。默认任务将扫描设置为 5 nm 方框、64×64、5 nA、P=35 pm、T=1 ms、每方向行时间 256 ms，保留当前偏压。64/128 分辨率由 CLI 选择。

写入前核验唯一的本机 Sim-Engine、端口属于 Nanonis Mimea、两进程来自同一安装目录、至少三条双向本机连接、无非回环连接、无其他 PI 控制客户端，以及 PID/创建时间等身份持续一致。只允许 `127.0.0.1` 的指定端口，没有解除 SIM 限制的参数。

Demo 先保存配置并执行 `ZCtrl.Withdraw`，核验反馈关闭和模拟器 Z 量程端点，再执行 `AutoApproach.OnOffSet`。进针必须观察到运行→停止且反馈开启，不能把 ACK 当完成。进针等待上限为 45 秒；扫描等待按帧时间计算且不超过 120 秒。常规写预算 224 次，包含清理在内总预算 256 次。通信状态不确定后禁止自动重连和猜测式重试。

扫描由本回合启动，观察运行→停止，确认配置未变化，读取完整 Current/Z 正反扫数组，并立即再次读取缓冲核对一致性。退出时停止本回合拥有的操作、撤回并回读，然后逐项恢复保存的 setpoint、P/T、扫描框、buffer、行时间、扫描属性及反馈设置；偏压仅验证一致，未纳入调节动作。

恢复报告中的 `restored=true` 只指记录的配置及停止状态一致，**不表示原 Z 位置或粗电机位置恢复**。`z_position_restored=false` 保留在结果中。已验证的 pilot 初始反馈关闭，结束时也关闭，Z 停在撤回端点。身份和进程检查是执行隔离措施，不是物理安全认证；本项目未实现真机控制入口。

## CLI 与数据划分

从克隆后的项目根目录运行；以下命令使用初始化脚本创建的 `.venv`：

```powershell
.\.venv\Scripts\python.exe -m stm_bench run --scenario nominal --seed 7 --policy rule
.\.venv\Scripts\python.exe -m stm_bench evaluate --split train --seeds 3 --policies rule random
.\.venv\Scripts\python.exe -m stm_bench evaluate --split dev --seeds 3 --policies rule random
.\.venv\Scripts\python.exe -m stm_bench evaluate --split test --seeds 3 --policies rule random
.\.venv\Scripts\python.exe -m stm_bench demo --port 6501 --pixels 64
.\.venv\Scripts\python.exe -m stm_bench compare --seeds 20 --seed-offset 100
.\.venv\Scripts\python.exe -m stm_bench demo-series --profile relaxed-v1 --repeats 5
.\.venv\Scripts\python.exe -m stm_bench audit .\runs\某次运行
.\.venv\Scripts\python.exe -m stm_bench stdio
```

`run/evaluate/demo/compare/demo-series` 可用 `--out` 指定一个尚不存在的新目录。`run` 默认最多 48 步，`demo` 及系列中的每次 Demo 为 32 步。`evaluate --seeds` 是**每个场景**的 seed 数，允许 1–50；默认 9 场景 × 3 seeds × 2 策略，共 54 回合。`run/evaluate/demo/stdio` 的默认 profile 为 `strict-v1`，`demo-series` 默认 `relaxed-v1`；脚本 `run_benchmark.ps1` 也默认宽松配置。

`make_cases` 按 `seed = split_base + scenario_index*1000 + seed_offset + j` 生成案例。train/dev/test 的 base 分别为 100、10000、1000000；`evaluate --seed-offset` 默认 0，偏移与 seed 数之和不能超过 1000。同一次套件中的各策略使用同一案例清单。`cases.json` 在执行前保存任务和预期结果。seed 分离不等同样品、材料、会话或仪器的分布外验证。名为 `train` 的集合可供外部训练使用；本项目的 `evaluate` 本身不训练模型。

`compare` 默认使用 test 集、偏移 100、每场景 20 seeds，在 `strict-v1/relaxed-v1` 下各运行 rule/random，共 720 回合、360 个策略与案例配对。两组起始 seeds 相同，门禁变化可能改变后续动作轨迹；它不是只对同一组图像重新评分。`demo-series` 顺序执行最多五个预先定义的参数组合，保留每次成功或失败记录；清理失败或执行异常会停止后续试验。

`rule` 是可检查的数值规则策略，直接根据公开指标和合法动作选择下一步；`random` 在合法动作菜单中随机选择并生成有界参数。它们都没有读取场景名或隐藏表面参数。规则基线的成功不能作为模型理解原子图像的证据。

`run/demo` 返回码 0 表示 `task_pass=true`，2 表示未通过；`audit` 的 0/1 分别表示文件核验通过/失败。`evaluate` 返回码主要反映执行错误是否为零，**不保证所有案例通过**；应读取 `summary.json` 中各策略的统计。

## 外部 Agent 接入

### Python

环境不是 `gymnasium.Env` 子类，但沿用相同的五元组 step 习惯：

```python
from stm_bench.env import STMEnv

env = STMEnv(max_steps=48)
obs, info = env.reset(seed=0, options={"scenario": "nominal"})
obs, reward, terminated, truncated, info = env.step({"type": "approach"})
# 后续每步把 obs 交给自己的模型；输出必须是 action_mask 中的动作。
env.close()
```

`env.step` 不直接调用模型。外部策略可以是函数、LLM 工具调用层或 RL 策略网络。只将约定的观测字段传给策略，把原始动作、观测、奖励、失败和清理结果记录在评测端。Python 和 stdio 直接调用不会自动生成 runner 的完整报告；需要使用 `run_episode` 中相同的 Recorder/冻结协议工作流，或自行实现等价记录。CLI 当前内置的 `--policy` 只接受 `rule/random`。

Python 中可显式构造 Demo 后端：

```python
from stm_bench.demo import DemoBackend
from stm_bench.env import STMEnv
from stm_bench.policies import RulePolicy

backend = DemoBackend(out_dir="runs/custom_demo_device", port=6501, pixels=64)
env = STMEnv(backend=backend, max_steps=32)
policy = RulePolicy()
try:
    obs, info = env.reset(seed=0, options={"scenario": "nominal"})
    while True:
        obs, reward, terminated, truncated, info = env.step(policy.act(obs))
        if terminated or truncated:
            break
finally:
    env.close()
```

该构造会连接真实运行的本机 Demo，`reset` 会执行写操作。每个 DemoBackend 实例只允许一次准备和一回合；新的会话应新建实例和输出目录。synthetic 则支持同一环境多次 deterministic reset。

### stdio JSONL

启动 `python -m stm_bench stdio` 后，保持进程不退出，向 stdin 每行写入一个 JSON 请求，并读取对应 stdout 行。`request_id` 原样返回；异常以 `error` 字段返回，不把 traceback 混入协议。

```json
{"request_id":"r1","tool":"reset","arguments":{"seed":0,"scenario":"nominal"}}
{"request_id":"r2","tool":"step","arguments":{"action":{"type":"approach"}}}
{"request_id":"r3","tool":"step","arguments":{"action":{"type":"observe"}}}
{"request_id":"r4","tool":"summary","arguments":{}}
{"request_id":"r5","tool":"close","arguments":{}}
```

`reset` 的 `result` 含 `observation/info`；`step` 含 `observation/reward/terminated/truncated/info`；`summary` 返回汇总；`close` 返回清理结果。数组转为 JSON 数组，非有限标量序列化为 `null`。外部评测器负责日志和模型调用超时。此接口当前使用 synthetic，不会根据 JSON 请求切换到 Demo。

## 证据目录与审计

每个 runner 回合输出：

| 文件或目录 | 内容 |
|---|---|
| `protocol.json` | 阈值、协议版本、源文件摘要、Python/NumPy/平台信息 |
| `source_snapshot/stm_bench/` | 开始运行时复制的 Python 源文件和 JSON 协议目录 |
| `events.jsonl` | reset、决策、逐步 transition、异常、清理事件 |
| `frames/*.npz` | 完整且未修改的四个 Current/Z 正反扫数组 |
| `frames/*.json` | 每帧元数据、配置、来源和采集 ID |
| `summary.json` | 阶段、分数、成功/退出原因、判图、重复性和清理结果 |
| `report.html` | 本地可打开的结果与图像预览 |
| `manifest.json` | 输出文件 SHA-256 清单 |
| `device/`（Demo） | 身份证据、设备事件、原始 TCP 请求/响应、NPY 扫描及清理记录 |

原始扫描在交给门禁后即使被拒收也会通过 `info.acquired_frame` 传给记录器；Demo 适配器另存协议字节和采集数组。报告中的颜色映射只作用于预览，不能代替原始数组。套件根目录另有 `cases.json`、聚合 `summary.json/report.html`、自己的源代码快照及包含子回合清单的 manifest。

`audit` 对缺失、增加、内容变化的文件逐项报告，且不修改被核验目录。它验证封存后的文件完整性，不重新采集、不重算科学结论，也不能证明原始证据具有真实物理意义。需要复核算法时可将 source_snapshot 与协议摘要对照，并从原始数组重新调用指标函数。封存后不要在原运行目录内添加笔记或重新生成报告；新分析应放到另一个目录。

## 已取得的证据与适用范围

实际 Demo pilot 已完成 11 动作、3 次新扫描、21 次写入，运行 140.141 秒，得分 98.9，重复图相关系数 0.9993532516，配置回读恢复通过；公开摘要见 [demo_pilot_001](../results/v0.1.0/demo_pilot_001/summary.json)。该 pilot 先于部分最终审计增强，不应被描述为所有后续代码改动的验证。v0.1 历史冻结运行、软件测试及套件结果由 [VALIDATION.md](VALIDATION.md) 记录；v0.2 见 [RELAXED_TRIALS.md](RELAXED_TRIALS.md)。

当前可评测完整的数值操作与证据链，不能据此声称已获得真实 STM 的自主科学实验能力。尚缺真实材料/仪器/操作者分层数据、专家双盲图像标签、物理进针风险标定、目标定位真值以及跨日跨样品评测。科学 ROI 准确率、原子分辨能力、真实双针尖判别均未宣称通过。

历史 logger、既有 RL 试验、旧模型、数据和结果保持独立。本工程不修改或重跑旧封版实验；旧成果仅作为接口设计与实现来源参考，所有新增实验都进入本工程的新目录。
