"""Offline exploratory context for C1; original ROI and primary images retained."""
from pathlib import Path
import hashlib, json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, '/Users/maxlin/Desktop/Nanonis/work/ag110_plot_dependencies')
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle
H=Path(__file__).resolve().parent
S=H.parents[1]/'session_02'
O=H/'restored_vs_215'
def ref(p):
    return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
rc=[12,62,80,128]
r0,r1,c0,c1=rc
items=[]
m=json.loads((O/'image_measurements.json').read_bytes())
assert m['pair_type']=='actual215_vs_R07_S02_full02_restored_validation'
for role,stage in [('reference','after_R07_S01_recovered_full'),('observed','after_R07_S02_restored_full')]:
    label=m['actual_native_labels'][role]
    p=S/stage/'analysis/analysis_planes.npz'
    assert ref(p) in m['sources'][label]
    a=np.load(p)
    for dr in ['F','B']:
        v=a['z'+dr+'_nm'][r0:r1,c0:c1]
        offset=float(np.median(np.r_[v[0],v[-1],v[1:-1,0],v[1:-1,-1]]))
        items.append((label,dr,v-offset,offset,ref(p)))
limits=[min(x[2].min() for x in items),max(x[2].max() for x in items)]
fig,ax=plt.subplots(2,2,figsize=(9,9),layout='constrained')
for aa,(lab,dr,v,offset,source) in zip(ax.flat,items):
    im=aa.imshow(v,origin='upper',extent=[-25+c0*50/240,-25+c1*50/240,25-r1*50/240,25-r0*50/240],interpolation='nearest',cmap='afmhot',vmin=limits[0],vmax=limits[1])
    a,b,c,d=[20,44,90,115]
    aa.add_patch(Rectangle((-25+c*50/240,25-b*50/240),(d-c)*50/240,(b-a)*50/240,fill=False,color='#66ccff',lw=1.3))
    aa.set(title=lab+' '+dr,xlabel='Nominal X (nm)',ylabel='Nominal Y (nm)')
fig.suptitle(f'C1 context fixed before S02 at unchanged coordinates\nUpper 215, lower {m["actual_native_labels"]["observed"]}. Blue = original fixed ROI. Raw pixels, no registration.\nOne perimeter-median scalar per crop. Shared unclipped range.',fontsize=12)
fig.colorbar(im,ax=ax.ravel().tolist(),label='Relative Z (nm)',shrink=.8)
out=O/'C1_expanded_context_raw_FB.png'
assert not out.exists()
fig.savefig(out,dpi=130,bbox_inches='tight');plt.close(fig)
record={'scope':'Exploratory larger unchanged-coordinate context only. Original fixed ROI and primary comparisons retained. No shape metric or selection rule replaced.','rc_half_open':rc,'original_C1_rc_half_open':[20,44,90,115],'interpolation':'nearest','registration':False,'smoothing':False,'range_nm':list(map(float,limits)),'panels':[{'label':x[0]+x[1],'perimeter_median_nm':x[3],'source':x[4]} for x in items],'figure':ref(out),'source':ref(Path(__file__))}
(O/'C1_expanded_context_record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,indent=2))
