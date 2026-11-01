# 记录工具、字段和术语

## 离线操作入口

在本技能目录运行（Python 3 标准库；不访问仪器）：

```sh
python3 scripts/action_record.py init event.json --event-id E_NEW --session-id S_NEW
python3 scripts/action_record.py validate event.json --phase draft
python3 scripts/action_record.py validate event.json --phase ready
python3 scripts/action_record.py prepare event.json --output prepared.json
```

先按当前证据编辑 event.json。空模板可用于草稿，ready/prepare 会拒绝缺少授权、预算、合格起点等条件。`prepare` 仅写离线回执，`execution_permitted=false`；实际适配器须重新读回仪器、核验授权及防重放。历史复核可用 validate 的 `--at` 指定评估时间，不能将这个选项用于绕过真实发送前的新鲜性检查。

已知动作完成并补全结果后运行 `validate event.json --phase completed`。超时/结束未知的尝试仍保留原文件，用 draft 检查结构并明确 outcome；completed 拒绝这类记录不代表删除失败尝试或退还预算。这检查记录结构和一致性，不代表独立验证原始数据、科学判断或设备安全。当前工具只覆盖本机毫秒绝对 Hold 脉冲记录，不支持把 Tip Shaper/进针转换成可执行记录。其他动作需扩展相应字段/校验后使用；不得冒充 Bias.Pulse。

- [JSON 模板](../assets/action-record.template.json)：复制后填值，未知字段保留 null/unknown，不填推测的数字。
- [JSON Schema](../assets/action-record.schema.json)：字段类型和枚举。
- [执行/采集契约](./execution-and-acquisition.md)：真实接口、原生采集和控制适配器要求。

## 必须表达的关系

| 记录域 | 含义及注意事项 |
|---|---|
| 身份、时间、状态段 | 目标、操作者、UTC时间、当前授权来源、源码版本和人工历史；时间源不同时保存对应关系/偏差 |
| 任务和 before | 原始图、F/B、物理坐标/尺度、偏压/成像setpoint/速度/反馈/处理，失败模式、备选解释、有效基线与图后连续证据 |
| action | 准备电流与成像电流分开；静息/目标偏压、绝对或相对、电极极性、时长、Hold、XY、理由及预算 |
| execution | claim、发送、原始回包/错误码、已知结束或unknown；离线准备回执与真实执行claim分开 |
| acquisition | 模块、实际dt、通道、量程/模拟带宽、文件hash/完整性、平台与边沿、采样极值及削顶/缺口 |
| recovery | Bias/反馈读回、I/Z窗口/趋势、脉冲与移动后时间、漂移、稳定判据及等待上限 |
| after | 匹配图、处理算法、指标与覆盖范围、无额外调理的复核、局部样品变化 |
| assessment | 各L标签及证据引用、因果混杂、闭环是否成立、下一步/停止原因；不把脉冲次数当session数 |

具体键名以模板和 Schema 为准。额外原始通道或处理产物用有 hash 的证据引用关联，不把压缩截图当原始测量。现场 raw_data_ref 可指本地路径；公开摘要使用经审查的相对链接/来源标识，避免发布账号、设备地址和私人目录。

## 术语定义

- **结状态响应**：隧穿结及反馈工作点的可观测电气/机械读数变化，不等于已证实化学或原子结构改变。
- **Z 工作点突变（旧称“Z跳态”）**：记录 Z 出现不能由当前扫描地形/已知命令直接解释的阶跃或水平变化。给出时点、幅度、采样率及已知动作；不能默认全部是针尖长度变化。
- **等待 ACK**：客户端尚在等待响应；**成功 ACK** 是完整且错误码为零的回包。其能否代表原生结束取决于该命令的 wait 参数和协议语义。记录枚举 `zero_error_waiting_ack` 特指 wait-until-done 命令已经收到零错误响应，不是“仍在等待”的状态。
- **已知原生结束**：命令定义的完成条件获得确认；不包含“反馈已恢复、成像已稳定”的额外保证。
- **历史状态**：过去设备快照而非当前读回。它可用于解释历史数据，不能驱动新的脉冲、整形、进退针、位移或反馈恢复。
- **删失/削顶**：测量触及量程端导致真实幅度不可恢复。保留样点和时长，不能把端点当真实峰值。
- **修复闭环**：有任务坏态、可归属干预、匹配修后可用及必要复核的完整事件；人工示范候选、诱导尝试和未完成事件分别计数。

## 原归档定位与证据保全

旧实验归档通常包含 `OFF31_CURRENT_STATE.json`、`OFF31_EVIDENCE_INDEX_through_I12.json`；E01 子目录 `expert_pulse_20261031` 中有 `E01_SUMMARY_zh.txt`、`EXPERT31_EVIDENCE_INDEX.json`、`manual_intervention_confirmed.json`、waveform/comparison 分析和已核验脚本。研究员案例归档名为 `researcher_tip_examples_20261101`，包含 `deck_extraction.json`、`offline_assessment.md`、`scientific_implications.md`。

用当前工作区定位这些文件并检查版本，不将历史 IP/端口当连接许可。原报告保持原版本，新判断写修订记录及索引，不能事后修改原始动作、掩盖人工介入或倒补成功次数。
