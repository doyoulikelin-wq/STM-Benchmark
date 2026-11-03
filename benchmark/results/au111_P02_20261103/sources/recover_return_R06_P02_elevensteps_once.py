#!/usr/bin/env python3
"""Offline plan by default. Independent P02 known-ACK recovery return stage; root alone executes.

Only fixed ZCtrl.SetpntSet writes; NO On, Withdraw, Scan, retry or rollback.
Software gates are engineering review criteria, not instantaneous protection.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import struct
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = HERE / 'scan_full50nm_fast_R06_baseline_once.py'
SOURCE_SHA = 'f55c58f30a29d9f5ebf908c49298e81d857878e4c1954b1e3a895a4f4803558d'
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA:
    raise RuntimeError('Frozen current50nm source changed')
spec = importlib.util.spec_from_file_location('setpoint_frozen_capture', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
b = m.b
ORIGINAL_SOURCE=ROOT/'setpoint_fullcycle_100pA_1nA_once.py'
ORIGINAL_SOURCE_SHA='7d537f110631e5d73fdc6ee7336a1ec077088705f0e455183def442f6889bbb4'
if hashlib.sha256(ORIGINAL_SOURCE.read_bytes()).hexdigest()!=ORIGINAL_SOURCE_SHA:raise RuntimeError('Original action source changed')
BINDINGS_SOURCE = HERE / 'action_bindings_R06_induction_P02.py'
BINDINGS_SHA = 'fcce265d1abfe23f4d677ef286b9d4d8dbf1f28fc138bd650a1d5b2cf8e73eb6'
if hashlib.sha256(BINDINGS_SOURCE.read_bytes()).hexdigest() != BINDINGS_SHA:
    raise RuntimeError('Frozen local action bindings changed')
_binding_spec = importlib.util.spec_from_file_location('five_session_action_bindings', BINDINGS_SOURCE)
ab = importlib.util.module_from_spec(_binding_spec)
_binding_spec.loader.exec_module(ab)
b.require({k:b.p.COMMANDS['ZCtrl.SetpntSet'][k] for k in ['inputs','outputs','access']} == {'inputs': ['f'], 'outputs': [], 'access': 'write'}, 'Setpoint setter codec changed')
b.require({k:b.p.COMMANDS['ZCtrl.SetpntGet'][k] for k in ['inputs','outputs','access']} == {'inputs': [], 'outputs': ['f'], 'access': 'read'}, 'Setpoint getter codec changed')
PA = [100 * 1.25**k for k in range(11)] + [1000.]
TARGETS = [struct.unpack('>f', struct.pack('>f', x * 1e-12))[0] for x in PA]
FROZEN = [k for k in m.FROZEN if k != 'ZCtrl.SetpntGet']
TOTAL_DEADLINE = 225.
LOGGER_MARGIN = 15.
STEP_WINDOW = 15.
STABLE_S = 5.
FINAL_S = 30.
Z_MARGIN = 2e-9
STEP_Z = 100e-12
TOTAL_DOWN_Z = 500e-12
XY_TOL = 2e-12


def sequence(mode):
    b.require(mode == 'recover_return', 'Only independent P02 known-ACK recovery return allowed')
    return list(reversed(TARGETS))


RECOVERY_EVENT = 'recovery_return_P02_01'
RECOVERY_OUTPUT = ROOT / 'session_02' / RECOVERY_EVENT
RECOVERY_CLAIM = ROOT / 'globalclaims' / ('session_02__' + RECOVERY_EVENT + '.claim')
RECOVERY_ADMISSION = ROOT / 'session_02' / (RECOVERY_EVENT + '.admission.json')
RECOVERY_ADMISSION_SHA = None
PARENT_SOURCE = HERE / 'setpoint_R06_induction_P02_once.py'
PARENT_SHA = 'd0bdb34e6d44f946352b4111e8306568e2b3a1511b6f998f7cec9c6b831b5a65'
PULSE_SOURCE = HERE / 'pulse_R06_induction_P02_once.py'
PULSE_SHA = 'e9ca1fd00da56dfc11c26b95d22e5f5ab6346a8bda3600c8f1e1fa46bb032998'
PULSE_DIR = ROOT / 'session_02/pulse_induction_P02'
ORIGINAL_ADMISSION = ROOT / 'session_02/induction_R06_P02.admission.json'
PULSE_CLAIM = ROOT / 'globalclaims/continuing_20261101_1939__pulse_04.claim'
READONLY_DIR = HERE / 'R06_pulse_P02/independent_readonly_recovery30'
FIXED_XY = [-2.5000000292152436e-8, -2.5000000292152436e-8]
PROOF_PINS = {'/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/setpoint_R06_induction_P02_once.py': 'd0bdb34e6d44f946352b4111e8306568e2b3a1511b6f998f7cec9c6b831b5a65', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/pulse_R06_induction_P02_once.py': 'e9ca1fd00da56dfc11c26b95d22e5f5ab6346a8bda3600c8f1e1fa46bb032998', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/induction_R06_P02.admission.json': '8cc618848b743205903517d574a35b1b74f0b7d0cd4befec74596e719c3b4e86', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/induction_P02.ledger.json': '585533a6565c663d96b49805a9492f37f59d1075d10c106bd01522c8710c7fa5', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/globalclaims/continuing_20261101_1939__pulse_04.claim': 'cffc21a6480e6a16b05caafdd53f63de9e126b4dc75e147c8c38ebd88ea85167', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/pulse_induction_P02/outcome.json': '61d379cd5d78590392b64b81273ab10fa4643e16c25cb6503a9008e4458d4bc9', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/pulse_induction_P02/manifest.json': 'd6df4443895cb802fa94dfdd894e13c4b3e8e533543e4d549b8db92032ef161a', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/pulse_induction_P02/pulse.claim': '41f75fdd19253c9c8cd96be76e054831adb69563ec97287fe7cf7d00aad44ace', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/pulse_induction_P02/pulse_ack.json': '27ab8cb6b3b85777ed44d77f0aec3e2d43912b2e316dda0de79cdce0fa6c16c5', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/pulse_induction_P02/session_reservation.json': 'd77383b2460c6ee0967926d0235a26f36b91c409e07dbcb02a5375b7f028b291', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/pulse_induction_P02/immediate_after.json': 'e457bb9d1246a6b4deef009511f65d21983ddac2ea5484ac4bbb85f82dceaca8', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/pulse_induction_P02/exception_recheck_00.json': '831a8fa71e257d1208b20be68ed1493c8808d38bd3034a594f37ced48b25072d', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/pulse_induction_P02/logger_ready_bound.json': '463890eb80aae4f6889e35d1c5c8db72c96f5a74fba28b01180b56f956cc7b10', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/prepare_induction_P02/outcome.json': '48a86da8e9ebc8e7bdaacf13b22ff0fa56fe1502ff42d6385e470f8cada571e0', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/prepare_induction_P02/manifest.json': '4f603a98439bbe2d10db0b53f13957c74b9e750c3ab3b204aa2c0b8f4126a733'}


def artifact_ref(path):
    return {'path':str(path), 'sha256':ab.sha(path)}


def pulse_module():
    b.require(ab.sha(PARENT_SOURCE) == PARENT_SHA and ab.sha(PULSE_SOURCE) == PULSE_SHA, 'Frozen physical sources changed')
    sp=importlib.util.spec_from_file_location('P02_recovery_original_pulse_guard',PULSE_SOURCE)
    pm=importlib.util.module_from_spec(sp);sp.loader.exec_module(pm)
    return pm


def known_pulse_proof():
    for p,h in PROOF_PINS.items():
        b.require(ab.sha(Path(p))==h,'Immutable actual P02 evidence changed: '+p)
    docs={n:json.loads((PULSE_DIR/n).read_bytes()) for n in ('outcome.json','manifest.json','pulse.claim','pulse_ack.json','session_reservation.json','immediate_after.json','exception_recheck_00.json')}
    out,mf,claim,ack=(docs[n] for n in ('outcome.json','manifest.json','pulse.claim','pulse_ack.json'))
    old=json.loads(ORIGINAL_ADMISSION.read_bytes())
    old_ref={'path':str(ORIGINAL_ADMISSION),'sha256':PROOF_PINS[str(ORIGINAL_ADMISSION)]}
    ab.ra.history_guard('return',old_ref['sha256'])  # Counts/history only: does not reinterpret failed recovery.
    b.require(mf['source_sha256']==PULSE_SHA and mf['induction_admission']==old_ref
              and mf['session_id']=='session_02' and mf['action_id']=='P02','Actual P02 source/identity differs')
    b.require(out['status']=='uncertain_or_recovery_failed' and out['error']=='Not known On2/allidle'
              and out['pulse_attempted'] is True and out['native_end_confirmed'] is True
              and out['writer_outcome_unknown'] is False and out['fault_not_persistent'] is True
              and out['pulse_ordinal']==4 and out['return_to100pA_performed'] is False,'Original P02 failure must remain intact and execution known')
    b.require(claim['command']=='Bias.Pulse' and claim['args']==ab.ra.REQUEST and ack['values']==[] and not ack.get('warning'),
              'Need exact waiting known pulse ACK')
    b.require(sorted(p.name for p in PULSE_DIR.glob('*.claim'))==['pulse.claim'],'Unexpected extra physical writer in failed pulse stage')
    shared=json.loads(PULSE_CLAIM.read_bytes())
    b.require(shared==docs['session_reservation.json'] and shared['source_sha256']==PULSE_SHA and shared['pulse_ordinal']==4
              and shared['pulse_attempts_before']==3 and shared['ledger_sha256']==claim['ledger_sha256']==mf['ledger_sha256']
              and shared['induction_admission_sha256']==old_ref['sha256'],'Known ordinal4 provenance differs')
    v=docs['immediate_after.json']['values'];rechecked=docs['exception_recheck_00.json']['values']
    b.require(v['ZCtrl.OnOffGet']==[1] and v['ZCtrl.StatusGet']==[3] and rechecked['ZCtrl.OnOffGet']==[1]
              and rechecked['ZCtrl.StatusGet']==[2] and v['FolMe.XYPosGet']==rechecked['FolMe.XYPosGet']==FIXED_XY,
              'Actual Hold then On2 observation differs')
    b.require(shared['monotonic_ns']<=claim['monotonic_ns']<=ack['monotonic_ns']
              <=docs['immediate_after.json']['start']['monotonic_ns']<=out['monotonic_ns'],'Known pulse chronology differs')
    b.require(not (ROOT/'session_02/return_induction_P02').exists()
              and not (ROOT/'globalclaims/session_02__return_induction_P02.claim').exists(),
              'Original happy-path return already attempted; no second return')
    ready=json.loads((m.sb.LOGGER_DIR/'READY.json').read_bytes())
    m.sb.verify_logger_identity(ready,m.LOGGER_SOURCE_SHA)
    b.require(json.loads((PULSE_DIR/'logger_ready_bound.json').read_bytes())==ready
              and all(mf.get(k)==value for k,value in m.sb.consumer_metadata(m.LOGGER_SOURCE_SHA).items()),'P02 native identity differs')
    return {'failed_pulse_outcome':artifact_ref(PULSE_DIR/'outcome.json'),
            'pulse_claim':artifact_ref(PULSE_CLAIM),'original_admission':old_ref,
            'proof_pins':PROOF_PINS,'fixed_xy_m':FIXED_XY,'pulse_attempts_total':4,
            'original_post_guard_succeeded':False,'native_pulse_end_known':True,
            'latest_known_history_monotonic_ns':out['monotonic_ns']}


def readonly_recovery_proof(out_ref,samples_ref,after_ns):
    out=ab.artifact(out_ref,READONLY_DIR/'outcome.json')
    samples=ab.artifact(samples_ref,READONLY_DIR/'samples.json')
    b.require(out['status']=='completed_readonly_30s_original_guards' and out['readonly'] is True
              and out['writes']==[] and out['duration_s']>=30.
              and out['original_failure_preserved'] is True and out['original_pulse_source_sha256']==PULSE_SHA,
              'Independent read-only thirty-second recovery incomplete')
    b.require(isinstance(samples,list) and len(samples)>=20 and out['samples']==len(samples),'Full raw read-only recovery samples required')
    ready=json.loads((m.sb.LOGGER_DIR/'READY.json').read_bytes())
    pm=pulse_module();dummy=object.__new__(pm.Run);dummy.xy=FIXED_XY
    rows=[];previous=after_ns;sample_refs=[]
    for idx,row in enumerate(samples):
        snapshot_ref={'path':row['snapshot'],'sha256':row['sha256']}
        p=Path(snapshot_ref['path']);b.require(p==READONLY_DIR/f'read_{idx:03d}'/'snapshot.json','Recovery snapshot sequence/path differs')
        v=ab.artifact(snapshot_ref,p)
        b.require(previous<=v['start']['monotonic_ns']<=v['end']['monotonic_ns']<=out['monotonic_ns'], 'Read-only recovery chronology differs')
        previous=v['end']['monotonic_ns']
        status=v['values']['DataLog.StatusGet']
        b.require(len(status)==10 and status[1]==ready['native_start_identity'] and not status[6], 'Recovery observation belongs to different/ended native recording')
        pm.Run.guard(dummy,v['values'],full=True,entry=True)  # Original physical state/1nA current and 5nm margin, read-only call.
        b.require(v['values']['FolMe.XYPosGet']==FIXED_XY and row['I_A']==v['values']['Current.Get'][0]
                  and row['Z_m']==v['values']['ZCtrl.ZPosGet'][0], 'Recovery samples not derived from bound actual full reads')
        rows.append({'t':v['end']['monotonic_ns']/1e9,'I_A':row['I_A'],'Z_m':row['Z_m']})
        sample_refs.append(snapshot_ref)
    b.require(rows[-1]['t']-rows[0]['t']>=30. and max(y['t']-x['t'] for x,y in zip(rows,rows[1:]))<=1.,
              'Need uninterrupted sampled thirty-second window with <=1s gaps')
    b.require(out['last_snapshot']==sample_refs[-1]['path'] and out['last_snapshot_sha256']==sample_refs[-1]['sha256'], 'Readonly final snapshot differs')
    metrics=pm.trend(rows)
    b.require(abs(metrics['Z_slope_m_per_s'])<=10e-12 and metrics['Z_detrended_RMS_m']<=10e-12,
              'Original last10s Z recovery gates failed')
    return {'outcome':out_ref,'samples':samples_ref,'snapshots':sample_refs,
            'recomputed_from_snapshot_completion_times':metrics,'last_snapshot_ns':previous,
            'completed_ns':out['monotonic_ns'],'sampled_only_not_native_peak_bound':True}


def recovery_admission(digest):
    b.require(digest and ab.sha(RECOVERY_ADMISSION)==digest, 'Explicit independent recovery decision/hash required')
    j=json.loads(RECOVERY_ADMISSION.read_bytes());proof=known_pulse_proof()
    b.require(j['schema']=='R06-P02-knownACK-recovery-return-v1' and j['session_id']=='session_02'
              and j['action_id']=='P02' and j['event_id']==RECOVERY_EVENT and j['recording_segment_id']=='R06'
              and j['source_sha256']==ab.sha(Path(__file__)), 'Independent recovery identity/source differs')
    b.require(j['root_reviewed_one_recovery'] is True and j['exclusive_root_writer'] is True
              and j['stop_requested'] is False and j['unresolved_previous_execution'] is False
              and j['no_unplanned_intervention_since_pulse'] is True, 'Root ownership/unplanned history unresolved')
    b.require(j['max_attempts']==1 and type(j['max_attempts']) is int and j['no_automatic_retry'] is True
              and j['new_pulse_permitted'] is False and j['pulse_attempts_total']==4 and j['pulse_count_reset'] is False
              and j['purpose']=='independent_reduce_known_1nA_after_P02_to100pA'
              and j['original_pulse_status_preserved']=='uncertain_or_recovery_failed'
              and j['original_post_guard_succeeded'] is False, 'Recovery must preserve failure and ordinal4')
    b.require(j['starting_target_A']==TARGETS[-1] and j['SetpntSet_targets_A']==sequence('recover_return')[1:]
              and j['failed_pulse_outcome']==proof['failed_pulse_outcome'] and j['proof_pins']==PROOF_PINS
              and j['fixed_xy_m']==FIXED_XY,'Exact eleven descending targets/history required')
    observed=readonly_recovery_proof(j['readonly_recovery_outcome'],j['readonly_recovery_samples'],proof['latest_known_history_monotonic_ns'])
    native=ab.ra.native_review(j['native_recovery_review'],proof['failed_pulse_outcome'],observed['completed_ns'])
    b.require(native['allow_one_independent_recovery_return'] is True
              and native['readonly_recovery_outcome']==j['readonly_recovery_outcome']
              and native['original_pulse_status_preserved']=='uncertain_or_recovery_failed', 'Independent recovery native decision missing')
    b.require(native['monotonic_ns']<=j['monotonic_ns']<=time.monotonic_ns() and j['reason'],'Recovery decision predates observation/native audit')
    proof.update(readonly_recovery=observed,native_recovery_review=j['native_recovery_review'],latest_known_history_monotonic_ns=j['monotonic_ns'])
    return j,proof


def reserve_recovery(output,source_sha,fresh_sha):
    b.require(Path(output).resolve()==RECOVERY_OUTPUT and source_sha==ab.sha(Path(__file__)), 'Independent recovery output/source differs')
    recovery_admission(RECOVERY_ADMISSION_SHA)
    return ab.exclusive(RECOVERY_CLAIM,{**b.stamp(),'session_id':'session_02','action_id':'P02','event_id':RECOVERY_EVENT,
        'output':str(output),'source_sha256':source_sha,'fresh_snapshot_sha256':fresh_sha,
        'recovery_admission_sha256':RECOVERY_ADMISSION_SHA,'purpose':'independent_reduce_known_1nA_after_P02_to100pA',
        'one_attempt_no_release_or_retry':True,'pulse_attempts_total':4,'original_pulse_status_preserved':'uncertain_or_recovery_failed'})


def trend(rows, seconds=10.):
    """Use the complete bracketed tail, with raw sequential group times retained."""
    stop = rows[-1]['t']
    start = max(i for i, x in enumerate(rows) if x['t'] <= stop - seconds)
    r = rows[start:]
    ts = [x['t'] - r[0]['t'] for x in r]
    zs = [x['z_m'] * 1e12 for x in r]
    mt, mz = sum(ts) / len(ts), sum(zs) / len(zs)
    den = sum((x - mt)**2 for x in ts)
    b.require(den > 0, 'No trend time variance')
    slope = sum((t - mt) * (z - mz) for t, z in zip(ts, zs)) / den
    rms = (sum((z - mz - slope * (t - mt))**2 for t, z in zip(ts, zs)) / len(zs))**.5
    return {'samples': len(r), 'duration_s': ts[-1], 'Z_slope_pm_s': slope,
            'Z_detrended_rms_pm': rms, 'tail_bracket_includes_last_sample_at_or_before_cutoff': True,
            'sequential_host_times_not_native_sample_times': True}


class Client(b.Client):
    def __init__(self, store, targets):
        super().__init__(store)
        self.timeout = .5
        self.permit = None
        self.targets = list(targets)
        self.index = 0

    def call(self, command, args=None, timeout=.5):
        args = [] if args is None else args
        if command in m.READ_ARGS and args == m.READ_ARGS[command]:
            pass
        elif command == 'LockIn.ModOnOffGet' and args in ([1], [2]):
            pass
        else:
            b.require(command == 'ZCtrl.SetpntSet' and self.index < len(self.targets)
                      and args == [self.targets[self.index]] and self.permit == (command, args),
                      'Unclaimed/repeated/out-of-sequence write forbidden')
            self.permit = None
            self.index += 1  # Burn before connecting/sending: unknown execution cannot retry.
        self.connect_bound()
        return b.p.NanonisClient.call(self, command, args, timeout)


class Run(m.Run):
    # Reuse only pinned read/audit/logger methods, never base execute/write/cleanup.
    def __init__(self, output, logger, fresh, fresh_sha, mode, completed_pulse=None, *, session, action, source_sha, logger_source_sha):
        self.session, self.action, self.event = session, action, RECOVERY_EVENT
        self.source_sha, self.logger_source_sha = source_sha, logger_source_sha
        self.store = b.Store(output)
        self.targets = sequence(mode)
        self.client = Client(self.store, self.targets[1:])
        self.mode, self.completed_pulse = mode, completed_pulse
        self.logger, self.fresh, self.fresh_sha = Path(logger), Path(fresh), fresh_sha
        self.abort = self.unknown_execution = False
        self.deadline = None
        self.last_logger_elapsed = self.logger_progress_time = None
        self.ready = self.logger_start = None
        self.origin_z = self.origin_xy = self.step_z = None
        self.current_target = self.targets[0]
        self.attempted = self.acknowledged = 0
        self.last_state = None
        self.last_full = -1e9

    def guard(self, v, full=False):
        b.require(v['ZCtrl.OnOffGet'] == [1] and v['ZCtrl.StatusGet'] == [2], 'Feedback not On/2')
        b.require(v['Scan.StatusGet'] == [0], 'Native scan running/unknown; root must separately exclude paused scan')
        b.require(v['Bias.Get'] == [-1.] and v['ZCtrl.SetpntGet'] == [self.current_target], 'Bias or exact setpoint mismatch')
        b.require(v['SafeTip.OnOffGet'] == [0], 'SafeTip no longer Off')
        for k in ['AutoApproach.OnOffGet', 'BiasSpectr.StatusGet', 'ZSpectr.StatusGet', 'FolMe.PSOnOffGet']:
            b.require(v[k] == [0], 'Concurrent/unknown native action: ' + k)
        current, z = v['Current.Get'][0], v['ZCtrl.ZPosGet'][0]
        gate = max(400e-12, 1.5 * self.current_target)
        b.require(b.finite(current) and abs(current) < gate, 'Sampled current software gate/nonfinite')
        hi, lo = m.EXPECTED['ZCtrl.LimitsGet']
        b.require(b.finite(z) and lo + Z_MARGIN <= z <= hi - Z_MARGIN, 'Z endpoint software margin')
        b.require(all(b.finite(x) for x in v['FolMe.XYPosGet']), 'Nonfinite XY')
        if self.origin_z is not None:
            b.require(self.origin_z - z <= TOTAL_DOWN_Z, 'Cumulative downward Z >500pm software gate')
            b.require(max(abs(a-c) for a,c in zip(v['FolMe.XYPosGet'], self.origin_xy)) <= XY_TOL, 'Fixed XY changed >2pm')
        if self.step_z is not None:
            b.require(abs(z - self.step_z) <= STEP_Z, 'Per-step absolute Z >100pm software gate')
        if full:
            for k in FROZEN:
                b.require(v[k] == m.EXPECTED[k], 'Exact frozen field changed: ' + k)

    def fresh_guard(self):
        b.require(self.fresh.resolve().is_relative_to(ROOT) and 'win_users' not in self.fresh.parts, 'Fresh local run snapshot required')
        raw = self.fresh.read_bytes()
        b.require(hashlib.sha256(raw).hexdigest() == self.fresh_sha, 'Fresh snapshot SHA mismatch')
        v = json.loads(raw)
        age = (time.monotonic_ns() - v['end']['monotonic_ns']) / 1e9
        b.require(0 <= age <= 180, 'Fresh snapshot older than180s')
        self.guard(v['values'], full=True)
        b.require(self.in_band(v['values']), 'Fresh snapshot current outside signed±20% band')
        self.store.save('root_fresh_snapshot.json', v)
        self.store.event('fresh_binding', path=str(self.fresh), sha256=self.fresh_sha, age_s=age)

    def known_recovery_guard(self):
        b.require(self.mode=='recover_return' and self.completed_pulse is None, 'Only separate known-ACK recovery stage')
        j,proof=recovery_admission(RECOVERY_ADMISSION_SHA)
        fresh=json.loads(self.fresh.read_bytes())
        b.require(fresh['start']['monotonic_ns']>=proof['latest_known_history_monotonic_ns'], 'Fresh snapshot predates independent recovery review')
        b.require(all(abs(x-y)<=XY_TOL for x,y in zip(fresh['values']['FolMe.XYPosGet'],j['fixed_xy_m'])), 'Fresh XY differs from recorded corner')
        self.store.save('known_failed_pulse_and_recovery_binding.json',proof)

    def in_band(self, v):
        return -1.2 * self.current_target <= v['Current.Get'][0] <= -.8 * self.current_target

    def observe(self, label, full=False):
        full = full or time.monotonic() - self.last_full >= 2.
        v = self.poll(label, full=full)
        self.last_state = {'end': b.stamp(), 'values': v}
        self.guard(v, full=full)
        if full:
            self.last_full = time.monotonic()
        self.logger_guard(max(0., self.deadline - time.monotonic()), post_budget=LOGGER_MARGIN, profile=full)
        return v

    def stability(self, label):
        start, since, previous = time.monotonic(), None, None
        while time.monotonic() - start < STEP_WINDOW:
            v = self.observe(label)
            now = time.monotonic()
            b.require(now - start <= STEP_WINDOW, '15s step deadline reached')
            b.require(previous is None or now - previous <= 1., 'Stability sampling gap >1s')
            if self.in_band(v):
                if since is None:
                    since = now
            else:
                since = None
            previous = now
            if since is not None and now - since >= STABLE_S:
                self.store.event(label + '_confirmed', target_A=self.current_target,
                    continuous_sampled_band_s=now-since, signed_band_A=[-1.2*self.current_target,-.8*self.current_target],
                    elapsed_s=now-start, no_between_sample_guarantee=True)
                return v
            time.sleep(.1)
        raise RuntimeError('15s step window without continuous5s signed current band')

    def write_target(self, target, index):
        label = f'step_{index:02d}'
        args = [target]
        self.store.save(label + '.claim', {**b.stamp(), 'command': 'ZCtrl.SetpntSet', 'args': args,
            'float32_hex': struct.pack('>f', target).hex(), 'index': index, 'mode': self.mode,
            'at_most_once': True, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'static_reference_sha256': m.REF_SHA, 'previous_target_A': self.current_target})
        fd = os.open(self.store.root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.check_abort()
        self.attempted += 1
        self.client.permit = ('ZCtrl.SetpntSet', args)
        try:
            result = self.client.call('ZCtrl.SetpntSet', args, timeout=.5)
            self.store.save(label + '_ack.json', result)
            b.require(result['values'] == [] and not result.get('warning'), 'Unknown/nonempty/warning Set ACK')
        except BaseException:
            self.unknown_execution = True
            raise
        self.acknowledged += 1
        self.current_target = target
        actual = self.q('ZCtrl.SetpntGet')
        self.store.event(label + '_exact_readback', expected_A=target, actual=actual)
        b.require(actual == [target], 'Setpoint float32 readback mismatch')

    def final_observation(self):
        rows, start, previous = [], time.monotonic(), None
        while True:
            v = self.observe('final30_guard')
            now = time.monotonic()
            b.require(previous is None or now - previous <= 1., 'Final observation gap >1s')
            previous = now
            rows.append({'t': now, 'monotonic_ns': time.monotonic_ns(), 'current_A': v['Current.Get'][0],
                         'z_m': v['ZCtrl.ZPosGet'][0], 'in_band': self.in_band(v)})
            if now - start >= FINAL_S and rows[-1]['t'] - rows[0]['t'] >= FINAL_S:
                break
            time.sleep(.1)
        self.store.save('final30_samples.json', rows)
        stats = trend(rows)
        cutoff = rows[-1]['t'] - 5.
        i = max(i for i,x in enumerate(rows) if x['t'] <= cutoff)
        stats['last5s_all_sampled_current_in_band'] = all(x['in_band'] for x in rows[i:])
        stats['Z_gates_passed'] = abs(stats['Z_slope_pm_s']) <= 10. and stats['Z_detrended_rms_pm'] <= 10.
        self.store.save('final30_statistics.json', stats)
        b.require(stats['last5s_all_sampled_current_in_band'] and stats['Z_gates_passed'], 'Final current or Z stability review gate failed; no subsequent action')
        return stats

    def execute(self):
        out = {'status': 'not_started', 'mode': self.mode, 'session_id': self.session, 'action_id': self.action, 'clean_tip_or_repair_claim': False,
               'native_waveform_audit_pending': True, 'automatic_cleanup_writes': [], 'event_id':RECOVERY_EVENT,
               'independent_recovery_return':True, 'original_pulse_status_preserved':'uncertain_or_recovery_failed', 'pulse_attempts_total':4}
        self.deadline = time.monotonic() + TOTAL_DEADLINE
        try:
            self.store.save('manifest.json', {**b.stamp(), **plan(self.mode), 'session_id': self.session, 'action_id': self.action, **m.sb.consumer_metadata(self.logger_source_sha), 'segment06_baseline':m.sb.completed_baseline(self.logger_source_sha), 'induction_admission':{'path':str(ORIGINAL_ADMISSION),'sha256':PROOF_PINS[str(ORIGINAL_ADMISSION)]}, 'recovery_admission':{'path':str(RECOVERY_ADMISSION),'sha256':RECOVERY_ADMISSION_SHA}, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'fresh_snapshot_path': str(self.fresh), 'fresh_snapshot_sha256': self.fresh_sha})
            self.store.save('stage_admission.json', reserve_recovery(self.store.root,self.source_sha,self.fresh_sha))
            self.known_recovery_guard()
            self.fresh_guard()
            before = self.observe('before', full=True)
            self.origin_z = before['ZCtrl.ZPosGet'][0]
            self.origin_xy = before['FolMe.XYPosGet']
            self.step_z = self.origin_z
            self.store.save('before.json', self.last_state)
            self.stability('entry_stability')
            for index, target in enumerate(self.targets[1:], 1):
                v = self.observe(f'step_{index:02d}_before', full=True)
                b.require(self.in_band(v), 'Current left band immediately before step')
                self.step_z = v['ZCtrl.ZPosGet'][0]
                self.write_target(target, index)
                self.stability(f'step_{index:02d}_settle')
            stats = self.final_observation()
            self.observe('after', full=True)
            b.require(self.in_band(self.last_state['values']), 'Current left target band at final full readback')
            self.store.save('after.json', self.last_state)
            self.store.save('native_audit_required.json', {'logger_directory': str(self.logger),
                'native_start_identity': self.ready['native_start_identity'], 'audit': 'After finite logger end archive ALL DAT blocks/hash/headers/rows; compare per-file coverage to every Set claim/ACK and final/postroll. Do not assert gapfree data, true peak, independent gap measurement or no creep.',
                'native_coverage_independently_verified': False})
            out.update(status='completed', final_target_A=self.current_target, final_statistics=stats,
                       final_sampled_state=self.last_state, elapsed_s=TOTAL_DEADLINE-self.deadline+time.monotonic())
        except BaseException as exc:
            out.update(status='uncertain_no_retry' if self.unknown_execution else ('stopped_no_further_sets' if self.attempted else 'rejected_before_write'),
                error=str(exc), execution_unknown=self.unknown_execution, last_known_target_A=self.current_target,
                last_observed_state=self.last_state, requires_fresh_independent_state_review=True,
                cleanup_omitted='Only stop further SetpntSet; no retry, rollback, On, Withdraw, Stop or automatic return. Unknown ACK: no further reads on this connection.')
        finally:
            self.client.close()
            out.update(attempted_sets=self.attempted, acknowledged_sets=self.acknowledged)
            self.store.save('outcome.json', {**b.stamp(), **out})
        print(json.dumps(b.clean(out), indent=2))
        return 0 if out['status'] == 'completed' else 1


def plan(mode='recover_return'):
    seq = sequence(mode)
    return {'recording_segment_id':m.sb.SEGMENT,'logger_directory':str(m.sb.LOGGER_DIR),'requires_completed_recording_baseline':str(ROOT/m.sb.SESSION/'baseline_segment06_full'),'usable_baseline':'Actual211 after_R06_I03_full must be complete/native-bitmatched and task-usable for remote C1/C3; local mound and affected C2/D4 remain explicit limitations','original_source_sha256':ORIGINAL_SOURCE_SHA,'mode': mode, 'origin':'independent_recovery_after_known_P02_pulse','stage_intent':'reduce_setpoint_after_independent_recovery','induction_effect':'not_assessed','repair_episode_active':False,'induced_bad_state_confirmed':False,'induced_cycle_complete':False,'induction_admission':None,'scope': 'One independent known-ACK recovery return after original P02 post-guard failure; actual new thirty-second sampled/native recovery required; original failure remains unchanged',
        'source':str(Path(__file__).resolve()),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'read_envelope_source':str(SOURCE),'read_envelope_sha256':SOURCE_SHA, 'static_reference': str(m.REF), 'static_reference_sha256': m.REF_SHA,
        'frozen_fields_except_setpoint': FROZEN, 'targets_including_unwritten_initial_A': seq,
        'wire_float32_hex': [struct.pack('>f', x).hex() for x in seq],
        'only_write': 'ZCtrl.SetpntSet, each of 11 fixed absolute targets once in sequence',
        'host': b.HOST, 'port': b.PORT, 'source_ip': b.SOURCE_IP, 'interface': b.INTERFACE,
        'fresh': '<=180s hashed local snapshot, exact initial setpoint/full static fields; dynamic Z/current freshly measured; live5s entry',
        'per_step': {'max_s': STEP_WINDOW, 'continuous_sampled_current_band_s': STABLE_S, 'signed_current_ratio': [-1.2,-.8],
                     'sampled_abs_current_abort': '>=max(400pA,1.5*target)', 'absolute_Z_from_immediate_prestep_pm': 100.},
        'software_review_gates_not_damage_limits': {'cumulative_downward_from_entry_pm': 500., 'physical_endpoint_margin_nm': 2.,
            'XY_tolerance_pm': 2., 'final30_last10s_abs_Z_slope_pm_s': 10., 'final30_last10s_Z_detrended_RMS_pm': 10.},
        'final': '30s sampled observation after final step5s stable, final5s signed current±20%, bracketed last10s Z trend/RMS; retain raw samples; this30s is the post-action native observation',
        'overall_deadline_s': TOTAL_DEADLINE, 'logger_margin_s': LOGGER_MARGIN,
        'logger': 'Independent21600nominal/extrapolated10800wall; actual total coverage pending audit. Manifest/READY/start session+source bound, pinned profile6channels, same identity/progress/fresh<=2s events checked throughout; admission225s+15s; final local-native audit mandatory.',
        'failure': 'No additional setters, retry, On, Withdraw, rollback, Scan or automatic return. Unknown ACK stays uncertain.',
        'limitations': 'SafeTip Off; sequential slow software samples miss transients. Historical25%/1s was unvalidated; gates remain engineering criteria, not physical safety guarantees. Stable I/Z gates do not prove safety/no creep/clean tip. Preparation+pulse+return is a composite intervention. ScanStatus0 alone cannot exclude paused scan; root confirms native state before execution.'}


def main():
    global RECOVERY_ADMISSION_SHA
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute',action='store_true')
    for n in ['output','logger','fresh-snapshot','recovery-admission']:
        ap.add_argument('--'+n,type=Path)
    for n in ['fresh-sha256','recovery-admission-sha256','source-sha256','logger-source-sha256']:
        ap.add_argument('--'+n)
    a=ap.parse_args()
    if not a.execute:
        print(json.dumps(plan(),indent=2));return 0
    b.require(all([a.output,a.logger,a.fresh_snapshot,a.fresh_sha256,a.recovery_admission,a.recovery_admission_sha256,a.source_sha256,a.logger_source_sha256]),'Explicit recovery/source/fresh/logger bindings required')
    b.require(ab.local(a.output)==RECOVERY_OUTPUT and not a.output.exists() and not RECOVERY_CLAIM.exists(), 'Recovery output/claim already exists or wrong path')
    b.require(ab.local(a.recovery_admission)==RECOVERY_ADMISSION and ab.sha(Path(__file__))==a.source_sha256, 'Exact recovery admission/source required')
    m.sb.paths('session_02',a.logger);ab.local(a.fresh_snapshot)
    b.require(a.logger.is_dir() and ab.sha(m.sb.LOGGER_SOURCE)==a.logger_source_sha256==m.LOGGER_SOURCE_SHA,'Exact active R06 logger/source required')
    RECOVERY_ADMISSION_SHA=a.recovery_admission_sha256
    recovery_admission(RECOVERY_ADMISSION_SHA)
    run=Run(a.output,a.logger,a.fresh_snapshot,a.fresh_sha256,'recover_return',None,session='session_02',action='P02',source_sha=a.source_sha256,logger_source_sha=a.logger_source_sha256)
    handlers={sig:signal.signal(sig,lambda *_:setattr(run,'abort',True)) for sig in [signal.SIGINT,signal.SIGTERM]}
    try:return run.execute()
    finally:
        for sig,handler in handlers.items():signal.signal(sig,handler)


if __name__=='__main__':
    raise SystemExit(main())
