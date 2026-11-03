"""Offline S01 setpoint-stage native audit with all step ACK and native counter bounds."""
import argparse,json,struct,hashlib
from pathlib import Path
BASE_REVIEWER=Path(__file__).with_name('review_native_phases.py')
BASE_REVIEWER_SHA='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
if hashlib.sha256(BASE_REVIEWER.read_bytes()).hexdigest()!=BASE_REVIEWER_SHA:raise ValueError('Frozen base native reviewer changed')
from review_native_phases import h,np,DT,BLOCK,L,S,PREFIX,LOGGER_IDENTITY_PINS,LOGGER_SHA,require,events,log_anchors,bracket,stats
SOURCE_SHA='0d6126617db189754615ef82190e18a6303268e8cab4e218b5759e32c371467c'
TARGETS=[struct.unpack('>f',struct.pack('>f',v*1e-12))[0] for v in [100.,125.,156.25,195.3125,200.]]
def main():
    cli=argparse.ArgumentParser();cli.add_argument('--mode',choices=['prepare','return'],required=True)
    cli.add_argument('--receipt',type=Path,required=True);cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args();A=S/(args.mode+'_R07_S01');output=h.local(args.output)
    require(not output.exists(),'New output required')
    source=Path(__file__).resolve().parents[1]/'setpoint_R07_scan_induction_S01_once.py'
    require(h.sha(source.read_bytes())==SOURCE_SHA,'Frozen S01 setpoint source changed')
    refs={}
    def read(p):
        j,r=h.read_json(p);refs[str(p)]=r;return j
    rr,ready,mf,out=[read(p) for p in (args.receipt,L/'READY.json',A/'manifest.json',A/'outcome.json')]
    require(all(h.sha(h.local(L/n).read_bytes())==d for n,d in LOGGER_IDENTITY_PINS.items()),'Actual R07 logger identity changed')
    require(rr['recording_segment_id']=='R07' and rr['native_start_identity']==ready['native_start_identity']
            and read(A/'logger_ready_bound.json')==ready and mf['source_sha256']==SOURCE_SHA
            and mf['logger_source_sha256']==LOGGER_SHA and mf['session_id']=='session_02' and mf['action_id']=='S01'
            and out['mode']==args.mode and out['status']=='completed' and out['attempted_sets']==out['acknowledged_sets']==4,'Known complete S01 setpoint stage required')
    goals=TARGETS if args.mode=='prepare' else list(reversed(TARGETS))
    ev,eref=events(A/'events.jsonl',{'tcp_exchange'}|{f'step_{k:02d}_exact_readback' for k in range(1,5)})
    writers=[e for e in ev if e['kind']=='tcp_exchange' and not e['command'].endswith('Get')]
    require(len(writers)==4 and all(e['command']=='ZCtrl.SetpntSet' for e in writers),'Expected exactly4 setpoint writers')
    lev,lref=events(L/'events.jsonl',{'datalog_status'});anchors=log_anchors(lev,ready['native_start_identity'])
    def at(lo,hi=None):
        b=bracket(anchors,lo,lo if hi is None else hi);require(b is not None,'Native counter bracket missing');return b
    before=read(A/'before.json');after=read(A/'after.json');final=read(A/'final30_samples.json')
    require(len(final)>20 and final[-1]['monotonic_ns']>final[0]['monotonic_ns'],'Missing final30s samples')
    bounds={'before':at(before['end']['monotonic_ns']),'final_start':at(final[0]['monotonic_ns']),
            'final_end':at(final[-1]['monotonic_ns']),'after':at(after['end']['monotonic_ns'])}
    steps=[]
    for k,(target,e) in enumerate(zip(goals[1:],writers,strict=True),1):
        claim=read(A/f'step_{k:02d}.claim');ack=read(A/f'step_{k:02d}_ack.json')
        exact=[x for x in ev if x['kind']==f'step_{k:02d}_exact_readback'];require(len(exact)==1,'Missing unique exact readback')
        require(claim['command']=='ZCtrl.SetpntSet' and claim['source_sha256']==SOURCE_SHA and claim['args']==e['args']==[target]
                and claim['previous_target_A']==goals[k-1] and ack['values']==[] and not ack['warning']
                and e['status']=='ok' and not e.get('warning') and exact[0]['actual']==[target]
                and claim['monotonic_ns']<=e['monotonic_ns']<=exact[0]['monotonic_ns'],'Step claim/ACK/exact-read chronology mismatch')
        for key in ('request_header','request_body','response_header','response_body'):
            r=e[key];raw=h.local(A/r['path']).read_bytes();require(len(raw)==r['bytes'] and h.sha(raw)==r['sha256'],'Step wire hash mismatch')
            if key=='response_body':require(raw==bytes(8),'Step response error')
            if key=='request_body':require(raw==struct.pack('>f',target),'Setpoint wire float differs')
        bound=at(claim['monotonic_ns'],exact[0]['monotonic_ns'])
        steps.append({'index':k,'setpoint_pA':target*1e12,'previous_setpoint_pA':goals[k-1]*1e12,'native_transition_bracket':bound,
                      'claim':refs[str(A/f'step_{k:02d}.claim')],'ack':refs[str(A/f'step_{k:02d}_ack.json')],'exact_readback':exact[0]})
    first=bounds['before']['before']['sample'];last=bounds['after']['after']['sample']
    partitions=[('entry_before_first_set',first,steps[0]['native_transition_bracket']['before']['sample'],goals[0]*1e12)]
    for i,step in enumerate(steps):
        a,b=step['native_transition_bracket']['before']['sample'],step['native_transition_bracket']['after']['sample']
        nxt=steps[i+1]['native_transition_bracket']['before']['sample'] if i+1<len(steps) else bounds['final_start']['before']['sample']
        require(a<=b<=nxt,'Overlapping step timing uncertainty')
        partitions.extend([(f"step_{i+1:02d}_transition_outer",a,b,step['setpoint_pA']),
                           (f"step_{i+1:02d}_post_readback_inner",b,nxt,step['setpoint_pA'])])
    partitions.extend([('final30_start_boundary',bounds['final_start']['before']['sample'],bounds['final_start']['after']['sample'],goals[-1]*1e12),
                       ('final30_inner',bounds['final_start']['after']['sample'],bounds['final_end']['before']['sample'],goals[-1]*1e12),
                       ('final30_end_and_after',bounds['final_end']['before']['sample'],last,goals[-1]*1e12)])
    stage_end=last
    last=rr['complete_through_index']*BLOCK
    require(last>=stage_end,'Closed archive does not cover stage end')
    partitions.append(('post_stage_context_through_closed_receipt',stage_end,last,goals[-1]*1e12))
    ids=range(first//BLOCK+1,(last-1)//BLOCK+2);require(ids[-1]<=rr['complete_through_index'],'Closed receipt does not cover final known stage')
    arrays=[];files=[];base=(ids[0]-1)*BLOCK
    for num in ids:
        name=f'{PREFIX}{num:05d}.dat';p=h.local(S/'native_R07'/name);m=rr['files'][name];raw=p.read_bytes()
        require(m['local_path']==str(p) and m['rows']==BLOCK and len(raw)==m['bytes'] and h.sha(raw)==m['sha256']
                and m['source_double_read_sha_equal'] and m['local_reread_sha_equal'],'Closed native block not verified')
        arrays.append(h.parse_block(raw,BLOCK));files.append({'path':str(p),'sha256':m['sha256'],'rows':BLOCK})
    data=np.concatenate(arrays);limits=sorted(v*1e9 for v in before['values']['ZCtrl.LimitsGet'])
    def describe(lo,hi,target):
        d=stats(data,lo-base,hi-base,target,limits);d['zero_based_sample_half_open']=[lo,hi];d['setpoint_reference_pA']=target
        if hi==lo:return d
        x=data[lo-base:hi-base];d['native_seconds_half_open']=[lo*DT,hi*DT]
        d['fraction_native_current_within20pct_setpoint']=float(np.mean((-1.2*target<=x[:,0])&(x[:,0]<=-.8*target)))
        idx=int(np.argmin(x[:,0]))+lo;d['minimum_I_location']={'block':idx//BLOCK+1,'row_zero_based':idx%BLOCK}
        for r in d['abs_I_sample_exceedances_pA'].values():
            if r['longest_native_seconds_half_open']:r['longest_native_seconds_half_open']=[t+base*DT for t in r['longest_native_seconds_half_open']]
        if d['Z_changes']['pair_first_native_s'] is not None:d['Z_changes']['pair_first_native_s']+=base*DT
        return d
    phases={name:describe(lo,hi,sp) for name,lo,hi,sp in partitions}
    require(sum(d['rows'] for d in phases.values())==last-first and all(lo<=hi for _,lo,hi,_ in partitions),'Incomplete phase partition')
    lo,hi=bounds['final_start']['after']['sample'],bounds['final_end']['before']['sample']
    win=[describe(i,min(i+20000,hi),goals[-1]*1e12) for i in range(lo,hi,20000)]
    z0=phases['entry_before_first_set']['samples']['Z_nm']['median']
    result={'source_sha256':h.sha(Path(__file__).read_bytes()),'base_reviewer_source':{'path':str(BASE_REVIEWER),'sha256':BASE_REVIEWER_SHA},'mode':args.mode,'known_completed_outcome':out,'native_sources':files,'sources':refs,'action_events':eref,'logger_events':lref,
            'steps':steps,'milestones':bounds,'phases':phases,'final_fixed10s_windows':win,'whole_review_window':describe(first,last,goals[-1]*1e12),
            'entry_Z_median_nm':z0,'final_inner_Z_median_minus_entry_nm':phases['final30_inner']['samples']['Z_nm']['median']-z0,'rows_accounted':last-first,'stage_native_end_upper_s':stage_end*DT,'stage_only':describe(first,stage_end,goals[-1]*1e12),'source_control':{'path':str(source),'sha256':SOURCE_SHA},
            'limits':'Native current band comparisons use the per-step setpoint reference. Transition windows bracket host claim/readback asynchronously and mix old/new targets. Shared -120..-80pA field remains a historical100pA descriptor, not the target-specific gate. Native DAT contains no high-rate setpoint or XY channel.'}
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(str(output),h.sha(output.read_bytes()))
if __name__=='__main__':main()
