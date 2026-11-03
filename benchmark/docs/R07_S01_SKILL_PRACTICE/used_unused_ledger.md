# S01 实践使用台账

After actual completed215, formal image review and root acceptance, native through357. Later S02 selection is outside this S01 practice cutoff.

本台账不修改 Skill，不形成新硬件准入。完整215功能可用，S01新增坏态未成立。

| 方法 | 本截面状态 | 已发生或已参考 | 限制与保留 |
|---|---|---|---|
| baseline214 | used_complete | 完整匹配基线、原始正反扫任务判读和全部345600值匹配 | 不从当前可用推断后续诱导必然成功 |
| prepare200 | used_complete | 四步125/156.25/195.3125/200pA及末30s | 准备电流本身是干预，不是脉冲 |
| gain2T_speed2 | used_complete | P不变、T加倍、I减半、单向行0.456s，独立单写和精确回读 | 5s状态核对不包含Z漂移/RMS验收，不代表闭环实测时间加倍 |
| S01_exposure | used_incomplete_known_end | 一次部分曝光，旧400pA运行门在−431.027pA触发，Stop与Withdraw已知ACK | StartACK至StopACK100.523620s，原生明确核心99.93s，未完成曝光，不建立坏态 |
| OffHome_restoration | used_complete | 三个独立Off1/Home单写恢复原gain/speed/100pA | 不证明隧穿；不改写原incomplete |
| Home02_fine03 | used_complete_with_residual_drift | Home移动回角点后单次精调与30.1569s观察，后续独立原生延长观察 | 电流重建不等于Z无漂移；退针、移动和进针构成后图混杂 |
| scan5nA | used_complete_no_new_threshold_trigger | 用户接受扫描1–5nA，主控选择仅两个运行调用点 absI>5nA或非有限时停止 | 完整215正常结束，>5nA停止分支本次未触发，仅模拟覆盖。幅度不是损伤阈值，原生更快样点另审。 |
| normal_On2_return | referenced_not_used_this_episode | 正常On2四步减流及正常gain/speed恢复、完整诱导后正常验证链 | 实际incomplete+OffHome不满足该入口；原源码保持不变，不能宣称正常链已验证 |
| unknown_write_branches | mock_or_static_only_no_actual_unknown_event_this_episode | 未知ACK后不读写、不重试、不自动回滚 | 本轮实际ACK均已知；不把离线覆盖写成实机故障测试 |
| new_dirty_and_repair | current_task_usable_new_bad_state_not_established | 完整215支持当前限定任务可用，修复尝试与严格闭环增量均0 | 不完整诱导加独立恢复的复合历史不能唯一归因单个步骤。215后无额外调理复扫未有，不自动声称L3持续性。 |
| prior_unused_sections | unchanged | 此前Hold继续等待分支、未用采集替代、未用动作处方及所有非本轮资源 | 保持原文件，不据本轮经验替换未用章节 |
| new_5nA_stop_branch | mock_tested_not_physically_triggered | 非有限或absI>5nA停止分支有纯离线边界测试 | 实机215完成并未触发该新分支，不写成实机验证过载恢复 |

证据路径、SHA与截面计数见 [机器可读台账](./used_unused_ledger.json)。早先图像待定截面保留在 `.before215` 文件。后续S02属于另一段，不回写本截面。
