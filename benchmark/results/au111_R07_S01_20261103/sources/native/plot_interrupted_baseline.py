"""Local figure of the incomplete baseline's last scan window and known withdrawal."""
import json
from pathlib import Path
import review_native_phases as m
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
D=Path(__file__).resolve().parent
receipt,rref=m.h.read_json(D/'interrupted_baseline_native_receipt.json')
assert rref['sha256']=='88baff324142a7a1acd5f8a5f26afb47deaf8c1d10f465b5d2eced27698b46f4'
font=FontProperties(fname='/System/Library/Fonts/Hiragino Sans GB.ttc')
plt.rcParams['axes.unicode_minus']=False
arrays=[];refs=[]
for index in [26,27]:
 name=f'{m.PREFIX}{index:05d}.dat';p=m.S/'native_R07'/name;raw=p.read_bytes();meta=receipt['files'][name]
 assert m.h.sha(raw)==meta['sha256'];arrays.append(m.h.parse_block(raw,25000));refs.append({'path':str(p),'sha256':meta['sha256']})
a=m.np.concatenate(arrays);base=25*25000;t=(base+m.np.arange(len(a)))*m.DT
fig,axes=plt.subplots(3,2,figsize=(12,8),gridspec_kw={'width_ratios':[1.5,1]})
windows=[(313.76,323.76),(323.5,325.0)]
for column,(start,end) in enumerate(windows):
 selected=(t>=start)&(t<end);x=t[selected];values=a[selected]
 for row,channel,scale,label in [(0,0,.001,'Current / nA'),(1,1,1,'Bias / V'),(2,2,1,'Z / nm')]:
  ax=axes[row,column];y=values[:,channel]*scale
  if column==0:
   step=10;usable=len(y)//step*step;xb=x[:usable].reshape(-1,step).mean(axis=1);yb=y[:usable].reshape(-1,step)
   ax.fill_between(xb,yb.min(axis=1),yb.max(axis=1),color='#5489b6',alpha=.45)
   ax.plot(xb,m.np.median(yb,axis=1),color='#163e65',lw=.8)
  else:
   ax.plot(x,y,color='#163e65',lw=.65)
   ax.axvspan(323.76,324.30,color='#e6ab45',alpha=.25)
   ax.axvline(324.204,color='#399469',lw=.8,ls='--')
  ax.set_xlim(start,end);ax.set_ylabel(label);ax.grid(alpha=.2)
  if row==0:
   ax.axhline(-.4,color='#b84f45',lw=.8,ls='--');ax.set_ylim(-6.6,.35)
  if row==1:ax.set_ylim(-1.01,-.99)
  if row==2 and column==0:ax.set_ylim(-106,-97.5)
  if row==2:ax.set_xlabel('Native sample time / s')
axes[0,0].set_title('触发边界之前完整 10 s\n5 ms 分箱最小值、最大值和中位数',fontproperties=font,fontsize=11)
axes[0,1].set_title('中止过程全部 0.5 ms 存盘点\n黄色为共享计数边界，绿线为首次 Home 样点',fontproperties=font,fontsize=11)
axes[0,0].annotate('−6.014 nA',(323.685,-6.014),xytext=(319,-5.6),arrowprops={'arrowstyle':'-','color':'#555'},fontsize=9)
fig.suptitle('R07 基线未完成　多次短电流尖峰后已知 Stop 与 Withdraw',fontproperties=font,fontsize=15,y=.98)
fig.text(.07,.052,'TCP 触发电流为 −498.708 pA。触发、Stop 与 Withdraw 均落入 323.76–324.30 s 计数范围，无法逐点拆分先后。',fontproperties=font,fontsize=10)
fig.text(.07,.028,'红虚线是原 400 pA 慢读软件门槛。Z 到 +123.700 nm 对应已知退针。后续近零电流为 Off/Home 状态。',fontproperties=font,fontsize=10)
fig.subplots_adjust(left=.08,right=.98,bottom=.13,top=.87,wspace=.25,hspace=.25)
p=D/'interrupted_baseline_native_waveform.png';assert not p.exists();fig.savefig(p,dpi=170);plt.close(fig)
provenance={'script_sha256':m.h.sha(Path(__file__).read_bytes()),'receipt':rref,'native_blocks':refs,'windows_native_s':windows,'left_bin_ms':5,'right_every_stored_point_ms':.5,'png_sha256':m.h.sha(p.read_bytes()),'meaning':'Interrupted scan and commanded withdrawal. Counter interval overlaps all three host events. No complete-frame or chemical conclusion.'}
q=D/'interrupted_baseline_native_waveform_provenance.json'
with q.open('x') as f:json.dump(provenance,f,indent=2);f.write('\n')
print(p,m.h.sha(p.read_bytes()))
