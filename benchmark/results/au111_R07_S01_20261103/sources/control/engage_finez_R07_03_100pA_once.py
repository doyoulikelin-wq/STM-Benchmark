"""Plan-only by default. One fine-Z On at -1V/100pA/SafeTipOff; no scan/coarse/retry.
Only --execute loads the existing transport. Importing opens no device or output.
"""
import argparse, hashlib, importlib.util, json, os, signal, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parents[1] / 'stm_tip_benchmark_goal_20261030'
REF = None
REF_SHA = None
ROOT_CHOICE_PATH = ROOT_CHOICE_SHA = None
LOGGER = ROOT.parent / 'session_02/logger_07'
OUTPUT = ROOT / 'engage_R07_03'
GLOBAL_CLAIM = ROOT.parent / 'claims/session_02__R07_fine_on03.claim'
LOGGER_SOURCE = ROOT / 'logger_fullcycle_segment07_observe_once.py'
LOGGER_SHA = '1e127682ad19e005660ff2d2d82ef132d468d2e3e786fd6afa15cbb4650967d0'
IDENTITY = {'session_id':'session_02','recording_segment_id':'R07','source_path':str(LOGGER_SOURCE),'source_sha256':LOGGER_SHA,'role':'fullcycle_native_logger'}
REBIND = ROOT / 'R07_scan_induction/post_S01_restoration_binding.py'
REBIND_SHA = '1bf262950f9ef26f562af3d1c1cd500eef77c00d1f6aeef317dfa5fc21c74be4'
if hashlib.sha256(REBIND.read_bytes()).hexdigest()!=REBIND_SHA:raise RuntimeError('Post-S01 restoration gate changed')
_spec=importlib.util.spec_from_file_location('fine03_postS01_evidence',REBIND);rb=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(rb)
MOVE=rb.MOVE_OUTPUT
PINS = {OLD/'conditioning_transport.py': '22228803ce76a0d99bd2993d16bdd807490621f3a6046cd876e916648d625b09',
        ROOT.parents[1]/'stm_tip_control_test_20261028/protocol.py': 'cb89eba6d0417b37b86ed593b9d85d96650ae5978d7d1e919b6a291e9ab2b742',
        ROOT.parents[1]/'stm_tip_control_test_20261028/catalog.json': 'f7637754438751ca52253f0884632d499202111140e945efaeaedbbb38a184ac',
        ROOT/'engage_finez_R07_02_100pA_once.py':'7a77ce1ef8689e26dd86f2a5615c1973a1cf7f5d12acf2f4c681c239b586e0af',
        rb.MOVE_SOURCE:'9b486103aae6f0a7310ba860d7901593004d80e7e124a69ab7736fb109cf859d',
        REBIND:REBIND_SHA,LOGGER_SOURCE:LOGGER_SHA,
        ROOT/'segment07_observe_binding.py':'7f6aa581f719a09b9433b06f5ed3d57d38a8c60f2346a1c36775b7e21edd7dbe'}
ON, WITHDRAW = ('ZCtrl.OnOffSet', [1]), ('ZCtrl.Withdraw', [1, 2000])
IDLE = ['Scan.StatusGet', 'AutoApproach.OnOffGet', 'BiasSpectr.StatusGet', 'ZSpectr.StatusGet', 'FolMe.PSOnOffGet']
LIVE = {'Current.Get', 'ZCtrl.OnOffGet', 'ZCtrl.StatusGet', 'ZCtrl.ZPosGet', 'SafeTip.SignalGet',
        'DataLog.StatusGet', 'DataLog.ChsGet', 'DataLog.PropsGet'}


def require(ok, message):
    if not ok: raise RuntimeError(message)


def prior_recovery():
    require(ROOT_CHOICE_PATH is not None and ROOT_CHOICE_SHA is not None,'Root choice must precede fine03')
    decision,proof=rb.choice(ROOT_CHOICE_PATH,ROOT_CHOICE_SHA,'fine03',hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    return {'root_choice':{'path':str(ROOT_CHOICE_PATH),'sha256':ROOT_CHOICE_SHA},'root_decision':decision,
            'known_restoration_and_Home_move':proof,'R07_fine_attempts_before':2,'fine_attempt_limit':3,
            'pulse_used_preserved':5,'pulse_maximum_preserved':6,'S01_incomplete_preserved':True,'no_retry_or_new_induction':True}

def reference():
    require(REF is not None and hashlib.sha256(REF.read_bytes()).hexdigest()==REF_SHA,'Fresh full reference required')
    record=json.loads(REF.read_bytes());v=record['values'];proof=prior_recovery();decision=proof['root_decision']
    age=(time.monotonic_ns()-record['end']['monotonic_ns'])/1e9
    require(0<=age<=180 and decision['monotonic_ns']<=record['start']['monotonic_ns']<=record['end']['monotonic_ns'],'Fresh read must follow root choice')
    previous=json.loads((MOVE/'after.json').read_bytes())['values']
    require(all(k in previous and previous[k]==v[k] for k in set(v)-LIVE),'Static full state differs from known Home move')
    require(v['Bias.Get']==[-1.] and v['ZCtrl.SetpntGet']==[1.000000013351432e-10] and v['SafeTip.OnOffGet']==[0]
            and v['ZCtrl.OnOffGet']==[0] and v['ZCtrl.StatusGet']==[1] and all(v[n]==[0] for n in IDLE),'Wrong original Off1 starting state')
    require(v['FolMe.XYPosGet']==proof['known_restoration_and_Home_move']['source_xy_m'],'Known corner changed')
    return v

def plan():
    return {'scope':'One independently selected fine03 after actual S01 failed induction and all original-parameter Home restorations',
        'reference':str(REF),'reference_sha256':REF_SHA,'recording_segment_id':'R07','output':str(OUTPUT),'single_attempt_claim':str(GLOBAL_CLAIM),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'fine_ordinal_in_recovery':3,'fine_attempt_limit':3,
        'prior_recovery':prior_recovery() if ROOT_CHOICE_PATH is not None else None,
        'normal_writer':ON,'conditional_writer':WITHDRAW,'logger_nominal_duration':21600,'observation_s':30,'final_stable_s':5,
        'signed_band_A':[-120e-12,-80e-12],'sampled_current_gate_A':400e-12,'Z_margin_m':2e-9,
        'unknown_On':'Zero subsequent commands, no retry','no_XY_coarse_scan_or_automatic_chain':True,
        'fine01_failure_and_S01_incomplete_preserved':True,'source_pins':{str(k):v for k,v in PINS.items()}}


def transport():
    for path, sha in PINS.items(): require(hashlib.sha256(path.read_bytes()).hexdigest() == sha, 'Dependency changed: '+str(path))
    spec = importlib.util.spec_from_file_location('engage_1101_transport', OLD/'conditioning_transport.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def reserve_on(stamp,logger_binding):
    GLOBAL_CLAIM.parent.mkdir(exist_ok=True)
    record={**stamp,'command':ON[0],'args':ON[1],'source':str(Path(__file__).resolve()),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'reference_sha256':REF_SHA,
        'logger_directory':str(LOGGER),'logger_source_sha256':LOGGER_SHA,'logger_ready_sha256':logger_binding['ready_sha256'],
        'logger_start_sha256':logger_binding['start_sha256'],'logger_native_start_identity':logger_binding['native_start_identity'],
        'session_id':'session_02','recording_segment_id':'R07','fine_ordinal':3,'fine_attempt_limit':3,'prior_recovery':prior_recovery(),
        'no_retry_or_release':True,'pulse_and_shaper_budgets_unchanged':True}
    fd=os.open(GLOBAL_CLAIM,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write((json.dumps(record,sort_keys=True,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno())
    fd=os.open(GLOBAL_CLAIM.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return {'path':str(GLOBAL_CLAIM),'sha256':hashlib.sha256(GLOBAL_CLAIM.read_bytes()).hexdigest()}


def bind_logger(logger):
    require(hashlib.sha256(LOGGER_SOURCE.read_bytes()).hexdigest()==LOGGER_SHA,'R07 logger source changed or unreviewed')
    require(not (logger/'outcome.json').exists(),'R07 logger ended')
    content={n:(logger/n).read_bytes() for n in ('READY.json','start.claim','manifest.json')}
    ready,start,manifest=[json.loads(content[n]) for n in ('READY.json','start.claim','manifest.json')]
    for doc in (ready,start,manifest):require(all(doc.get(k)==v for k,v in IDENTITY.items()),'R07 logger identity mismatch')
    ready_sha,start_sha,manifest_sha=[hashlib.sha256(content[n]).hexdigest() for n in ('READY.json','start.claim','manifest.json')]
    require(ready['ready'] is True and Path(ready['output_directory']).resolve()==logger and ready['native_duration_s']==21600,'Wrong R07 READY')
    require(ready['start_claim']['sha256']==start_sha and start['command']=='DataLog.Start' and start['args']==[],'R07 Start provenance mismatch')
    claim_path=Path(ready['start_claim']['path']);claim_path=claim_path if claim_path.is_absolute() else logger/claim_path
    require(claim_path.resolve()==logger/'start.claim','Wrong R07 Start claim path')
    require(isinstance(ready['native_start_identity'],str) and bool(ready['native_start_identity'])
            and ready['native_start_identity']==json.loads(REF.read_bytes())['values']['DataLog.StatusGet'][1],'R07 must match current reference Start')
    prior=json.loads((MOVE/'logger_ready_bound.json').read_bytes())
    require(ready_sha==hashlib.sha256((MOVE/'logger_ready_bound.json').read_bytes()).hexdigest() and ready==prior
            and start_sha==prior['start_claim']['sha256'],'R07 recording differs from known Home move instance')
    return {'ready_sha256':ready_sha,'start_sha256':start_sha,'manifest_sha256':manifest_sha,
            'native_start_identity':ready['native_start_identity'],'ready':ready,'start':start,'manifest':manifest}

class EngagementFailure(RuntimeError):
    pass


def run(output, logger, *, runtime=None, clock=time):
    base = reference(); static = sorted(set(base)-LIVE); logger_binding=bind_logger(logger)
    a = transport() if runtime is None else runtime
    reads = dict(a.READ_ARGS); reads['FolMe.XYPosGet'] = [0]
    for n, code in [('Util.RTFreqGet','f'), ('Util.RTOversamplGet','i'), ('Util.AcqPeriodGet','f')]:
        schema = {'inputs': [], 'outputs': [code], 'access': 'read'}
        if n not in a.p.COMMANDS: a.p.COMMANDS[n] = schema
        require(a.p.COMMANDS[n] == schema, 'Unexpected utility codec'); reads[n] = []
    for n, schema in [(ON[0], ['I']), (WITHDRAW[0], ['I','i'])]:
        require(a.p.COMMANDS[n]['inputs'] == schema and a.p.COMMANDS[n]['outputs'] == [], 'Unexpected writer codec')
    class Client(a.Client):
        def __init__(self, store):
            super().__init__(store); self.timeout=.5; self.permit=None; self.used=set()
        def call(self, n, args=None, timeout=.5):
            args=[] if args is None else args
            if (n,args) in (ON,WITHDRAW):
                require(self.permit==(n,args) and n not in self.used, 'Unclaimed/repeated writer')
                require(timeout == (.5 if n==ON[0] else 2.5), 'Unexpected writer timeout')
                self.used.add(n); self.permit=None
            else:
                require((n in reads and args==reads[n]) or (n=='LockIn.ModOnOffGet' and args in ([1],[2])), 'Only reviewed getters')
            self.connect_bound(); return a.p.NanonisClient.call(self,n,args,timeout)
    s=a.Store(output); s.save('logger_instance_bound.json',logger_binding); c=Client(s); attempted=False; on_ack=False; withdraw_attempted=False; abort=False
    deadline=clock.monotonic()+50.; cleanup=False
    out={'status':'not_started','stable':False,'automatic_retry':False,'temperature_K':None}
    def interrupted(*_):
        nonlocal abort; abort=True
    handlers={sig:signal.signal(sig,interrupted) for sig in (signal.SIGTERM,signal.SIGINT)}
    def q(n):
        require(clock.monotonic()<deadline, 'Query deadline reached')
        if not cleanup: require(not abort and not (s.root/'ABORT').exists(), 'Operator abort')
        name,args=('LockIn.ModOnOffGet',[int(n[-2])]) if n.startswith('LockIn.ModOnOffGet[') else (n,reads[n])
        r=c.call(name,args,.5); require(not r.get('warning'),'Native warning: '+n); return r['values']
    def capture(label):
        start=clock.monotonic(); v={n:q(n) for n in dict.fromkeys(static+['Current.Get','ZCtrl.OnOffGet','ZCtrl.StatusGet','ZCtrl.ZPosGet'])}
        s.save(label+'.json', {**a.stamp(),'values':v,'duration_s':clock.monotonic()-start,'sequential_not_atomic':True})
        require(clock.monotonic()-start<1., 'Read group exceeds1s'); return v
    def same(v):
        for n in static: require(v[n]==base[n], 'Changed static setting: '+n)
        require(all(v[n]==[0] for n in IDLE), 'Concurrent action; no writer')
    def home(v):
        return (v['ZCtrl.OnOffGet']==[0] and v['ZCtrl.StatusGet']==[1]
                and a.finite(v['Current.Get'][0]) and abs(v['Current.Get'][0])<10e-12
                and a.finite(v['ZCtrl.ZPosGet'][0]) and abs(v['ZCtrl.ZPosGet'][0]-base['ZCtrl.HomePropsGet'][1])<1e-12)
    def check(v):
        same(v); current=v['Current.Get'][0]; z=v['ZCtrl.ZPosGet'][0]; hi,lo=base['ZCtrl.LimitsGet']
        if not a.finite(current) or abs(current)>=400e-12: raise EngagementFailure('sampled_current_limit')
        if not a.finite(z) or not lo+2e-9<z<=hi: raise EngagementFailure('Z_margin_or_range')
    def write(pair,label):
        nonlocal attempted,on_ack,withdraw_attempted
        if pair==ON:
            require(not attempted,'On already claimed')
            s.save('episode_fine_reservation.json',reserve_on(a.stamp(),logger_binding)); attempted=True
        else: require(on_ack and not withdraw_attempted,'Withdraw forbidden/used'); withdraw_attempted=True
        s.save(label+'.claim',{**a.stamp(),'command':pair[0],'args':pair[1],'at_most_once':True})
        fd=os.open(s.root,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
        c.permit=pair
        try:
            result=c.call(*pair,timeout=.5 if pair==ON else 2.5)
            s.save(label+'_ack.json',{**a.stamp(),**result})
            require(result['values']==[] and not result.get('warning'),'Nonempty/warning ACK')
        except BaseException as exc:
            s.save(label+'_error.json',{**a.stamp(),'error':str(exc),'outcome_unknown':True}); raise
        if pair==ON: on_ack=True
    def logger_guard(min_remaining):
        require(not (logger/'outcome.json').exists(),'Logger ended')
        ready=json.loads((logger/'READY.json').read_bytes()); start=json.loads((logger/'start.claim').read_bytes())
        manifest=json.loads((logger/'manifest.json').read_bytes())
        require(hashlib.sha256(LOGGER_SOURCE.read_bytes()).hexdigest()==LOGGER_SHA,'R07 logger source changed')
        require(hashlib.sha256((logger/'READY.json').read_bytes()).hexdigest()==logger_binding['ready_sha256']
                and hashlib.sha256((logger/'start.claim').read_bytes()).hexdigest()==logger_binding['start_sha256']
                and hashlib.sha256((logger/'manifest.json').read_bytes()).hexdigest()==logger_binding['manifest_sha256'],'R07 recording instance changed')
        for doc in (manifest,ready,start):require(all(doc.get(k)==v for k,v in IDENTITY.items()),'R07 logger source/session/segment binding differs')
        require(start.get('command')=='DataLog.Start' and start.get('args')==[] and ready.get('native_start_identity')==logger_binding['native_start_identity'],'Wrong R07 Start claim')
        require(ready['ready'] is True and Path(ready['output_directory']).resolve()==logger
                and hashlib.sha256((logger/'start.claim').read_bytes()).hexdigest()==ready['start_claim']['sha256'],'Logger provenance')
        with (logger/'events.jsonl').open('rb') as f:
            f.seek(max(0,f.seek(0,2)-200000)); lines=f.read().splitlines()
        event=None
        for line in reversed(lines):
            try: row=json.loads(line)
            except ValueError: continue
            if row.get('kind')=='datalog_status': event=row; break
        require(event is not None and 0<=(clock.monotonic_ns()-event['monotonic_ns'])/1e9<=2
                and event['raw_values'][1]==ready['native_start_identity'] and not event['raw_values'][6],'Logger stale/not active')
        require(set(ready['profile'])=={'DataLog.ChsGet','DataLog.PropsGet','Util.RTFreqGet','Util.RTOversamplGet','Util.AcqPeriodGet'},'Logger profile keys')
        for n,v in ready['profile'].items(): require(q(n)==v,'Logger profile changed: '+n)
        require(ready['profile']['DataLog.ChsGet']==[6,[0,24,30,98,99,100]],'Wrong native channels')
        require(ready['profile']['DataLog.PropsGet'][:5]==[1,6,0,0.,1],'Wrong R07 timed profile')
        for n in ('Util.RTFreqGet','Util.RTOversamplGet','Util.AcqPeriodGet'): require(ready['profile'][n]==base[n],'Sampling changed')
        raw=q('DataLog.StatusGet'); clock.sleep(.1); fresh=q('DataLog.StatusGet')
        require(raw[1]==fresh[1]==ready['native_start_identity'] and not raw[6] and not fresh[6]
                and (raw[2:5]!=fresh[2:5] or raw[-1]!=fresh[-1]),'No fresh native logger progress')
        duration=ready['native_duration_s']; age=(clock.monotonic_ns()-start['monotonic_ns'])/1e9
        elapsed=fresh[2]*3600+fresh[3]*60+fresh[4]
        require(duration == 21600 and a.finite(elapsed) and elapsed>=0 and age>=0,'Logger duration/age')
        remaining=min((duration-elapsed)/2,duration/2-age)
        require(remaining>min_remaining and not (logger/'outcome.json').exists(),'Insufficient logger coverage')
        s.event('logger_admission',native=fresh,estimated_remaining_s=remaining,coverage_guaranteed=False)
    try:
        s.save('manifest.json',{**a.stamp(),**plan(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        v=capture('before'); check(v); require(home(v),'Not withdrawn Off1/Home')
        require(base['ZCtrl.HomePropsGet']==[0,base['ZCtrl.LimitsGet'][0]],'Unreviewed Home')
        logger_guard(60.)
        v=capture('immediate_before'); check(v); require(home(v),'Withdrawn state changed before On')
        write(ON,'feedback_on'); start=clock.monotonic(); stable=previous=None; count=0; last_logger=start
        while clock.monotonic()-start<30.:
            v=capture('observation_%03d'%count); check(v); now=clock.monotonic(); count+=1
            is_on=v['ZCtrl.OnOffGet']==[1] and v['ZCtrl.StatusGet']==[2]
            if not is_on and now-start>=2.: raise EngagementFailure('feedback_not_On2_after2s')
            hi,lo=base['ZCtrl.LimitsGet']; z=v['ZCtrl.ZPosGet'][0]
            good=is_on and -120e-12<=v['Current.Get'][0]<=-80e-12 and lo+2e-9<z<hi-2e-9
            stable=(now if stable is None or (previous is not None and now-previous>1) else stable) if good else None
            previous=now
            if now-last_logger>=2.: logger_guard(5.); last_logger=clock.monotonic()
            clock.sleep(.1)
        if stable is None or previous-stable<5.: raise EngagementFailure('final5s_stability_timeout')
        v=capture('after'); check(v)
        if not (v['ZCtrl.OnOffGet']==[1] and v['ZCtrl.StatusGet']==[2]
                and -120e-12<=v['Current.Get'][0]<=-80e-12
                and base['ZCtrl.LimitsGet'][1]+2e-9<v['ZCtrl.ZPosGet'][0]<base['ZCtrl.LimitsGet'][0]-2e-9):
            raise EngagementFailure('final_stable_readback_failed')
        out.update(status='tunneling_reestablished',stable=True,sampled_stable_s=previous-stable,samples=count,observation_elapsed_s=clock.monotonic()-start)
    except BaseException as exc:
        out.update(status='failed_after_known_On_ack' if on_ack else ('unknown_On_outcome_no_retry' if attempted else 'rejected_before_On'),error=str(exc))
        if attempted and not on_ack: out['cleanup_withheld']='On outcome unknown; no subsequent command'
        elif on_ack and isinstance(exc,EngagementFailure) and not c._closed:
            try:
                cleanup=True; deadline=clock.monotonic()+10.
                v=capture('withdraw_admission'); same(v)
                if not home(v): write(WITHDRAW,'failure_withdraw')
                since=previous=None; n=0
                while clock.monotonic()<deadline:
                    v=capture('withdraw_verify_%03d'%n); same(v); now=clock.monotonic(); n+=1
                    since=(now if since is None or (previous is not None and now-previous>1) else since) if home(v) else None
                    previous=now
                    if since is not None and now-since>=3.: out['withdraw_home_confirmed']=True; break
                    clock.sleep(.1)
                require(out.get('withdraw_home_confirmed'), 'No3s Off1/Home verification')
            except BaseException as failure: out['withdraw_error']=str(failure)
        elif on_ack: out['cleanup_withheld']='No automatic Withdraw for changed settings, logger/transport/audit failure or abort; root review required'
    finally:
        out.update(on_attempted=attempted,on_zero_error_ack=on_ack,withdraw_attempted=withdraw_attempted)
        c.close(); s.save('outcome.json',{**a.stamp(),**out})
        for sig,handler in handlers.items(): signal.signal(sig,handler)
    return out


def main():
    global REF,REF_SHA,ROOT_CHOICE_PATH,ROOT_CHOICE_SHA
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--execute',action='store_true')
    for key in ('output','logger','fresh-snapshot','admission'):ap.add_argument('--'+key,type=Path)
    for key in ('source-sha256','fresh-sha256','admission-sha256'):ap.add_argument('--'+key)
    args=ap.parse_args()
    if not args.execute:print(json.dumps(plan(),indent=2));return 0
    require(all(vars(args).values()) and args.source_sha256==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'All root/fresh/source bindings required')
    output,logger=args.output.resolve(),args.logger.resolve()
    require(args.output.absolute()==output==OUTPUT and not output.exists() and not GLOBAL_CLAIM.exists(),'Only exact unused fine03 output/claim')
    require(logger==LOGGER and logger.is_dir(),'Only selected R07 recorder')
    REF=rb.local(args.fresh_snapshot);REF_SHA=args.fresh_sha256
    ROOT_CHOICE_PATH=rb.local(args.admission);ROOT_CHOICE_SHA=args.admission_sha256
    reference()
    out=run(output,logger);print(json.dumps(out,indent=2));return 0 if out['stable'] else 1
if __name__=='__main__':raise SystemExit(main())
