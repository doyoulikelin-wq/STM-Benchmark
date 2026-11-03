#!/usr/bin/env python3
"""Offline plan by default. Bounded five-slot setpoint stage; root alone executes.

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
BINDINGS_SOURCE = HERE / 'action_bindings_R06_induction_P03.py'
BINDINGS_SHA = 'e7e3fcad26d11e3da24fd31b0c652cf1d472f2234aad76ebba85cbf4b67a4165'
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
    b.require(mode in ('prepare', 'return'), 'Unknown mode')
    return list(TARGETS if mode == 'prepare' else reversed(TARGETS))


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
        self.session, self.action, self.event = session, action, mode+'_induction_'+action
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

    def pulse_guard(self):
        if self.mode == 'prepare':
            b.require(self.completed_pulse is None, 'Prepare does not accept pulse context')
            return
        p = Path(self.completed_pulse).resolve() if self.completed_pulse else None
        b.require(p is not None and p.is_relative_to(ROOT) and 'win_users' not in p.parts, 'Return needs completed local single-pulse directory')
        b.require(p == ROOT/self.session/('pulse_induction_'+self.action), 'Return requires this exact session/action pulse')
        names = ['pulse.claim', 'pulse_ack.json', 'outcome.json', 'manifest.json']
        docs = {n: json.loads((p / n).read_bytes()) for n in names}
        claim, ack, out = (docs[n] for n in names[:3])
        b.require(docs['manifest.json'].get('session_id') == self.session and docs['manifest.json'].get('action_id') == self.action, 'Pulse manifest session/action mismatch')
        b.require(claim['args'] == [1,.020,-6.0,1,2], 'Return pulse differs from reviewed one-shot family')
        claims = [x for x in p.glob('*.claim') if json.loads(x.read_bytes()).get('command') == 'Bias.Pulse']
        b.require(len(claims) == 1 and claims[0].name == 'pulse.claim', 'Exactly one pulse claim required')
        b.require(claim['command'] == 'Bias.Pulse' and len(claim['args']) == 5 and claim['args'][0] == 1,
                  'Completed wait-until-done pulse required')
        b.require(ack['values'] == [] and not ack.get('warning') and out.get('pulse_attempted') is True
                  and out.get('native_end_confirmed') is True and out.get('writer_outcome_unknown') is False
                  and out.get('status') == 'single_pulse_knownend_30s_observed', 'Pulse not independently completed')
        b.require(docs['manifest.json'].get('induction_admission')=={'path':str(ab.ADMISSION_PATH),'sha256':ab.ADMISSION_SHA},'Return pulse admission differs')
        b.require(docs['manifest.json'].get('source_sha256')==ab.sha(HERE/'pulse_R06_induction_P03_once.py'),'Return pulse source differs')
        self.store.save('completed_pulse_binding.json', {'directory': str(p), 'documents': docs,
            'sha256': {n: hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names},
            'return_is_independent_action_not_failed_prepare_cleanup': True})

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
               'native_waveform_audit_pending': True, 'automatic_cleanup_writes': []}
        self.deadline = time.monotonic() + TOTAL_DEADLINE
        try:
            self.store.save('manifest.json', {**b.stamp(), **plan(self.mode), 'session_id': self.session, 'action_id': self.action, **m.sb.consumer_metadata(self.logger_source_sha), 'segment06_baseline':m.sb.completed_baseline(self.logger_source_sha), 'induction_admission':{'path':str(ab.ADMISSION_PATH),'sha256':ab.ADMISSION_SHA}, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'fresh_snapshot_path': str(self.fresh), 'fresh_snapshot_sha256': self.fresh_sha})
            self.store.save('stage_admission.json', ab.reserve_stage(self.session,self.action,self.mode,self.store.root,self.source_sha,self.fresh_sha))
            self.pulse_guard()
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


def plan(mode='prepare'):
    seq = sequence(mode)
    return {'recording_segment_id':m.sb.SEGMENT,'logger_directory':str(m.sb.LOGGER_DIR),'requires_completed_recording_baseline':str(ROOT/m.sb.SESSION/'baseline_segment06_full'),'usable_baseline':'Actual212 after_R06_P02_recovery_full must be complete/native-bitmatched and task-usable with recorded C1 local changes; old mound and affected C2/D4 remain explicit limitations','original_source_sha256':ORIGINAL_SOURCE_SHA,'mode': mode, 'origin':'task_usable_baseline_induction','stage_intent':'induction_attempt','induction_effect':'not_assessed','repair_episode_active':False,'induced_bad_state_confirmed':False,'induced_cycle_complete':False,'induction_admission':None,'scope': 'Bounded prepare/return in fixed session/action; explicit return only after this exact completed pulse',
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=['prepare','return'], default='prepare')
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--output', type=Path)
    ap.add_argument('--logger', type=Path)
    ap.add_argument('--fresh-snapshot', type=Path)
    ap.add_argument('--fresh-sha256')
    ap.add_argument('--completed-pulse-dir', type=Path)
    ap.add_argument('--return-review-sha256')
    ap.add_argument('--episode-admission',type=Path)
    ap.add_argument('--episode-admission-sha256')
    for name in ['session','action','source-sha256','logger-source-sha256']:
        ap.add_argument('--'+name)
    a = ap.parse_args()
    if not a.execute:
        print(json.dumps(plan(a.mode), indent=2))
        return 0
    b.require(all([a.output,a.logger,a.fresh_snapshot,a.fresh_sha256,a.session,a.action,a.source_sha256,a.logger_source_sha256]), 'Explicit session/action/source/logger/fresh bindings required')
    b.require(a.episode_admission and a.episode_admission_sha256,'Explicit frozen induction admission required')
    ab.ra.RETURN_REVIEW_SHA=a.return_review_sha256
    ab.bind_admission(a.episode_admission,a.episode_admission_sha256,a.mode)
    ab.paths(a.session,a.action,a.mode,a.output,a.logger,a.fresh_snapshot,Path(__file__),a.source_sha256,a.logger_source_sha256)
    run = Run(a.output,a.logger,a.fresh_snapshot,a.fresh_sha256,a.mode,a.completed_pulse_dir,
              session=a.session,action=a.action,source_sha=a.source_sha256,logger_source_sha=a.logger_source_sha256)
    handlers = {s: signal.signal(s, lambda *_: setattr(run,'abort',True)) for s in [signal.SIGINT,signal.SIGTERM]}
    try:
        return run.execute()
    finally:
        for s,h in handlers.items():
            signal.signal(s,h)


if __name__ == '__main__':
    raise SystemExit(main())
