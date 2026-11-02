# Au(111) 专家脉冲建议：一手证据核对

检索日期：2026-10-31。范围仅公开原始论文、作者学位论文和作者官方程序说明；没有连接仪器、SMB 或 GUI，没有选定或执行新动作。本文件是证据输入，不是已验证的硬件操作规范。

## 结论

可访问的一手资料支持“几伏电压脉冲能够改变金相关针尖/表面，且准备间隙、脉冲时长和反馈状态影响结果”。**没有找到直接核实本地规程全部准备条件与波形组合的通用配方。** 用户给出的范围集中在 [本地规程](local-au111-protocol.md)，是本机/实验室经验与待检验假说；没有找到整套论文，不表示该经验错误。

最重要的迁移陷阱是电压符号：文献的“负针尖电压”可能等价于本机“正样品电压”。不能凭论文写了−5 V或本机电流为负，就认定两者电场方向相同。

## 可核验的原始操作数值

| 原始研究及定位 | 实际给出的参数/结果 | 极性、反馈及不能迁移之处 |
|---|---|---|
| Jung et al., *Fabrication of Gate-tunable Graphene Devices…*, JoVE 2015，§7.2，DOI 10.3791/52711 | 在Au(111)上用 **10 V tip pulses**，以看见herringbone重构作为该步骤终点。 | 该条未给脉冲时长、脉冲前电流或保持Z设置；不能补写为−10 V、100 ms、1 nA。它支持高电压调针实践，不验证本机−4…−7 V范围。[全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC4544993/) |
| Hamidi et al., *In air STM observation of Au(111) surface disturbance including Au magic fingers as modified by solvent choice*, Surface Science，§3.1/Fig.2，DOI 10.1016/j.susc.2024.122629 | **5–9 V**脉冲；Fig.2为**5 V**后图像变清晰并出现材料沉积迹象。实验为室温空气、溶剂处理Au(111)、Pt0.8Ir0.2针；常规扫描 **sample−0.100 V、70 pA**。 | 原文把材料从针尖排出作为解释；不能据此认定本机材料或方向。可见段落没有核实pulse duration、hold和脉冲准备电流；常规70 pA不能自动当准备值。空气/吸附物环境不能当2.9 K UHV行为。[出版商原文及图注](https://www.sciencedirect.com/science/article/pii/S0039602824001808) |
| Cho, UC Berkeley博士论文2010，*Exploring Self-Assembly and Photomechanical Switching Properties of Molecules at Surfaces*，§5.4，正文pp.37–38/PDF pp.48–49 | Au(111)/azobenzene，**50 K**；**tip−6 V、1 μs**制作分子锚点，所述阈值约**tip−4 V、1 μs**；前后图也有轻微针尖变化。 | 是**微秒，不是毫秒**；终点是分子锚定/表面改变，不是清针成功。该段未给对应脉冲准备电流、hold，不能从另一STS章节借用。属于作者原始实验，不是同条件清针配方。[作者论文](https://escholarship.org/content/qt0q10c1m9/qt0q10c1m9.pdf) |
| Park & Phaneuf, *Polarity dependence in pulsed scanning tunneling microscopy fabrication and modification of metal nanodots on silicon*, JAP 92,2139–2143 (2002)，§II–III/Figs.1,3，DOI 10.1063/1.1495889 | **Au-coated W tip / Si(100)**；准备 **sample+2 V、3 nA**；关反馈后施加0.1–100 ms脉冲。示例**effective tip−5 V、1 ms**生成Au点；**tip−8 V、100 ms**也制点。固定前放增益使脉冲电流饱和，作者明确报告。 | 实际硬件给**样品**加脉冲、针尖接地，但文中采用**相反符号的等效针尖电压**！因此tip−5 V对应sample+5 V。基底是Si而不是Au，半导体掺杂也影响所需时间。文献的饱和记录不是本机容许过载认证。[原论文全文](https://www.researchgate.net/publication/228709367_Polarity_dependence_in_pulsed_scanning_tunneling_microscopy_fabrication_and_modification_of_metal_nanodots_on_silicon)；[作者机构书目](https://pure.kaist.ac.kr/en/publications/polarity-dependence-in-pulsed-scanning-tunneling-microscopy-fabri/) |
| Méndez et al., *Diffusion of atoms on Au(111) by the electric field gradient in scanning tunneling microscopy*, JVST B14,1145–1148 (1996)，DOI 10.1116/1.588417 | UHV干净Au(111)，**2.5 V、30 s**例子；升电压时**保持恒电流**，产生突起/团簇；作者未观察到该过程的符号依赖。 | 这是反馈参与、秒级电场诱导表面扩散，不能当HoldZ毫秒清针的证据。它反而说明出现新凸起不必然是针尖掉原子，也不存在对所有Au过程统一的负极性规则。[原论文全文](https://www.researchgate.net/publication/224466922_Diffusion_of_atoms_on_Au111_by_the_electric_field_gradient_in_scanning_tunneling_microscopy) |

对Wang等2021 *Automated Tip Conditioning for Scanning Tunneling Spectroscopy* 的核对：其Au(111)自动流程核心是**poke与STS功能判别**；作者程序说明给2 nm、1 nm/s的ZRamp示例，并没有给出本任务的负高压毫秒脉冲配方。不能把论文中常规0.05 V/20 pA成像或STS参数当作负脉冲准备条件。[作者官方代码与论文链接](https://github.com/Kaiden713/autotipwork_release)

## 对本地建议的适用性

经验配方的数值只在 [本地规程](local-au111-protocol.md) 维护；本表的文献数字是各原实验的参数，不能当作本机授权或允许范围。

- 准备电流改变工作间隙，精确距离仍需适用当前针态的独立证据；准备电流不是脉冲平台电流。
- Hold 避免控制器主动为维持设流而调 Z，仍不保证真实原子间隙不变，也不能把反馈积分时间当闭环带宽。
- 平台电流、Z 工作点和新凸起属于响应线索；削顶电流不是清针目标、真实峰值或接触证明。
- 毫秒、微秒、秒级过程不可互换；空气/吸附环境不能直接迁移到低温 UHV。这里未找到整套条件的通用成功阈值。

## 图像参照与远处调理补充（2026-11-01 核查）

Tewari et al., *Robust procedure for creating and characterizing the atomic structure of scanning tunneling microscope tips*, 2017，DOI 10.3762/bjnano.8.238。在 Au 表面以孤立 adatom 观察有效尖端响应，远离参照进行机械调理后返回；同时使用接触电导轨迹。该设计支持“保留固定参照、在其他位置调理、再看成像响应”的方法，不证明任意未知对象都是对称参照，也不能将接触电导剂量照搬到当前量程。[原文](https://beilstein-journals.org/bjnano/articles/8/238)

压电厂商 PI 的位移说明解释了电压变化后随时间继续变化的位移。它支持记录等待时间与漂移，而没有提供本机的固定稳定秒数或电流保护阈值。[原厂说明](https://www.pi-usa.us/en/products/piezo-flexure-nanopositioners/piezo-motion-control-tutorial/tutorial-4-20)

## 可以沉淀到skill的科学规则

1. 参数记录同时写“控制器Bias值”和已知的电极参考；物理接线未核验时保留未知，不擅自反号。用户本机经验与论文参数分列，不以文章数值代替实际仪器能力。
2. 把准备电流、准备偏压、hold状态、目标绝对脉冲电压、时长、边沿、实际原生样点、恢复状态分别记录。多变量一起变化是一次组合协议，不称单变量机制验证。
3. 保存脉冲前后同工作点图像；修复以可复核的成像功能改善为终点，不能以大电流、Z跃变或表面新点代替。允许真实局部材料变化，不要求所有像素一样。
4. 脉冲前/边沿/平台/恢复各段分别分析；电容/前放瞬态可能污染边沿。削顶段记censored，2 kHz采样值不是真实高速峰的上界，不能由被削顶I积分宣称实际能量。
5. 一次有限候选后回到评估；不因−4 V无效就自动升到−7 V。用户授权的范围、仪器真实量程/恢复表现与本次事前冻结候选各自记录。

## 访问与证据质量说明

文献核查使用原始研究，压电行为补充使用厂商资料；搜索到的实验室wiki、通用综述、搜索摘要式“配方”未作为一手验证。Park/Méndez论文全文通过ResearchGate可读页面读取，并以原期刊DOI/可得的作者机构书目信息核对；Hamidi出版商直接open一度403，但其原文Methods和Fig.2由同一出版商索引返回。未能核验的准备电流、hold、时长均明确留空。全文没有将文献给出的电流饱和或电压数值称为本机安全上限。
