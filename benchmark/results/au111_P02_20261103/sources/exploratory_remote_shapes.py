from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,'/Users/maxlin/Desktop/Nanonis/work/ag110_plot_dependencies')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
C=Path('/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102'); S=C.parent/'session_02'; D=C/'R06_pulse_P02_recovery_image_review/after_vs_211'
a={211:np.load(S/'after_R06_I03_full/analysis/analysis_planes.npz'),212:np.load(S/'after_R06_P02_recovery_full/analysis/analysis_planes.npz')}
regs={'Expanded C1':[14,54,84,121],'C3 nearby protrusion':[40,66,66,89],'S1 expanded':[124,155,37,69],'Left two protrusions\n(post hoc)':[54,82,10,29]}
fig,ax=plt.subplots(4,4,figsize=(13,12),layout='constrained'); pitch=50/240
for ri,(name,rc) in enumerate(regs.items()):
 r0,r1,c0,c1=rc; vs=[]
 for n in [211,212]:
  for d in ['F','B']:
   v=a[n]['z'+d+'_nm'][r0:r1,c0:c1]; ring=np.r_[v[0],v[-1],v[1:-1,0],v[1:-1,-1]]; vs.append(v-np.median(ring))
 lo=min(v.min() for v in vs);hi=max(v.max() for v in vs)
 for col,((n,d),v) in enumerate(zip([(211,'F'),(211,'B'),(212,'F'),(212,'B')],vs)):
  im=ax[ri,col].imshow(v,extent=[-25+c0*pitch,-25+c1*pitch,25-r1*pitch,25-r0*pitch],origin='upper',cmap='afmhot',vmin=lo,vmax=hi,interpolation='nearest'); ax[ri,col].set(title=f'{name}\n{n}{d}',xlabel='X nm',ylabel='Y nm')
 fig.colorbar(im,ax=ax[ri],label='nm minus perimeter median',shrink=.7)
fig.suptitle('Exploratory additional views, selected after viewing 212\nPrimary fixed regions and criteria unchanged. Raw pixels, scalar offset only, no shift or filtering.');fig.savefig(D/'exploratory_remote_shapes.png',dpi=125);plt.close(fig)
out={'scope':'posthoc descriptive enlargement, not replacement controls or acceptance threshold','windows_rc_half_open':regs,'sources':{str(n):{d:hashlib.sha256((S/d/'analysis/analysis_planes.npz').read_bytes()).hexdigest()} for n,d in [(211,'after_R06_I03_full'),(212,'after_R06_P02_recovery_full')]},'raw_arrays_unchanged':True,'no_registration':True,'script':{'path':str(Path(__file__).resolve()),'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'figure':{'path':str(D/'exploratory_remote_shapes.png'),'sha256':hashlib.sha256((D/'exploratory_remote_shapes.png').read_bytes()).hexdigest()}}
(D/'exploratory_remote_shapes.json').write_text(json.dumps(out,indent=2)+'\n')
