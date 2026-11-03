"""Five original local ROIs; full214 baseline above and S01 independent recovery validation below."""
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
S=HERE.parents[1]/'session_02'
sys.path.insert(0,str(S.parents[1]/'ag110_plot_dependencies'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager
from matplotlib import pyplot as plt

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    D=HERE/'recovered_vs_214'
    report_path=D/'image_measurements.json'
    m=json.loads(report_path.read_bytes())
    assert m['pair_type']=='actual214_vs_R07_S01_independently_recovered_validation'
    labels=m['actual_native_labels']
    dirs={'reference':S/'baseline_segment07_full02','observed':S/'after_R07_S01_recovered_full'}
    fonts=Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
    if fonts.is_file():
        font_manager.fontManager.addfont(fonts)
        plt.rcParams['font.family']=font_manager.FontProperties(fname=fonts).get_name()
    array={}
    for stage,directory in dirs.items():
        p=directory/'analysis/analysis_planes.npz'
        assert any(r['sha256']==sha(p) and r['path']==str(p) for r in m['sources'][labels[stage]])
        array[stage]=np.load(p)
    regions=m['regions']; assert [r['id'].split('_')[0] for r in regions]==['C1','C2','C3','D4','S1']
    names=['C1　上方孤立突起','C2　邻近局部影响检查','C3　斜台阶及邻近突起','D4　丘体影响区','S1　左侧远端突起']
    rows=[('reference','F','S01前基线','正扫'),('reference','B','S01前基线','反扫'),('observed','F','独立恢复后','正扫'),('observed','B','独立恢复后','反扫')]
    fig,ax=plt.subplots(4,5,figsize=(15,9.5),layout='constrained')
    for j,reg in enumerate(regions):
        a,b,c,d=reg['rc_half_open'];views=[]
        for stage,direction,_,_ in rows:
            v=array[stage]['z'+direction+'_nm'][a:b,c:d]
            perimeter=np.r_[v[0],v[-1],v[1:-1,0],v[1:-1,-1]]
            views.append(v-np.median(perimeter))
        vmin=min(v.min() for v in views);vmax=max(v.max() for v in views)
        for i,((stage,dr,role,way),v) in enumerate(zip(rows,views)):
            img=ax[i,j].imshow(v,origin='upper',interpolation='nearest',cmap='afmhot',vmin=vmin,vmax=vmax,
                   extent=[c*50/240-25,d*50/240-25,25-b*50/240,25-a*50/240])
            if i==0:ax[i,j].set_title(names[j],fontsize=12)
            if j==0:ax[i,j].set_ylabel(f'{role} {labels[stage]}　{way}\nY (nm)',fontsize=11)
            if i==3:ax[i,j].set_xlabel('X (nm)')
            ax[i,j].tick_params(labelsize=8)
        fig.colorbar(img,ax=ax[:,j],location='bottom',shrink=.78,pad=.025,label='相对高度 (nm)')
    fig.suptitle(f'同一区域五个固定窗口　上两行：S01前基线 {labels["reference"]}　下两行：独立恢复后 {labels["observed"]}\n各窗口减边缘中位数，同列共用高度范围。保留原始像素，无配准、平滑或逐行校正。',fontsize=13)
    out=D/'objects_before_top_after_bottom.png'
    if out.exists():raise FileExistsError(out)
    fig.savefig(out,dpi=150);plt.close(fig)
    print(str(out),sha(out))

if __name__=='__main__':
    main()
