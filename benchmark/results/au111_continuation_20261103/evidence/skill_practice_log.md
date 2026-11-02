> Portable export of a dated source. Original SHA-256: `7a97f81ede5a102c5b267f14c9d579b7202967c80909f3bfa1e40a42f3386274`. Local links were remapped; historical conclusions were not updated. See the package README for the final cutoff.

# 五次完整修针验证：skill 实践与未采用项记录

记录日期：2026-11-02（Asia/Shanghai）。本文件是**滚动实践台账**，不是五轮已执行的声明，也不是控制程序。本日志作者仅整理已落盘本地文件，未连接仪器、SMB、RustDesk或GUI，未发送硬件命令；真实设备操作由root单独记录。**未修改 skill、references、模板或控制代码。**

## 用户要求、状态边界与唯一当前覆盖

- 用户要求本轮做 **5 次完整修针记录**，每轮保留完整修前图、完整修后图及全过程记录。五个记录槽位不等于五个已执行动作，更不等于五个成功闭环；失败/中止/未达可用均如实记录。
- 用户已确认：自扫描 195 后，仅做过**扫描、进退针或移动**，未换针、未换样。来源为本轮对话中用户确认（root 转交）。这保留样品/针身份连续性，**不证明针态、位置或工作点未改变**；昨日 195 不能自动充当今日紧邻修前图。
- **唯一已明确的执行顺序覆盖：**用户要求完整修前/修后图，优先于 skill §4“先扫覆盖诊断对象的短条带”。本轮采用完整图作为主证据；不得只给短条带冒充完整图。完整几何/像素/方向/参数仍须按每轮新鲜状态与冻结计划明确，不能由“完整”二字直接猜定。
- 其余条款未因“五次”被覆盖。尤其未把次数目标解释为自动连发、无上限动作、已好针再强行刺激、重置脉冲计数或保证五次成功。已有用户授权与本机规则继续按实际范围核查，不重复索要已经明确的许可。
- 已有一份 root 采集的起始快照：**2026-11-02 08:13:21.947→08:13:22.062**，Bias −1 V、setpoint 100 pA、反馈 On/status2、Scan0、SafeTip Off；保留的几何仍为上一轮 50×12.5 nm /240×60，并非新完整图已经配置。[初始快照](../../au111_five_sessions_20261102/evidence/read_001_initial/snapshot.json)，SHA256 `9de72fc487ed050909cd0e8f1ba5f1dd328f5b314d9ee82ad12337f7229e5a71`。这是历史顺序读回，不替代任何后续动作前 fresh guard。

## 状态用词与证据规则

下表“采用（计划）”只表示已选择遵守该条款，**不表示设备步骤已经完成**；只有明确链接到本轮已落盘事件才写“已记录/已核实”。“未用”表示当前方案未选该方法，未被解释为禁止；“未触发”表示条件尚未发生或无新事件证据；“能力缺口”表示当前尚缺相应测量/适配能力或证据。每轮证据栏中的 `S01…S05 待填` 是待建索引，不是已存在文件。

每次更新保留时间、引用路径、SHA、事实/判断/计划三者差异；原始记录不事后覆盖。若新证据改变解释，在本表追加修订，不把旧条款静默改写成已验证程序。

## 建档时条款实践表（历史截面）

下表保留最初建档时的计划/未触发状态；并非截至结束时的状态。实际变化按后文顺序追加，最新结果见“五轮状态索引”及末尾“S01结束记录”。

|条款 / 来源|本轮状态|采用或未用原因|每轮证据（截至本次建档）|待提炼，暂不改 skill|
|---|---|---|---|---|
|§1 新鲜设备身份、I/Bias/设流、XY/Z、反馈/动作状态|采用：起始读回已记录；执行前复核待做|旧终态不能驱动新动作；新状态段从用户历史澄清与 fresh read 开始|initial snapshot 已链接；S01–S05 各自 before/state/hash 待填|列出每轮最小固定字段和动态字段；不要仅沿用旧固定 ref|
|§1 本项目 SafeTip Off，前后读回|采用（计划）；初始 Off 已核实|用户已明确本机规则，非泛化所有 STM|initial SafeTip=0；每轮动作前后 Off 证据待填|若实际需 On→Off，单列命令、ACK、读回；不能把初始 Off 当五轮全程 Off|
|§1 人工历史 / 状态段|采用：用户确认已记录|自195仅扫描/进退/移动，未换针样；可能改变针态|本轮用户确认；S01–S05 人工干预、移动和时间边界待填|身份连续与尖态连续分字段；“无人工报告”不等于连续监视|
|§1 每次动作授权范围 / 目标|采用（计划）|已有许可沿用，实际目标、极性、幅度、时间、电流、位移仍与计划绑定|每轮 authorization/target_id/reason/source 待填|经验范围不能补成新授权；未知物理电极极性保留 unknown|
|§1/§5 pulse最多6、连续2次无改善复核、换策略不清零|采用（计划）；本轮计数尚未建立实际事件|用户已确认；6是每session上限，不是打满目标；复核不是自动刺激|S01–S05 各自总动作/pulse/shaper、claim、失败史和复核 checkpoint 待填|连续无改善按 pulse 计；未知ACK消耗尝试；不能换目录/session绕同一修复预算|
|§2 事前任务与失败判据|采用（计划）|完整图需先定任务，不用后验容易通过指标|各轮 task/criteria.freeze、full-before、人工判读待填|沿用“数值通过≠人工稳定通过”的教训；每轮阈值来源明确|
|§2 原始F/B、多对象/可靠参照、背景与替代解释|采用（计划）|不凭双瓣、亮点或稳定电流单独定义坏针|每轮 full-before 原生矩阵、处理版本、失效证据待填|分别记录对象分辨、整行偏置、漂移、反馈、速度/处理混杂|
|§2 固定诊断区、其他授权位置调理后返回|未用：新轮位置方案尚未选|不能预先宣称已远离参照，移动路径/范围必须有证据|各轮 conditioning_xy、reference_xy、路径与返回证据待填|同处/异处设计何时必要，由实际空间与局部表面改变决定|
|§2 物理依据 / 一手资料|采用：已读 skill 内现有资料；本轮未新增公共检索|已有资料足以界定机制限制；不是当前参数保证|本文件来源hash表；每轮 hypothesis/alternative 待填|分清本机测得、实验员经验、文献和模型；不虚构新文献支持|
|§3 local-au111离线模板/prepare|未用：本轮尚未运行离线 init/validate/prepare|记录结构可沿用，实际准备完成前不伪造ready回执|S01–S05 action-record/validation receipt 待填|如实际由本机ledger补足，要记录模板未使用原因及字段映射；不得写成已验证|
|§3 实机适配器源码/协议/目标绑定|采用（计划）；新轮具体适配尚待绑定|skill不附通用实机驱动；旧helper有固定配置|每轮 adapter path/SHA/allowlist/协议/目标待填|历史helper只提供参考，不能把旧20nm/条带 guard当今日完整图|
|§3 单一写控制者 / 原子claim / 原始wire|采用（计划）|root唯一实机操作者；离线prepare不是执行claim|每轮 exclusive owner、claim、send/ACK/wirehash 待填|新的事件ID不重放旧事件；claim先持久化再发一次|
|§3 I/Bias/Z原生同步记录|采用：S01新logger已ACK/READY/progress；完整记录待审|短脉冲不能由普通Current.Get重建|S01 READY和首块dt/早期闭块已核（见下方执行更新）；各轮完整块、终止与全程覆盖待填|2kHz是本机历史已验证采样；1kHz/≥20平台点仅粗分段，不保证快沿/峰值|
|采集契约：模拟量程/前放带宽/过载恢复|能力缺口|历史前放型号/带宽未独立确认；本轮Current.CalibrGet仍gain index无效|initial errors；各轮range/bandwidth写unknown并引用实际材料|软件量程/校准不是物理保护；不把历史−9.99948nA当目标或真实上界|
|采集契约：Hi-Res/外部示波器替代|未用|同步、接线、触发及带宽尚未核验；本轮未选择|S01–S05 均待实际方法选择，不预填已配置|如今后使用应独立验证；模块名称不等于能力已具备|
|§3 修前图结束→动作连续记录 / 空档|采用（计划），尚未证明全程连续|用户要求全过程，需检查实际记录，不以logger名或文件hash代替覆盖|每轮 coverage intervals、gap ledger、人为事件、baseline_is_immediate 待填|若rollover有空档，重建基线或降低因果；不称严格连续|
|本地规程：准备电流与成像电流分开|采用（计划）；具体值待单次计划|用户要求完整图不代表始终1nA成像，也不自动沿用旧准备值|各轮 prepare/bias/setpoint/ramp与returned imaging字段待填|昨日11步验证存在，但skill仍写旧25%/1s草案未验证；见下方新证据差异，不先改skill|
|本地规程：单次−4V20msHold / 候选范围|未用：当前未冻结新轮动作|历史确有已验证命令，不等于五轮默认或自动梯度|各轮 chosen_action/hypothesis/actual native平台待填|同名协议在新针态也可能削顶；不能以E01未削顶推断今日不削顶|
|本地规程：TipShaper / 历史−1nm|未用：当前未选择整形|历史实际−1nm已确认，但不是新动作默认位移|若发生：轨迹、各阶段bias、first/second相对量、恢复、独立预算待填|不得用Bias.Pulse记录冒充TipShaper；不由截图参数直接Start|
|§3/执行契约：未知ACK/原生结束不明|未触发：尚无本轮新动作证据|此分支是保护门禁，不是默认发生|各轮执行状态、是否unknown、停止写入/现场核查证据待填|unknown不重发/On/猜测撤回；不能把TCP超时当取消|
|§4 恢复bias/反馈/电流分别确认|采用（计划）|ACK只证明相应完成条件，不能证明恢复或图好|每轮native-end、restingBias、feedback、current稳定证据待填|命令结束/反馈恢复/返回参照/scan-start时间分列|
|§4 I/Z趋势、漂移、稳定窗和等待上限|采用（计划）；横向实时漂移有能力缺口|等固定秒数不证明蠕变消失；Z工作点不必回旧值|每轮maxwait、elapsed、有效稳定窗、I噪声、Z slope/RMS、drift证据待填|无横向独立测量标unknown；后图配准不是实时XY测量|
|§4 匹配成像bias/current/speed/gain/尺寸/方向/处理|采用：S01完整图几何已配置，完整修前图仅已Start|完整修前后比较必须明确匹配项及实际偏差|各轮full before/after配置readback+native metadata+hash待填|几何需先冻结；不能用旧条带截图作今日完整后图|
|§4 “先短条带，足够则初判”|**未用：用户明确覆盖；S01已按完整图配置/Start**|本轮要求完整修前/修后图优先；这是目前唯一明确override|来源：本轮用户要求；每轮完整原生帧与覆盖检查待填|记录全图开销/信息收益，但不先修改skill默认顺序|
|§4 无额外调理独立复扫/重复窗口|采用（计划），尚未发生|完整修后图不自动代表持续可用；确认不能夹入新调理|每轮确认帧/窗口、间隔、无额外动作记录待填|允许任务范围/时长明确；诊断复扫不另计修针session|
|§4 L0–L4独立标签与因果|采用（计划），五轮均not_assessed|功能、化学、命令完成、因果不是一条递增总分|各轮每标签status+evidence、causal_valid、cycle verdict待填|L4未知不阻止L3；L0/L1不推出L2/L3；五个完整记录不等于五个成功闭环|
|§5 成功即停|未触发：本轮无成功事件证据|不为了凑五次刺激已达到任务标准的针态|各轮停止原因与后续新起点资格待填|若新轮需独立坏态/诱导，另记真实原因与授权，不自动创造坏态|
|§5 两次无改善策略复核|未触发：本轮无两次pulse结果|复核可自主有据完成，不是默认人工接管，也不是发下一动作|每轮连续pulse无改善/改善边界、复核所覆盖序号与hash待填|不以成功ACK清零；旧review不得覆盖新的无改善段|
|§5 预算/边界停止|未触发：本轮无预算耗尽证据|每实际writer有限预算，5轮目标不覆盖单轮边界|每轮预算before/claim/after、终止记录待填|失败、中止保留，不退还未知尝试、不换ID续打|
|§5 扫描饱和/Z限位/持续失稳/采集失败|未触发：本轮尚无新扫描/动作原生证据|历史异常不是当前发生；若新事件发生应停止升级并核查|各轮异常、饱和点数/时长、边界归属、处理ACK/验证待填|本机50pm图像旗标可漏低幅整行偏置；人工条款独立保留|
|§5 已知动作结束、owned scan可Stop；未知状态不竞争|采用（计划）；实际cleanup尚未触发|不能误写为必须等扫描自然结束；也不能对unknown盲撤|每轮cleanup前条件、唯一writer、Stop/Withdraw原始结果待填|记录调用准确语义、方向、终点和恢复证据；不把规范文字当命令|
|L4独立化学测量|能力缺口 / 未用|当前无适用尖端的独立化学表征手段或数据|各轮L4 unknown，不能用好图/电流/Z替代|化学标签独立，避免将“脏→干净”口语当检测事实|

## 五轮最简记录结构与当前状态索引

结构建议保留建档原貌；S01已按实际目录完成一轮记录，S02–S05尚未执行。

只需一个跨轮索引和每轮一个小目录，不必把skill重写成新框架：

|建议记录|最低内容|何时填写|
|---|---|---|
|`five_sessions_index.json`|S01–S05目标槽位、实际状态、前段终止/新起点关系、pulse与TipShaper与成功闭环分别计数、各目录hash索引|现在可列槽位；实际次数仅据claim/outcome推进|
|`Sxx/session.json`|身份/任务、用户授权来源、人工历史、geometry/settings、预算、事前指标、状态边界、计划与实际差异|该轮进入前先填已有证据；未知留null|
|`Sxx/before/`|完整原生修前图、F/B/通道、wire/metadata比对、人工失败判断；不能只留截图或crop|该轮完整图完成并核验后|
|`Sxx/action_01/`等|local-au111动作记录/验证回执，准备步骤、唯一claim、发送/ACK/knownend、源码与协议hash；每次动作独立记录|实际冻结/执行/完成时分阶段追加；不存在的动作不建“completed”占位|
|`Sxx/native/`及`coverage.json`|全过程闭合原生块、dt/通道/量程带宽、实际覆盖、空档与未知、采样峰/平顶/边沿及时间边界|先READY，后闭块hash核验；不读进行中共享文件作完整结论|
|`Sxx/recovery.json`|Bias/feedback/current/Z读回、真实elapsed、稳定窗口、Z趋势/漂移、返回参照及scan-start、异常分支|恢复实际发生后|
|`Sxx/after/`和`Sxx/confirm/`|完整匹配修后图；无新增调理复核或预定义重复窗口；原始数据和处理版本|实际完成后；失败帧同样保存|
|`Sxx/assessment.json`|L0–L4分别标注、因果混杂、完整轮次/成功闭环分开、停止理由、下一步是否仅分析|图像、原生、恢复共同审查后|
|本文件各轮更新|采用/未用/未触发/能力缺口实际变化、原因、证据路径/hash、待提炼|每轮结束追加，不回填虚构历史|

`S01…S05`是建议标识，不强制 root 改已有命名。一次准备＋一次脉冲＋返回＋多次诊断属于一个有记录的复合流程；不能把每幅图、每次SetpntSet、每次脉冲都叫一个完整session。若用其他实际目录名，本表填映射即可。

|轮次槽位|新起点/完整修前|调理动作及计数|完整修后/无调理复核|L0/L1/L2/L3/L4|完整轮次状态/成功闭环|skill条款实际差异|
|---|---|---|---|---|---|---|
|S01|完整196 DOWN已核，存在任务相关失稳|11步100pA→1nA；单−5V20msHold（本轮1，累计2/6）；11步返回100pA；TipShaper0|完整197＋无额外调理完整198均已结束、原生位匹配；229块归档完成|L0/L1/L2 supported；L3 not_supported；L4 unknown|完整尝试1/5；成功闭环0；等待扫描期软件限值事件解释后再决策|完整图覆盖短条带；未远处调理；软件下限读回已核但物理前放仍有缺口；有意提前Stop采集已对账|
|S02|待独立新起点证据|待发生|待发生|均not_assessed|planned / 未判定|待实践|
|S03|待独立新起点证据|待发生|待发生|均not_assessed|planned / 未判定|待实践|
|S04|待独立新起点证据|待发生|待发生|均not_assessed|planned / 未判定|待实践|
|S05|待独立新起点证据|待发生|待发生|均not_assessed|planned / 未判定|待实践|

## 已知新证据与skill文字差异：先记，不改

以下只作历史方法输入，**不转成2026-11-02的实时状态或自动处方**：

1. `local-au111-protocol.md`仍保存E01前已有1nA、不含实际电流爬升的历史；2026-11-01另有 **11步100pA→1nA及精确反序返回100pA** 的完成记录。两者不是同一个实验；新验证的每步持续5s与末30s/末10s趋势门槛，不能被简化成旧“25%/1s”草案已验证。来源：[昨日最终报告](../omitted-evidence.md#archive-224b65e04cc11293)、[prepare](../omitted-evidence.md#archive-23140e58a0811135)、[return](../omitted-evidence.md#archive-31a2bf58e3b9036a)。待积累五轮实践后再决定如何分开描述历史草案与已测路径。
2. 同一名义−4V20msHold协议在E01与昨日表现不同：昨日脉冲记录 **52点约−9.99948nA平顶**，故不得以E01未削顶给新针态作保证。平顶是真实峰值未知的证据，不是清针目标。来源：[昨日完整脉冲审计](../omitted-evidence.md#archive-35f8dcedbda75a7a)。
3. 昨日194/195两个固定背景及50pm旗标通过，但人工仍检出低幅整行偏置；因此“数值过”不能自动代表整ROI任务通过。来源：[截至195最终图像索引](../omitted-evidence.md#archive-6080df37d8d54341)。本轮应保留预定义人工条款，不为完成五次而降低标准。
4. 用户此次要求完整图，覆盖skill的短条带优先顺序。记录完整图的耗时、原生覆盖与信息收益，待五轮结束再评估是否需要可配置的“完整图优先”条款；**当前不修改skill**。

## 已读来源与版本固定

本轮只读取下列已安装skill版本；公开文献仅读取本地已有核查摘要，未重新浏览原论文，不把它标成今日重新验证。相对条款定位以以下文件内容为准。

|来源|SHA256|
|---|---|
|[SKILL.md](../omitted-evidence.md#archive-bc7221ef4dd8366f)|`fbafd84b86afdb6cbe6683b5e5de6dd1f1a6d1cb8b0dd903be8541cf818c18dc`|
|[references/local-au111-protocol.md](../omitted-evidence.md#archive-b2696bb9a32f72d7)|`dc19ebd3287869b7d58df8c916b1fd46161f15afe6cb9521a9074f1e94ed2643`|
|[references/execution-and-acquisition.md](../omitted-evidence.md#archive-6dd7ce8b5675cde1)|`8ed647bf2f10857618550ba7100f3346101c25d141f744162f4ed5b7e467199b`|
|[references/record-and-local-context.md](../omitted-evidence.md#archive-65b936e14149c994)|`0ea9b618b9aac9900d0af94bee10e0f34743b08167a022e7cf66337094e5ceaa`|
|[references/physics-and-evidence.md](../omitted-evidence.md#archive-485175501827a95f)|`a13dad1b4f0f33f30738489ce644aadb792e842e29ccc638be79d9812ddd9ee1`|
|[references/primary-literature.md](../omitted-evidence.md#archive-9160c59ac1df3e7d)|`907e22d12e001894ea707926c85ff390ed59a709c52767773e31fb1f9edef743`|

## 更新约定

仅将真实发生的步骤从“计划/待填”推进为已核实，并写证据与局限；发生未知ACK、人工干预、采集空档、削顶或未达标准时保留原始事件，不用后续好图删除它。每轮末追加：采用了哪些条款、哪些没有用及原因、哪些分支未触发、哪些能力缺口仍在、有哪些值得将来提炼的证据。用户本轮要求是**先记录实践，不改skill**；没有实际新证据时本表保持待填，不为五个槽位制造完成事实。


## 离线准备更新：单轮长时 logger 候选

本次增补只记录**离线工程准备完成**，不表示任何 logger 已启动或修针步骤已执行。旧 1200 nominal /历史600 wall 秒不足以一段覆盖完整修前图＋准备＋脉冲＋返回＋完整修后图；已准备最小派生 [logger_fullcycle_once.py](../../au111_five_sessions_20261102/evidence/logger_fullcycle_once.py)，SHA256 `f6a3a1b38b06123effc02c0c33599185f30b018d2378416311930815400557fa`，固定7200名义单位，以2小时0分钟0秒编码。历史比例只提供约3600 wall秒的容量估计，不构成本次已测时长。

|条款对应|更新后的准确状态|本地证据|仍未使用/待核实部分|
|---|---|---|---|
|执行与采集契约：当地适配器|采用：最小派生已离线准备/审查，未由本日志执行|[差异](../../au111_five_sessions_20261102/evidence/logger_fullcycle_source.diff)、[42项离线审查](../../au111_five_sessions_20261102/evidence/logger_fullcycle_offline_review.json)|根控制者实际预检、配置与Start尚不在此条宣称完成|
|原生单次计时/源码绑定|已固定五个精确输出目录 `session_01..05/logger`，manifest/READY/start.claim/outcome均绑定session_id/source_sha256/role|[离线测试](../../au111_five_sessions_20261102/evidence/test_logger_fullcycle_offline.py)|新时长的实际原生dt、总样点、开始/结束、块完整性待真实采集核验|
|原有被动logger控制范围|DataLog配置/Start/条件Stop；入场100pA/SafeOff，Start后junction只观测，未新增Bias/Setpoint/Scan/Move/On写入|与旧版state/q/poll/cleanup等12个函数AST一致；仅默认plan调用|它不能替代调理动作guard，也不是硬件保护或完整轮次的执行器|
|全过程覆盖|采用保守阶段预算模型 `min((7200-nativeElapsed)/2,3600-hostAge)`；记录等待仍有限（总7280s/完成等待7215s）|脚本manifest及offline plan|1小时未必覆盖最坏6次pulse与全部完整图；不足时停止发送待覆盖动作，不能将拼接记录默认为无空档|

离线测试封锁 socket/create_connection/DNS 后导入及默认plan，共42项通过、0网络尝试；没有调用原生 `run()`。原skill及references保持原SHA。具体现场执行及每轮真实证据仍由root后续更新，不用这一工程完成状态填充S01–S05的动作结果。


## S01 实际执行更新：完整图配置与长时采集早期核验

**证据截面：**本次root交付已完成配置、已开始完整修前扫描及前15个闭合原生块；只按这些证据更新，不把扫描尚在运行写成完整图已完成。root唯一硬件操作者；本日志作者仅读取本地复制件和既有原始回包。

|实际阶段|已核事实 / 来源|未据此宣称的部分|
|---|---|---|
|长时logger启动|DataLog.Start claim为08:21:18.450922，native start identity `2026/11/2 8:21:18`；08:21:19.114515发布READY；7200nominal读回[1,2,0,0.0,1]、6通道、RT20k/oversampling10均保留。[READY](../../au111_five_sessions_20261102/evidence/session_01/logger/READY.json)、[Start claim](../../au111_five_sessions_20261102/evidence/session_01/logger/start.claim)|这是成功开始与进展，不是已完成1小时记录；actual_remaining_seconds仍null|
|完整图几何配置|08:21:50.219806结果 `configured_and_readback_verified`；仅FrameSet+BufferSet两次已确认写入，后5.145s采样观察。目标50×50nm、240²，其他冻结字段保留。[结果](../../au111_five_sessions_20261102/evidence/session_01/configure_full/outcome.json)、[快照](../../au111_five_sessions_20261102/evidence/session_01/configure_full/snapshot.json)，SHA `e7a28eaff5a60ecba34632719699235e9b3d54d42d2292a1877ace418d2873b3`|配置本身未发Scan/Move，也不等于完整修前图已采集|
|完整修前扫描开始|08:22:25.766091单次 `Scan.Action[0,0]`，对应Down；Start ACK为空且无warning。[claim](../../au111_five_sessions_20261102/evidence/session_01/before_full/scan_start.claim)、[ACK](../../au111_five_sessions_20261102/evidence/session_01/before_full/scan_start_ack.json)|没有据Start ACK推断整帧完成、质量合格或脉冲已获准执行；名义437.76s不是已完成时长|
|首闭块|00001本地SHA `7d1630432594a516db204a08c3af5b5b9d852bf891aa09544d993b8acf4dc466`，25000行×6列、全有限、Bias−1、header dt0.5ms；名义块12.5s。[root首块审查](../../au111_five_sessions_20261102/evidence/session_01/initial_native_header_review.json)|只证明这一已闭块的格式/采样，不证明全过程无隙、原生完整时长或硬件高频峰已捕获|
|计数与保存时标复核|前101个状态：host55.652812s、native elapsed111.020000units，比1.994868；10组Status原始包共40文件hash及解码核对。[独立时序审查](../../au111_five_sessions_20261102/evidence/session_01/initial_native_timing_review/review.json)|支持历史约2倍计数的早期表现；不能外推为本轮完整7200必然3600wall|
|前15闭块阶段审查|每通道375000行/187.5名义s，225万有限标量，全部SHA/bytes/header/channel通过；Bias全−1。I采样最负−1.1991995nA（block15零基17179），幅值≥400pA16点、≥1nA2点；无≥9.99nA或历史相同平顶。[早期审查](../../au111_five_sessions_20261102/evidence/session_01/native_early_15_review/review.json)|没有把已采样极值当真实峰上界，也没有把混合配置/静置/扫描早段RMS当静态噪声；完整before/后续调理/全程覆盖未审|

**Saved Date 与 DataLog 语义限制：**首块header `Saved Date=08:21:23`，nativeStart后约5s；首次Status显示00001时counter10360，而该最终完整块按header为12.5s。因此Saved Date不能当作完整块结束时刻或样点绝对触发时间。首次Status已换00002是在08:21:31.452/counter980，支持root按“当前路径已推进至下一块”复制00001的闭合依据，但path与counter更新异步，不能逐点硬对齐。READY初期last_saved_path还可保留昨日文件；新start identity与progress、以及后来当前basename的闭块证据必须分开看。

上述前15块由root已有copy工具归档；独立审计工具 [audit_local_closed_blocks.py](../../au111_five_sessions_20261102/evidence/audit_local_closed_blocks.py) **只打开本NEW下的local_path**，不访问receipt中的source_path、共享目录或仪器。早期审查固定到through_index15，保留当时receipt副本；不是给运行中的整批采集出具完整性证书。待root交付完整修前与新闭块后再追加，不改任何控制源码。


## S01 更新：完整修前196结束、54闭块分期与单次候选

完整修前196于 **08:29:44.1257** 得到已完成WaitEnd；root已检查完整50nm图和四分区行差，按冻结标准支持任务相关坏态，L3不支持。两个固定背景虽通过，但低Y处F/B仍有跨全宽瞬态线：例如F rows231→232约351–364pm后反向回落，另一处约163–176pm。机制保留结/针尖/反馈不稳及局部遭遇、机械/电气等替代解释，未确诊化学污染。[root完整修前判断](../../au111_five_sessions_20261102/evidence/session_01/full_before_root_review.json)

原生审计已从首15块推进到 **54个闭合块**：135万行/通道，810万有限标量，header合675s，全部hash/bytes/0.5ms/通道核验，Bias全−1V。利用scanner自身原始DataLog.Status包夹定边界：Start为block6 counter9560..10100（0.27s边界），End为block41 counter9940..11780（0.92s边界）；边界单列，不强归scan/post。4组状态的16个原始包hash与解码核验。

|实际阶段|已核原生结果|限制|
|---|---|---|
|196保守扫描核心437.42s|I最负−6.6787234nA；幅值≥400pA106点、≥1nA25点；max相邻Z158.98pm；峰与Z大步均在扫描内|无≥9.99nA或历史相同平顶，不证明模拟链绝无饱和或真实高频峰上界；不是图像像素电流|
|保守post169.11s|I−152.402..−66.715pA，均−99.794/RMS4.143pA，无≥400pA|已采样后段未见持续nA级异常，不代表未来live状态|
|最后30s /10s|30s I均−99.729/RMS2.994pA，Z斜率−.0444pm/s、去线性RMS1.443pm；30s仅1原生点略出±20%（−121.833pA）。末10s I−114.129..−85.628pA、Z斜率+.00906pm/s/RMS1.335pm|原生瞬时电流与慢Getter稳定带不同；该1点保留，不隐藏；下一动作仍需独立freshguard|

权威阶段索引：[before196_native_phase_review/final_review.json](../../au111_five_sessions_20261102/evidence/session_01/before196_native_phase_review/final_review.json)，SHA `5c05f387ffdd25219bd525ee59adce3e114e10728e3909cfc7785248479a114b`；尾段详表[post54_supplement.json](../../au111_five_sessions_20261102/evidence/session_01/before196_native_phase_review/post54_supplement.json)。旧41块review只有6.61s post，作为历史保留，不能再单独引用为最终后段。本次54块仍非长logger完整结束，不把675s样本总和当7200nominal整段已核实。

root的[A01单次候选决策](../../au111_five_sessions_20261102/evidence/session_01/authorization_decision_A01.json)选择 **−5V、20ms、Hold、准备1nA**，保持完整−1V/100pA DOWN修后图。理由是昨日−4V复合操作局部改善但未稳定恢复，今日196仍有功能缺陷；仅选择一个新候选，未自动梯度。本轮slot `session_01`承接 `continuing_20261101_1939` 的既有pulse1，因此候选为 **累计第2/6次**，不能因新批次/目录清零。该决策文件并不是pulse发送证据；准备、claim、ACK、恢复与后图各自等待实际记录。

实践中的未用项现已具体化：本候选选择当前扫描端点(−25,−25)nm，不额外建立远处移动路径，因此skill“其他位置调理再返回参照”未采用，保留局部样品变化混杂；这不是新的用户override。只有“完整图优先于短条带”属于本轮明确覆盖。没有修改skill或控制源码。


## S01 更新：A01准备、单次脉冲与返回已执行；完整后图仍在采集

本条仅据完成的动作文件与root交付的闭合原生块推进事实，不追改前述历史截面。**累计pulse为2/6（昨日1＋本轮A01一次）**；五个完整记录槽位不重置该episode预算。

|条款 / 阶段|本次采用与实际证据|未用、未触发或能力限制|
|---|---|---|
|先完整修前证据，再选一个调理候选|196完整图及54块分期已审；root明确选择−5V20ms，非脚本自动梯度|“先短条带”按用户要求未采用；未额外远处移动，保留局部变化混杂|
|准备电流与成像电流分域记录|[prepare_A01/outcome.json](../../au111_five_sessions_20261102/evidence/session_01/prepare_A01/outcome.json)：08:36:41结束，11/11 Setpnt ACK，约95.794s，−1V、100pA→1nA；慢末段Z斜率−.421pm/s/RMS2.022pm|[准备原生快审](../../au111_five_sessions_20261102/evidence/session_01/prepare_A01/native_quick_review/review.json)：67–75闭块存在短峰−1.5852963nA，未见历史相同平顶；末10原生波动不等于慢Getter样点，未隐藏局部越带|
|一次绝对脉冲、Hold、已知结束再观察|[pulse_A01/pulse.claim](../../au111_five_sessions_20261102/evidence/session_01/pulse_A01/pulse.claim)于08:39:30.915570写唯一 `[1,.02,-5,1,2]`；等待ACK 08:39:30.947076；[outcome](../../au111_five_sessions_20261102/evidence/session_01/pulse_A01/outcome.json)为knownend＋30s观察|未知ACK、自动On、自动重发和Withdraw分支未触发；不以ACK推断修复成功|
|原生削顶与恢复需特殊记录|[原生脉冲审核](../../au111_five_sessions_20261102/evidence/session_01/pulse_A01/native_quick_review/review.json)，SHA `c0e23da1ad90124bf12ac7fa9cd4a7648b6329a23da52d5d3aba5f2d51a7f497`：−5平台39点且Z完全held；历史相同负平顶87点，其中回−1后48点；Z最大退让+4.418569nm，而慢终点+5.123pm|平顶按潜在记录删失/过载处理，真实峰/前放量程/电荷未知；2kHz是存储采样率，不证明模拟带宽。已知调理瞬态与扫描中未解释异常分开记录，但不消除其测量局限|
|恢复观察与实时波形不可互代|后20–30s原生I RMS95.607pA，前10s48.671pA；慢末段RMS24.573pA，两者均保留。[波形](../../au111_five_sessions_20261102/evidence/session_01/pulse_A01/native_quick_review/pulse_and_recovery.png)|慢带内并不等于逐点原生全带内或无瞬时异常；不能因此反推化学洁净|
|显式返回成像电流|[return_A01/outcome.json](../../au111_five_sessions_20261102/evidence/session_01/return_A01/outcome.json)：08:45:09结束，11/11 ACK，96.620s，恢复100pA；慢末5s带内，末10 Z斜率−.169pm/s/RMS4.627pm|原生return完整分期审查待补；返回是显式独立阶段，不是未知失败后的自动回滚|
|完整修后与独立复核|root已开始 `after_A01_full`；本条写入时尚未获得完整修后结论|L2/L3及成功cycle未定；不把正在扫描或局部截图计作完整后图/成功轮次。L4仍无独立化学证据|

7200nominal长logger仍持续，已闭前缀可逐段核验，但完整实际时长/全部阶段无采集空档仍待停止后归档。未更改Skill或控制代码；这里记录已采用条款、未用短条带/远处调理，以及未触发的异常分支和真实前放能力缺口。

### S01 补充：返回原生、完整修后197与元数据溯源

- [return原生分期](../../au111_five_sessions_20261102/evidence/session_01/return_A01/native_phase_review/review.json)，SHA `2a922b873986621fc32d06d0ab43fb309bd85f33280a6a460e59921d72303a1f`：11个writer/ACK及精确readback核验；第一目标931.3226pA，最终100pA。最终30s原生I均−117.925/RMS13.618pA，无≥400pA；末5s4458/10000原生点在−120..−80pA外，慢Getter通过仍单独保留。这是采样测试的区别，未事后修改准入门槛。
- 完整修后197已于08:52:43.605711结束，约438.754s；[after197原生分期](../../au111_five_sessions_20261102/evidence/session_01/after197_native_phase_review/review.json)，SHA `cac047d03d85429243b887e37c5be6912d3c96a7b3e78574c2eaed86bdd1d11b`：scan核心437.99s，最负−9.984670nA，下一点Z跃升162.55pm；无历史相同平顶，但该近floor短峰不能排除未标定模拟链过载。post64.59s无≥400pA，末30s均−99.873/RMS3.621pA、全±20%内，Z去趋势RMS2.380pm。此处未把“没有完全相同平顶”提升成“真实无过流/无模拟饱和”。
- 图像与原生分别判断；197完整原始图与匹配图像标准由root/imageagent审查。本日志不由局部图观感代替独立复核，不提前给L3、化学L4或成功cycle。需要无额外调理复扫的条款仍等待实际证据，不自动视为已触发/完成。
- [source路径字段对账](../../au111_five_sessions_20261102/evidence/session_01/metadata_source_path_reconciliation.json)记录prepare/pulse/return manifest的`source`路径继承了scanner名，而`source_sha256`确实分别匹配实际setpoint/pulse入口；保留原manifest与原始wire，不改控制源码或把元数据错指当硬件失败。该记录是待提炼的溯源教训，不修改Skill。

### S01 更新：完整无调理复扫198与扫描期软件下限事件

[confirm_A01_full/outcome.json](../../au111_five_sessions_20261102/evidence/session_01/confirm_A01_full/outcome.json)确认198于09:03:09.876结束，约438.799s；196→197调理后再做198，中间未新增pulse/shaper。完整复扫条款已实际采用，不能仅由“完成两帧”认定任务可用。

[198最终原生索引](../../au111_five_sessions_20261102/evidence/session_01/confirm198_native_phase_review/final_review_index.json)保留scan核心438.19s及post63.42s。扫描内有两个相隔5.482s的分离事件，各1个−9.9994768nA样点；随后[09:06:31只读软件范围](../../au111_five_sessions_20261102/evidence/read_012_signal_currentrange/snapshot.json)给 `Signals.RangeGet[0]` 下限−9.999476802136087nA，按DAT精度完全一致。已独立核验8命令/32原始wire文件，见[范围对账](../../au111_five_sessions_20261102/evidence/session_01/confirm198_native_phase_review/software_range_reconciliation.json)。这把“与历史floor相同”进一步落实为“达到软件记录下限”；**物理前放型号、真实量程/带宽/更快峰仍未确定**，不把软件信号标定等同完整硬件标定。

|条款|实践状态与原因|本轮证据与待提炼|
|---|---|---|
|扫描异常与调理期异常分别处理|已触发扫描期软件下限事件审查；root当时不发新的scan/conditioning，需结合实验解释|[两事件逐点图](../../au111_five_sessions_20261102/evidence/session_01/confirm198_native_phase_review/two_software_limit_events.png)。不能把已授权pulse期平顶自动扩展为扫描期允许；尚未给机制唯一解释|
|完整修后无额外调理复扫|已采用，198已完整结束；有更好post但未用它抹去scan事件|原生尾30s全100pA±20%、RMS3.147pA，Z去趋势RMS2.187pm；这是尾段恢复证据，非L3自动通过|
|事件记录的测量限制|已采用每点散点图、分离两事件、不推断真实峰宽|每事件只有1个精确限值样点；相邻近限值点/软件饱和和更快模拟过程需分清，不将2点串成1ms持续平台|
|策略切换/TipShaper|仅有离线候选及静态代码审查；本条证据截面没有该动作已执行的claim|未将代码审查通过充当实机动作准入；累计pulse仍2/6，未因候选或五session槽位重置|

以上仅补日志与离线审计；原Skill、控制源、原始wire/DAT、先前JSON均保持原样。采集尚未原生结束，整轮长记录完整性仍待最终闭合归档；本日志不把S01预填为成功，更不宣称五轮或十个闭环已达成。

## S01结束记录：完整尝试1/5，成功闭环0；采集有意提前结束

root的[联合判断](../../au111_five_sessions_20261102/evidence/session_01/A01_root_joint_verdict.json)将本轮计为**完整修针尝试1/5、成功闭环0**：196显著全宽横带经准备＋pulse＋返回后改善，并在无额外调理的198中保留；但仍有约10–22pm间歇跨背景偏置和局部对象边缘/尾迹，严格整帧任务标准未满足。L0命令执行、L1结状态响应、L2成像改善均supported；L3任务可用not_supported；L4化学状态unknown。这不是“完全无效”，也不是经证实化学脏针/洁净。

**实际序列：**完整196 → 11步100pA→1nA → 单次−5V20msHold（global ordinal2）→ 11步回100pA → 完整197 → 无新调理完整198。此次新增pulse1；同一episode累计pulse2/6，TipShaper实际执行0。结束本段并非脉冲预算耗尽或五轮目标完成。root保持后续硬件动作未激活，等待扫描期软件限值事件的实验解释与前放信息；原子/化学能力没有因此被臆测建立。

### 原生全过程归档与停止语义

[全229块最终审计](../../au111_five_sessions_20261102/evidence/session_01/final_native_record_review/review.json)，SHA `38996fb501acb9741827bf0559dccfe81775c394c69124c9e025e3c5bf6e4c67`：228块各25000行＋末块7660行，**5,707,660行/通道、34,245,960有限标量、0.5ms存储间隔、按样点2853.83s（47分33.83秒）**。全部文件SHA、字节、块序号、行数、6通道和采样头核验；未发现缺失/重复块。停止后的native elapsed为5707.6599998名义单位，其一半与样点时长一致。全段恰有89个软件下限匹配样点：已知pulse期87＋198扫描期2，其他区间0；非−1V Bias共41点且全部对应这一单次pulse。相同native Start、块序号/计数和阶段原始记录支持此次覆盖196、prepare、pulse、return、197和198；**文件/计数一致性不是逐样点硬件时钟证明，也不是模拟带宽或更快峰的保证**。

[有意停止对账](../../au111_five_sessions_20261102/evidence/session_01/final_native_record_review/intentional_stop_reconciliation.json)，SHA `eeaa13b05548f12fac72ea9515ab333316e51a406a39dc63601481431845b64a`：root在09:08:51.981附近向owned logger发一次SIGINT，logger只发一次DataLog.Stop并获零错误ACK，未发任何junction writer。原始outcome仍保留 `recorder_failed_no_retry / Recorder termination requested / native_stop_confirmed=false`，因为cleanup即时只读时停止尚待完成；不能事后覆盖成“自然成功”。随后read013和read014独立读回同一Start08:21:18、Stop09:08:52、末文件229/7660点，间隔约18s不变，证明该采集已结束并允许末块闭合归档。**这是一段有意提前结束的完整归档，不是7200nominal自然采满，也不是结故障诊断。**

最终原生尾30s I均−99.6785pA、RMS1.3511pA、范围−107.115..−92.191pA，全100pA±20%；Z slope−.02856pm/s、去线性RMS1.0993pm。最后[read014只读快照](../../au111_five_sessions_20261102/evidence/read_014_stop_confirm/snapshot.json)（09:09:19）为Bias−1V、setpoint100pA、I−99.67598pA、Z−101.983659nm、On/status2、Scan0、SafeTipOff，XY(−25,−25)nm，50×50nm/240²；这是最终保存读回，不延伸成永久live状态保证。

### 已读而未采用、未触发及仍有能力缺口（截至S01结束）

|条款 / 方法|最终实践状态|具体原因 / 本轮证据|待提炼，不改Skill|
|---|---|---|---|
|先短条带|未用，用户明确覆盖|用户要求完整修前/修后；196/197/198均50nm240²完整帧|完整图的信息收益和时间开销应单列；不能用条带替代完整轮次|
|远处调理再回参考|未用|实际在当前端点(−25,−25)nm，不另发移动；局部样品变化混杂保留|定位选择与因果局限分列，不能事后假装远离参考|
|Skill附带通用local-au111 init/validate/prepare入口|未用|实际由本机源码pin、session ledger、episode原子claim和root前瞻决策完成绑定；没有运行通用离线CLI的回执|记录本机ledger映射，不能冒称已通过未运行的工具|
|历史−4V20ms默认候选|未用于本次新增pulse|基于已有−4V部分改善但未恢复及196坏态，root单独选择−5V20ms；不是自动电压阶梯|记录单次理由与测得响应，不写成通用−5V安全/有效阈值|
|TipShaper及历史−1nm|未执行|只有离线900pm候选和静态审查；扫描期软件下限事件尚需解释；既有历史位移没有自动变为新动作|候选参数/代码审查与实际claim必须分开|
|未知ACK后现场核查/不重发|未触发|本轮prepare/pulse/return均已知ACK与结束；不伪造unknown事件|相同禁重放规则仍保留；成功ACK不等于质量成功|
|已知动作异常后的Withdraw/On等cleanup|未触发junction cleanup|没有实际Withdraw、AutoApproach、On或SafeTip切换；只结束owned DataLog|DataLog.Stop与junction停止/退针不能混称|
|两次连续无改善策略复核|未触发该计数门槛|本次仅新增1pulse且有L2改善；累计计数不清零|策略复核也不应因ACK而复位，更不能新建五目录绕6次上限|
|成功即停 / 预算耗尽|均未作为本次停止原因触发|L3不支持、累计2/6未耗尽；停止新动作是待解释扫描期软件限值事件|有限轮次结束、硬件状态、成功与失败/预算分别记|
|1kHz粗采集/Hi-Res/外部示波器替代|未用|实际本机原生2kHz；没有额外接线/触发/带宽验证|2kHz平台粗分段不代表快沿峰与模拟量程已知|
|物理前放带宽/量程/过载恢复|能力缺口仍在|软件Signals校准/范围已实际只读确认；不能代替物理型号、模拟带宽或恢复测量|软件记录触限与真实峰、前放过载机制分别记|
|实时横向漂移、独立化学表征|能力缺口/未用|只有保存XY读回和图像比较；无独立实时漂移或化学测量|不得由图像改善、Z变化或电流稳定推出化学clean|

值得保留的本轮实践差异是：①完整图覆盖短条带；②长记录应使用原生停止/末块对账，而不是只看helper成功字符串；③slow Getter带内可与原生局部出带同时发生；④软件范围只读可以落实记录削顶，但仍不提供真实电流峰上界；⑤有限复合调理可有明显L2改善却未达到L3。以上先记录，不修改Skill。S02–S05继续留为未执行，用户要求的五次记录任务未完成。


## R03 定位与前检增量（2026-11-03；不改未采用的 Skill 条款）

当前阶段是同区域诱导的准备与诊断，不是已经完成整形或修复。201/202 两张完整图支持有限的纳米对象/边缘辨识能力；局部形貌和动态条纹仍保留。目标 C2 与独立参照 C1/C3 分开；原用户蓝框截图没有可证明的精确像素映射。

| 方法/条款 | 实践状态 | 证据与待提炼问题 |
|---|---|---|
| 独立原生 I/Bias/Z +慢TCP检查 | 两者均实际使用 | 目标处慢读电流约100pA并不排除原生Z动态；前检TCP末10sZ RMS12.844pm，原生此前末10sRMS28.731pm。不同带宽与采样时刻的数值不得相互替代。 |
| 先恢复已知动作状态，不重发XY | 实际使用 | 唯一定位已到16.5/2.5nm；记录文件名碰撞导致后续观察失败，FolMe.Stop已知ACK。独立5s观察、一次SpeedSet原模式恢复、5s后检完成，没有再次XY。原失败记录不覆盖。 |
| 实机记录文件名唯一性 | 发现实现缺口并单独修复恢复入口 | 原observe函数两阶段都从motion_0000起名，被排他Store拒绝；恢复入口使用阶段+全局序号，并离线用真实排他Store测试。不能以旧仅Mock成功测试证明实机落盘流程完整。 |
| 900pm TipShaper候选 | 仅实际执行30s前检，配置/Start均未发 | 末10sTCPZ RMS12.844pm超本次冻结10pm门槛；未放宽门槛/重试/消耗一次Shaper Start。共享admission占用与实际发送次数分开。 |
| 完整图优先、图像判断功能 | 正在执行移动后完整诊断 | 事件after_localization_I01_full，非after-shaper/修后。新图用于判断参照与作用点，不能由Z波动单独假标坏针。 |
| 高电压脉冲升级/更深整形 | 本段未用 | 累计既有pulse3/6保持；没有新脉冲或更深整形。旧候选/Skill未采用部分不改。 |
| 全过程因果记录 | 实际保留混杂 | 202后包含定位、known Stop、速度模式恢复和长时间等待；未来比较不能称“纯TipShaper效果”。 |

证据入口：[移动失败及Stop](session_02/move_induction_I01/outcome.json)、[独立速度恢复](session_02/move_induction_I01_recovery_01/outcome.json)、[原生审查](continuation_slow_20261102/speed_recovery_R03_I01_native_review/review.json)、[前检拒绝](../omitted-evidence.md#archive-6a2c1da75cbfab1d)。截至此截面，完整历史尝试1/5、严格成功0、剩余4未完成；不能把恢复隧穿或拒绝下探计为修针。

## R03 203→204：无调理的功能恢复（2026-11-03）

204完整正反扫中，固定C1/C3参照重新可辨，C2/D4也恢复辨识，局部下半部横线仍在。无新Pulse或TipShaper，不记修针成功，亦不沿用203坏态启动repair A02。单独准备诱导P01，实际是否变坏待完整扫描。原±20%扫描入场规则曾拒绝未启动，另经前瞻工程审查仅放宽诊断扫描入口，当前35个连续样点5.07s通过；400pA运行中规则及清理不变，调理门槛未改。10pm Z门槛在I01未通过的记录仍保留，不改成物理损伤阈值或自动放宽。未实施策略继续只记录，不修改Skill正文。来源：continuation_slow_20261102/baseline204_root_functional_review.json、diagnostic_scan_entry_policy_review.json。

Step04应用：只在installed references/local-au111-protocol.md追加实际202/203/204状态变化和P01升流停止/六级减流恢复案例。主SKILL、profile、脚本及读过未用部分未变。新完整对照扫描仍进行中，不预判结果。见continuation_slow_20261102/skill_step04_application.json。

## 2026-11-03 A03：有坏态图但整形未发送

205 完整正反扫显示 C1/C3 固定参照轮廓/背景受长线遮扰，C2仍可辨；它是100→381pA准备、独立返回100pA和扫描这一复合过程之后的诊断图，没有计划的P01脉冲。单次−0.9nm/+2V抬升轨迹按修复目的另立A03，未把失败的可用态诱导准入强改为通过。

A03实际运行至30s前置观察：195个慢采样，末10.136s Z去趋势RMS13.733pm、斜率−0.103pm/s；电流−112.035±3.050pA，末29.805s满足原±20%电流带。原10pm工程门未过，3425请求头审计均只读，没有PropsSet/TipShaper.Start/Pulse/Withdraw；共享Start预算未消耗。原参数和旧失败保留，未加宽门槛或重放。

已将实测数值交实验员判断此波动是否属于本机正常状态。独立科学评估认为原10pm并非已证物理损伤边界，但15pm远小于900pm也不能证明接触安全；原生2kHz/30s与TCP末10s不可互换。候选PSD/50ms均值描述只用于诊断，不变成新保护或自动动作许可。

本次实际用到：完整图优先、失效任务范围、准备过程独立记账、一次动作前的读回和冻结条件、失败未执行与未知ACK区分。读过但仍未用到：P01 −5.7V脉冲平台、A03 TipShaper实际轨迹/恢复后成像、条件撤回、L3复扫判定及化学洁净证据；这些部分未修改。Skill主文件/profile/scripts未变，Step04是当前已安装的最新观察补注。

证据：[A03无动作审查](continuation_slow_20261102/A03_no_action_review.md)、[205诊断报告](continuation_slow_20261102/REPORT205_current_only.md)、[门槛科学草案](continuation_slow_20261102/A03_observation_gate_scientific_draft.json)。计数仍1/5完整尝试、0严格成功、余4，脉冲3/6。
