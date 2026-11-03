"""Offline interrupted R07 S01 exposure at200pA, including trigger and commanded withdrawal."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

D=Path(__file__).resolve().parent
base=D/'review_native_phases.py'
assert hashlib.sha256(base.read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
spec=importlib.util.spec_from_file_location('r07_interrupted_native_base',base)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
h,np=m.h,m.np
m.RUN=m.S/'induction_R07_S01_full'
m.SCAN_SHA='757d27ae1b250afdad5a9649f8837f81d7e9cd73806ab351479cb21855f86a66'
assert h.sha((m.C/'scan_full50nm_fast_R07_induction_S01_once.py').read_bytes())==m.SCAN_SHA
receipt,rref=h.read_json(D/'S01_induction_interrupted_through239_native_receipt.json')
h.require(rref['sha256']=='41428c3fced0cc804b2e144e7c032b2620fc39b62282f98f3a8ac496e8bd9ff7','Frozen receipt changed')
outcome,oref=h.read_json(m.RUN/'outcome.json')
h.require(oref['sha256']=='2fa06f2bfb0553ca4fb50f1f41903318a72527e105be482c25be7a81008b0a42' and outcome['status']=='incomplete' and outcome['completed_frame_confirmed'] is False,'Unexpected incomplete outcome')
ready,rr=h.read_json(m.L/'READY.json')
for name,sha in m.LOGGER_IDENTITY_PINS.items():h.require(h.sha((m.L/name).read_bytes())==sha,'Immutable R07 identity changed')
manifest,mref=h.read_json(m.RUN/'manifest.json')
h.require(manifest['source_sha256']==m.SCAN_SHA and manifest['logger_source_sha256']==m.LOGGER_SHA and manifest['event_id']=='induction_R07_S01_full','Wrong baseline source')
arrays=[];files=[]
for block in range(1,receipt['complete_through_index']+1):
    name=f'{m.PREFIX}{block:05d}.dat';meta=receipt['files'][name];p=h.local(m.S/'native_R07'/name);raw=p.read_bytes()
    h.require(str(p)==meta['local_path'] and len(raw)==meta['bytes'] and h.sha(raw)==meta['sha256'] and meta['rows']==25000 and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Raw archive evidence differs')
    arrays.append(h.parse_block(raw,25000));files.append({'path':str(p),'sha256':meta['sha256'],'rows':25000})
a=np.concatenate(arrays);del arrays
raw=(m.RUN/'events.jsonl').read_bytes();events=[json.loads(line) for line in raw.splitlines()]
er={'path':str(m.RUN/'events.jsonl'),'sha256':h.sha(raw),'bytes':len(raw)}
lev,lr=m.events(m.L/'events.jsonl',{'datalog_status'});anchors=m.log_anchors(lev,ready['native_start_identity'])
writers=[e for e in events if e['kind']=='tcp_exchange' and e['command'] in ('Scan.Action','ZCtrl.Withdraw')]
h.require([(e['command'],e['args']) for e in writers]==[('Scan.Action',[0,0]),('Scan.Action',[1,0]),('ZCtrl.Withdraw',[1,2000])],'Actual writer sequence changed')
wire_proof=[]
for e in writers:
    for key in ('request_header','request_body','response_header','response_body'):
        ref=e[key];p=h.local(m.RUN/ref['path']);b=p.read_bytes();h.require(len(b)==ref['bytes'] and h.sha(b)==ref['sha256'],'Wire hash mismatch')
    h.require(e['status']=='ok' and not e['warning'] and (m.RUN/e['response_body']['path']).read_bytes()==bytes(8),'Writer ACK not known')
    expected=struct.pack('>HI',*e['args']) if e['command']=='Scan.Action' else struct.pack('>Ii',*e['args'])
    h.require((m.RUN/e['request_body']['path']).read_bytes()==expected,'Actual writer bytes differ')
    wire_proof.append(e)
trigger=[e for e in events if e['kind']=='scan_guard' and abs(e['values']['Current.Get'][0])>=400e-12]
h.require(len(trigger)==1,'Unexpected guard trigger count');trigger=trigger[0]
cleanup=next(e for e in events if e['kind']=='cleanup_control_state')
post=next(e for e in events if e['kind']=='post_stop')
withdrawals=[e for e in events if e['kind']=='withdraw_verification']
first_home=next(e for e in withdrawals if e['values']['ZCtrl.OnOffGet']==[0] and e['values']['ZCtrl.StatusGet']==[1] and abs(e['values']['ZCtrl.ZPosGet'][0]-123.69999069505866e-9)<1e-12)

def host_scope(e):
    if e['kind']=='tcp_exchange':return [int(round(e['start_perf']*1e9)),int(round(e['end_perf']*1e9))]
    return [e['monotonic_ns']-int(round(e['duration_s']*1e9)),e['monotonic_ns']]

def bracket(e):
    lo,hi=host_scope(e);result=m.bracket(anchors,lo,hi);h.require(result is not None,'Native counter bracket missing');return result

keys=('Current.Get','ZCtrl.ZPosGet','ZCtrl.OnOffGet','ZCtrl.StatusGet','Scan.StatusGet','FolMe.XYPosGet','Bias.Get','ZCtrl.SetpntGet','SafeTip.OnOffGet')
observations={}
for label,e in [('trigger',trigger),('cleanup_before_Stop',cleanup),('after_Stop_before_Withdraw',post),('first_Off1_Home',first_home),('last_Off1_Home',withdrawals[-1])]:
    current_call=next(v for v in reversed(events) if v['kind']=='tcp_exchange' and v['command']=='Current.Get' and v['monotonic_ns']<=e['monotonic_ns'])
    ref=current_call['response_body'];body=(m.RUN/ref['path']).read_bytes();h.require(h.sha(body)==ref['sha256'] and len(body)==12 and body[4:]==bytes(8),'Current getter wire differs')
    h.require(struct.unpack('>f',body[:4])[0]==e['values']['Current.Get'][0],'Current wire value differs')
    observations[label]={'utc':e['utc'],'monotonic_ns':e['monotonic_ns'],'snapshot_scope':host_scope(e),'values':{k:e['values'][k] for k in keys},'bracket':bracket(e),'current_getter':current_call,'current_getter_bracket':bracket(current_call)}
bs={label:bracket(e) for label,e in zip(('Start','Stop','Withdraw'),writers)}
initial_active=next(e for e in events if e['kind']=='running_observed')
start_boundary=m.bracket(anchors,host_scope(writers[0])[0],initial_active['monotonic_ns'])
lo_trigger=observations['trigger']['bracket']['before']['sample'];hi_home=observations['first_Off1_Home']['bracket']['after']['sample']
phases=[('prior_R07_history_mixed_targets',0,5600000),('speed224_end_to_Start',5600000,start_boundary['before']['sample']),('Start_positioning_boundary',start_boundary['before']['sample'],start_boundary['after']['sample']),('interrupted_running_before_trigger_boundary',start_boundary['after']['sample'],lo_trigger),('trigger_Stop_Withdraw_overlapping_boundaries',lo_trigger,hi_home),('post_Withdraw_Off1_Home',hi_home,len(a))]
limits=sorted(x*1e9 for x in json.loads((m.L/'before.json').read_bytes())['values']['ZCtrl.LimitsGet'])
results={name:m.stats(a,lo,hi,200.0000026702864,limits) for name,lo,hi in phases}
window_start=max(0,lo_trigger-20000);window_end=min(len(a),hi_home+4000)
thresholds={}
for level in (400,1000,4000):
    mask=np.abs(a[window_start:window_end,0])>=level;edges=np.diff(np.r_[False,mask,False].astype(int));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
    runs=[]
    for lo,hi in zip(starts,ends):
        lo=int(lo)+window_start;hi=int(hi)+window_start;peak=lo+int(np.argmax(abs(a[lo:hi,0])))
        runs.append({'zero_based_sample_half_open':[lo,hi],'native_seconds_half_open':[lo*m.DT,hi*m.DT],'rows':hi-lo,'duration_ms':(hi-lo)*.5,'peak_pA':float(a[peak,0]),'peak_native_s':peak*m.DT,'peak_location':{'block':peak//m.BLOCK+1,'row_zero_based':peak%m.BLOCK}})
    thresholds[str(level)]={'groups':len(runs),'samples':sum(x['rows'] for x in runs),'longest':max(runs,key=lambda x:x['rows']) if runs else None,'largest5':sorted(runs,key=lambda x:abs(x['peak_pA']),reverse=True)[:5],'all_at_least4nA_groups':runs if level==4000 else None}
home_candidates=np.flatnonzero(abs(a[:,2]-123.69999069505866)<.001)
home_candidates=home_candidates[home_candidates>=bs['Withdraw']['before']['sample']]
h.require(len(home_candidates)>0,'No recorded Home plateau')
home_sample=int(home_candidates[0])
windows=[]
for name,lo,hi in phases:
    for k in range(lo,hi,20000):windows.append({'phase':name,'partial_tail':k+20000>hi,**m.stats(a,k,min(k+20000,hi),200.0000026702864,limits)})
h.require(sum(v['rows'] for v in results.values())==len(a)==sum(v['rows'] for v in windows),'Phase accounting failed')
result={'strict10s_before_trigger_lower_boundary':m.stats(a,lo_trigger-20000,lo_trigger,200.0000026702864,limits),'scope':'Interrupted S01 exposure only. Actual software trigger, Stop and commanded Withdraw are preserved separately from image quality. No complete-frame claim.', 'source_sha256':h.sha(Path(__file__).read_bytes()),'sources':{'receipt':rref,'outcome':oref,'logger_ready':rr,'scan_manifest':mref,'scan_events':er,'logger_events':lr,'native_blocks':files},'outcome':outcome,'native_start':ready['native_start_identity'],'native_rows':len(a),'stored_dt_s':m.DT,'wire_verified_writers':wire_proof,'writer_counter_brackets':bs,'observations':observations,'phases':results,'nonoverlapping_ten_second_windows':windows,'trigger_neighborhood_seconds':[window_start*m.DT,window_end*m.DT],'trigger_neighborhood':m.stats(a,window_start,window_end,200.0000026702864,limits),'threshold_runs_in_neighborhood':thresholds,'first_recorded_Home_sample':{'sample':home_sample,'native_s':home_sample*m.DT,'block':home_sample//m.BLOCK+1,'row':home_sample%m.BLOCK,'I_pA':float(a[home_sample,0]),'Z_nm':float(a[home_sample,2])},'limits':['Current.Get and native samples are asynchronous. Counter brackets overlap for trigger, Stop and Withdraw, so no exact raw point is assigned to the TCP trigger.','The large positive Z transition and endpoint status occur under known commanded Withdraw. They do not establish a spontaneous crash or previous contact depth.','After Withdraw the near-zero current is an Off/Home observation, not recovered tunnelling.','Only Scan Start, Scan Stop and Withdraw occurred within this exposure event. The preceding separately logged S01 setpoint200pA, doubled time constant and doubled speed were already applied. No automatic normal return occurred.','Stored0.5ms sample intervals are not calibrated analog bandwidth or a true-peak bound. Raster Z includes topography and controller response.']}

for entry in [results['prior_R07_history_mixed_targets']]+[x for x in windows if x['phase']=='prior_R07_history_mixed_targets']:
    for key in ['control_minus_setpoint','error_minus_control_minus_setpoint','error_minus_setpoint_minus_control']:entry.get('algebraic_descriptors_pA',{}).pop(key,None)
    entry['actual_target_mixed_not_constant200pA']=True
p=D/'S01_induction_trigger_stop_withdraw_native_review.json'
with p.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(p,h.sha(p.read_bytes()))
for name,v in results.items():print(name,v['native_seconds_half_open'],'Iminmax',v['samples']['Current_pA']['min'],v['samples']['Current_pA']['max'],'Zminmax',v['samples']['Z_nm']['min'],v['samples']['Z_nm']['max'],'over400',v['abs_I_sample_exceedances_pA']['400'],'edge',v['matches_historical_negative_digitizer_value_samples'])
print('brackets',{k:[v['before']['native_s'],v['after']['native_s']] for k,v in bs.items()})
print('strictpre10',result['strict10s_before_trigger_lower_boundary']['native_seconds_half_open'],result['strict10s_before_trigger_lower_boundary']['samples']['Current_pA'],result['strict10s_before_trigger_lower_boundary']['abs_I_sample_exceedances_pA'])
print('home',result['first_recorded_Home_sample'])
for label,v in observations.items():print(label,v['utc'],v['values']['Current.Get'],v['values']['ZCtrl.OnOffGet'],v['values']['ZCtrl.StatusGet'])
for e in wire_proof:print('writer',e['command'],e['args'],e['utc'],e['duration_s'] if 'duration_s' in e else None)
