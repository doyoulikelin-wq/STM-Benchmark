"""Locate archived current events in approximate slow-axis bands using R06 observed counter/XY brackets."""
import argparse
import bisect
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
P = Path(__file__).resolve().with_name('review_native_phases.py')
if hashlib.sha256(P.read_bytes()).hexdigest()!='7543764d9f1d8410169ba10e4e0210d25b50d579e19a196516c7e3bd7b9fe111':
    raise RuntimeError('R06 phase parser changed')
spec = importlib.util.spec_from_file_location('r06_phase_parser',P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.RUN = m.S/'after_R06_P02_recovery_full'
m.SCAN_SHA = 'c30f251302f30d0bf8b5e204bf5ccaac066a08acf677ccd98d48bfbc89ee94f6'
h, np = m.h, m.np


def summarize(first,last,receipt,output,single=None):
    output=h.local(output)
    h.require(not output.exists() and output.parent.is_dir(),'New local output required')
    ready,_=h.read_json(m.L/'READY.json')
    bound,_=h.read_json(m.RUN/'logger_ready_bound.json')
    manifest,mf=h.read_json(m.RUN/'manifest.json')
    rr,rref=h.read_json(receipt)
    h.require(ready==bound and ready['source_sha256']==m.LOGGER_SHA and ready['recording_segment_id']=='R06'
              and manifest['source_sha256']==m.SCAN_SHA and rr['recording_segment_id']=='R06'
              and rr['native_start_identity']==ready['native_start_identity'] and 1<=first<=last<=rr['complete_through_index'],
              'Native archive/R06 start or scan manifest mismatch')
    lv,lr=m.events(m.L/'events.jsonl',{'datalog_status'})
    ev,er=m.events(m.RUN/'events.jsonl',{'running_observed','scan_guard'})
    anchors=m.log_anchors(lv,ready['native_start_identity'])
    ns=[a['sample'] for a in anchors]
    activity=[r for r in ev if r['values']['Scan.StatusGet']==[1]]
    span_starts=[r['monotonic_ns']-round(r['duration_s']*1e9) for r in activity]
    span_ends=[r['monotonic_ns'] for r in activity]
    h.require(span_starts==sorted(span_starts) and span_ends==sorted(span_ends),'Nonmonotone scan clock')
    def localize(idx):
        j=bisect.bisect_right(ns,idx)-1;k=bisect.bisect_left(ns,idx)
        if j<0 or k>=len(ns):
            return {'mapping':'missing native counter observations'}
        left,right=anchors[j],anchors[k]
        if left['monotonic_ns']>right['monotonic_ns']:
            left,right=right,left
        t0,t1=left['monotonic_ns'],right['monotonic_ns']
        r={'mapping':'no bounded positive-running slow-axis readbacks','native_counter_bracket':[left,right]}
        u=bisect.bisect_right(span_ends,t0)-1
        v=bisect.bisect_left(span_starts,t1)
        if not (t1-t0<=2e9 and 0<=u<=v<len(activity) and t0-span_ends[u]<=1.5e9 and span_starts[v]-t1<=1.5e9):
            return r
        points=[{'utc':e['utc'],'monotonic_ns':e['monotonic_ns'],'getter_group_s':e['duration_s'],
                 'y_nm':e['values']['FolMe.XYPosGet'][1]*1e9} for e in activity[u:v+1]]
        y=[q['y_nm'] for q in points]
        if not all(-25.01<=f<=25.01 for f in y) or any(b>a+.005 for a,b in zip(y,y[1:])):
            return dict(r,reason='nonmonotonic or out-of-frame slow axis')
        rows=sorted(max(0,min(239,int(np.floor((25-v)*240/50)))) for v in [min(y),max(y)])
        return dict(r,mapping='nominal slow-axis band from enclosing grouped XY readbacks',host_bracket_s=(t1-t0)*1e-9,
                    enclosing_running_Y_reads=points,Y_nm=[min(y),max(y)],zero_based_row_interval=rows)
    channels=[]
    sources=[]
    for k in range(first,last+1):
        name=f'{m.PREFIX}{k:05d}.dat';rec=rr['files'][name];p=h.local(m.S/'native_R06'/name);raw=p.read_bytes()
        h.require(str(p)==rec['local_path'] and len(raw)==rec['bytes'] and h.sha(raw)==rec['sha256'],'Archived bytes mismatch')
        h.require(rec['rows']==m.BLOCK or (k==rr['complete_through_index'] and rec.get('terminal') and rr['all_blocks_including_last_archived']),'Unexpected partial block')
        if rec['rows']:
            channels.append(h.parse_block(raw,rec['rows'])[:,[0,1,2]])
        sources.append({'path':str(p),'sha256':rec['sha256'],'rows':rec['rows']})
    a=np.concatenate(channels); amps=abs(a[:,0]); base=(first-1)*m.BLOCK
    def row(j):
        g=base+j
        return {'global_zero_based':g,'block':g//m.BLOCK+1,'zero_based_row_in_block':g%m.BLOCK,
                'native_s':g*m.DT,'I_pA':a[j,0],'Bias_V':a[j,1],'Z_nm':a[j,2]}
    def detail(j):
        return {'peak':row(j),'nearby_native_rows':[row(q) for q in range(max(0,j-2),min(len(a),j+3))],
                'slow_axis':localize(base+j)}
    def threshold(level):
        mask=amps>=level
        edges=np.diff(np.r_[False,mask,False].astype(int))
        group_starts,group_ends=np.flatnonzero(edges==1),np.flatnonzero(edges==-1)
        out={'samples':int(mask.sum()),'groups':len(group_starts),'stored_sample_occupancy_ms':float(mask.sum()*.5)}
        if level>=1000:
            groups=[]
            for a0,b0 in zip(group_starts,group_ends):
                aa,bb=int(a0),int(b0)
                j=aa+int(np.argmax(amps[aa:bb]))
                groups.append({'global_half_open':[base+aa,base+bb],'samples':bb-aa,'peak':detail(j)})
            out['events']=groups
        return out
    if single is not None:
        block,rrw=single
        j=(block-first)*m.BLOCK+rrw
        h.require(first<=block<=last and 0<=rrw<m.BLOCK and 0<=j<len(a),'Requested row missing')
        result={'checked_single_row':detail(j)}
    else:
        result={'abs_current_thresholds_pA':{str(k):threshold(k) for k in [400,1000,4000]},
                'all_range_most_negative':detail(int(np.argmin(a[:,0]))),'all_range_most_positive':detail(int(np.argmax(a[:,0]))),
                'matches_historical_negative_digitizer_value_samples':int(np.isclose(a[:,0],-9999.4768,atol=.00005,rtol=0).sum()),
                'current_minmax_pA':[float(a[:,0].min()),float(a[:,0].max())]}
    result.update(blocks=[first,last],rows=len(a),receipt=rref,blocks_sha256=sources,manifest=mf,logger_events=lr,scan_events=er,
        script_sha256=h.sha(Path(__file__).read_bytes()),scope='Counter/host/slow-axis mapping only. Current thresholds are descriptive sample levels. The raw logger has no XY; output cannot assign exact pixels, pass direction, or simultaneous XY. Grouped readback and native buffering delays are uncalibrated.')
    with output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'output':str(output),'sha256':h.sha(output.read_bytes()),'rows':len(a),
                      'range_pA':result.get('current_minmax_pA'),'checked_row':single}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--first',type=int,required=True);p.add_argument('--last',type=int,required=True)
    p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--single',type=int,nargs=2,metavar=('BLOCK','ZERO_BASED_ROW'))
    x=p.parse_args();summarize(x.first,x.last,x.receipt,x.output,x.single)
