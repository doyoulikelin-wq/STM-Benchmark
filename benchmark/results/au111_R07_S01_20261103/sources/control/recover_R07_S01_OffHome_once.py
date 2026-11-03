"""Plan by default. One independently selected known-S01-failure Home configuration write.
No On, XY, Scan, Pulse, TipShaper, coarse command, automatic inverse or chain.
"""
import argparse,hashlib,importlib.util,json,signal,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parent
PARENT=C/'configure_R07_scan_induction_S01_once.py';PARENT_SHA='b9bf1adb7540dfb30c4ba7d26b6392b7c666b2e4d2da9b9ffe94c77a8a102fdc'
BIND=C/'R07_scan_induction/offhome_recovery_binding.py';BIND_SHA='5d795aa0044b91d3cc642f21271872bddab3f4161bcdc77b7136d3a03be03a9d'
def imported(path,digest,name):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise RuntimeError('Frozen dependency changed '+str(path))
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
p=imported(PARENT,PARENT_SHA,'S01_existing_configuration_lifecycle');b=p.b;scan=p.m
h=imported(BIND,BIND_SHA,'S01_Home_recovery_gate')

class Client(p.Client):
    def __init__(self,store,command,args,timeout):super().__init__(store,command,args);self.only_timeout=timeout
    def call(self,command,args=None,timeout=.5):
        args=[] if args is None else args
        if command in scan.READ_ARGS and args==scan.READ_ARGS[command]:pass
        elif command=='LockIn.ModOnOffGet' and args in ([1],[2]):pass
        else:
            b.require((command,args)==self.only_write and self.permit==(command,args) and not self.used and timeout==self.only_timeout,
                      'Unclaimed/repeated/unreviewed Home recovery writer')
            self.used=True;self.permit=None
        self.connect_bound();return p.PRIVATE_CALL(self,command,args,timeout)

class Run(p.Run):
    def __init__(self,a,proof):
        self.session,self.action,self.event='session_02','S01_H01',h.EVENTS[a.stage];self.stage=a.stage
        self.source_path=Path(__file__);self.source_sha=a.source_sha256;self.logger_source_sha=h.normal.LOGGER_SHA
        self.expected=h.expected_fields(scan.EXPECTED,self.stage);self.target=h.expected_fields(scan.EXPECTED,self.stage,True)
        self.command,self.args,self.write_timeout=h.command(self.stage)
        self.store=b.Store(a.output);self.client=Client(self.store,self.command,self.args,self.write_timeout)
        self.logger,self.fresh,self.fresh_sha=a.logger,a.fresh_snapshot,a.fresh_sha256
        self.proof=proof;self.fixed_xy=list(proof['choice']['fixed_xy_m'])
        self.abort=self.unknown_execution=False;self.deadline=None
        self.last_logger_elapsed=self.logger_progress_time=None;self.ready=self.logger_start=None
    def config_guard(self,v):
        h.check_home(v,self.expected)
        for key in scan.FROZEN:b.require(v[key]==self.expected[key],'Known partial configuration changed '+key)
        b.require(all(abs(x-y)<=2e-12 for x,y in zip(v['FolMe.XYPosGet'],self.fixed_xy)),'Home recovery must not move XY')
    def fresh_guard(self):
        raw=self.fresh.read_bytes();b.require(hashlib.sha256(raw).hexdigest()==self.fresh_sha,'Fresh snapshot hash changed')
        record=json.loads(raw);age=(time.monotonic_ns()-record['end']['monotonic_ns'])/1e9
        b.require(0<=age<=180 and self.proof['choice']['monotonic_ns']<=record['start']['monotonic_ns']<=record['end']['monotonic_ns'],
                  'New full snapshot must follow independent Home stage choice')
        self.config_guard(record['values']);self.store.save('root_fresh_snapshot.json',record)
    def execute(self):
        out={'status':'not_started','stage':self.stage,'event_id':self.event,'acknowledged_writers':[],
             'writer_outcome_unknown':False,'automatic_retry':False,'automatic_restore':False,'automatic_chain':False}
        self.deadline=time.monotonic()+35.
        try:
            self.store.save('known_failure_and_root_choice.json',self.proof)
            self.store.save('stage_reservation.json',h.reserve(self.stage,self.source_sha,self.proof['root_choice']))
            self.store.save('manifest.json',{**b.stamp(),**plan(self.stage),**scan.sb.consumer_metadata(self.logger_source_sha),
                'source_sha256':self.source_sha,'session_id':self.session,'event_id':self.event,'root_choice':self.proof['root_choice'],
                'original_S01_admission':self.proof['choice']['original_S01_admission']})
            self.fresh_guard();self.logger_guard(0.,post_budget=50.,profile=True)
            before,span=self.stable('entry_Home_stability');self.store.save('before.json',{'values':before,'sampled_stable_s':span})
            v=self.poll('immediate_before_configuration',full=True);self.config_guard(v)
            self.logger_guard(0.,post_budget=40.,profile=True);self.check_abort()
            self.write(self.command,self.args,'configuration_0',timeout=self.write_timeout)
            out['acknowledged_writers'].append(self.command);self.expected=self.target
            v=self.poll('after_configuration',full=True);self.config_guard(v)
            if self.command=='ZCtrl.GainSet':p.g.checked_readback(v['ZCtrl.GainGet'],self.target['ZCtrl.GainGet'])
            self.store.save('readback_0.json',{'values':v})
            after,span=self.stable('post_configuration_Home');self.store.save('after.json',{'end':b.stamp(),'values':after,'sampled_stable_s':span})
            out.update(status='Home_configuration_knownACK_exact_readback',sampled_post_stable_s=span,
                       exact_restored_field=self.command,feedback_remained_Off1=True)
        except BaseException as exc:
            out.update(status='Home_configuration_incomplete_or_rejected',error=str(exc),writer_outcome_unknown=self.unknown_execution,
                       no_subsequent_command_after_failure=True,independent_root_review_required=True)
        finally:
            self.client.close();self.store.save('outcome.json',{**b.stamp(),**out})
        return 0 if out['status']=='Home_configuration_knownACK_exact_readback' else 1

def plan(stage):
    n,args,timeout=h.command(stage)
    return {'scope':'INACTIVE separately chosen known-Stop/Withdraw Home recovery','stage':stage,'event_id':h.EVENTS[stage],
        'only_write':[n,args],'writer_timeout_s':timeout,'expected_before':h.expected_fields({},stage),
        'expected_after':h.expected_fields({},stage,True),'entry_and_post_Home_observation_s':5.,'overall_deadline_s':35.,
        'home_criteria':'Off1 / absoluteHome within1pm / |I|<10pA / idle / fixedXY2pm and exact partial config',
        'no_On_XY_scan_pulse_shaper_coarse':True,'unknown_zero_followup':True,'known_ACK_wrong_readback_not_success':True,
        'one_recovery_write_only':True,'normal_S01_sources_unchanged':True,'prior_failed_induction_not_rewritten':True,
        'next_stage':'Not automatic. Root must review native evidence and independently choose a new stage.',
        'home_checks_not_engaged_Z_RMS_claim':True}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--stage',choices=h.STAGES,required=True);ap.add_argument('--execute',action='store_true')
    for key in ('output','logger','fresh-snapshot','admission'):ap.add_argument('--'+key,type=Path)
    for key in ('fresh-sha256','source-sha256','admission-sha256'):ap.add_argument('--'+key)
    a=ap.parse_args()
    if not a.execute:print(json.dumps(plan(a.stage),indent=2));return 0
    b.require(all(vars(a).values()),'Every explicit root source/admission/fresh binding required')
    b.require(h.local(a.output)==h.S/h.EVENTS[a.stage] and not a.output.exists() and not h.claim_path(a.stage).exists(),'Exact new Home stage output and unused reservation required')
    b.require(h.local(a.logger)==h.normal.LOGGER and h.sha(Path(__file__))==a.source_sha256,'Recorder/source differs')
    h.local(a.fresh_snapshot)
    proof=h.admission(a.admission,a.admission_sha256,a.stage,scan.EXPECTED,a.source_sha256)
    run=Run(a,proof);handlers={s:signal.signal(s,lambda *_:setattr(run,'abort',True)) for s in (signal.SIGINT,signal.SIGTERM)}
    try:return run.execute()
    finally:
        for s,handler in handlers.items():signal.signal(s,handler)
if __name__=='__main__':raise SystemExit(main())
