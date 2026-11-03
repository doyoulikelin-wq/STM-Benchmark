"""Reproduce P02 native pulse and independent recovery from local SHA-verified DAT."""
import json
from pathlib import Path
from review_native_phases import h,np,DT,BLOCK,require
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
HERE=Path(__file__).resolve().parent
PINS={'P02_native_recovery_through364.json':'cd9989c147e4a8b2f80bc6caf3e9efd8dde6963ba0383c55e945cf607235c5d3',
      'P02_independent30_native_review.json':'1b78bdc0b6d175cea1072049d0e0990eaca011f99b9e80ce5a161bd94231bfbe',
      'P02_actual_pulse_and_native_recovery.json':'73cbdb9462f24c764da42b7ad77203f653db7bbd012d8fd6447b40e2ecf598c4',
      'P02_status_transition_review.json':'01a1298e7cffbf68826bb3b03b6c5aa8cebc7b55f64ff9c3898ec67a1db26c1a'}
docs={};refs={}
for name,digest in PINS.items():
    docs[name],refs[name]=h.read_json(HERE/name)
    require(refs[name]['sha256']==digest,'Frozen source changed')
j=docs['P02_native_recovery_through364.json'];recovery=docs['P02_independent30_native_review.json']
arrays=[]
for e in j['native_blocks']:
    p=h.local(e['path']);raw=p.read_bytes();require(h.sha(raw)==e['sha256'],'Native block changed')
    arrays.append(h.parse_block(raw,e['rows']))
a=np.concatenate(arrays);base=(int(Path(j['native_blocks'][0]['path']).stem[-5:])-1)*BLOCK
pulse=j['bias_below_minus4V_within_Start_outer'];require(len(pulse)==1,'Pulse threshold segments changed')
start,end=pulse[0]['zero_based_sample_half_open'];require(end-start==40,'Observed pulse width changed')
first=j['phases']['pre30s_start_edge']['zero_based_sample_half_open'][0]
last=j['phases']['post_ACK_through_available_closed_data']['zero_based_sample_half_open'][1]
z0=j['phases']['pre30s_inner']['samples']['Z_nm']['median']
post_z=j['phases']['post_ACK_through_available_closed_data']['Z_relative_pre_inner_median_nm']['median']*1000
early_z=docs['P02_actual_pulse_and_native_recovery.json']['phases']['post_ACK_through_available_closed_data']['Z_relative_pre_inner_median_nm']['median']*1000
rlo,rhi=recovery['native_inner']['zero_based_sample_half_open']
data=np.c_[a[:,0]/1000,a[:,1],(a[:,2]-z0)*1000]
font='/System/Library/Fonts/Hiragino Sans GB.ttc';matplotlib.font_manager.fontManager.addfont(font)
plt.rcParams.update({'font.family':FontProperties(fname=font).get_name(),'axes.unicode_minus':False,'font.size':10,
                    'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
fig,axes=plt.subplots(3,2,figsize=(12.8,9.4),dpi=160,gridspec_kw={'width_ratios':[1.55,1]})
fig.subplots_adjust(left=.08,right=.975,bottom=.225,top=.81,hspace=.34,wspace=.22)
fig.text(.08,.953,'P02  |  20 ms 脉冲与独立恢复观察',fontsize=22,weight='bold',color='#152c3a')
fig.text(.08,.91,'1 nA 起点    ·    -5.7 V / 20 ms / Z hold    ·    2 kHz 存盘    ·    单次已知等待 ACK',fontsize=11,color='#344b5a')
fig.text(.08,.87,'原程序在 ACK 后状态检查失败，原 post30 缺失。后续独立只读 30 s 已完成。',fontsize=10.6,color='#9b532c')
fig.text(.08,.835,'动作前后（每 100 ms 极值及中位数）',fontsize=11,weight='bold')
fig.text(.632,.835,'脉冲放大（全部 0.5 ms 原生点）',fontsize=11,weight='bold')
provenance={'sources':refs,'plot_origin_native_s':start*DT,'Z_reference_pre_inner_median_nm':z0,
            'source_native_blocks':j['native_blocks'],'binning':[], 'original_failed_pulse_preserved':True}
for col,(lo,hi,width,scale) in enumerate(((first,last,200,1),(start-10,start+100,1,1000))):
    v=data[lo-base:hi-base];rows=[]
    for off in range(0,len(v),width):
        chunk=v[off:off+width]
        center=off if width==1 else off+len(chunk)/2
        rows.append(((lo+center-start)*DT*scale,chunk.min(axis=0),np.median(chunk,axis=0),chunk.max(axis=0)))
    x=np.array([r[0] for r in rows]);mins=np.array([r[1] for r in rows]);med=np.array([r[2] for r in rows]);maxs=np.array([r[3] for r in rows])
    provenance['binning'].append({'samples_per_bin':width,'native_sample_half_open':[lo,hi],'all_samples_included':len(v)})
    for row,(label,color) in enumerate((('电流 (nA)','#206e89'),('偏压 (V)','#665294'),('相对 Z (pm)','#246d55'))):
        ax=axes[row,col];ax.vlines(x,mins[:,row],maxs[:,row],color=color,alpha=.55,lw=.8,zorder=2)
        ax.plot(x,med[:,row],color=color,lw=1.,marker='.' if col else None,markersize=2.8)
        if col==0:ax.set_ylabel(label,labelpad=8)
        ax.grid(axis='y',color='#dae2e7',lw=.6);ax.set_axisbelow(True)
        ax.set_xlim((lo-start)*DT*scale,(hi-start)*DT*scale);ax.tick_params(labelsize=9)
        if col==0:
            ax.axvline(0,color='#bd8043',lw=.7,alpha=.3,zorder=0)
            ax.axvspan((rlo-start)*DT,(rhi-start)*DT,color='#77bb9e',alpha=.18,zorder=-1)
            ax.set_xticks([-30,0,30,60,90,120,150,180])
        else:
            ax.axvspan(0,(end-start)*DT*scale,color='#f1d7a4',alpha=.35,zorder=-1)
            ax.set_xticks([0,10,20,30,40,50])
        if row==0:
            ax.set_ylim(-10.8,3.1);ax.set_yticks([-10,-5,-1,2]);ax.axhline(-1,color='#71808b',ls='--',lw=.7)
            ax.axhline(-9.9994768,color='#b26b3e',ls=':',lw=.8)
        elif row==1:
            ax.set_ylim(-6.1,-.6);ax.set_yticks([-5.7,-3,-1])
        else:
            ax.set_ylim(-203,18);ax.set_yticks([-200,-100,0]);ax.axhline(0,color='#87969f',ls=':',lw=.7)
            ax.axhline(post_z,color='#87969f',ls=':',lw=.7)
        if row==2:ax.set_xlabel('相对原生 Bias<-4 V 首点的时间 ('+('s' if col==0 else 'ms')+')',labelpad=5)
axes[0,0].text(.48,.08,'绿色区间  ·  后续独立观察内部窗',transform=axes[0,0].transAxes,fontsize=9,color='#255b45')
axes[0,1].text(.43,.1,'最小 -9.463 nA\n存盘未触及量程边缘',transform=axes[0,1].transAxes,fontsize=9,color='#206e89',bbox={'facecolor':'white','alpha':.86,'edgecolor':'none','pad':2})
axes[1,1].text(.44,.12,'Bias<-4 V 共 40 点 / 20 ms',transform=axes[1,1].transAxes,fontsize=8.8,color='#665294')
axes[2,1].text(.04,.52,'40 点期间 Z 跨度 0.04 pm',transform=axes[2,1].transAxes,fontsize=9,color='#246d55')
axes[2,0].text(.29,.42,f'后续 186.26 s 中位 {post_z:.1f} pm',transform=axes[2,0].transAxes,fontsize=9,color='#246d55',bbox={'facecolor':'white','alpha':.86,'edgecolor':'none','pad':2})
fig.text(.08,.142,'TCP 异步读回    ACK +3.94 ms 读到 Status 3（onHold），+116.33 ms 读到 Status 2。',fontsize=9.5,color='#344b5a')
fig.text(.08,.112,'原生计数给出请求至 ACK 外包窗 4363.21–4363.74 s。状态读回与原生电压边沿存在时序不确定性。',fontsize=9.1,color='#344b5a')
fig.text(.08,.082,'100 ms 分箱保留全部极值。绿色内部窗 29.12 s，来自独立完整 30 s 观察，两端为异步采样边界。',fontsize=9.1,color='#344b5a')
fig.text(.08,.052,f'Z 以脉冲前内部窗中位为零。最初 23.76 s 中位 {early_z:.1f} pm，后续全窗 {post_z:.1f} pm。物理机制仍待判定。',fontsize=9.1,color='#344b5a')
fig.text(.08,.022,'数据截于原生 4550 s，原程序失败状态与后续独立恢复记录分别保留。虚线 -1 nA 为设定电流参考。',fontsize=9.1,color='#344b5a')
out=HERE/'P02_native_waveform.png';fig.savefig(out);plt.close(fig)
provenance['image']={'path':str(out),'sha256':h.sha(out.read_bytes())};provenance['script_sha256']=h.sha(Path(__file__).read_bytes())
(HERE/'P02_native_waveform_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
print(out,provenance['image']['sha256'])
