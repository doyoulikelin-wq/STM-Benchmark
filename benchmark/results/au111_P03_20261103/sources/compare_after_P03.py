"""Completed local full frame only; 212 usable baseline and one actual complete P03 compound-protocol result, no automatic classification."""
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

REFERENCES = {'212': ('after_R06_P02_recovery_full', 'dd448b665062664e20669d3b86d92b7b99879a0e91094b73fe7b18484b4a3739')}
def linked(path, ref):
 if path != Path(ref['path']) or sha(path) != ref['sha256']:
  raise ValueError('Matched event evidence changed: '+str(path))
 return json.loads(path.read_bytes())

def validate_completed_P03_stages(stage_docs, scan_start_ns, pulse_support):
 pulse=stage_docs['pulse'];prep=stage_docs['prepare'];ret=stage_docs['return']
 if (pulse.get('status')!='single_pulse_knownend_30s_observed' or pulse.get('pulse_attempted') is not True
     or pulse.get('native_end_confirmed') is not True or pulse.get('writer_outcome_unknown') is not False
     or pulse.get('pulse_ordinal')!=5 or pulse.get('action_id')!='P03'):
  raise ValueError('Normal P03 known-end/full-post30 path required; failed or independent-recovery paths need separate labels and adapters')
 for stage,j in [('prepare',prep),('return',ret)]:
  if (j.get('status')!='completed' or j.get('mode')!=stage or j.get('action_id')!='P03'
      or j.get('attempted_sets')!=11 or j.get('acknowledged_sets')!=11 or j.get('execution_unknown',False)):
   raise ValueError('Actual normal11-step prepare and return are required')
 if abs(prep['final_target_A']-1e-9)>1e-15 or abs(ret['final_target_A']-1e-10)>1e-16:
  raise ValueError('Actual prepared/returned setpoints differ')
 ack=pulse_support['pulse_ack.json'];cl=pulse_support['pulse.claim'];ready=pulse_support['feedback_readiness.json']
 rows=ready['observations'];post_rows=pulse_support['post30s_samples.json']['rows'];summary=pulse_support['post30s_summary.json'];after=pulse_support['after30s.json']
 if ack.get('values')!=[] or ack.get('warning') or cl.get('command')!='Bias.Pulse' or cl.get('args')!=[1,.020,-6.0,1,2]:
  raise ValueError('Actual selected Pulse/zero-error ACK differs')
 if (ready.get('ready') is not True or ready.get('readonly') is not True or ready.get('writes')!=[]
     or ready.get('error') is not None or ready.get('max_wait_s')!=2.
     or ready.get('Hold_is_waiting_not_stable') is not True or ready.get('post30s_excludes_readiness_time') is not True or not rows):
  raise ValueError('Actual bounded getter-only readiness evidence required')
 ack_s=ack['monotonic_ns']/1e9;previous=ack_s
 for k,row in enumerate(rows):
  v=row['values'];t=row['host_monotonic_s'];elapsed=row['elapsed_from_ACK_s']
  if (row.get('observation_index')!=k or t<previous or not 0<=elapsed<=2. or abs(elapsed-(t-ack_s))>1e-9
      or v['ZCtrl.OnOffGet']!=[1] or v['ZCtrl.StatusGet']!=([2] if k==len(rows)-1 else [3])):
   raise ValueError('Readiness must end with actual On2 within2s, earlier observations eligible Hold3 only')
  if (v['Bias.Get']!=[-1.] or abs(v['ZCtrl.SetpntGet'][0]-1e-9)>1e-15 or v['SafeTip.OnOffGet']!=[0]
      or any(v[key]!=[0] for key in ['Scan.StatusGet','AutoApproach.OnOffGet','BiasSpectr.StatusGet','ZSpectr.StatusGet','FolMe.PSOnOffGet'])
      or v['FolMe.XYPosGet']!=pulse['fixed_xy_m']):
   raise ValueError('Actual readiness fixed setting/state differs')
  previous=t
 ro=pulse['feedback_readiness']
 if (ro.get('status')!='known_On2_ready' or ro.get('getter_observations')!=len(rows)
     or ro.get('Hold_observations')!=len(rows)-1 or ro.get('elapsed_from_ACK_s')!=rows[-1]['elapsed_from_ACK_s']
     or ro.get('post30s_not_yet_started') is not True or ro.get('total_deadline_not_reset') is not True):
  raise ValueError('Readiness outcome and source observations differ')
 if (summary!=pulse.get('post_metrics') or summary.get('elapsed_s',0)<30. or not post_rows
     or post_rows[0]['t']<rows[-1]['host_monotonic_s'] or post_rows[-1]['t']<post_rows[0]['t']
     or after['start']['monotonic_ns']/1e9<post_rows[-1]['t']):
  raise ValueError('Full original post30 must start after actual ready observation')
 if not prep['monotonic_ns']<=cl['monotonic_ns']<=ack['monotonic_ns']<=after['start']['monotonic_ns']<=pulse['monotonic_ns']<ret['monotonic_ns']<=scan_start_ns:
  raise ValueError('Actual P03 preparation/ACK/post30/return/scan chronology differs')
 return pulse

def main():
 assert sha(C/'R02_functional_image_plan.json')=='9ccb1dc1507bb640ae9a6969f75b7f777b5558d454f94b682202168e219e5a0c'
 assert sha(C/'R06_pulse_P03_image_review/prospective_image_review_plan.json')=='8dcd17f720347b4f9f541223d35a772dc4c46402354bf06fbca1049318a44059'
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--reference',choices=REFERENCES,required=True);ap.add_argument('--scan-source',type=Path,required=True);ap.add_argument('--scan-source-sha256',required=True);args=ap.parse_args()
 run=args.run.resolve();D=args.output.resolve();assert run.parent==S and run.is_dir()
 assert not D.exists(),'New output required; do not overwrite reviewed evidence'
 ref=args.reference
 reference_dir,reference_sha=REFERENCES[ref]
 paired = True
 event = 'after_R06_P03_full'
 if run!=S/event or not D.is_relative_to(C/'R06_pulse_P03_image_review'):
  raise ValueError('Expected R06 post-induction and new review output')
 manifest=json.loads((run/'manifest.json').read_bytes())
 if (manifest.get('event_id'),manifest.get('recording_segment_id'),manifest.get('source_sha256'))!=(event,'R06',args.scan_source_sha256):
  raise ValueError('Post-P03 actual scanner source/event mismatch')
 source=args.scan_source.resolve()
 if source!=C/'scan_full50nm_fast_R06_after_induction_P03_once.py' or args.scan_source_sha256!='2d92acb42fb7f0324b5d1063194f77f634f39ca63b88c4e00b1cf58be064c0ee' or sha(source)!=args.scan_source_sha256:
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
 for r in refs:
  if sha(r['path'])!=r['sha256']:raise ValueError('Captured scan proof reference changed: '+r['path'])
 def bound(path):
  ref=next((r for r in refs if r.get('path')==str(path) and r.get('sha256')==sha(path)),None)
  if ref is None:raise ValueError('Actual postscan proof does not bind '+str(path))
  return linked(path,ref)
 for name in ['outcome.json','manifest.json','logger_ready_bound.json','scan_start.claim']:
  bound(S/reference_dir/name)
 bound(S/reference_dir/'analysis/quality_report.json')
 stage_docs={stage:bound(S/(stage+'_induction_P03')/'outcome.json') for stage in ['prepare','pulse','return']}
 pulse_support={name:bound(S/'pulse_induction_P03'/name) for name in ['pulse.claim','pulse_ack.json','feedback_readiness.json','post30s_samples.json','post30s_summary.json','after30s.json']}
 pulse=validate_completed_P03_stages(stage_docs,json.loads((run/'scan_start.claim').read_bytes())['monotonic_ns'],pulse_support)
 if pulse_support['feedback_readiness.json']['known_ACK']!=src(S/'pulse_induction_P03/pulse_ack.json'):raise ValueError('Readiness ACK reference differs')
 if proof.get('pulse_ordinal')!=5 or proof.get('completed_action_XY_m')!=pulse['fixed_xy_m']:raise ValueError('Actual scan P03 ordinal/XY differs')
 prior_manifest=json.loads((S/reference_dir/'manifest.json').read_bytes())
 prior_ready=json.loads((S/reference_dir/'logger_ready_bound.json').read_bytes())
 this_ready=json.loads((run/'logger_ready_bound.json').read_bytes())
 if prior_manifest['source_sha256']!='c30f251302f30d0bf8b5e204bf5ccaac066a08acf677ccd98d48bfbc89ee94f6' or prior_ready!=this_ready:
  raise ValueError('Actual212 baseline/recording identity differs')
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
 pair_label=f'Before P03 scan {ref} / after completed preparation + pulse + return scan {labels["observed"]}'
 assert datetime.datetime.fromisoformat(outcomes['observed']['end_event']['utc'])>datetime.datetime.fromisoformat(outcomes['reference']['end_event']['utc']),'Observed frame must finish after the reference'
 for k in ['SCAN_PIXELS','SCAN_TIME','SCAN_RANGE','SCAN_OFFSET','SCAN_ANGLE','SCAN_DIR','BIAS','Z-CONTROLLER']:assert q['reference']['header'][k]==q['observed']['header'][k],k
 prior=C/'compare201_202_offline/measurements.json';assert sha(prior)=='ef3a3fb7b4fb0cf966163999ae4cc4a21716101c3518f56c068f4d480e16bc6c';regs=json.loads(prior.read_text())['regions'];regs.append({'id':'S1_left_nonselected_I03_candidate','rc_half_open':[129,150,42,63],'role':'Original P02 prospective S1 window retained for P03 relative to212'});pitch=50/240
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
 fig.suptitle('Top: before P03; bottom: after completed preparation + pulse + return. Cross marks previous I03 interaction site.\nLocal morphology alone does not establish whole-tip failure; no chemical identity assumed.',fontsize=11)
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
      'pair_type':'before212_vs_completed_P03_compound_protocol',
      'current_scan_evidence':src(run/'fresh_recording_evidence.json'),'exposure_kind':'completed_preparation_P03_pulse_known_readiness_full_post30_normal_return','actual_P03_fixed_xy_m':pulse['fixed_xy_m'],'actual_stage_outcomes':{stage:src(S/(stage+'_induction_P03')/'outcome.json') for stage in ['prepare','pulse','return']},'actual_feedback_readiness':src(S/'pulse_induction_P03/feedback_readiness.json'),'original_post30':src(S/'pulse_induction_P03/post30s_samples.json'),'baseline_212_prior_P02_failure_preserved':src(C/'R06_pulse_P02_recovery_image_review/post_manual_review.json'),'executed_scan_source':src(source),'causal_limit':'Compound preparation + pulse + return, no isolated Pulse-only effect claim',
      'functional_plan':src(C/'R06_pulse_P03_image_review/prospective_image_review_plan.json'),
      'actual_native_labels':labels,'sources':{labels[n]:[src(paths[n]/'analysis/quality_report.json'),src(paths[n]/'analysis/analysis_planes.npz'),src(paths[n]/'outcome.json')] for n in paths},'reference_partition_source':src(C/'R06_pulse_P03_image_review/prospective_image_review_plan.json'),'independent_reference_ids':['C1_upper_isolated','C3_diagonal_edge'],'secondary_reference_id':'S1_left_nonselected_I03_candidate','local_affected_check_ids':['C2_right_upper','D4_lower_object'],'regions':regs,'I03_mound_region_rc_half_open':[119,141,195,221],'same_header_imaging_settings':True,'region_metrics':metrics,'prior_mask_contrast_descriptors':mask_descriptors,'metric_limit':'Unrestricted maximum may be row artifact/background. C3 includes edge and multiple objects: mask contrast is not calibrated individual height. New surface objects are allowed; actual task function requires manual review.','shared_shift_sensitivity':{'best':max(shifts,key=lambda x:x['mean']),'limit_pixels':[-4,4],'only_C1_C3_S1_shared_across_FB':True,'not_applied_to_display_or_metrics':True,'not_a_pass_threshold':True},'global':{labels[n]:{'raw_Z_FB':q[n]['quality']['raw_Z_FB_pm'],'pixel_current':{d:q[n]['fixed_descriptors']['directions'][d]['current_pixel_pA'] for d in ['F','B']},'manual_row_flags':{d:q[n]['fixed_descriptors']['directions'][d]['full_width_review_flags'] for d in ['F','B']}} for n in paths},'display':{'pooled_nm_limits':[float(lo),float(hi)],'clipped_counts':cl},'figures':[src(fc),src(ff),src(ft)],'I03_mound_local_descriptors':target_qa,'pure_function_reuse':src(old),'script':src(__file__),'image_function_impairment':'pending actual visual review','project_L0_L4':'not assigned by this script'}
 p=D/'image_measurements.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':sha(p),'actual_native_labels':labels,'contrasts':mask_descriptors},ensure_ascii=False))
if __name__=='__main__':main()
