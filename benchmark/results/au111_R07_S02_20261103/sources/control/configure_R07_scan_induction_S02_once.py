#!/usr/bin/env python3
"""Plan by default. One independent R07 S02 GainSet or SpeedSet and exact readback."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import sys
import time
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parent
N=C.parent
BASE=C/'scan_full50nm_fast_R07_baseline_once.py'
BASE_SHA='afc4e361af8bbb9d6d6a59baad2ef5ade4d1151bee125047fca6545bdd9cdc95'
BIND=C/'R07_scan_induction_S02/stage_binding.py'
BIND_SHA='18c315fd74e33b782f2bbe35f71622fc6e8baed3f7486107c69773b9f6f82769'
GAIN=C/'R07_scan_induction/gain_codec_support.py'
GAIN_SHA='dbb76f29571fa9d4f4580ee5601dbb99f93d06f86ee70e3d8b1a0c561c3fe451'

def imported(path,digest,name):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise RuntimeError('Changed source '+str(path))
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
m=imported(BASE,BASE_SHA,'R07_S02_config_reads');b=m.b
ab=imported(BIND,BIND_SHA,'R07_S02_configuration_binding')
g=imported(GAIN,GAIN_SHA,'R07_S02_gain_codec')
PRIVATE_CALL=g.private_nanonis_call(b.p.NanonisClient.call)
STAGES=('configure_gain','configure_speed','restore_gain','restore_speed')

def configuration(stage):
    b.require(stage in STAGES,'Only four separately claimed configuration stages')
    before=ab.expected_fields(m.EXPECTED,stage);after=ab.expected_fields(m.EXPECTED,stage,after=True)
    if stage.endswith('gain'):
        command='ZCtrl.GainSet';args=after['ZCtrl.GainGet'];g.encode_gain_body(args)
    else:
        command='Scan.SpeedSet';speed=after['Scan.SpeedGet'];args=speed[:4]+[2,speed[5]]
    return before,after,command,args

class Client(b.Client):
    def __init__(self,store,command,args):
        super().__init__(store);self.timeout=.5;self.permit=None;self.used=False
        self.only_write=(command,args)
    def call(self,command,args=None,timeout=.5):
        args=[] if args is None else args
        if command in m.READ_ARGS and args==m.READ_ARGS[command]:pass
        elif command=='LockIn.ModOnOffGet' and args in ([1],[2]):pass
        else:
            b.require((command,args)==self.only_write and self.permit==(command,args) and not self.used and timeout==.7,
                      'Unclaimed/repeated/unreviewed configuration')
            self.used=True;self.permit=None
        self.connect_bound()
        return PRIVATE_CALL(self,command,args,timeout)

class Run(m.Run):
    def __init__(self,output,logger,fresh,fresh_sha,stage,source_sha,logger_sha):
        self.session,self.action,self.event='session_02','S02',ab.EVENTS[stage]
        self.stage=stage;self.source_path=Path(__file__);self.source_sha=source_sha;self.logger_source_sha=logger_sha
        self.expected,self.target,self.command,self.args=configuration(stage)
        self.store=b.Store(output);self.client=Client(self.store,self.command,self.args)
        self.logger,self.fresh,self.fresh_sha=Path(logger),Path(fresh),fresh_sha
        self.abort=self.unknown_execution=False;self.deadline=None
        self.last_logger_elapsed=self.logger_progress_time=None;self.ready=self.logger_start=None
        self.fixed_xy=None;self.stage_proof=None
    def config_guard(self,v):
        b.require(v['ZCtrl.OnOffGet']==[1] and v['ZCtrl.StatusGet']==[2] and v['Scan.StatusGet']==[0],'Known idle On2 required')
        for k in ('BiasSpectr.StatusGet','ZSpectr.StatusGet','AutoApproach.OnOffGet','FolMe.PSOnOffGet'):
            b.require(v[k]==[0],'Other native action active')
        b.require(v['SafeTip.OnOffGet']==[0] and v['Bias.Get']==[-1.],'Bias/SafeTip differs')
        current,z=v['Current.Get'][0],v['ZCtrl.ZPosGet'][0];target=self.expected['ZCtrl.SetpntGet'][0]
        b.require(b.finite(current) and abs(current)<400e-12 and -1.2*target<=current<=-.8*target,'Original signed20% /400pA config guard')
        hi,lo=m.EXPECTED['ZCtrl.LimitsGet'];b.require(b.finite(z) and lo+2e-9<=z<=hi-2e-9,'Original2nm Z endpoint guard')
        for k in m.FROZEN:b.require(v[k]==self.expected[k],'Configuration changed '+k)
        b.require(len(v['FolMe.XYPosGet'])==2 and all(b.finite(x) for x in v['FolMe.XYPosGet']),'Nonfinite or incomplete XY')
        if self.fixed_xy is not None:b.require(all(abs(x-y)<=2e-12 for x,y in zip(v['FolMe.XYPosGet'],self.fixed_xy)),'Fixed XY changed')
    def fresh_guard(self):
        raw=self.fresh.read_bytes();b.require(hashlib.sha256(raw).hexdigest()==self.fresh_sha,'Fresh SHA changed')
        record=json.loads(raw);age=(time.monotonic_ns()-record['end']['monotonic_ns'])/1e9
        b.require(0<=age<=180 and self.stage_proof['stage_review_monotonic_ns']<=record['start']['monotonic_ns']<=record['end']['monotonic_ns'],'Fresh read must follow stage review')
        self.fixed_xy=list(self.stage_proof['admission']['fixed_xy_m']);self.config_guard(record['values'])
        self.store.save('root_fresh_snapshot.json',record)
    def stable(self,label):
        since=previous=None
        while True:
            v=self.poll(label,full=True);self.config_guard(v);now=time.monotonic()
            b.require(previous is None or now-previous<=1.,'Original stability sample gap >1s')
            if since is None:since=now
            previous=now;self.logger_guard(0.,post_budget=40.,profile=True)
            if now-since>=5.:return v,now-since
            time.sleep(.1)
    def execute(self):
        out={'status':'not_started','stage':self.stage,'event_id':self.event,'acknowledged_writers':[],
             'writer_outcome_unknown':False,'automatic_retry':False,'automatic_restore':False}
        self.deadline=time.monotonic()+35.
        try:
            self.stage_proof=ab.validate_stage(ab.ADMISSION_PATH,ab.ADMISSION_SHA,self.stage,ab.REVIEW_PATH,ab.REVIEW_SHA)
            self.store.save('stage_evidence.json',self.stage_proof)
            self.store.save('stage_admission.json',ab.reserve_stage(self.session,self.action,self.stage,self.store.root,self.source_sha,self.fresh_sha))
            self.store.save('manifest.json',{**b.stamp(),**plan(self.stage),**m.sb.consumer_metadata(self.logger_source_sha),
                'source_sha256':self.source_sha,'session_id':self.session,'action_id':self.action,'event_id':self.event,
                'induction_admission':{'path':str(ab.ADMISSION_PATH),'sha256':ab.ADMISSION_SHA},
                'root_stage_review':{'path':str(ab.REVIEW_PATH),'sha256':ab.REVIEW_SHA}})
            self.fresh_guard();self.logger_guard(0.,post_budget=50.,profile=True)
            before,span=self.stable('entry_stability');self.store.save('before.json',{'values':before,'sampled_stable_s':span})
            v=self.poll('immediate_before_config',full=True);self.config_guard(v)
            self.logger_guard(0.,post_budget=40.,profile=True);self.check_abort()
            self.write(self.command,self.args,'configuration_0',timeout=.7)
            out['acknowledged_writers'].append(self.command)
            self.expected=self.target
            v=self.poll('after_config',full=True);self.config_guard(v)
            if self.command=='ZCtrl.GainSet':g.checked_readback(v['ZCtrl.GainGet'],self.target['ZCtrl.GainGet'])
            self.store.save('readback_0.json',{'values':v})
            after,span=self.stable('post_config_stability')
            self.store.save('after.json',{'end':b.stamp(),'values':after,'sampled_stable_s':span})
            out.update(status='configured_and_exact_readback_verified',sampled_post_stable_s=span,
                       target_fields={k:after[k] for k in ('ZCtrl.SetpntGet','ZCtrl.GainGet','Scan.SpeedGet','FolMe.SpeedGet')})
        except BaseException as exc:
            out.update(status='configuration_incomplete_or_rejected',error=str(exc),writer_outcome_unknown=self.unknown_execution,
                       no_subsequent_command_after_failure=True,root_fresh_read_required=True)
        finally:
            self.client.close();self.store.save('outcome.json',{**b.stamp(),**out})
        return 0 if out['status']=='configured_and_exact_readback_verified' else 1

def plan(stage):
    before,after,command,args=configuration(stage)
    return {'stage':stage,'event_id':ab.EVENTS[stage],'only_write':[command,args],
        'expected_before':before,'expected_after':after,'deadline_s':35.,'entry_and_post_stability_s':5.,
        'inherited_speed_lifecycle_source':'config_full50nm_speed_segment02_once.py',
        'physical_configuration_prescription_not_yet_validated':True,'automatic_chain':False,
        'unknown_failure':'No follow-up read, inverse setting, retry, On or other action after unknown write',
        'known_partial_state':'Known ACK plus failed readback is not successful configuration. Independent root review required.',
        'no_new_physical_damage_threshold':True}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--stage',choices=STAGES,required=True)
    for key in ('output','logger','fresh-snapshot','episode-admission','stage-review'):p.add_argument('--'+key,type=Path)
    for key in ('fresh-sha256','source-sha256','logger-source-sha256','episode-admission-sha256','stage-review-sha256'):p.add_argument('--'+key)
    a=p.parse_args()
    if not a.execute:print(json.dumps(plan(a.stage),indent=2));return 0
    b.require(all([a.output,a.logger,a.fresh_snapshot,a.fresh_sha256,a.source_sha256,a.logger_source_sha256,
                   a.episode_admission,a.episode_admission_sha256,a.stage_review,a.stage_review_sha256]),'Explicit source/fresh/stage bindings required')
    ab.validate_stage(a.episode_admission,a.episode_admission_sha256,a.stage,a.stage_review,a.stage_review_sha256)
    ab.paths('session_02','S02',a.stage,a.output,a.logger,a.fresh_snapshot,Path(__file__),a.source_sha256,a.logger_source_sha256)
    run=Run(a.output,a.logger,a.fresh_snapshot,a.fresh_sha256,a.stage,a.source_sha256,a.logger_source_sha256)
    handlers={s:signal.signal(s,lambda *_:setattr(run,'abort',True)) for s in (signal.SIGINT,signal.SIGTERM)}
    try:return run.execute()
    finally:
        for s,h in handlers.items():signal.signal(s,h)

if __name__=='__main__':raise SystemExit(main())
