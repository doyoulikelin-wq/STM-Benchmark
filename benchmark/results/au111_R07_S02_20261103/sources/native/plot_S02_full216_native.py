"""Reproducible local-only216 exposure and pre-return200pA recovery figure."""
from pathlib import Path
import hashlib
import json
import review_native_phases as m
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

D=Path(__file__).resolve().parent
assert hashlib.sha256((D/'review_native_phases.py').read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
receipt,rref=m.h.read_json(D/'S02_full216_post_through499_native_receipt.json')
assert rref['sha256']=='d3ec6807cef8c92e62a654e636af2a920d0a4da6badcf896d00fa06b09d145d0'
audit,aref=m.h.read_json(D/'S02_full216_native_review.json')
assert aref['sha256']=='e241a60e5005f07a3723cea15ff04b1e86e4d066718f2e5aea530be8ee0c7bb9'
event,eref=m.h.read_json(D/'S02_full216_events_and_rows.json')
assert eref['sha256']=='1333a1abfa32584ed00e577f5a38d4df97ecac43f6efac296c22b427ab2fbbf6'
font=FontProperties(fname='/System/Library/Fonts/Hiragino Sans GB.ttc');plt.rcParams['axes.unicode_minus']=False
arrays=[];refs=[]
for number in range(477,500):
    name=f'{m.PREFIX}{number:05d}.dat';path=m.S/'native_R07'/name;raw=path.read_bytes();meta=receipt['files'][name]
    assert m.h.sha(raw)==meta['sha256'] and len(raw)==meta['bytes']
    arrays.append(m.h.parse_block(raw,25000));refs.append({'path':str(path),'sha256':meta['sha256']})
a=m.np.concatenate(arrays);base=476*25000;t=(base+m.np.arange(len(a)))*m.DT
windows=[(5956.9,6175.5),(6074.05,6074.25),(6176.06,6237.5)]
fig,axes=plt.subplots(3,3,figsize=(16,8.3),gridspec_kw={'width_ratios':[1.25,1,1.2]})
for column,(start,end) in enumerate(windows):
    choose=(t>=start)&(t<end);x=t[choose];v=a[choose]
    for row,channel,scale,label in [(0,0,.001,'Current / nA'),(1,1,1,'Bias / V'),(2,2,1,'Z / nm')]:
        ax=axes[row,column];y=v[:,channel]*scale
        if column==1:
            ax.plot(x-6074.,y,color='#234f76',lw=.85)
            ax.axvspan(.138,.1785,color='#d39a91',alpha=.25)
            ax.set_xlim(.05,.25);ax.set_xticks([.05,.10,.15,.20,.25])
        else:
            bins=[slice(k,min(k+100,len(y))) for k in range(0,len(y),100)]
            xb=[x[z].mean() for z in bins]
            ax.fill_between(xb,[y[z].min() for z in bins],[y[z].max() for z in bins],color='#5388b3',alpha=.45)
            ax.plot(xb,[m.np.median(y[z]) for z in bins],color='#123f65',lw=.65)
            ax.set_xlim(start,end)
        ax.set_ylabel(label);ax.grid(alpha=.18)
        if row==0:
            ax.axhline(-.2,color='#397e52',ls=':',lw=.8)
            if column<2:
                ax.axhline(-5.,color='#b6624b',ls='--',lw=.8)
                ax.axhline(-9.9994768,color='#7b3f78',ls=':',lw=.9)
                ax.set_ylim(-10.5,.55)
            else:
                ax.axhspan(-.24,-.16,color='#6d9d6e',alpha=.10)
                ax.set_ylim(-.245,-.155)
        elif row==1:ax.set_ylim(-1.01,-.99)
        else:ax.set_xlabel('Native sample time - 6074 s' if column==1 else 'Native sample time / s')
titles=['完整扫描明确核心 218.60 s\n50 ms 分箱保留极值与中位数',
        '最长历史负量程边缘段 40.5 ms\n逐个 0.5 ms 存盘点',
        '结束外包之后 61.44 s\n200 pA 观察。后续返回尚未开始']
for ax,title in zip(axes[0],titles):ax.set_title(title,fontproperties=font,fontsize=10)
fig.suptitle('216 完整诱导曝光及其后电学恢复　200 pA、速度 2 倍、配置 T 为 2 倍',fontproperties=font,fontsize=15,y=.984)
fig.text(.055,.066,'扫描核心有 1856 个历史负量程边缘样点，共 52 组。累计 0.928 s。真实负峰值受删失，不能以存盘下限定量。',fontproperties=font,fontsize=10)
fig.text(.055,.040,'红虚线是 5 nA 慢读运行条件。更快原生样点可越过它。Start 外包另有 2 个边缘点，此处不混入核心计数。',fontproperties=font,fontsize=10)
fig.text(.055,.014,'结束后 61.44 s 无 ≥400 pA 样点且电流在 200 pA ±20% 内。坏态与成像质量须由恢复原参数后的完整图判断。',fontproperties=font,fontsize=10)
fig.subplots_adjust(left=.06,right=.985,bottom=.145,top=.855,wspace=.28,hspace=.27)
out=D/'S02_full216_native_waveform.png';assert not out.exists();fig.savefig(out,dpi=170);plt.close(fig)
provenance={'source_sha256':m.h.sha(Path(__file__).read_bytes()),'receipt':rref,'full_audit':aref,'event_audit':eref,
            'native_blocks':refs,'windows_native_seconds':windows,'bins_ms':[50,None,50],
            'middle_all_stored_points_ms':.5,'partial_bins_kept':True,'png_sha256':m.h.sha(out.read_bytes()),
            'meaning':'Known completed changed-setting216 exposure and200pA recovery before any subsequent return. Not chemical attribution or proof of persistent bad-tip state.'}
p=D/'S02_full216_native_waveform_provenance.json'
with p.open('x') as f:json.dump(provenance,f,indent=2);f.write('\n')
print(out,m.h.sha(out.read_bytes()))
