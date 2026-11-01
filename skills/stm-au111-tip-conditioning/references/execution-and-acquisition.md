# 工具入口、原生采集和执行契约

## 本包可直接使用的部分

Python 3 标准库离线工具：`scripts/action_record.py`，模板 `assets/action-record.template.json`，字段约束 `assets/action-record.schema.json`。从技能目录执行 `python3 scripts/action_record.py --help` 查看 init/validate/prepare 的准确参数。本项目用 `init --profile local-au111` 选择当前本地规则，并在 validate/prepare 中加 `--require-profile local-au111`；generic profile 不能替代本项目规则。工具没有 socket、仪器驱动或 GUI 操作；准备回执不发送命令、不读取设备、不获得许可，也不是防止设备重放的执行 claim。

这是一份流程技能加离线记录工具。**仓库的 `nanonis_demo` 后端只支持已核验的 Simulator，不能把实机地址传给它或绕过身份检查。** 当前包没有实机适配器；跨设备执行前必须找到、审阅并绑定当地适配器，记录脚本 SHA、协议版本、允许命令及真实目标。

## 已有本机实现与对应接口

历史本机实现可通过下表文件名在原实验归档中定位（定位根目录由当地环境提供，不将私人路径/地址写入可移植技能）。这些实现含固定状态、源文件 SHA 和旧配置依赖，**不是安装本技能后即可跨会话运行的脚本**。当前状态变化不能只改一个脉冲常数；须重新核对 readback/guard/cleanup。

| 责任 | 本机实现入口 | Nanonis 接口/动作 |
|---|---|---|
| 查询并核对起点 | `expert_profile.py: guard, in_band, plan`；pulse 脚本 `Run.capture, Run.guard` | `Bias.Get`、`Current.Get`、`ZCtrl.SetpntGet`、`ZCtrl.ZPosGet`、`ZCtrl.OnOffGet`、`ZCtrl.StatusGet`、`Scan.StatusGet`、`BiasSpectr.StatusGet`、`ZSpectr.StatusGet`；SafeTip/XY/温度还须绑定本机已核验入口或原生 UI |
| 单次脉冲、原始收发、claim、恢复 | `pulse_expert_1nA_neg4V_20ms_hold_once.py: Run.execute, Run.write, Run.cleanup` | `Bias.Pulse`；实际编码和值集中见 local protocol；错误回包不能当成功 |
| 独立原生采集 | `datalog_expert_1nA_once.py: settings, state_guard, run` | `DataLog.ChsSet/ChsGet`、`DataLog.PropsSet/PropsGet`、`DataLog.Start/Stop/StatusGet` |
| 身份/通道/时序/标定 | 上述 logger 的 preflight / timing_guard | `Util.VersionGet`、`Util.SessionPathGet`、`Signals.NamesGet`、`Util.RTFreqGet`、`Util.RTOversamplGet`、`Util.AcqPeriodGet`、`Current.CalibrGet` |
| 离线历史审计 | `check_expert_offline.py` | 不连接设备；不能代替当前实机预检 |

`Bias.Pulse` 本机编码依次为 unsigned 32-bit wait、float32 width_seconds、float32 bias_V、unsigned 16-bit Z-hold 枚举、unsigned 16-bit bias-mode 枚举，按本机协议的大端格式封装。必须核对当前厂商协议和适配器测试；本表不是独立发包程序。GUI `stm_tip_session.exe` 与直接 Nanonis TCP 是不同控制途径，记录实际使用者。

## 采样验收

- 原生同步 **I、Bias、Z** 为最小通道集合；电流前放量程、增益、模拟带宽、滤波、采样率和时间对齐均记录。普通 TCP `Current.Get` 轮询用于慢状态检查，不负责还原短脉冲。
- 针对本地协议的毫秒脉冲，默认沿用已验证 Data Logger 采样配置（数值在 [local protocol](./local-au111-protocol.md)）。本技能把 **至少 1 ksample/s 且名义最短平台不少于 20 样点** 作为粗分段的最低记录门槛；这是工程可分析性门槛，不是硬件安全阈值。改变脉宽须重新算 `fs × duration`。
- 该门槛只能区分脉冲前、平台和恢复的大体区段，**不保证解析真实上升/下降沿或峰值**。要测边沿波形，需根据边沿时间和模拟带宽选择更高采样率，并核验同步触发、抗混叠与电压量程；不要宣称“两个边沿样点 = 已解析边沿”。
- 首选本机已验证的 **Nanonis Data Logger**。Oscilloscope Hi-Res 或外部示波器可作为经核验的替代，当前未验证其通道同步、带宽、接线和触发，不把模块名字写成已完成配置。外部接线须当地操作者核验。
- 先验证 logger 正在记录、文件头的真实 `dt`、正确通道、剩余记录时长覆盖准备/动作/恢复。结束后确认原生结束、完整样本数和文件块；header-only 文件或仅 hash 暂时不变不证明完整。
- 用实测 Bias 定位平台，保留名义时长、目标平台样点数、过渡区、恢复段、缺口、削顶样点/时长。削顶峰值记 censored；低采样峰值记采样极值，不称真实峰上界。

## 单次适配器必须满足的状态转换

`draft → validated → claim_persisted → sent → acknowledged → native_end_known → recovery_checked → imaged → assessed`

- `claim_persisted`：唯一事件 ID、精确命令、参数、授权范围、预读回和源码 SHA 已原子落盘。已有 claim 不重放；发送失败也不能仅因没 ACK 就复用 ID。
- `acknowledged`：收到完整回包，记录错误码、内容和时间。仅在协议明确 wait-flag 的返回语义且无错误时，才能用 ACK 支持 `native_end_known`。
- `unknown`：发送结果、命令结束、连接状态任一不明时分支到人工核查，不继续正常状态链，不发送自动 On 或第二次动作。
- `recovery_checked`：已知结束后，独立确认 Bias/setpoint/反馈及恢复窗口；本项目 local-au111 流程核对 SafeTip 仍为 Off，generic 流程按其已声明状态核对。协议未明确自动恢复的内容必须读取验证，不能以 ACK 代替。
- 策略复核是继续规划的检查点，不是执行 claim：连续无改善的历史不清零，保存复核覆盖的累计 pulse 序号；跨电压、阶段或 Tip Shaper 都沿用同一 session pulse 总数。不能复用旧复核覆盖后来新的无改善段。
- 实时每次发送前重新验证计数、范围、新鲜性及独占控制。离线 JSON 可以伪造/过期，所以本包校验器只检查自报记录一致性，不签发硬件许可或宣称“安全”。

## 恢复等待与故障处置

恢复记录包括 pulse-end、Hold release（可观测时）、反馈恢复、XY 返回、scan-start 时间及各时间源偏差。保存最后稳定窗长度、I 均值/噪声/尖峰、Z 斜率/噪声、端点余量及可观测的横向漂移。没有位置测量时把横漂标 unknown，后续图像配准不能伪装成实时读回。

冻结等待上限和任务相关容差；若超过上限或数据不足，结论为 not_stable/unknown，停止该流程。Z 不必回原绝对值，电流回设定值也不足以证明针态未变。PI 对压电位移的原厂说明指出，驱动电压变化后仍可能有随时间继续的位移，因此不规定“等待固定秒数即消除蠕变”。[PI 位移行为说明](https://www.pi-usa.us/en/products/piezo-flexure-nanopositioners/piezo-motion-control-tutorial/tutorial-4-20)

扫描中持续饱和、Z 限位或失稳：停止追加动作并立即交接。仅在控制状态明确、已知调理动作结束且扫描归当前控制者所有时使用本机已审核的停止扫描/撤回流程；**实际命令名、撤回方向、终点及成功读回由适配器明示，不能把此处文字当可发送的命令**。未知状态转原生 GUI/现场应急规程，避免多个客户端竞争写入。
