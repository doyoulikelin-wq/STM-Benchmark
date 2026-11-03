"""Offline R07 fine01 Current/Control/Error and observed recovery evidence."""
import importlib.util
import json
from pathlib import Path
import struct
import hashlib
D=Path(__file__).resolve().parent
base=D/'review_native_phases.py'
assert hashlib.sha256(base.read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
spec=importlib.util.spec_from_file_location('R07_fine01_native_base',base);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
h,np=m.h,m.np;F=m.C/'engage_R07_01'
receipt,rref=h.read_json(D/'fine01_completed_native_receipt.json');h.require(rref['sha256']=='d43acafa686945337bfe575bd814a2514ce53c8d5c97b153bfef08bcb972b282','Receipt changed')
source=m.C/'engage_finez_R07_100pA_once.py';h.require(h.sha(source.read_bytes())=='5586d4c64d9bbb6a188dc5f966c7b100371aa540126a0cf0f1961299ef2e4477','Fine source changed')
out,oref=h.read_json(F/'outcome.json');h.require(out['status']=='failed_after_known_On_ack' and out['error']=='final5s_stability_timeout' and out['on_zero_error_ack'] and out['withdraw_home_confirmed'],'Unexpected fine outcome')
for name,digest in m.LOGGER_IDENTITY_PINS.items():h.require(h.sha((m.L/name).read_bytes())==digest,'R07 identity changed')
ready,rr=h.read_json(m.L/'READY.json');bound,bref=h.read_json(F/'logger_instance_bound.json')
h.require(bound['ready']==ready and bound['ready_sha256']==rr['sha256'],'Fine belongs to another recorder')
arrays=[];files=[]
for block in range(1,66):
 name=f'{m.PREFIX}{block:05d}.dat';meta=receipt['files'][name];p=h.local(m.S/'native_R07'/name);raw=p.read_bytes()
 h.require(str(p)==meta['local_path'] and len(raw)==meta['bytes'] and h.sha(raw)==meta['sha256'] and meta['rows']==25000 and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Raw evidence mismatch')
 arrays.append(h.parse_block(raw,25000));files.append({'path':str(p),'sha256':meta['sha256'],'rows':25000})
a=np.concatenate(arrays);del arrays
lev,lr=m.events(m.L/'events.jsonl',{'datalog_status'});anchors=m.log_anchors(lev,ready['native_start_identity'])
raw=(F/'events.jsonl').read_bytes();events=[json.loads(x) for x in raw.splitlines()];eref={'path':str(F/'events.jsonl'),'sha256':h.sha(raw),'bytes':len(raw)}
writers=[e for e in events if e.get('kind')=='tcp_exchange' and e.get('command') in ('ZCtrl.OnOffSet','ZCtrl.Withdraw')]
h.require([(e['command'],e['args']) for e in writers]==[('ZCtrl.OnOffSet',[1]),('ZCtrl.Withdraw',[1,2000])],'Fine writer sequence changed')
writer_brackets={}
for label,e in zip(('fine_On','conditional_Withdraw'),writers):
 for key in ('request_header','request_body','response_header','response_body'):
  r=e[key];p=h.local(F/r['path']);b=p.read_bytes();h.require(h.sha(b)==r['sha256'] and len(b)==r['bytes'],'Writer wire changed')
 expected=struct.pack('>I',1) if label=='fine_On' else struct.pack('>Ii',1,2000)
 h.require((F/e['request_body']['path']).read_bytes()==expected and (F/e['response_body']['path']).read_bytes()==bytes(8) and e['status']=='ok' and not e['warning'],'Known fine writer proof failed')
 b=m.bracket(anchors,int(round(e['start_perf']*1e9)),int(round(e['end_perf']*1e9)));h.require(b is not None,'Missing writer counter bracket');writer_brackets[label]=b
obs=[]
for p in sorted(F.glob('observation_*.json')):
 j,r=h.read_json(p);v=j['values'];h.require(v['ZCtrl.GainGet']==[3.4123519981887895e-12,4.29563588113524e-05,7.943764757101235e-08] and v['ZCtrl.SetpntGet']==[1.000000013351432e-10] and v['Bias.Get']==[-1.] and v['SafeTip.OnOffGet']==[0] and v['FolMe.XYPosGet']==[1.4309210705221176e-08,-3.0431048791967896e-09],'Static condition changed during fine observation')
 b=m.bracket(anchors,j['monotonic_ns']-round(j['duration_s']*1e9),j['monotonic_ns'])
 obs.append({'source':r,'utc':j['utc'],'monotonic_ns':j['monotonic_ns'],'bracket':b,'values':{k:v[k] for k in ('Current.Get','ZCtrl.ZPosGet','ZCtrl.OnOffGet','ZCtrl.StatusGet','Scan.StatusGet','ZCtrl.GainGet','ZCtrl.SetpntGet')}})
on=writer_brackets['fine_On'];off=writer_brackets['conditional_Withdraw'];limits=sorted(x*1e9 for x in json.loads((m.L/'before.json').read_bytes())['values']['ZCtrl.LimitsGet'])
intervals=[('previous_Withdraw_to_fine_On',int(round(324.86/m.DT)),on['before']['sample']),('fine_On_boundary',on['before']['sample'],on['after']['sample']),('after_On_to_before_Withdraw',on['after']['sample'],off['before']['sample']),('conditional_Withdraw_boundary',off['before']['sample'],off['after']['sample']),('after_Withdraw_through_closed65',off['after']['sample'],len(a))]
def describe(lo,hi):
 r=m.stats(a,lo,hi,100,limits);x=a[lo:hi]
 r['Control_equals_abs_Current_exact_fraction']=float(np.mean(x[:,3]==abs(x[:,0])))
 r['Control_minus_abs_Current_max_abs_pA']=float(np.max(abs(x[:,3]-abs(x[:,0]))))
 r['SafeTip_minus_Control_max_abs_pA']=float(np.max(abs(x[:,5]-x[:,3])))
 r['current_within_signed100pA20percent_fraction']=float(np.mean((-120<=x[:,0])&(x[:,0]<=-80)))
 r['bias_not_minus1_samples']=int(np.count_nonzero(x[:,1]!=-1))
 return r
phases={label:describe(lo,hi) for label,lo,hi in intervals}
lo=on['after']['sample'];hi=off['before']['sample'];bins=[{'partial_tail':k+2000>hi,**describe(k,min(k+2000,hi))} for k in range(lo,hi,2000)]
# Explicit fixed subwindows support comparisons without claiming a signal-selected stable endpoint.
selected={}
for label,start,end in [('early_observation_native752_753',752,753),('transition_native753_754',753,754),('middle_native760_770',760,770),('late_native770_779',770,779)]:
 l=int(round(start/m.DT));r=int(round(end/m.DT));h.require(lo<=l<r<=hi,'Diagnostic subwindow outside known On interval');selected[label]=describe(l,r)
result={'scope':'Fine01 failed final5s stability at fixed XY and returned to Off/Home. Simultaneous native signal comparisons are descriptive and not a controller transfer-function calibration.','source_sha256':h.sha(Path(__file__).read_bytes()),'sources':{'receipt':rref,'outcome':oref,'fine_source':{'path':str(source),'sha256':h.sha(source.read_bytes())},'ready':rr,'bound_ready':bref,'events':eref,'logger_events':lr,'native_blocks':files},'outcome':out,'writer_wire_verified':writers,'writer_brackets':writer_brackets,'phases':phases,'one_second_nonoverlapping_On_windows':bins,'explicit_subwindows':selected,'slow_observations':obs,'fixed_conditions':{'Bias_V':-1,'setpoint_pA':100,'XY_nm':[14.309210705221176,-3.0431048791967896],'gains_P_T_I':[3.4123519981887895e-12,4.29563588113524e-05,7.943764757101235e-08],'SafeTip':'Off','new_S01_configuration_writers':0},'limits':['The original final5s timeout result remains failed. No successful tunnelling recovery is inferred from later Off/Home near-zero current.','Z Control signal equals absolute Current within saved precision during the high-current observation. This supports a signal-path observation, not proof of an independently calibrated controller internal state.','Z Error signal is retained in its native units. A log-mode control error need not equal Control minus100pA, and its transfer function is uncalibrated.','The recorded Z increases while current remains around300pA. Physical junction, sample position, changing conductance and control-response mechanisms are not separated by these data.','On/Withdraw native boundaries use asynchronous counter brackets. All six channels have0.5ms stored intervals, not an analog bandwidth guarantee.']}
p=D/'fine01_native_review.json'
with p.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(p,h.sha(p.read_bytes()))
for label,v in phases.items():print(label,v['native_seconds_half_open'],'I',v['samples']['Current_pA']['min'],v['samples']['Current_pA']['median'],v['samples']['Current_pA']['max'],'Ctrlmed',v['samples']['Z_Control_pA']['median'],'Errmed',v['samples']['Z_Error_pA']['median'],'Z',v['samples']['Z_nm']['min'],v['samples']['Z_nm']['max'],'ge400',v['abs_I_sample_exceedances_pA']['400']['sample_count'],'ge4000',v['abs_I_sample_exceedances_pA']['4000']['sample_count'])
for label,v in selected.items():print(label,'I med',v['samples']['Current_pA']['median'],'Control med',v['samples']['Z_Control_pA']['median'],'Error med',v['samples']['Z_Error_pA']['median'],'exactctrl',v['Control_equals_abs_Current_exact_fraction'],'Zmed',v['samples']['Z_nm']['median'],'Zslope',v['Z_linear_slope_pm_per_s'])
