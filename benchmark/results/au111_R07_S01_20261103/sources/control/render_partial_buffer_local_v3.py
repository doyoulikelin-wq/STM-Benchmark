"""Offline raw buffer display, no completed image or current-row mask claimed."""
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,'/Users/maxlin/Desktop/Nanonis/work/ag110_plot_dependencies')
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
C=Path(__file__).resolve().parents[1];D=Path(__file__).resolve().parent/'partial_buffer_before_fine01';O=D/'offline_display_v3'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ref=lambda p:{'path':str(p),'sha256':sha(p)}
result=json.loads((D/'outcome.json').read_bytes());assert result['status']=='six_raw_buffers_preserved_readonly' and result['completed_scan'] is False
assert len(result['frames'])==6
arrays={};sources={}
for k,di in [('F',1),('B',0)]:
 for channel in (0,30,89):
  meta=json.loads((D/f'frames/channel_{channel}_{di}.json').read_bytes());p=D/meta['matrix']['path']
  assert sha(p)==meta['matrix']['sha256'] and meta['rows']==meta['columns']==240
  arrays[channel,k]=np.frombuffer(p.read_bytes(),dtype='>f4').astype(float).reshape(240,240)
  sources[f'{channel}{k}']=ref(p)
O.mkdir(exist_ok=False)
z={d:arrays[30,d]*1e9 for d in 'FB'}
offsets={d:float(np.nanmedian(z[d])) for d in 'FB'}
z={d:z[d]-offsets[d] for d in 'FB'}
full=[min(np.nanmin(v) for v in z.values()),max(np.nanmax(v) for v in z.values())]
frozen=json.loads((C/'R06_induction_I03/after_vs_210/dynamic_range_display_record.json').read_bytes())['frozen_baseline_only_p1_p99_nm']
fig,ax=plt.subplots(2,2,figsize=(12,11),layout='constrained');cmap=plt.get_cmap('afmhot').copy();cmap.set_bad('#888888');cmap.set_over('#ff00bb');cmap.set_under('#00bfff')
for row,limits in enumerate((full,frozen)):
 for col,d in enumerate('FB'):
  v=z[d];im=ax[row,col].imshow(v,origin='upper',extent=[-25,25,-25,25],cmap=cmap,vmin=limits[0],vmax=limits[1],interpolation='nearest')
  ax[row,col].set(title=f'Buffer {d} | '+('common full raw range' if row==0 else 'inherited210 terrace contrast; colored clipping'),xlabel='Nominal X (nm), freshness unknown',ylabel='Nominal Y (nm), freshness unknown')
  ax[row,col].scatter(18,-2.1,marker='+',color='cyan',s=60)
 fig.colorbar(im,ax=ax[row,:],shrink=.8,label='Z minus one buffer median (nm)',extend='neither' if row==0 else 'both')
fig.suptitle('READONLY BUFFER AFTER INTERRUPTED SCAN — OLD/NEW ROW MIXTURE POSSIBLE\nGRAY = nonfinite values in original raw buffers, not a manual mask.\nNo completed SXM identity or validated acquisition-row mask.\nTCP orientation retained; no smoothing, row subtraction, registration or filling. Plus marks historical I03 site.',fontsize=11)
p=O/'partial_buffer_Z_full_and_frozen.png';fig.savefig(p,dpi=145,bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(12,5.8),layout='constrained');icmap=plt.get_cmap('coolwarm').copy();icmap.set_bad('#888888');current={d:arrays[0,d]*1e12 for d in 'FB'};low=min(np.nanmin(x) for x in current.values());high=max(np.nanmax(x) for x in current.values())
for a,d in zip(ax,'FB'):
 im=a.imshow(current[d],origin='upper',extent=[-25,25,-25,25],cmap=icmap,vmin=low,vmax=high,interpolation='nearest');a.set(title=f'Current buffer {d}, raw stored pixels',xlabel='Nominal X (nm)',ylabel='Nominal Y (nm)')
fig.colorbar(im,ax=ax,shrink=.8,label='pA, pixel values are not native transient peaks')
fig.suptitle('Interrupted scan read-only buffer; possible OLD/NEW ROW MIXTURE\nGRAY = nonfinite original buffer values, not a manual mask.\nNo valid acquisition-row mask or full-frame claim',fontsize=11)
pc=O/'partial_buffer_current_raw.png';fig.savefig(pc,dpi=145,bbox_inches='tight');plt.close(fig)
record={'scope':'Offline visualization of raw TCP buffers after known stop/withdraw. All rows have unverified acquisition epoch.','completed_frame':False,'native_SXM_available':False,'valid_current_scan_mask':None,'sources':sources,'capture_outcome':ref(D/'outcome.json'),'source_script':ref(Path(__file__)),'orientation':'TCP arrays already display-oriented according to prior completed native/TCP bitmatches. No additional flips. Nominal positions are not timestamped pixels.','scalar_offset_nm':offsets,'full_raw_Z_relative_range_nm':[float(x) for x in full],'frozen210_contrast_nm':frozen,'raw_current_pA_range':[float(low),float(high)],'figures':[ref(p),ref(pc)],'raw_nonfinite_pixels':{f'{c}{d}':int((~np.isfinite(v)).sum()) for (c,d),v in arrays.items()},'nonfinite_display':'gray without filling or inferred scan mask','wholeframe_quality_classification':'not_assessable from mixed buffer'}
(O/'display_record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'figures':record['figures'],'Zrange':full,'Irange':[low,high]}))
