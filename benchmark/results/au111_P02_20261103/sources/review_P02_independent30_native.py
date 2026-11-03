"""Bind the separate read-only recovery observation to the immutable native stream."""
import json
from pathlib import Path
from review_native_phases import h,np,DT,BLOCK,L,require,events,log_anchors,bracket
P=Path(__file__).resolve().parent
D=P.parent/'R06_pulse_P02/independent_readonly_recovery30'
j,jref=h.read_json(P/'P02_native_recovery_through364.json')
obs,oref=h.read_json(D/'outcome.json');samples,sref=h.read_json(D/'samples.json')
require(obs['status']=='completed_readonly_30s_original_guards' and obs['readonly'] and obs['writes']==[] and obs['original_failure_preserved']
        and len(samples)==obs['samples']==57 and obs['duration_s']>=30.,'Known independent30 missing')
snapshots=[]
for e in samples:
    snap,ref=h.read_json(e['snapshot']);require(ref['sha256']==e['sha256'],'Read snapshot changed')
    v=snap['values']
    require(v['ZCtrl.OnOffGet']==[1] and v['ZCtrl.StatusGet']==[2] and v['Bias.Get']==[-1.]
            and abs(v['ZCtrl.SetpntGet'][0]-1e-9)<1e-16 and v['SafeTip.OnOffGet']==[0]
            and all(v[n]==[0] for n in ('Scan.StatusGet','AutoApproach.OnOffGet','BiasSpectr.StatusGet','ZSpectr.StatusGet','FolMe.PSOnOffGet')),
            'Read-only original recovery flags changed')
    rows,_=events(Path(e['snapshot']).parent/'events.jsonl',{'tcp_exchange'})
    require(all(r['command'].endswith('Get') for r in rows),'Unexpected recovery writer')
    snapshots.append((snap,ref))
ready,_=h.read_json(L/'READY.json');rows,lref=events(L/'events.jsonl',{'datalog_status'});anchors=log_anchors(rows,ready['native_start_identity'])
start=snapshots[0][0];stop=snapshots[-1][0]
edge_a=bracket(anchors,start['start']['monotonic_ns'],start['end']['monotonic_ns'])
edge_b=bracket(anchors,stop['start']['monotonic_ns'],stop['end']['monotonic_ns'])
require(edge_a is not None and edge_b is not None,'Missing native recovery anchors')
lo=edge_a['after']['sample'];hi=edge_b['before']['sample']
first=edge_a['before']['sample'];last=edge_b['after']['sample']
data=[]
for e in j['native_blocks']:
    p=h.local(e['path']);raw=p.read_bytes();require(h.sha(raw)==e['sha256'],'Native archived block changed')
    data.append(h.parse_block(raw,e['rows']))
a=np.concatenate(data);base=(int(Path(j['native_blocks'][0]['path']).stem[-5:])-1)*BLOCK
require(base<=first<lo<hi<last<=base+len(a),'Recovery not fully inside selected native archive')
v=a[lo-base:hi-base];d=h.describe(v,lo,1000.)
d['fraction_native_in_pulse_band']=float(np.mean((-1250<=v[:,0])&(v[:,0]<=-750)))
result={'original_pulse_outcome':j['outcome'],'pulse_through364_review':jref,'independent_getters_outcome':oref,'samples':sref,
        'first_snapshot':snapshots[0][1],'last_snapshot':snapshots[-1][1],'all57_snapshots_getter_only_original_flags_verified':True,
        'native_outer_half_open':[first,last],'native_outer_seconds_half_open':[first*DT,last*DT],'native_first_boundary':edge_a,'native_last_boundary':edge_b,
        'native_inner':d,'native_inner_fixed10s_windows':[h.describe(v[k:min(k+20000,len(v))],lo+k,1000.) for k in range(0,len(v),20000)],
        'native_blocks':j['native_blocks'],'logger_events':lref,'scope':'Independent recovery evidence after original post-ACK guard failure. Host/counter bounds preserve asynchronous state updates; no reinterpretation of the original pulse outcome as a completed post30s.'}
p=P/'P02_independent30_native_review.json'
with p.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(str(p),h.sha(p.read_bytes()))
print('outer',first*DT,last*DT,'inner',lo*DT,hi*DT,'current',d['samples']['Current_pA'],'Zrms',d['Z_linear_residual_RMS_pm'],'slope',d['Z_linear_slope_pm_per_s'])
