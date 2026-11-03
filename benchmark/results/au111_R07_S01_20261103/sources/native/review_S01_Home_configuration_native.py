"""Local-only native audit of one actual known-complete S01 separate Off/Home recovery setting."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
sys.dont_write_bytecode = True
BASE_REVIEWER=Path(__file__).with_name('review_native_phases.py')
BASE_REVIEWER_SHA='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
if hashlib.sha256(BASE_REVIEWER.read_bytes()).hexdigest()!=BASE_REVIEWER_SHA:raise ValueError('Frozen base native reviewer changed')
from review_native_phases import h,np,DT,BLOCK,L,S,PREFIX,LOGGER_IDENTITY_PINS,LOGGER_SHA,require,events,log_anchors,bracket,stats
C = Path(__file__).resolve().parents[1]
B = C/'R07_scan_induction/offhome_recovery_binding.py'
B_SHA = '5d795aa0044b91d3cc642f21271872bddab3f4161bcdc77b7136d3a03be03a9d'
SOURCE = C/'recover_R07_S01_OffHome_once.py'
SOURCE_SHA = 'f8c16650b97f9296b5ed59dbde86e44d889474992ae70f71dcb611e46770bafd'
require(h.sha(B.read_bytes())==B_SHA,'Stage binding changed')
spec=importlib.util.spec_from_file_location('S01_native_configuration_binding',B)
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--stage',choices=['gain','speed','current'],required=True)
    cli.add_argument('--receipt',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args();A=S/b.EVENTS[args.stage];output=h.local(args.output)
    require(not output.exists() and h.sha(SOURCE.read_bytes())==SOURCE_SHA,'New output and frozen source required')
    refs={}
    def read(p):
        d,r=h.read_json(p);refs[str(p)]=r;return d
    rr,ready,mf,out=[read(p) for p in (args.receipt,L/'READY.json',A/'manifest.json',A/'outcome.json')]
    require(all(h.sha(h.local(L/n).read_bytes())==d for n,d in LOGGER_IDENTITY_PINS.items()),'Recorder identity changed')
    require(rr['recording_segment_id']=='R07' and rr['native_start_identity']==ready['native_start_identity']
            and read(A/'logger_ready_bound.json')==ready and mf['source_sha256']==SOURCE_SHA
            and mf['logger_source_sha256']==LOGGER_SHA and mf['event_id']==A.name
            and out['stage']==args.stage and out['status']=='Home_configuration_knownACK_exact_readback'
            and not out['writer_outcome_unknown'],'Known complete configuration required')
    expected=b.expected_fields({},args.stage);target=b.expected_fields({},args.stage,after=True)
    command,wanted,timeout=b.command(args.stage)
    fmt={'ZCtrl.GainSet':'>fff','Scan.SpeedSet':'>ffffHf','ZCtrl.SetpntSet':'>f'}[command]
    ev,eref=events(A/'events.jsonl',{'tcp_exchange','entry_Home_stability','immediate_before_configuration','after_configuration','post_configuration_Home'})
    writers=[e for e in ev if e['kind']=='tcp_exchange' and not e['command'].endswith('Get')]
    require(len(writers)==1 and writers[0]['command']==command and writers[0]['args']==wanted,'Unexpected writer count or values')
    e=writers[0];claim=read(A/'configuration_0.claim');ack=read(A/'configuration_0_ack.json')
    require(claim['source_sha256']==SOURCE_SHA and claim['command']==command and claim['args']==wanted
            and ack['command']==command and ack['values']==[] and not ack.get('warning')
            and e['status']=='ok' and not e.get('warning'),'Configuration claim/ACK differs')
    for key in ('request_header','request_body','response_header','response_body'):
        r=e[key];raw=h.local(A/r['path']).read_bytes()
        require(len(raw)==r['bytes'] and h.sha(raw)==r['sha256'],'Writer wire SHA differs')
        if key=='request_body':require(raw==struct.pack(fmt,*wanted),'Actual configuration body differs')
        if key=='response_body':require(raw==bytes(8),'Native ACK error')
    before=read(A/'before.json');after=read(A/'after.json');readback=read(A/'readback_0.json')
    require(all(before['values'][k]==v for k,v in expected.items())
            and all(after['values'][k]==readback['values'][k]==v for k,v in target.items()),'Exact setting readbacks differ')
    for state in [before['values'],after['values'],readback['values']]:
        b.check_home(state,state)
        require(state['ZCtrl.HomePropsGet'][1]==123.69999069505866e-9 and state['SafeTip.OnOffGet']==[0] and state['Bias.Get']==[-1.], 'Known Home reference/Bias/SafeTip differs')
    lev,lref=events(L/'events.jsonl',{'datalog_status'});anchors=log_anchors(lev,ready['native_start_identity'])
    def bound(lo,hi=None):
        v=bracket(anchors,lo,lo if hi is None else hi);require(v is not None,'Native counter bracket missing');return v
    entries=[r for r in ev if r['kind']=='entry_Home_stability'];posts=[r for r in ev if r['kind']=='post_configuration_Home']
    rb=[r for r in ev if r['kind']=='after_configuration'];require(entries and posts and len(rb)==1,'Recorded stability groups missing')
    bounds={'entry':bound(entries[0]['monotonic_ns']-round(entries[0]['duration_s']*1e9),entries[0]['monotonic_ns']),
            'configuration_and_first_readback':bound(claim['monotonic_ns'],rb[0]['monotonic_ns']),
            'post_stability_start':bound(posts[0]['monotonic_ns']),
            'after':bound(after['end']['monotonic_ns'])}
    first=bounds['entry']['before']['sample'];edge=bounds['configuration_and_first_readback']
    end=bounds['after']['after']['sample'];last=rr['complete_through_index']*BLOCK
    require(0<=first<=edge['before']['sample']<=edge['after']['sample']<=end<=last,'Incomplete or overlapping native bounds')
    arrays=[];files=[]
    for num in range(1,rr['complete_through_index']+1):
        name=f'{PREFIX}{num:05d}.dat';p=h.local(S/'native_R07'/name);meta=rr['files'][name];raw=p.read_bytes()
        require(meta['local_path']==str(p) and meta['rows']==BLOCK and len(raw)==meta['bytes'] and h.sha(raw)==meta['sha256']
                and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Closed native block not verified')
        arrays.append(h.parse_block(raw,BLOCK));files.append({'path':str(p),'sha256':meta['sha256'],'rows':BLOCK})
    data=np.concatenate(arrays);del arrays
    limits=sorted(v*1e9 for v in before['values']['ZCtrl.LimitsGet']);sp=target['ZCtrl.SetpntGet'][0]*1e12
    def describe(lo,hi):
        d=stats(data,lo,hi,sp,limits);d['setpoint_reference_pA']=sp
        if hi>lo:
            v=data[lo:hi];d['fraction_native_abs_current_below10pA']=float(np.mean(abs(v[:,0])<10.))
            d['maximum_raw_Z_deviation_from_Home_pm']=float(np.max(abs(v[:,2]-123.69999069505866))*1000)
            d['Bias_not_minus1V_samples']=int(np.count_nonzero(v[:,1]!=-1.))
        return d
    partitions=[('entry_before_configuration',first,edge['before']['sample']),
                ('configuration_and_readback_outer',edge['before']['sample'],edge['after']['sample']),
                ('post_readback_to_after_confirmation',edge['after']['sample'],end),
                ('post_stage_context_through_closed_receipt',end,last)]
    phases={k:describe(lo,hi) for k,lo,hi in partitions}
    require(sum(v['rows'] for v in phases.values())==last-first,'Unaccounted review rows')
    result={'scope':'Actual separate S01 Off/Home restoration. Near-zero current at Home is not stable tunnelling. Original induction failure remains unchanged.',
            'source_sha256':h.sha(Path(__file__).read_bytes()),'base_reviewer_source':{'path':str(BASE_REVIEWER),'sha256':BASE_REVIEWER_SHA},'control_source':{'path':str(SOURCE),'sha256':SOURCE_SHA},
            'stage':args.stage,'known_outcome':out,'actual_command':{'command':command,'args':wanted,'wire':e},
            'sources':refs,'native_sources':files,'action_events':eref,'logger_events':lref,'boundaries':bounds,'phases':phases,
            'ten_second_windows':[dict(phase=k,partial_tail=min(i+20000,hi)-i<20000,**describe(i,min(i+20000,hi)))
                                  for k,lo,hi in partitions for i in range(lo,hi,20000)],
            'limits':['Native DAT has no high-rate gain, speed, XY or setpoint channel. Configuration is established by actual wire and exact readback, not inferred from waveforms.',
                      'File counters and host reads are asynchronous. Outer boundary includes transition and uncertainty, not a hardware trigger.',
                      'The actual five-second checks establish sampled Off1/Home and low current. They are not engaged junction stability or a new image-quality claim.',
                      'Current thresholds are sampled descriptors, not calibrated analog peaks, instantaneous protection or a verdict on imaging quality. Historical100pA fields are not the200pA target band.']}
    with output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(str(output),h.sha(output.read_bytes()))


if __name__=='__main__':main()
