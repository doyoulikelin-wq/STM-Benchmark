"""Local exposure-only displays versus215. Actual216 acquisition parameters differ; no persistent bad-state label."""
from pathlib import Path
import sys,json,hashlib,datetime
sys.path.insert(0,'/Users/maxlin/Desktop/Nanonis/work/ag110_plot_dependencies')
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
C=Path(__file__).resolve().parents[1];S=C.parent/'session_02';D=Path(__file__).resolve().parent/'exposure216_vs215'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p)}
roles={'215':S/'after_R07_S01_recovered_full','216':S/'induction_R07_S02_full02'}
pins={'215':'c596a3d1b63d096d4bd035ab9c2df618969ba2313dc764c4dd4195741114a2a6','216':'529032028f5182e0685a24fc3e6d24e4ac22f5942940cd890a4adc448c56a774'}
assert not D.exists();data={};sources={};stats={}
for name,path in roles.items():
 q=json.loads((path/'analysis/quality_report.json').read_text());out=json.loads((path/'outcome.json').read_text())
 assert out['status']=='completed' and out['completed_frame_confirmed'] and q['integrity']['native_TCP_wire_bitmatch'] and q['integrity']['matched_float32_values']==345600
 assert q['source']['sha256']==pins[name] and sha(q['source']['path'])==pins[name]
 p=path/'analysis/analysis_planes.npz';assert any(r['path']==str(p) and r['sha256']==sha(p) for r in q['artifacts'])
 data[name]=np.load(p);sources[name]=[ref(path/'outcome.json'),ref(path/'analysis/quality_report.json'),ref(p)]
 stats[name]={}
 for d in 'FB':
  z=data[name]['z'+d+'_nm'];assert z.shape==(240,240) and np.isfinite(z).all()
  stats[name][d]={'raw_Z_min_nm':float(z.min()),'raw_Z_max_nm':float(z.max()),'raw_Z_median_nm':float(np.median(z)),'relative_Z_max_nm':float(z.max()-np.median(z)),'current_pixels':q['fixed_descriptors']['directions'][d]['current_pixel_pA']}
manifest=json.loads((roles['216']/'manifest.json').read_text());assert manifest['source_sha256']=='fc4592c0b16257d0c6f1fab4a484681235dbcb99bbbed7be03108c4131448319'
D.mkdir()
cols=[('215','F'),('215','B'),('216','F'),('216','B')];zv=[data[n]['z'+d+'_nm']-np.median(data[n]['z'+d+'_nm']) for n,d in cols]
lo=min(x.min() for x in zv);hi=max(x.max() for x in zv);clips={}
for name,limits in [('full_raw_range',(lo,hi)),('frozen210_contrast',(-.2886687155978507,.40538459700201085))]:
 fig,axes=plt.subplots(2,2,figsize=(12,10.5),layout='constrained');cmap=plt.get_cmap('afmhot').copy();cmap.set_over('magenta');cmap.set_under('cyan')
 for ax,(n,d),z in zip(axes.flat,cols,zv):
  im=ax.imshow(z,origin='upper',extent=[-25,25,-25,25],interpolation='nearest',cmap=cmap,vmin=limits[0],vmax=limits[1]);ax.set(title=f'{n}{d}',xlabel='Nominal X (nm)',ylabel='Nominal Y (nm)');ax.scatter(18,-2.1,c='cyan',marker='+',s=45)
  clips[n+d]={'below':int((z<limits[0]).sum()),'above':int((z>limits[1]).sum())}
 fig.colorbar(im,ax=axes.ravel().tolist(),label='Raw Z minus frame median (nm)',extend='both' if name!='full_raw_range' else 'neither',shrink=.75)
 fig.suptitle('Exposure comparison only. Top215:100pA/.912s/originalGain. Bottom216:200pA/.456s/2T.\nRaw pixels, scalar offset only. No registration/smoothing/row correction. Persistent effect awaits restored frame.',fontsize=11)
 fig.savefig(D/(name+'.png'),dpi=145);plt.close(fig)
plan=json.loads((C/'R07_S02_image_review/prospective_S02_plan.json').read_text());regions=[('C1 context',plan['C1_context_rc_half_open'])]+list(plan['frozen_ROIs'].items())
fig,axes=plt.subplots(len(regions),4,figsize=(13.5,17),layout='constrained')
for row,(label,rc) in enumerate(regions):
 r0,r1,c0,c1=rc;views=[]
 for n,d in cols:
  z=data[n]['z'+d+'_nm'][r0:r1,c0:c1];ring=np.r_[z[0],z[-1],z[1:-1,0],z[1:-1,-1]];views.append(z-np.median(ring))
 low=min(z.min() for z in views);high=max(z.max() for z in views)
 for col,((n,d),z) in enumerate(zip(cols,views)):
  im=axes[row,col].imshow(z,origin='upper',extent=[-25+c0*50/240,-25+c1*50/240,25-r1*50/240,25-r0*50/240],interpolation='nearest',vmin=low,vmax=high,cmap='afmhot');axes[row,col].set(title=f'{label} | {n}{d}',xlabel='Nominal X (nm)',ylabel='Nominal Y (nm)')
 fig.colorbar(im,ax=axes[row,:],label='Z minus perimeter median (nm)',shrink=.6)
fig.suptitle('Frozen regions and previously fixed expanded C1 context. Columns215F/B then216F/B.\nAcquisition parameters differ. Feature visibility and local effects only; no persistent tip verdict.',fontsize=12)
fig.savefig(D/'fixed_regions_and_C1_context.png',dpi=145);plt.close(fig)
out={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Exposure-only215-to216 comparison under different imaging parameters. Not matched post-conditioning evidence.','actual_native_labels':['215','216'],'sources':sources,'script':ref(__file__),'frozen_scientific_plan':ref(C/'R07_S02_image_review/prospective_S02_plan.json'),'statistics':stats,'display':{'full_raw_range_nm':[float(lo),float(hi)],'frozen210_nm':[-.2886687155978507,.40538459700201085],'last_display_clipping':clips,'scalar_offsets_only':True,'registration':False,'smoothing':False,'per_line_correction':False},'regions':regions,'persistent_bad_tip':'unassessed_pending_restored_original_setting_full_frame','figures':[ref(p) for p in sorted(D.glob('*.png'))]}
(D/'exposure_display_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'record':str(D/'exposure_display_record.json'),'sha256':sha(D/'exposure_display_record.json'),'relative_max':{n:{d:stats[n][d]['relative_Z_max_nm'] for d in 'FB'} for n in stats}},indent=2))
