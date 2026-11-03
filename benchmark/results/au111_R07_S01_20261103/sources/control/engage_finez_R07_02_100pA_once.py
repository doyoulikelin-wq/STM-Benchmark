"""Plan-only by default. One fine-Z On at -1V/100pA/SafeTipOff; no scan/coarse/retry.
Only --execute loads the existing transport. Importing opens no device or output.
"""
import argparse, hashlib, importlib.util, json, os, signal, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parents[1] / 'stm_tip_benchmark_goal_20261030'
REF = ROOT / 'read_087_after_Home_move/snapshot.json'
LOGGER = ROOT.parent / 'session_02/logger_07'
OUTPUT = ROOT / 'engage_R07_02'
GLOBAL_CLAIM = ROOT.parent / 'claims/session_02__R07_fine_on02.claim'
LOGGER_SOURCE = ROOT / 'logger_fullcycle_segment07_observe_once.py'
LOGGER_SHA = '1e127682ad19e005660ff2d2d82ef132d468d2e3e786fd6afa15cbb4650967d0'
IDENTITY = {'session_id':'session_02','recording_segment_id':'R07','source_path':str(LOGGER_SOURCE),'source_sha256':LOGGER_SHA,'role':'fullcycle_native_logger'}
REF_SHA = '44f5962f36646ffb2fe4cd0eeb8146ce6a1fecb5777017769f09ffd08e40052b'
MOVE = ROOT / 'move_R07_home01'
MOVE_SOURCE = ROOT / 'move_R07_home_corner_once.py'
MOVE_SOURCE_SHA = 'f6f3c0c0c93521e3c0a9dd3d5db011f8494d271786ce16b0ad684363eb6917c3'
PRIOR_FINE = ROOT / 'engage_R07_01/outcome.json'
BASELINE_SOURCE_SHA = 'afc4e361af8bbb9d6d6a59baad2ef5ade4d1151bee125047fca6545bdd9cdc95'
HISTORY = ROOT / 'R07_fine_recovery/prior_fine02_claim_inventory.json'
HISTORY_SHA = '1f42e13a46e238a2f841b9af8fc21d1d6fe00f545c660b9a9d7a3e5c18dd6cd1'
RECOVERY_PINS = {Path(k):v for k,v in {'/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/move_R07_home01/outcome.json': '38fd4f5139c88f1dae4b131d5016434df964842fa1f07781c725205f42cd2de6', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/move_R07_home01/manifest.json': 'ba2b0084539d717f443af24e0a78aa8cc0cea4862e8caafa5ee1689ed811d652', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/move_R07_home01/move.claim': 'a1e58c03284d895e6cea5a3e954fc7b06fb31e956cdb31e1165b6c14308727d4', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/move_R07_home01/move_ack.json': 'c47297c9db31656b0d36ede196e5855cfc9f768aa2553c5b0768df427ede1b12', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/move_R07_home01/target_confirmed.json': '34710ac7257d52859ebaff712e51a06c2afdd53906eb17c8be7dc7a6bb82fe87', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/move_R07_home01/target_stable.json': '3994154aa664f727a829e47cd49b80493f2894d63b40fe409ef8714194e470e0', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/move_R07_home01/after.json': '8b8154782fe652428c556475ce3f4a62bb19f95e5a0f46967bdaf72efff51868', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/move_R07_home01/logger_ready_bound.json': 'c1c50e68c637cba2e77e6292ab84d764aec7af0475caf7e4aa4c36ba13acc3b7', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/move_R07_home01/logger_manifest_bound.json': '3352882ed403b994728a8105553e424f65f26616d198ba88ee43e194dd368ecf', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/move_R07_home01/admission_bound.json': 'fbbb027740f81e188804e08deea24bf1d35286ac22a5823d731ac9d76b8a736a', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/engage_R07_01/outcome.json': '840cc3888bb1a5b06811d2b2fe8bfac13c710e41321df4a72131cbe0368449c3', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/claims/session_02__R07_home_move01.claim': '4df4a4bae810e785a3b3a3957dbe85aba31e4597fe91930c80d1416b04103128', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/claims/session_02__R07_fine_on01.claim': '87cbe97631d9001c016160860f597fe57d76789d5987e3de5c125af14bd0b64a'}.items()}
PINS = {OLD/'conditioning_transport.py': '22228803ce76a0d99bd2993d16bdd807490621f3a6046cd876e916648d625b09',
        ROOT.parents[1]/'stm_tip_control_test_20261028/protocol.py': 'cb89eba6d0417b37b86ed593b9d85d96650ae5978d7d1e919b6a291e9ab2b742',
        ROOT.parents[1]/'stm_tip_control_test_20261028/catalog.json': 'f7637754438751ca52253f0884632d499202111140e945efaeaedbbb38a184ac',
        ROOT/'engage_finez_R03_100pA_once.py':'74bbc304b95417669624a8f5144fe481894393e370c4073a2bb350eaf56fc0cf',
        ROOT/'scan_full50nm_fast_R07_baseline_once.py':BASELINE_SOURCE_SHA,
        ROOT/'engage_finez_R07_100pA_once.py':'5586d4c64d9bbb6a188dc5f966c7b100371aa540126a0cf0f1961299ef2e4477',
        MOVE_SOURCE:MOVE_SOURCE_SHA,
        LOGGER_SOURCE:LOGGER_SHA,
        ROOT/'segment07_observe_binding.py':'7f6aa581f719a09b9433b06f5ed3d57d38a8c60f2346a1c36775b7e21edd7dbe'}
ON, WITHDRAW = ('ZCtrl.OnOffSet', [1]), ('ZCtrl.Withdraw', [1, 2000])
IDLE = ['Scan.StatusGet', 'AutoApproach.OnOffGet', 'BiasSpectr.StatusGet', 'ZSpectr.StatusGet', 'FolMe.PSOnOffGet']
LIVE = {'Current.Get', 'ZCtrl.OnOffGet', 'ZCtrl.StatusGet', 'ZCtrl.ZPosGet', 'SafeTip.SignalGet',
        'DataLog.StatusGet', 'DataLog.ChsGet', 'DataLog.PropsGet'}


def require(ok, message):
    if not ok: raise RuntimeError(message)


def prior_recovery():
    for path,digest in RECOVERY_PINS.items():
        require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Prior move/fine evidence changed '+str(path))
    require(hashlib.sha256(MOVE_SOURCE.read_bytes()).hexdigest()==MOVE_SOURCE_SHA,'Home move source changed')
    require(hashlib.sha256(HISTORY.read_bytes()).hexdigest()==HISTORY_SHA,'Prior claim inventory changed')
    rows=json.loads(HISTORY.read_bytes())['claim_refs'];expected={Path(r['path']) for r in rows}
    actual={p for folder in ('claims','globalclaims') for p in (ROOT.parent/folder).glob('*.claim')}
    require(actual==expected,'Unexpected new or removed writer reservation')
    for r in rows:require(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'],'Prior claim changed')
    first=json.loads(PRIOR_FINE.read_bytes())
    require(first['status']=='failed_after_known_On_ack' and first['stable'] is False and first['withdraw_home_confirmed'] is True
            and first['on_zero_error_ack'] is True,'Fine01 known failure not preserved')
    out=json.loads((MOVE/'outcome.json').read_bytes());manifest=json.loads((MOVE/'manifest.json').read_bytes())
    require(out['status']=='home_target_verified_5s_stationary' and out['writer_outcome_unknown'] is False
            and all(out[k] is True for k in ('move_attempted','asynchronous_move_ACK','target_confirmed','stable5s_confirmed'))
            and out['stop_attempted'] is False and out['stable_after_s']>=5.,'Home move not known complete')
    require(manifest['source_sha256']==MOVE_SOURCE_SHA and manifest['recording_segment_id']=='R07'
            and manifest['logger_source_sha256']==LOGGER_SHA,'Home move identity differs')
    claim=json.loads((MOVE/'move.claim').read_bytes());ack=json.loads((MOVE/'move_ack.json').read_bytes())
    require(claim['command']==ack['command']=='FolMe.XYPosSet' and claim['args']==[-25e-9,-25e-9,0]
            and ack['values']==[] and not ack.get('warning'),'Move command/ACK differs')
    after=json.loads((MOVE/'after.json').read_bytes());stable=json.loads((MOVE/'target_stable.json').read_bytes());r=json.loads(REF.read_bytes());v=r['values']
    require(first['monotonic_ns']<claim['monotonic_ns']<ack['monotonic_ns']<stable['monotonic_ns']<after['end']['monotonic_ns']<out['monotonic_ns']<r['start']['monotonic_ns'],'Home move/reference order differs')
    require(stable['stable_s']>=5. and all(abs(x+25e-9)<=20e-12 for x in out['actual_target_m'])
            and after['values']['FolMe.XYPosGet']==v['FolMe.XYPosGet']==out['actual_target_m']
            and after['values']['ZCtrl.OnOffGet']==[0] and after['values']['ZCtrl.StatusGet']==[1]
            and after['values']['ZCtrl.ZPosGet']==v['ZCtrl.HomePropsGet'][1:],'Verified Home target differs')
    return {'prior_fine01_outcome':{'path':str(PRIOR_FINE),'sha256':RECOVERY_PINS[PRIOR_FINE]},
            'known_Home_move_outcome':{'path':str(MOVE/'outcome.json'),'sha256':RECOVERY_PINS[MOVE/'outcome.json']},
            'known_Stop_and_Home':True,'R07_fine_attempts_before':1,'R07_fine_attempt_limit':2,
            'prior_claim_inventory_sha256':HISTORY_SHA,'pulse_used_preserved':5,'pulse_maximum_preserved':6,
            'fine01_failure_preserved':True,'no_XY_or_coarse_in_this_stage':True}


def reference():
    require(hashlib.sha256(REF.read_bytes()).hexdigest() == REF_SHA, 'Reference changed')
    v = json.loads(REF.read_bytes())['values']
    require(v['Bias.Get'] == [-1.] and v['ZCtrl.SetpntGet'] == [1.000000013351432e-10]
            and v['SafeTip.OnOffGet'] == [0] and v['ZCtrl.OnOffGet'] == [0]
            and v['ZCtrl.StatusGet'] == [1] and all(v[n] == [0] for n in IDLE), 'Wrong frozen starting state')
    prior_recovery()
    return v


def plan():
    return {'reference': str(REF), 'reference_sha256': REF_SHA, 'reference_structure': 'values',
            'independent_logger_directory': str(LOGGER),'recording_segment_id':'R07','output':str(OUTPUT),'single_attempt_claim':str(GLOBAL_CLAIM),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'history_boundary':'Fine01 failed and withdrew with known ACK. One separate Home move reached prior corner with known ACK and five-second stationary confirmation. Every claim and prior failure is preserved. One independently selected fine02 On here, no move/coarse/replay; success still needs a new full baseline.',
            'fine_ordinal_in_recovery':2,'fine_attempt_limit':2,'prior_recovery':prior_recovery(),
            'logger_nominal_duration':21600,'logger_instance_binding':'Freeze actual READY/start/manifest and same R07 instance as known Home move before transport',
            'normal_writer': ON, 'conditional_writer': WITHDRAW, 'temperature_K': None,
            'preflight': 'Fresh complete unchanged static state, Off1/absolute Home/|I|<10pA/all idle; native logger READY+fresh progress and >60s estimated coverage.',
            'observation_s': 30, 'final_stable_s': 5, 'signed_band_A': [-120e-12, -80e-12], 'Z_margin_m': 2e-9,
            'failure_conditions': '|sampled I|>=400pA/nonfinite; Z within2nm lower endpoint/outside physical range; no On2 after2s; final5s band/Z-margin not established after30s.',
            'cleanup': 'Only zero-error On command ACK permits one conditional Withdraw after fresh unchanged static/idle/Home/limits checks. Unknown/error/warning On ACK permits no subsequent command. No retry/reconnect/On/scan/coarse.',
            'ACK_limit': 'OnOffSet has no wait flag. ACK confirms command response, not successful engagement; realtime readback and30s observation separately establish sampled state.',
            'limits': 'Software polls are not transient protection. Logger timing estimate is not guaranteed coverage. No claim of clean tip/contact/repair or pulse budget consumed.',
            'source_pins': {str(k): v for k,v in PINS.items()}}


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
        'session_id':'session_02','recording_segment_id':'R07','fine_ordinal':2,'fine_attempt_limit':2,'prior_recovery':prior_recovery(),
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
    require(ready_sha==RECOVERY_PINS[MOVE/'logger_ready_bound.json'] and ready==prior
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
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--execute',action='store_true')
    ap.add_argument('--output',type=Path); ap.add_argument('--logger',type=Path); ap.add_argument('--source-sha256'); args=ap.parse_args()
    if not args.execute: reference(); print(json.dumps(plan(),indent=2)); return 0
    require(args.output and args.logger and args.source_sha256==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'Execute requires output/logger/exact source hash')
    output,logger=args.output.resolve(),args.logger.resolve()
    require(args.output.absolute()==output==OUTPUT and not output.exists(),'Only new exact C/engage_R07_02 output')
    require(not GLOBAL_CLAIM.exists(),'R07 fine On02 already reserved; no replay')
    require(logger==LOGGER and logger.is_dir(),'Only the explicitly selected independent logger directory is allowed')
    out=run(output,logger); print(json.dumps(out,indent=2)); return 0 if out['stable'] else 1


if __name__=='__main__': raise SystemExit(main())
