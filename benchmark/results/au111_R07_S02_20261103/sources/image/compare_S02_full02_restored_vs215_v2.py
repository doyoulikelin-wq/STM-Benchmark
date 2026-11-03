"""Complete S02 original-setting validation versus actual full215 baseline; offline only, no automatic classification."""
from pathlib import Path
import argparse,ast,datetime,hashlib,json,re,sys
sys.path.insert(0,'/Users/maxlin/Desktop/Nanonis/work/ag110_plot_dependencies')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
C=Path(__file__).resolve().parent.parent;S=C.parent/'session_02'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p):return {'path':str(p),'sha256':sha(p)}
def residual(z,rc):
 r0,r1,c0,c1=rc;v=z[r0:r1,c0:c1];yy,xx=np.indices(v.shape);ring=(yy<2)|(yy>=v.shape[0]-2)|(xx<2)|(xx>=v.shape[1]-2);X=np.c_[np.ones(v.size),xx.ravel(),yy.ravel()];co=np.linalg.lstsq(X[ring.ravel()],v[ring],rcond=None)[0];return v-(X@co).reshape(v.shape),ring

REFERENCES = {'215': ('after_R07_S01_recovered_full', 'c596a3d1b63d096d4bd035ab9c2df618969ba2313dc764c4dd4195741114a2a6')}
def linked(path, ref):
 if path != Path(ref['path']) or sha(path) != ref['sha256']:
  raise ValueError('Matched event evidence changed: '+str(path))
 return json.loads(path.read_bytes())

def main():
 assert sha(C/'R02_functional_image_plan.json')=='9ccb1dc1507bb640ae9a6969f75b7f777b5558d454f94b682202168e219e5a0c'
 assert sha(C/'R07_S02_full02_image_review/prospective_S02_full02_plan_v2.json')=='7bba9d864f900079267b9cedc2a54555eef36483a88fe165d0db863b10780e98'
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--reference',choices=REFERENCES,required=True);ap.add_argument('--scan-source',type=Path,required=True);ap.add_argument('--scan-source-sha256',required=True);args=ap.parse_args()
 run=args.run.resolve();D=args.output.resolve();assert run.parent==S and run.is_dir()
 assert not D.exists(),'New output required; do not overwrite reviewed evidence'
 ref=args.reference
 reference_dir,reference_sha=REFERENCES[ref]
 paired = True
 event = 'after_R07_S02_restored_full'
 if run!=S/event or not D.is_relative_to(C/'R07_S02_full02_image_review'):
  raise ValueError('Expected S02 restored validation and new local review output')
 manifest=json.loads((run/'manifest.json').read_bytes())
 source=args.scan_source.resolve()
 expected_sha='187c80bf513083aa0822e516fd6ce338e24c0b23b883d6f7d2f86455d2d90396'
 if (manifest.get('event_id'),manifest.get('recording_segment_id'),manifest.get('source_sha256'))!=(event,'R07',expected_sha):
  raise ValueError('Actual R07 scanner source/event mismatch')
 if source!=C/'scan_full50nm_fast_R07_after_S02_full02_restored_once.py' or args.scan_source_sha256!=expected_sha or sha(source)!=expected_sha:
  raise ValueError('Exact executed S02 restored scanner source required, no source import')
 proof=json.loads((run/'fresh_recording_evidence.json').read_bytes())
 prerequisite=proof['scan_based_induction_prerequisites']
 if prerequisite['stage']!=event or prerequisite['prerequisites_known_ended'] is not True:raise ValueError('Known completed S02 prerequisites required')
 def verify_refs(value):
  if isinstance(value,dict):
   if 'path' in value and 'sha256' in value:
    p=Path(value['path']).absolute()
    if p!=p.resolve() or not p.is_relative_to(C.parent) or any(x.lower() in ('win_users','volumes') for x in p.parts) or sha(p)!=value['sha256']:raise ValueError('Local immutable prerequisite reference changed')
   for child in value.values():verify_refs(child)
  elif isinstance(value,list):
   for child in value:verify_refs(child)
 verify_refs(prerequisite)
 prior_stages=prerequisite['prior_stages']
 order=['prepare','configure_gain','configure_speed','induction','return','restore_gain','restore_speed']
 if list(prior_stages)!=order:raise ValueError('Complete ordered normal S02 sequence required')
 for stage in order:
  rec=prior_stages[stage];out=linked(Path(rec['refs']['outcome.json']['path']),rec['refs']['outcome.json'])
  if out!=rec['outcome'] or out.get('execution_unknown',False) or out.get('writer_outcome_unknown',False):raise ValueError('Prior writer unknown or evidence mismatch')
  if stage in ('prepare','return'):
   if out['status']!='completed' or out['attempted_sets']!=4 or out['acknowledged_sets']!=4:raise ValueError('Four-step complete preparation/return required')
  elif stage=='induction':
   if out['status']!='completed' or out['completed_frame_confirmed'] is not True or len(out['frames'])!=6:raise ValueError('Complete normal exposure required')
  elif out['status']!='configured_and_exact_readback_verified':raise ValueError('Verified known configuration required')
 plan=json.loads((C/'R07_S02_full02_image_review/prospective_S02_full02_plan_v2.json').read_bytes())
 if prerequisite.get('known_prior_prestart_rejection') != plan['known_prior_prestart_rejection']:raise ValueError('Exact old local-only rejection must be retained')
 if prior_stages['induction']['event'] != 'induction_R07_S02_full02':raise ValueError('Actual new full02 exposure required')
 for key in ('baseline_outcome','baseline_quality','baseline_review'):
  r=plan[key];linked(Path(r['path']),r)
 if prerequisite['baseline_manual_review']!=plan['baseline_review'] or prerequisite['baseline_quality']!=plan['baseline_quality']:raise ValueError('Actual215 manual/quality identity mismatch')
 this_ready=json.loads((run/'logger_ready_bound.json').read_bytes());prior_ready=json.loads((S/reference_dir/'logger_ready_bound.json').read_bytes())
 if this_ready!=prior_ready or this_ready!=json.loads((S/'logger_07/READY.json').read_bytes()):raise ValueError('Different R07 native Start')
 if json.loads((S/reference_dir/'manifest.json').read_bytes())['source_sha256']!='027d412a476808348b3fbe008ec668c16103dbb96654fa084f9e8077de3267e1':raise ValueError('Actual recovered215 source differs')
 paths={'reference':S/reference_dir,'observed':run};q={};a={};outcomes={};labels={}
 for key,p in paths.items():
  qp=p/'analysis/quality_report.json';q[key]=json.loads(qp.read_text());outcomes[key]=json.loads((p/'outcome.json').read_text());i=q[key]['integrity'];assert q[key]['script_sha256']=='b171e535c4918bd9ba9429c8bd803e5a8ee4cef30b04b44685696ae8ea4800e7'
  assert outcomes[key]['completed_frame_confirmed'] and outcomes[key]['status']=='completed'
  assert i['completed_outcome'] and i['native_TCP_wire_bitmatch'] and i['matched_float32_values']==345600
  assert i['capture_outcome_sha256']==sha(p/'outcome.json')
  native=Path(q[key]['source']['path']).resolve();assert native.parent==p/'native';assert sha(native)==q[key]['source']['sha256']
  labels[key]=re.search(r'(\d+)\.sxm$',native.name).group(1).lstrip('0') or '0'
  plane_file=p/'analysis/analysis_planes.npz'
  if not any(Path(r['path'])==plane_file and r['sha256']==sha(plane_file) for r in q[key]['artifacts']):
   raise ValueError('Quality-report provenance for analysis planes does not match')
  a[key]=np.load(plane_file)
  for d in ['F','B']:assert a[key]['z'+d+'_nm'].shape==(240,240) and np.isfinite(a[key]['z'+d+'_nm']).all()
 assert q['reference']['source']['sha256']==reference_sha and labels['reference']==ref
 ref = labels['reference']
 pair_label=f'S02 restored validation {labels["observed"]} / actual full215 baseline; matched original settings'
 assert datetime.datetime.fromisoformat(outcomes['observed']['end_event']['utc'])>datetime.datetime.fromisoformat(outcomes['reference']['end_event']['utc']),'Observed frame must finish after the reference'
 for k in ['SCAN_PIXELS','SCAN_TIME','SCAN_RANGE','SCAN_OFFSET','SCAN_ANGLE','SCAN_DIR','BIAS','Z-CONTROLLER']:assert q['reference']['header'][k]==q['observed']['header'][k],k
 prior=C/'compare201_202_offline/measurements.json';assert sha(prior)=='ef3a3fb7b4fb0cf966163999ae4cc4a21716101c3518f56c068f4d480e16bc6c';regs=json.loads(prior.read_text())['regions'];regs.append({'id':'S1_left_nonselected_I03_candidate','rc_half_open':[129,150,42,63],'role':'Original S1 window retained relative to actual215'});pitch=50/240
 old=C/'compare201_202_offline/analyze.py';assert sha(old)=='61201f20375bbe902896413924410532dc87af510d9f94d649e7baade517503a';tree=ast.parse(old.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='region_metrics');env={'np':np,'pitch':pitch};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(old),'exec'),env);region_metrics=env['region_metrics']
 metrics={r['id']:{labels[n]:{d:region_metrics(a[n]['z'+d+'_nm'],r['rc_half_open']) for d in ['F','B']} for n in paths} for r in regs}
 mask_descriptors={}
 for r in regs:
  md={}
  for d in ['F','B']:
   b,ring=residual(a['reference']['z'+d+'_nm'],r['rc_half_open']);v,_=residual(a['observed']['z'+d+'_nm'],r['rc_half_open']);mask=b>=b.max()/2
   md[d]={'mask_definition':f'{ref} fixed ROI local perimeter-plane residual >=half of its maximum; no observed-frame tuning','mask_pixels':int(mask.sum()),'reference_mask_median_pm':float(np.median(b[mask])*1000),'observed_same_mask_median_pm':float(np.median(v[mask])*1000),'reference_perimeter_MAD_pm':float(np.median(abs(b[ring]-np.median(b[ring])))*1482.6),'observed_perimeter_MAD_pm':float(np.median(abs(v[ring]-np.median(v[ring])))*1482.6)}
  mask_descriptors[r['id']]=md
 D.mkdir(parents=True)
 cols=[('reference','F'),('reference','B'),('observed','F'),('observed','B')]
 fig,ax=plt.subplots(len(regs),4,figsize=(14,15),layout='constrained')
 for row,r in enumerate(regs):
  r0,r1,c0,c1=r['rc_half_open'];views=[]
  for n,d in cols:
   v=a[n]['z'+d+'_nm'][r0:r1,c0:c1];per=np.r_[v[0],v[-1],v[1:-1,0],v[1:-1,-1]];views.append(v-np.median(per))
  lo=min(v.min() for v in views);hi=max(v.max() for v in views)
  for col,((n,d),v) in enumerate(zip(cols,views)):
   im=ax[row,col].imshow(v,origin='upper',extent=[-25+c0*pitch,-25+c1*pitch,25-r1*pitch,25-r0*pitch],vmin=lo,vmax=hi,cmap='afmhot',interpolation='nearest');ax[row,col].set(title=f'{r["id"].split("_")[0]} | {labels[n]}{d}',xlabel='Nominal X (nm)',ylabel='Nominal Y (nm)')
  fig.colorbar(im,ax=ax[row,:],label='Z - perimeter median (nm)',shrink=.65)
 fig.suptitle(f'{pair_label} | corresponding nominal positions, trace and retrace\nFixed original spatial windows; one scale per row; scalar offset only, no smoothing, row correction or registration.',fontsize=12)
 fc=D/'fixed_objects_raw_FB.png';fig.savefig(fc,dpi=145);plt.close(fig)
 allp=np.concatenate([a[n]['p'+d+'_nm'].ravel() for n in paths for d in ['F','B']]);lo,hi=np.percentile(allp,[1,99]);cl={};fig,ax=plt.subplots(2,2,figsize=(12,10.5),layout='constrained')
 for row,n in enumerate(paths):
  for col,d in enumerate(['F','B']):
   v=a[n]['p'+d+'_nm'];im=ax[row,col].imshow(v,origin='upper',extent=[-25,25,-25,25],vmin=lo,vmax=hi,cmap='afmhot',interpolation='nearest');ax[row,col].set(title=f'{labels[n]}{d}: one global plane removed',xlabel='Nominal X (nm)',ylabel='Nominal Y (nm)');cl[labels[n]+d]={'below':int((v<lo).sum()),'above':int((v>hi).sum()),'total':57600}
 fig.colorbar(im,ax=ax.ravel().tolist(),label='nm; pooled1/99% display-only clipping',shrink=.75)
 fig.suptitle(f'{pair_label} | matched full fields and display limits\nFull raw images retained separately; no row flattening, smoothing or registration.',fontsize=12)
 ff=D/'full_shared_contrast.png';fig.savefig(ff,dpi=145);plt.close(fig)
 target_rc=[119,141,195,221]
 target_qa={labels[n]:{d:region_metrics(a[n]['z'+d+'_nm'],target_rc) for d in ['F','B']} for n in paths}
 target_views=[]
 r0,r1,c0,c1=target_rc
 for n,d in cols:
  v=a[n]['z'+d+'_nm'][r0:r1,c0:c1];per=np.r_[v[0],v[-1],v[1:-1,0],v[1:-1,-1]];target_views.append(v-np.median(per))
 tlo=min(v.min() for v in target_views);thi=max(v.max() for v in target_views)
 fig,ax=plt.subplots(2,2,figsize=(10,8),layout='constrained')
 for idx,((n,d),v) in enumerate(zip(cols,target_views)):
  aa=ax.flat[idx];im=aa.imshow(v,origin='upper',extent=[-25+c0*pitch,-25+c1*pitch,25-r1*pitch,25-r0*pitch],vmin=tlo,vmax=thi,cmap='afmhot',interpolation='nearest')
  aa.set(title=f'{labels[n]} {d}: existing I03 mound region',xlabel='Nominal X (nm)',ylabel='Nominal Y (nm)')
  aa.scatter(18,-2.1,marker='+',color='cyan',s=70)
 fig.colorbar(im,ax=ax,label='Z minus perimeter median (nm)',shrink=.75)
 fig.suptitle('Top: full215 baseline; bottom: S02 restored validation. Cross marks previous I03 interaction site.\nLocal morphology alone does not establish whole-tip failure; no chemical identity assumed.',fontsize=11)
 ft=D/'target_region_before_after_FB.png';fig.savefig(ft,dpi=145);plt.close(fig)
 shifts=[]
 for dy in range(-4,5):
  for dx in range(-4,5):
   cs=[]
   for r in [regs[0],regs[2],regs[4]]:
    r0,r1,c0,c1=r['rc_half_open']
    for d in ['F','B']:
     x=a['reference']['z'+d+'_nm'][r0:r1,c0:c1].ravel();y=a['observed']['z'+d+'_nm'][r0+dy:r1+dy,c0+dx:c1+dx].ravel();cs.append(float(np.corrcoef(x,y)[0,1]))
   shifts.append({'dy':dy,'dx':dx,'mean':float(np.mean(cs)),'individual':cs})
 out={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':pair_label,
      'pair_type':'actual215_vs_R07_S02_full02_restored_validation',
      'current_scan_evidence':src(run/'fresh_recording_evidence.json'),'same_recording_pair_without_intervening_gap':True,'earlier_recording_and_recovery_history_preserved':True,'exposure_kind':'complete_S02_compound_exposure_then_original_settings_restored','executed_scan_source':src(source),'causal_limit':'S02 preparation, gain/speed changes, exposure scan, return and restoration are a compound exposure. Functional judgement uses the original-setting complete pair; mechanism and chemistry remain unassigned.',
      'functional_plan':src(C/'R07_S02_full02_image_review/prospective_S02_full02_plan_v2.json'),
      'actual_native_labels':labels,'sources':{labels[n]:[src(paths[n]/'analysis/quality_report.json'),src(paths[n]/'analysis/analysis_planes.npz'),src(paths[n]/'outcome.json')] for n in paths},'reference_partition_source':src(C/'R07_S02_full02_image_review/prospective_S02_full02_plan_v2.json'),'independent_reference_ids':['C1_upper_isolated','C3_diagonal_edge'],'secondary_reference_id':'S1_left_nonselected_I03_candidate','local_affected_check_ids':['C2_right_upper','D4_lower_object'],'regions':regs,'I03_mound_region_rc_half_open':[119,141,195,221],'same_header_imaging_settings':True,'region_metrics':metrics,'prior_mask_contrast_descriptors':mask_descriptors,'metric_limit':'Unrestricted maximum may be row artifact/background. C3 includes edge and multiple objects: mask contrast is not calibrated individual height. New surface objects are allowed; actual task function requires manual review.','shared_shift_sensitivity':{'best':max(shifts,key=lambda x:x['mean']),'limit_pixels':[-4,4],'only_C1_C3_S1_shared_across_FB':True,'not_applied_to_display_or_metrics':True,'not_a_pass_threshold':True},'global':{labels[n]:{'raw_Z_FB':q[n]['quality']['raw_Z_FB_pm'],'pixel_current':{d:q[n]['fixed_descriptors']['directions'][d]['current_pixel_pA'] for d in ['F','B']},'manual_row_flags':{d:q[n]['fixed_descriptors']['directions'][d]['full_width_review_flags'] for d in ['F','B']}} for n in paths},'display':{'pooled_nm_limits':[float(lo),float(hi)],'clipped_counts':cl},'figures':[src(fc),src(ff),src(ft)],'I03_mound_local_descriptors':target_qa,'pure_function_reuse':src(old),'script':src(__file__),'image_function_impairment':'pending actual visual review','project_L0_L4':'not assigned by this script'}
 p=D/'image_measurements.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':sha(p),'actual_native_labels':labels,'contrasts':mask_descriptors},ensure_ascii=False))
if __name__=='__main__':main()
