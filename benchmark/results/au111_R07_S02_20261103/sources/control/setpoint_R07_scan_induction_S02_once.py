#!/usr/bin/env python3
"""Offline plan by default. Bounded four-step R07 scan-induction setpoint stage; root alone executes.

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
SOURCE = HERE / 'scan_full50nm_fast_R07_baseline_once.py'
SOURCE_SHA = 'afc4e361af8bbb9d6d6a59baad2ef5ade4d1151bee125047fca6545bdd9cdc95'
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA:
    raise RuntimeError('Frozen current50nm source changed')
spec = importlib.util.spec_from_file_location('setpoint_frozen_capture', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
b = m.b
ORIGINAL_SOURCE=ROOT/'setpoint_fullcycle_100pA_1nA_once.py'
ORIGINAL_SOURCE_SHA='7d537f110631e5d73fdc6ee7336a1ec077088705f0e455183def442f6889bbb4'
if hashlib.sha256(ORIGINAL_SOURCE.read_bytes()).hexdigest()!=ORIGINAL_SOURCE_SHA:raise RuntimeError('Original action source changed')
BINDINGS_SOURCE = HERE / 'R07_scan_induction_S02/stage_binding.py'
BINDINGS_SHA = '18c315fd74e33b782f2bbe35f71622fc6e8baed3f7486107c69773b9f6f82769'
if hashlib.sha256(BINDINGS_SOURCE.read_bytes()).hexdigest() != BINDINGS_SHA:
    raise RuntimeError('Frozen local action bindings changed')
_binding_spec = importlib.util.spec_from_file_location('five_session_action_bindings', BINDINGS_SOURCE)
ab = importlib.util.module_from_spec(_binding_spec)
_binding_spec.loader.exec_module(ab)
b.require({k:b.p.COMMANDS['ZCtrl.SetpntSet'][k] for k in ['inputs','outputs','access']} == {'inputs': ['f'], 'outputs': [], 'access': 'write'}, 'Setpoint setter codec changed')
b.require({k:b.p.COMMANDS['ZCtrl.SetpntGet'][k] for k in ['inputs','outputs','access']} == {'inputs': [], 'outputs': ['f'], 'access': 'read'}, 'Setpoint getter codec changed')
PA = [100.,125.,156.25,195.3125,200.]
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
        self.session, self.action, self.event = session, action, ab.EVENTS[mode]
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
        self.expected = ab.expected_fields(m.EXPECTED,mode)
        self.stage_proof = None

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
                b.require(v[k] == self.expected[k], 'Exact frozen field changed: ' + k)

    def fresh_guard(self):
        b.require(self.fresh.resolve().is_relative_to(ROOT) and 'win_users' not in self.fresh.parts, 'Fresh local run snapshot required')
        raw = self.fresh.read_bytes()
        b.require(hashlib.sha256(raw).hexdigest() == self.fresh_sha, 'Fresh snapshot SHA mismatch')
        v = json.loads(raw)
        age = (time.monotonic_ns() - v['end']['monotonic_ns']) / 1e9
        b.require(0 <= age <= 180, 'Fresh snapshot older than180s')
        b.require(self.stage_proof['stage_review_monotonic_ns'] <= v['start']['monotonic_ns'] <= v['end']['monotonic_ns'],
                  'Fresh snapshot must follow the independent stage review')
        self.guard(v['values'], full=True)
        b.require(self.in_band(v['values']), 'Fresh snapshot current outside signed±20% band')
        self.store.save('root_fresh_snapshot.json', v)
        self.store.event('fresh_binding', path=str(self.fresh), sha256=self.fresh_sha, age_s=age)

    def predecessor_guard(self):
        evidence=ab.validate_stage(ab.ADMISSION_PATH,ab.ADMISSION_SHA,self.mode,ab.REVIEW_PATH,ab.REVIEW_SHA)
        self.stage_proof=evidence
        self.store.save('stage_evidence.json',evidence)

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
            self.store.save('manifest.json', {**b.stamp(), **plan(self.mode), 'session_id': self.session, 'action_id': self.action, **m.sb.consumer_metadata(self.logger_source_sha), 'segment07_baseline':ab.completed_baseline(self.logger_source_sha), 'induction_admission':{'path':str(ab.ADMISSION_PATH),'sha256':ab.ADMISSION_SHA}, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'fresh_snapshot_path': str(self.fresh), 'fresh_snapshot_sha256': self.fresh_sha,
                'root_stage_review':{'path':str(ab.REVIEW_PATH),'sha256':ab.REVIEW_SHA}})
            self.store.save('stage_admission.json', ab.reserve_stage(self.session,self.action,self.mode,self.store.root,self.source_sha,self.fresh_sha))
            self.predecessor_guard()
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
    return {'recording_segment_id':'R07','logger_directory':str(m.sb.LOGGER_DIR),
        'mode':mode,'event':ab.EVENTS[mode],'action_id':'S02','scope':'One independently selected four-step setpoint stage for finite scan induction',
        'targets_including_unwritten_initial_A':sequence(mode),'fixed_expected_fields':ab.expected_fields(m.EXPECTED,mode),
        'only_write':'ZCtrl.SetpntSet; four predetermined targets once each','induction_frame_budget':1,'pulse_budget_used':5,'pulse_budget_maximum':6,
        'stage_order':ab.ORDER,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'inherited_source_sha256':'c329771b2f63c43b1f5401fcabe21cba44bd08b199d5fa6010c3356dd4809745',
        'overall_deadline_s':TOTAL_DEADLINE,'step_window_s':STEP_WINDOW,'stable_s':STABLE_S,'final_s':FINAL_S,
        'per_step_Z_m':STEP_Z,'total_downward_Z_m':TOTAL_DOWN_Z,'endpoint_margin_m':Z_MARGIN,'XY_tolerance_m':XY_TOL,
        'signed_current_ratio':[-1.2,-.8],'absolute_current_gate':'max(400pA,1.5*target), equal400pA for this whole sequence',
        'failure':'No retry, rollback, auto-return, On, Withdraw or Scan; unknown ACK zero further reads',
        'return_predecessor':'Only this actual completed full induction plus independent root native review',
        'source_and_physical_limits':'Engineering guards inherited from executed driver; not physical damage thresholds'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=['prepare','return'], default='prepare')
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--output', type=Path)
    ap.add_argument('--logger', type=Path)
    ap.add_argument('--fresh-snapshot', type=Path)
    ap.add_argument('--fresh-sha256')
    ap.add_argument('--stage-review',type=Path)
    ap.add_argument('--stage-review-sha256')
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
    b.require(a.stage_review and a.stage_review_sha256,'Independent root stage review required')
    ab.validate_stage(a.episode_admission,a.episode_admission_sha256,a.mode,a.stage_review,a.stage_review_sha256)
    ab.paths(a.session,a.action,a.mode,a.output,a.logger,a.fresh_snapshot,Path(__file__),a.source_sha256,a.logger_source_sha256)
    run = Run(a.output,a.logger,a.fresh_snapshot,a.fresh_sha256,a.mode,None,
              session=a.session,action=a.action,source_sha=a.source_sha256,logger_source_sha=a.logger_source_sha256)
    handlers = {s: signal.signal(s, lambda *_: setattr(run,'abort',True)) for s in [signal.SIGINT,signal.SIGTERM]}
    try:
        return run.execute()
    finally:
        for s,h in handlers.items():
            signal.signal(s,h)


if __name__ == '__main__':
    raise SystemExit(main())
