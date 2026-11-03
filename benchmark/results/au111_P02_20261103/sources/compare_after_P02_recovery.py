"""Completed local full frame only; 211 usable baseline and one actual complete frame after P02 and independent recovery; original failure preserved, no automatic classification."""
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

REFERENCES = {'211': ('after_R06_I03_full', '736d255572999e5cc6c82fbf86d644a152c20e214abab2cfe804e733b72649bc')}
def linked(path, ref):
 if path != Path(ref['path']) or sha(path) != ref['sha256']:
  raise ValueError('Matched event evidence changed: '+str(path))
 return json.loads(path.read_bytes())

def validate_P02_independent_recovery_stages(stage_docs, scan_start_ns):
 prep=stage_docs['prepare'];pulse=stage_docs['pulse'];readonly=stage_docs['readonly_recovery'];ret=stage_docs['return']
 if (pulse.get('status')!='uncertain_or_recovery_failed' or pulse.get('pulse_attempted') is not True
     or pulse.get('native_end_confirmed') is not True or pulse.get('writer_outcome_unknown') is not False
     or pulse.get('error')!='Not known On2/allidle' or 'post_metrics' in pulse):
  raise ValueError('Expected preserved actual P02 failure after known Pulse end, original post30 not executed')
 if (readonly.get('status')!='completed_readonly_30s_original_guards' or readonly.get('readonly') is not True
     or readonly.get('writes')!=[] or readonly.get('original_failure_preserved') is not True
     or readonly.get('duration_s',0)<30.):
  raise ValueError('Independent read-only original-guard recovery window is required')
 if (prep.get('status')!='completed' or prep.get('mode')!='prepare'
     or ret.get('status')!='completed' or ret.get('mode')!='recover_return'
     or ret.get('event_id')!='recovery_return_P02_01' or ret.get('independent_recovery_return') is not True
     or ret.get('original_pulse_status_preserved')!=pulse['status']
     or ret.get('attempted_sets')!=11 or ret.get('acknowledged_sets')!=11):
  raise ValueError('Completed preparation and separately recorded recovery return required')
 if abs(prep['final_target_A']-1e-9)>1e-15 or abs(ret['final_target_A']-1e-10)>1e-16:
  raise ValueError('Prepared 1nA / independently returned 100pA target mismatch')
 if not prep['monotonic_ns']<pulse['monotonic_ns']<readonly['monotonic_ns']<ret['monotonic_ns']<=scan_start_ns:
  raise ValueError('Independent recovery sequence or postscan chronology differs')
 return pulse

def main():
 assert sha(C/'R06_pulse_P02_recovery_image_review/independent_recovery_image_context.json')=='de48d0e007600358d71b4b871371b21a5498d78265a9b74dcfbd7a34274c64fc'
 assert sha(C/'R02_functional_image_plan.json')=='9ccb1dc1507bb640ae9a6969f75b7f777b5558d454f94b682202168e219e5a0c'
 assert sha(C/'R06_pulse_P02_image_review/prospective_image_review_plan.json')=='993009578a95d550b9a18b729306bec06c525c7ecd1f147f09336958b41679a3'
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--reference',choices=REFERENCES,required=True);ap.add_argument('--scan-source',type=Path,required=True);ap.add_argument('--scan-source-sha256',required=True);args=ap.parse_args()
 run=args.run.resolve();D=args.output.resolve();assert run.parent==S and run.is_dir()
 assert not D.exists(),'New output required; do not overwrite reviewed evidence'
 ref=args.reference
 reference_dir,reference_sha=REFERENCES[ref]
 paired = True
 event = 'after_R06_P02_recovery_full'
 if run!=S/event or not D.is_relative_to(C/'R06_pulse_P02_recovery_image_review'):
  raise ValueError('Expected R06 post-induction and new review output')
 manifest=json.loads((run/'manifest.json').read_bytes())
 if (manifest.get('event_id'),manifest.get('recording_segment_id'),manifest.get('source_sha256'))!=(event,'R06',args.scan_source_sha256):
  raise ValueError('Post-P02 actual scanner source/event mismatch')
 source=args.scan_source.resolve()
 if source!=C/'scan_full50nm_fast_R06_after_P02_recovery_once.py' or args.scan_source_sha256!='c30f251302f30d0bf8b5e204bf5ccaac066a08acf677ccd98d48bfbc89ee94f6' or sha(source)!=args.scan_source_sha256:
  raise ValueError('Explicit batch-local executed source hash required; no source import')
 proof=json.loads((run/'fresh_recording_evidence.json').read_bytes())
 def collect_refs(x):
  out=[]
  if isinstance(x,dict):
   if 'path' in x and 'sha256' in x:out.append(x)
   for v in x.values():out+=collect_refs(v)
  elif isinstance(x,list):
   for v in x:out+=collect_refs(v)
  return out
 refs=collect_refs(proof)
 def bound(path):
  ref=next((r for r in refs if r.get('path')==str(path) and r.get('sha256')==sha(path)),None)
  if ref is None:raise ValueError('Actual postscan proof does not bind '+str(path))
  return linked(path,ref)
 for name in ['outcome.json','manifest.json','logger_ready_bound.json','scan_start.claim']:
  bound(S/reference_dir/name)
 bound(S/reference_dir/'analysis/quality_report.json')
 stage_paths={'prepare':S/'prepare_induction_P02/outcome.json','pulse':S/'pulse_induction_P02/outcome.json',
              'readonly_recovery':C/'R06_pulse_P02/independent_readonly_recovery30/outcome.json',
              'return':S/'recovery_return_P02_01/outcome.json'}
 if sha(stage_paths['pulse'])!='61d379cd5d78590392b64b81273ab10fa4643e16c25cb6503a9008e4458d4bc9' or sha(stage_paths['readonly_recovery'])!='cd6a6bd89200d99a972dc649adae5132b0da0e9aad314f61147de6be9ceb2871':
  raise ValueError('Original failed pulse or separate read30 evidence changed')
 stage_docs={name:bound(path) for name,path in stage_paths.items()}
 pulse=validate_P02_independent_recovery_stages(stage_docs,json.loads((run/'scan_start.claim').read_bytes())['monotonic_ns'])
 prior_manifest=json.loads((S/reference_dir/'manifest.json').read_bytes())
 prior_ready=json.loads((S/reference_dir/'logger_ready_bound.json').read_bytes())
 this_ready=json.loads((run/'logger_ready_bound.json').read_bytes())
 if prior_manifest['source_sha256']!='d039b5fc37d47672f0319e050615b7e3294273b3215259b0aac1923da61bc591' or prior_ready!=this_ready:
  raise ValueError('Actual211 baseline/recording identity differs')
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
 pair_label=f'Before P02 scan {ref} / P02 executed, independent recovery, full scan {labels["observed"]}'
 assert datetime.datetime.fromisoformat(outcomes['observed']['end_event']['utc'])>datetime.datetime.fromisoformat(outcomes['reference']['end_event']['utc']),'Observed frame must finish after the reference'
 for k in ['SCAN_PIXELS','SCAN_TIME','SCAN_RANGE','SCAN_OFFSET','SCAN_ANGLE','SCAN_DIR','BIAS','Z-CONTROLLER']:assert q['reference']['header'][k]==q['observed']['header'][k],k
 prior=C/'compare201_202_offline/measurements.json';assert sha(prior)=='ef3a3fb7b4fb0cf966163999ae4cc4a21716101c3518f56c068f4d480e16bc6c';regs=json.loads(prior.read_text())['regions'];regs.append({'id':'S1_left_nonselected_I03_candidate','rc_half_open':[129,150,42,63],'role':'P02 prospectively added secondary remote region'});pitch=50/240
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
   im=ax[row,col].imshow(v,origin='upper',extent=[-25+c0*pitch,-25+c1*pitch,25-r1*pitch,25-r0*pitch],vmin=lo,vmax=hi,cmap='afmhot',interpolation='nearest');ax[row,col].set(title=f'{r["id"]} | {labels[n]}{d}',xlabel='Nominal X (nm)',ylabel='Nominal Y (nm)')
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
 fig.suptitle('Top: before P02; bottom: P02 executed, independent recovery, full image. Cross marks previous I03 interaction site.\nLocal morphology alone does not establish whole-tip failure; no chemical identity assumed.',fontsize=11)
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
      'pair_type':'before211_vs_P02_executed_independent_recovery_full',
      'current_scan_evidence':src(run/'fresh_recording_evidence.json'),'exposure_kind':'pulse_executed_original_guard_failed_then_independent_recovery_return','actual_P02_fixed_xy_m':json.loads((S/'pulse_induction_P02/root_fresh_snapshot.json').read_bytes())['values']['FolMe.XYPosGet'],'actual_stage_outcomes':{name:src(path) for name,path in stage_paths.items()},'original_pulse_failure_preserved':True,'original_pulse_post30_executed':False,'original_pulse_status':pulse['status'],'original_pulse_error':pulse['error'],'independent_recovery_context':src(C/'R06_pulse_P02_recovery_image_review/independent_recovery_image_context.json'),'executed_scan_source':src(source),'causal_limit':'Compound preparation, Pulse, interrupted original recovery check, independent read30 and separately recorded return. Original failed outcome retained; no isolated Pulse-only attribution.',
      'functional_plan':src(C/'R06_pulse_P02_image_review/prospective_image_review_plan.json'),
      'actual_native_labels':labels,'sources':{labels[n]:[src(paths[n]/'analysis/quality_report.json'),src(paths[n]/'analysis/analysis_planes.npz'),src(paths[n]/'outcome.json')] for n in paths},'reference_partition_source':src(C/'R06_pulse_P02_image_review/prospective_image_review_plan.json'),'independent_reference_ids':['C1_upper_isolated','C3_diagonal_edge'],'secondary_reference_id':'S1_left_nonselected_I03_candidate','local_affected_check_ids':['C2_right_upper','D4_lower_object'],'regions':regs,'I03_mound_region_rc_half_open':[119,141,195,221],'same_header_imaging_settings':True,'region_metrics':metrics,'prior_mask_contrast_descriptors':mask_descriptors,'metric_limit':'Unrestricted maximum may be row artifact/background. C3 includes edge and multiple objects: mask contrast is not calibrated individual height. New surface objects are allowed; actual task function requires manual review.','shared_shift_sensitivity':{'best':max(shifts,key=lambda x:x['mean']),'limit_pixels':[-4,4],'only_C1_C3_S1_shared_across_FB':True,'not_applied_to_display_or_metrics':True,'not_a_pass_threshold':True},'global':{labels[n]:{'raw_Z_FB':q[n]['quality']['raw_Z_FB_pm'],'pixel_current':{d:q[n]['fixed_descriptors']['directions'][d]['current_pixel_pA'] for d in ['F','B']},'manual_row_flags':{d:q[n]['fixed_descriptors']['directions'][d]['full_width_review_flags'] for d in ['F','B']}} for n in paths},'display':{'pooled_nm_limits':[float(lo),float(hi)],'clipped_counts':cl},'figures':[src(fc),src(ff),src(ft)],'I03_mound_local_descriptors':target_qa,'pure_function_reuse':src(old),'script':src(__file__),'image_function_impairment':'pending actual visual review','project_L0_L4':'not assigned by this script'}
 p=D/'image_measurements.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':sha(p),'actual_native_labels':labels,'contrasts':mask_descriptors},ensure_ascii=False))
if __name__=='__main__':main()
