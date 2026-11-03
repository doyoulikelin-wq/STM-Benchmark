"""Offline P03 native waveform. Recheck every archived byte before rendering."""
import json
from pathlib import Path
from review_native_phases import h,np,DT,BLOCK,require
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
D=Path(__file__).resolve().parent
j,jref=h.read_json(D/'P03_native_pre_pulse_post.json')
p,pref=h.read_json(D/'P03_pulse_postroll.json')
t,tref=h.read_json(D/'P03_pulse_transition_timeline.json')
require(jref['sha256']=='e1b1f6e9df22a76bb7c5d9b65a7cf1631fc243c749c6dadb3924ef85968d3418','Pulse audit changed')
require(pref['sha256']=='8e14f1430c399a6eb65efc319e044ee902d1f0a600d85fe78949b15ec12da255','Postroll audit changed')
require(tref['sha256']=='7d0a337aa81dee5e668b21ffc8fe9c0b53623500dcb00d6f3a587342dce24316','Transition audit changed')
blocks={v['path']:v['sha256'] for v in j['native_blocks']+p['native_blocks']}
arrays=[]
for name,digest in sorted(blocks.items()):
    raw=h.local(name).read_bytes();require(h.sha(raw)==digest,'Native bytes changed');arrays.append(h.parse_block(raw,BLOCK))
a=np.concatenate(arrays);base=(int(Path(sorted(blocks)[0]).stem[-5:])-1)*BLOCK
pulse=j['bias_below_minus4V_within_Start_outer'][0];start,end=pulse['zero_based_sample_half_open']
first=j['phases']['pre30s_start_edge']['zero_based_sample_half_open'][0];last=p['post_after_known_complete']['zero_based_sample_half_open'][1]
z0=j['phases']['pre30s_inner']['samples']['Z_nm']['median'];data=np.c_[a[:,0]/1000,a[:,1],a[:,2]-z0]
post=j['phases']['post30s_inner'];postlo,posthi=post['zero_based_sample_half_open']
font='/System/Library/Fonts/Hiragino Sans GB.ttc';matplotlib.font_manager.fontManager.addfont(font)
plt.rcParams.update({'font.family':FontProperties(fname=font).get_name(),'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
fig,axes=plt.subplots(3,2,figsize=(12.8,9.0),dpi=160,gridspec_kw={'width_ratios':[1.55,1]})
fig.subplots_adjust(left=.08,right=.975,bottom=.22,top=.81,hspace=.34,wspace=.22)
fig.text(.08,.95,'P03  |  20 ms 脉冲、量程下限与恢复',fontsize=22,weight='bold',color='#152c3a')
fig.text(.08,.91,'1 nA 起点    ·    -6.0 V / 20 ms / Z hold    ·    第 5 次脉冲    ·    2 kHz 存盘',fontsize=11,color='#344b5a')
fig.text(.08,.87,'等待 ACK 已知，原程序 post30 完成。首次完整读回已为 On2，本次没有进入 Hold 等待分支。',fontsize=10.2,color='#344b5a')
fig.text(.08,.835,'动作前后（每 50 ms 极值及中位数）',fontsize=11,weight='bold')
fig.text(.632,.835,'脉冲及早期恢复（全部 0.5 ms 原生点）',fontsize=11,weight='bold')
provenance={'sources':[jref,pref,tref],'native_blocks':[{'path':n,'sha256':x} for n,x in sorted(blocks.items())],'plot_origin_native_s':start*DT,'Z_reference_pre_inner_median_nm':z0,'binning':[]}
for col,(lo,hi,width,scale) in enumerate(((first,last,100,1),(start-10,start+200,1,1000))):
    v=data[lo-base:hi-base];rows=[]
    for off in range(0,len(v),width):
        chunk=v[off:off+width];center=off if width==1 else off+len(chunk)/2
        rows.append(((lo+center-start)*DT*scale,chunk.min(axis=0),np.median(chunk,axis=0),chunk.max(axis=0)))
    x=np.array([r[0] for r in rows]);mins=np.array([r[1] for r in rows]);med=np.array([r[2] for r in rows]);maxs=np.array([r[3] for r in rows])
    provenance['binning'].append({'samples_per_bin':width,'native_sample_half_open':[lo,hi],'all_samples_included':len(v)})
    for row,(label,color) in enumerate((('电流 (nA)','#206e89'),('偏压 (V)','#665294'),('相对 Z (nm)','#246d55'))):
        ax=axes[row,col];ax.vlines(x,mins[:,row],maxs[:,row],color=color,alpha=.55,lw=.8,zorder=2);ax.plot(x,med[:,row],color=color,lw=1,marker='.' if col else None,markersize=2.5)
        if col==0:ax.set_ylabel(label,labelpad=8)
        ax.grid(axis='y',color='#dae2e7',lw=.6);ax.set_axisbelow(True);ax.set_xlim((lo-start)*DT*scale,(hi-start)*DT*scale);ax.tick_params(labelsize=9)
        if col==0:
            ax.axvline(0,color='#bd8043',lw=.7,alpha=.3,zorder=0);ax.axvspan((postlo-start)*DT,(posthi-start)*DT,color='#77bb9e',alpha=.18,zorder=-1);ax.set_xticks([-30,-20,-10,0,10,20,30,40,50])
        else:
            ax.axvspan(0,(end-start)*DT*scale,color='#f1d7a4',alpha=.35,zorder=-1);ax.set_xticks([0,20,40,60,80,100])
        if row==0:
            ax.set_ylim(-10.8,1.3);ax.set_yticks([-10,-5,-1,0]);ax.axhline(-1,color='#71808b',ls='--',lw=.7);ax.axhline(-9.9994768,color='#b26b3e',ls=':',lw=.8)
        elif row==1:
            ax.set_ylim(-6.4,-.5);ax.set_yticks([-6,-3,-1])
        else:
            ax.set_ylim(-.35,5.8);ax.set_yticks([0,2,4]);ax.axhline(0,color='#87969f',ls=':',lw=.7)
        if row==2:ax.set_xlabel('相对原生 Bias<-4 V 首点的时间 ('+('s' if col==0 else 'ms')+')',labelpad=5)
axes[0,0].text(.54,.16,'绿色区间  ·  原 post30 内部窗',transform=axes[0,0].transAxes,fontsize=9,color='#255b45')
axes[0,1].text(.51,.17,'96 点触及记录下限\n真实电流峰值未知',transform=axes[0,1].transAxes,fontsize=9,color='#8b4b25',bbox={'facecolor':'white','alpha':.87,'edgecolor':'none','pad':2})
axes[1,1].text(.39,.25,'Bias<-4 V 共 40 点 / 20 ms',transform=axes[1,1].transAxes,fontsize=9,color='#665294')
peak=t['native_Z_transient_peak'];axes[2,1].annotate('瞬态峰 +5.264 nm',xy=((peak['native_s']-start*DT)*1000,peak['Z_relative_pre_nm']),xytext=(55,4.5),fontsize=9,color='#246d55',arrowprops={'arrowstyle':'-','color':'#657a6a','lw':.7})
axes[2,0].text(.42,.32,'post30 工作点中位 -8.02 pm',transform=axes[2,0].transAxes,fontsize=9,color='#246d55')
fig.text(.08,.14,'40 点脉冲段 Z 跨度约 0.02 pm。精确记录下限持续 48 ms，其中包含 Bias 回到 -1 V 后的 28.5 ms。',fontsize=9.2,color='#344b5a')
fig.text(.08,.108,'原 post30 内部窗 29.27 s，随后已封存 21.3 s 均恢复至约 -1 nA。原生时序与顺序 TCP 状态读回分别记录。',fontsize=9.2,color='#344b5a')
fig.text(.08,.076,'Z 以动作前内部窗中位为零。瞬态抬升峰、恢复后工作点和接触深度是独立记录项，当前数据未给出接触深度。',fontsize=9.2,color='#344b5a')
fig.text(.08,.044,'电流受存盘量程删失，真实峰值与完整电荷未知。波形无法唯一分离放大器过载恢复、反馈与结的响应。',fontsize=9.2,color='#344b5a')
fig.text(.08,.012,'此次实际未执行 2 s Hold 等待分支，该分支目前仅通过离线模拟。图像功能效果仍待匹配完整后扫判断。',fontsize=9.2,color='#344b5a')
out=D/'P03_native_waveform.png';fig.savefig(out);plt.close(fig)
provenance['image']={'path':str(out),'sha256':h.sha(out.read_bytes())};provenance['source_sha256']=h.sha(Path(__file__).read_bytes())
(D/'P03_native_waveform_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');print(out,provenance['image']['sha256'])
