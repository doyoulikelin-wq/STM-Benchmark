"""Local R07 Home relocation and fine02 evidence, compared with preserved fine01."""
import importlib.util,json,hashlib,struct
from pathlib import Path
D=Path(__file__).resolve().parent;B=D/'review_native_phases.py'
assert hashlib.sha256(B.read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
spec=importlib.util.spec_from_file_location('r07_fine02_native_base',B);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
h,np=m.h,m.np;F=m.C/'engage_R07_02';M=m.C/'move_R07_home01'
receipt,rref=h.read_json(D/'after_fine02_native_receipt.json');h.require(rref['sha256']=='59f2c940adca6c0cec341b03c4daf28d845e0c3b61e60e1bcb39d160c80ea599','Receipt changed')
fine01,fref=h.read_json(D/'fine01_native_review.json');h.require(fref['sha256']=='9ae45e73930fc10d7250c4cbc8eae6db50a96a7f2caf7f167b6156fd04e92304','Fine01 review changed')
for name,digest in m.LOGGER_IDENTITY_PINS.items():h.require(h.sha((m.L/name).read_bytes())==digest,'R07 identity changed')
fine_source=m.C/'engage_finez_R07_02_100pA_once.py';move_source=m.C/'move_R07_home_corner_once.py'
h.require(h.sha(fine_source.read_bytes())=='7a77ce1ef8689e26dd86f2a5615c1973a1cf7f5d12acf2f4c681c239b586e0af' and h.sha(move_source.read_bytes())=='f6f3c0c0c93521e3c0a9dd3d5db011f8494d271786ce16b0ad684363eb6917c3','Source changed')
out,oref=h.read_json(F/'outcome.json');move,mref=h.read_json(M/'outcome.json')
h.require(out['status']=='tunneling_reestablished' and out['on_zero_error_ack'] and not out['withdraw_attempted'] and out['observation_elapsed_s']>=30 and out['sampled_stable_s']>=5,'Fine02 not known successful')
h.require(move['status']=='home_target_verified_5s_stationary' and not move['writer_outcome_unknown'] and not move['stop_attempted'],'Move not known complete')
ready,rr=h.read_json(m.L/'READY.json');lev,lr=m.events(m.L/'events.jsonl',{'datalog_status'});anchors=m.log_anchors(lev,ready['native_start_identity'])
arrays=[];files=[]
for block in range(1,102):
 name=f'{m.PREFIX}{block:05d}.dat';meta=receipt['files'][name];p=h.local(m.S/'native_R07'/name);raw=p.read_bytes()
 h.require(str(p)==meta['local_path'] and h.sha(raw)==meta['sha256'] and len(raw)==meta['bytes'] and meta['rows']==25000 and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Raw block evidence changed')
 arrays.append(h.parse_block(raw,25000));files.append({'path':str(p),'sha256':meta['sha256'],'rows':25000})
a=np.concatenate(arrays);del arrays

def bracket(lo,hi):
 b=m.bracket(anchors,lo,hi);h.require(b is not None,'Counter bracket missing');return b

def actual_writer(folder,command,args,fmt):
 raw=(folder/'events.jsonl').read_bytes();events=[json.loads(x) for x in raw.splitlines()]
 ws=[e for e in events if e.get('kind')=='tcp_exchange' and e.get('command') in ('FolMe.XYPosSet','FolMe.Stop','ZCtrl.OnOffSet','ZCtrl.Withdraw')]
 h.require(len(ws)==1 and ws[0]['command']==command and ws[0]['args']==args,'Unexpected actual writer sequence')
 e=ws[0]
 for key in ('request_header','request_body','response_header','response_body'):
  r=e[key];p=h.local(folder/r['path']);body=p.read_bytes();h.require(h.sha(body)==r['sha256'] and len(body)==r['bytes'],'Writer wire changed')
 h.require((folder/e['request_body']['path']).read_bytes()==struct.pack(fmt,*args) and (folder/e['response_body']['path']).read_bytes()==bytes(8) and e['status']=='ok' and not e['warning'],'Writer ACK unknown')
 return {'event':e,'events_ref':{'path':str(folder/'events.jsonl'),'sha256':h.sha(raw)},'bracket':bracket(round(e['start_perf']*1e9),round(e['end_perf']*1e9))}

wmove=actual_writer(M,'FolMe.XYPosSet',[-25e-9,-25e-9,0],'>ddI');won=actual_writer(F,'ZCtrl.OnOffSet',[1],'>I')
ma,maref=h.read_json(M/'after.json');fa,faref=h.read_json(F/'after.json');stable,stref=h.read_json(M/'target_stable.json')
bma=bracket(ma['start']['monotonic_ns'],ma['end']['monotonic_ns']);bfa=bracket(fa['monotonic_ns']-round(fa['duration_s']*1e9),fa['monotonic_ns'])
limits=sorted(x*1e9 for x in json.loads((m.L/'before.json').read_bytes())['values']['ZCtrl.LimitsGet'])
intervals=[('fine01_OffHome_to_Home_move',int(round(780.35/m.DT)),wmove['bracket']['before']['sample']),('Home_XY_move_and_confirmation',wmove['bracket']['before']['sample'],bma['after']['sample']),('Home_corner_wait_before_fine02',bma['after']['sample'],won['bracket']['before']['sample']),('fine02_On_boundary',won['bracket']['before']['sample'],won['bracket']['after']['sample']),('fine02_observation_inner',won['bracket']['after']['sample'],bfa['before']['sample']),('fine02_after_readback_boundary',bfa['before']['sample'],bfa['after']['sample']),('fine02_postroll_through101',bfa['after']['sample'],len(a))]
def describe(lo,hi):
 r=m.stats(a,lo,hi,100,limits);x=a[lo:hi]
 r['Control_equals_abs_Current_exact_fraction']=float(np.mean(x[:,3]==abs(x[:,0])))
 r['Control_minus_abs_Current_max_abs_pA']=float(np.max(abs(x[:,3]-abs(x[:,0]))))
 r['signed_current_within100pA20percent_fraction']=float(np.mean((-120<=x[:,0])&(x[:,0]<=-80)))
 r['Bias_not_minus1V_samples']=int(np.count_nonzero(x[:,1]!=-1))
 return r
phases={k:describe(lo,hi) for k,lo,hi in intervals};lo=won['bracket']['after']['sample'];hi=bfa['before']['sample'];last10=describe(hi-20000,hi)
windows=[{'partial_tail':i+2000>hi,**describe(i,min(i+2000,hi))} for i in range(lo,hi,2000)]
obs=[]
for p in sorted(F.glob('observation_*.json')):
 j,r=h.read_json(p);v=j['values'];h.require(v['Bias.Get']==[-1.] and v['ZCtrl.SetpntGet']==[1.000000013351432e-10] and v['SafeTip.OnOffGet']==[0] and v['ZCtrl.GainGet']==[3.4123519981887895e-12,4.29563588113524e-05,7.943764757101235e-08] and v['FolMe.XYPosGet']==move['actual_target_m'],'Observed configuration changed')
 obs.append({'source':r,'utc':j['utc'],'monotonic_ns':j['monotonic_ns'],'Current_A':v['Current.Get'][0],'Z_m':v['ZCtrl.ZPosGet'][0],'OnOff_Status':[v['ZCtrl.OnOffGet'][0],v['ZCtrl.StatusGet'][0]]})
r83,ref83=h.read_json(m.C/'read_083_R07_before_baseline/snapshot.json');r88,ref88=h.read_json(m.C/'read_088_R07_fine02_stable/snapshot.json')
h.require(r83['values']['FolMe.XYPosGet']==r88['values']['FolMe.XYPosGet']==move['actual_target_m'],'Same old corner not established')
comparison={'old_corner_before_baseline':{'source':ref83,'Z_nm':r83['values']['ZCtrl.ZPosGet'][0]*1e9,'I_pA':r83['values']['Current.Get'][0]*1e12},'old_corner_after_fine02':{'source':ref88,'Z_nm':r88['values']['ZCtrl.ZPosGet'][0]*1e9,'I_pA':r88['values']['Current.Get'][0]*1e12},'same_XY_m':move['actual_target_m'],'after_minus_before_Z_nm':(r88['values']['ZCtrl.ZPosGet'][0]-r83['values']['ZCtrl.ZPosGet'][0])*1e9,'scope':'Difference spans interrupted scan, two withdrawals, elapsed time, Home relocation and two fine engagements. No exclusive action or chemical cause assigned.'}
result={'scope':'R07 Home relocation and successful fine02, preserving failed fine01 and incomplete baseline.','source_sha256':h.sha(Path(__file__).read_bytes()),'sources':{'receipt':rref,'fine01_review':fref,'fine02_outcome':oref,'Home_move_outcome':mref,'logger_ready':rr,'logger_events':lr,'native_blocks':files,'Home_move_after':maref,'Home_move_stable':stref,'fine02_after':faref},'actual_move':wmove,'actual_fine02_On':won,'move_after_bracket':bma,'fine02_after_bracket':bfa,'fine02_outcome':out,'Home_move_outcome':move,'phases':phases,'fine02_final_native10s_before_after_readback_lower_bound':last10,'fine02_one_second_windows':windows,'slow_observation_refs_and_values':obs,'same_corner_before_after_sequence':comparison,'comparison_to_fine01':{'fine01_late9s':fine01['explicit_subwindows']['late_native770_779'],'fine02_last10s':last10,'limitations':'Position and elapsed time changed together. Corner recovery supports a role for local site and/or time dependence, without isolating the cause or proving tip repair.'},'counts':{'shared_pulses':5,'pulse_limit':6,'repair_attempts':2,'requested':5,'strict_cycles':0,'new_conditioning_writers':0},'limits':['No high-rate XY channel is present, so the native current/Z trace alone does not prove the lateral trajectory. Actual known move ACK and5s stationary readbacks independently establish the endpoint.','Signal names and units are preserved. ZControl is an absolute-current-valued signal and its match to Current is not an independent sensor validation. ZError transfer function remains uncalibrated.','Fine02 success is sampled current stability at a fixed corner. Z creep and image quality are separately recorded. No complete new baseline has yet been established by this result.','Partial scan failure, fine01 failure and all earlier claims remain in the history.']}
p=D/'relocation_and_fine02_native_review.json'
with p.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(p,h.sha(p.read_bytes()))
for k,v in phases.items():print(k,v['native_seconds_half_open'],'Imin/med/max',v['samples']['Current_pA']['min'],v['samples']['Current_pA']['median'],v['samples']['Current_pA']['max'],'Zmin/max',v['samples']['Z_nm']['min'],v['samples']['Z_nm']['max'],'>=400',v['abs_I_sample_exceedances_pA']['400']['sample_count'])
print('final10',last10['native_seconds_half_open'],'I',last10['samples']['Current_pA'],'ctrl',last10['samples']['Z_Control_pA']['median'],'error',last10['samples']['Z_Error_pA']['median'],'ZRMS',last10['Z_linear_residual_RMS_pm'],'slope',last10['Z_linear_slope_pm_per_s']);print('samecorner',comparison)
