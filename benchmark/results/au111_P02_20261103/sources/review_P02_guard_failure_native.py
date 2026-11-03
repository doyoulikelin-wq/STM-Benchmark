"""P02 local byte-verified native action and recovery review. No hardware client or share access."""
import argparse, json
from pathlib import Path
from review_native_phases import L, S, BLOCK, DT, PREFIX, LOGGER_SHA, LOGGER_IDENTITY_PINS, h, np, require, events, log_anchors, bracket, stats
A = S/'pulse_induction_P02'
SCRIPT_SHA = 'e9ca1fd00da56dfc11c26b95d22e5f5ab6346a8bda3600c8f1e1fa46bb032998'

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--receipt',required=True,type=Path); cli.add_argument('--output',required=True,type=Path)
    args=cli.parse_args(); output=h.local(args.output)
    require(not output.exists(),'Output must be new')
    refs={}
    def read(p):
        j,ref=h.read_json(p);refs[str(p)]=ref;return j
    rr=read(args.receipt);ready=read(L/'READY.json');mf=read(A/'manifest.json')
    require(all(h.sha(h.local(L/k).read_bytes())==v for k,v in LOGGER_IDENTITY_PINS.items()),'R06 identity changed')
    require(read(A/'logger_ready_bound.json')==ready and rr['recording_segment_id']=='R06'
            and rr['native_start_identity']==ready['native_start_identity'] and mf['action_id']=='P02'
            and mf['session_id']=='session_02' and mf['recording_segment_id']=='R06' and mf['source_sha256']==SCRIPT_SHA
            and mf['logger_source_sha256']==LOGGER_SHA,'Wrong action or recorder')
    start=read(A/'pulse.claim');ack=read(A/'pulse_ack.json');out=read(A/'outcome.json')
    require(start['command']=='Bias.Pulse' and start['args']==[1,.020,-5.7,1,2]
            and ack['command']==start['command'] and ack['values']==[] and not ack['warning']
            and out['pulse_attempted'] and out['native_end_confirmed'] and not out['writer_outcome_unknown'],'Known waiting Start/end required')
    tcp,evref=events(A/'events.jsonl',{'tcp_exchange'})
    w=[e for e in tcp if e['command']=='Bias.Pulse']
    require(len(w)==1 and w[0]['args']==[1,.020,-5.7,1,2] and w[0]['status']=='ok' and not w[0].get('warning'),'Expected sole waiting Start exchange')
    for key in ('request_header','request_body','response_header','response_body'):
        entry=w[0][key];buf=h.local(A/entry['path']).read_bytes()
        require(len(buf)==entry['bytes'] and h.sha(buf)==entry['sha256'],'Wire mismatch')
        if key=='response_body':require(buf==bytes(8),'Start response has error body')
    lev,lref=events(L/'events.jsonl',{'datalog_status'})
    anchors=log_anchors(lev,ready['native_start_identity'])
    def at(t):
        b=bracket(anchors,t,t);require(b is not None,'Missing native counter bracket')
        return b
    geom={}
    for k in ('pre30s',):
        rows=read(A/(k+'_samples.json'))['rows'];require(len(rows)>1,'Insufficient host samples')
        geom[k+'_first']=at(round(rows[0]['t']*1e9))
        geom[k+'_last']=at(round(rows[-1]['t']*1e9))
    geom['start_claim']=at(start['monotonic_ns']);geom['waiting_ack']=at(ack['monotonic_ns'])
    def l(k):return geom[k]['before']['sample']
    def r(k):return geom[k]['after']['sample']
    first,last=l('pre30s_first'),rr['complete_through_index']*BLOCK
    windows=[('pre30s_start_edge',first,r('pre30s_first')),('pre30s_inner',r('pre30s_first'),l('pre30s_last')),
             ('pre_end_to_pulse_claim',l('pre30s_last'),l('start_claim')),
             ('claim_to_ACK_outer_including_timing_uncertainty',l('start_claim'),r('waiting_ack')),
             ('post_ACK_through_available_closed_data',r('waiting_ack'),last)]
    require(all(left<=right for _,left,right in windows),'Overlapping milestone uncertainty')
    ids=range(first//BLOCK+1,(last-1)//BLOCK+2);require(ids[-1]<=rr['complete_through_index'],'Closed coverage not sufficient')
    arrays=[];block_refs=[];base=(ids[0]-1)*BLOCK
    for num in ids:
        name=f'{PREFIX}{num:05d}.dat';p=h.local(S/'native_R06'/name);entry=rr['files'][name];raw=p.read_bytes()
        require(str(p)==entry['local_path'] and len(raw)==entry['bytes'] and h.sha(raw)==entry['sha256'] and
                ((entry.get('source_double_read_sha_equal') and entry.get('local_reread_sha_equal')) or
                 (entry.get('two_source_reads_same_sha') and entry.get('local_reread_matches'))),'Block receipt mismatch')
        arrays.append(h.parse_block(raw,entry['rows']));block_refs.append({'path':str(p),'sha256':entry['sha256'],'rows':entry['rows']})
    a=np.concatenate(arrays);require(last<=base+len(a),'Missing final rows')
    before=read(A/'before.json')['values'];sp=before['ZCtrl.SetpntGet'][0]*1e12;limits=sorted(v*1e9 for v in before['ZCtrl.LimitsGet'])
    def desc(left,right):
        x=a[left-base:right-base]
        if not len(x):return {'zero_based_sample_half_open':[left,right],'rows':0}
        d=stats(a,left-base,right-base,sp,limits)
        # Translate all sample/boundary location fields of the shared helper to absolute native coordinates.
        d['zero_based_sample_half_open']=[left,right];d['native_seconds_half_open']=[left*DT,right*DT]
        i=int(np.argmin(x[:,0]))+left;d['minimum_I_location']={'block':i//BLOCK+1,'row_zero_based':i%BLOCK}
        for info in d['abs_I_sample_exceedances_pA'].values():
            if info['longest_native_seconds_half_open']:info['longest_native_seconds_half_open']=[s+base*DT for s in info['longest_native_seconds_half_open']]
        if d['Z_changes']['pair_first_native_s'] is not None:d['Z_changes']['pair_first_native_s']+=base*DT
        d['fraction_native_current_within_pulse_band'] = float(np.mean((-1.25*sp <= x[:,0]) & (x[:,0] <= -.75*sp)))
        d['abs_current_at_least_9p99nA_samples']=int(np.count_nonzero(abs(x[:,0])>=9990))
        return d
    phases={name:desc(left,right) for name,left,right in windows}
    lo,hi=l('start_claim'),r('waiting_ack')
    bb=a[lo-base:hi-base,1]
    edges=np.diff(np.r_[False,bb<-4.,False].astype('i1'))
    plateau=[]
    for u,v in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
        lower,upper=lo+int(u),lo+int(v);plateau.append(desc(lower,upper))
    zref=phases['pre30s_inner']['samples']['Z_nm']['median']
    for d in list(phases.values())+plateau:
        if d['rows']:
            z=d['samples']['Z_nm'];d['Z_relative_pre_inner_median_nm']={k:z[k]-zref for k in ('min','max','median')}
    require(sum(d['rows'] for d in phases.values())==last-first,'Partition not exhaustive')
    result={'native_start':ready['native_start_identity'],'action_id':'P02','outcome':out,'sources':refs,'native_blocks':block_refs,
            'source_sha256':h.sha(Path(__file__).read_bytes()),'action_events':evref,'logger_events':lref,'dt_s':DT,
            'phase_bounds':geom,'phases':phases,'bias_below_minus4V_within_Start_outer':plateau,
            'post_fixed10s_windows':[desc(k,min(k+20000,last)) for k in range(r('waiting_ack'),last,20000)],'all_rows_accounted':last-first,'limits':'Original immediate-guard failure is preserved; no program post30s observation occurred. Later native blocks are separately reviewed. Host-bracketed windows include time uncertainty. 2 kHz DAT averages/sampling do not bound true analog peaks. At fixed posture Z is piezo readback rather than a contact proxy. No atomic pixel or contact evidence.'}
    with output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(output,h.sha(output.read_bytes()),last-first)
if __name__=='__main__':main()
