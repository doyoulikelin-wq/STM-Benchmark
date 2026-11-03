"""Reproducible local-only S01 partial-exposure and commanded-withdrawal figure."""
import json,hashlib
from pathlib import Path
import review_native_phases as m
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
D=Path(__file__).resolve().parent
assert hashlib.sha256((D/'review_native_phases.py').read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
receipt,rref=m.h.read_json(D/'S01_induction_interrupted_through239_native_receipt.json')
assert rref['sha256']=='41428c3fced0cc804b2e144e7c032b2620fc39b62282f98f3a8ac496e8bd9ff7'
audit,aref=m.h.read_json(D/'S01_induction_trigger_stop_withdraw_native_review.json')
assert aref['sha256']=='6240cd17add6dbc3e8e8c4fbfada07e3144e3bf6cfdbc060f751656f02c813b1'
font=FontProperties(fname='/System/Library/Fonts/Hiragino Sans GB.ttc');plt.rcParams['axes.unicode_minus']=False
arrays=[];refs=[]
for index in range(230,240):
    name=f'{m.PREFIX}{index:05d}.dat';p=m.S/'native_R07'/name;raw=p.read_bytes();meta=receipt['files'][name]
    assert m.h.sha(raw)==meta['sha256'];arrays.append(m.h.parse_block(raw,25000));refs.append({'path':str(p),'sha256':meta['sha256']})
a=m.np.concatenate(arrays);base=229*25000;t=(base+m.np.arange(len(a)))*m.DT
fig,axes=plt.subplots(3,3,figsize=(16,8.2),gridspec_kw={'width_ratios':[1.25,1.1,1]})
windows=[(2874.93,2974.86),(2964.86,2974.86),(2974.5,2976.3)]
for col,(start,end) in enumerate(windows):
    choose=(t>=start)&(t<end);x=t[choose];v=a[choose]
    for row,ch,scale,label in [(0,0,.001,'Current / nA'),(1,1,1,'Bias / V'),(2,2,1,'Z / nm')]:
        ax=axes[row,col];y=v[:,ch]*scale
        if col<2:
            step=100 if col==0 else 10
            bins=[slice(k,min(k+step,len(y))) for k in range(0,len(y),step)]
            xb=[x[z].mean() for z in bins];low=[y[z].min() for z in bins];high=[y[z].max() for z in bins]
            ax.fill_between(xb,low,high,color='#5489b6',alpha=.45)
            ax.plot(xb,[m.np.median(y[z]) for z in bins],color='#163e65',lw=.65)
        else:
            ax.plot(x,y,color='#163e65',lw=.65)
            ax.axvspan(2974.86,2975.39,color='#e6ab45',alpha=.25)
            ax.axvspan(2975.39,2975.94,color='#a6c6ab',alpha=.3)
            ax.axvline(2975.512,color='#32774c',lw=.9,ls='--')
        ax.set_xlim(start,end);ax.set_ylabel(label);ax.grid(alpha=.18)
        if row==0:
            ax.axhline(-.4,color='#b84f45',lw=.8,ls='--')
            ax.set_ylim((-8.1,.35) if col==0 else (-2.1,.2))
        if row==1:ax.set_ylim(-1.01,-.99)
        if row==2:
            if col<2:ax.set_ylim(-106.6,-102.3)
            ax.set_xlabel('Native sample time / s')
titles=['实际曝光核心 99.93 s\n50 ms 分箱保留每箱极值与中位数','触发计数边界之前完整 10 s\n5 ms 分箱，峰为 -1.888 nA','中止过程全部 0.5 ms 存盘点\n黄色为 Stop 边界，绿色为 Withdraw 边界']
for ax,title in zip(axes[0],titles):ax.set_title(title,fontproperties=font,fontsize=10)
axes[0,0].annotate('-7.568 nA',(2934.627,-7.5678),xytext=(2910,-6.5),arrowprops={'arrowstyle':'-','color':'#555'},fontsize=9)
fig.suptitle('S01 诱导曝光未完成　200 pA、扫描速度加倍、配置时间常数加倍',fontproperties=font,fontsize=15,y=.985)
fig.text(.055,.064,'TCP 慢读触发为 -431.027 pA。已知 Stop 后读到 -263.326 pA，未进入原恢复电流带，随后已知 Withdraw。',fontproperties=font,fontsize=10)
fig.text(.055,.039,'绿虚线为首次原生 Home 样点。其电流尚为 -454.28 pA。后续完整 Home 窗口电流近零，不能称为恢复隧穿。',fontproperties=font,fontsize=10)
fig.text(.055,.014,'红虚线为 400 pA 慢读软件门槛。分箱保留尖峰，但不是瞬时硬件保护或真实模拟峰值。此图不证明已诱导坏针。',fontproperties=font,fontsize=10)
fig.subplots_adjust(left=.06,right=.985,bottom=.145,top=.855,wspace=.28,hspace=.26)
p=D/'S01_interrupted_native_waveform.png';assert not p.exists();fig.savefig(p,dpi=170);plt.close(fig)
provenance={'script_sha256':m.h.sha(Path(__file__).read_bytes()),'receipt':rref,'trigger_audit':aref,'native_blocks':refs,
            'windows_native_s':windows,'bin_ms':[50,5,None],'right_every_stored_point_ms':.5,'partial_bins_kept':True,
            'png_sha256':m.h.sha(p.read_bytes()),'meaning':'Incomplete exposure and separately known Stop/Withdraw. Not a completed before/after image or chemical conclusion.'}
q=D/'S01_interrupted_native_waveform_provenance.json'
with q.open('x') as f:json.dump(provenance,f,indent=2);f.write('\n')
print(p,m.h.sha(p.read_bytes()))
