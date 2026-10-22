"""Bounded Nanonis V5e Demo backend; no real-hardware override exists.

Protocol and identity validation are vendored from the workspace's independently
tested diagnostics and tip laboratory (see demo_wire.py and demo_identity.py).
Only the local, mutually connected Nanonis/Sim-Engine pair may receive writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import threading
import time
import uuid

import numpy as np

from .demo_identity import fresh_sim_identity
from .demo_wire import Connection, InstrumentError, decode, encode, summarize

CATALOG = {c['name']: c for c in json.loads(Path(__file__).with_name('demo_catalog.json').read_text(encoding='utf-8-sig'))['commands']}
WRITES = frozenset({'ZCtrl.OnOffSet', 'ZCtrl.SetpntSet', 'ZCtrl.GainSet', 'ZCtrl.Withdraw',
                    'Scan.Action', 'Scan.FrameSet', 'Scan.BufferSet', 'Scan.SpeedSet', 'Scan.PropsSet',
                    'AutoApproach.Open', 'AutoApproach.OnOffSet'})
READS = frozenset(CATALOG) - WRITES
SETTINGS = ('Bias.Get', 'ZCtrl.OnOffGet', 'ZCtrl.SetpntGet', 'ZCtrl.GainGet', 'Scan.FrameGet',
            'Scan.BufferGet', 'Scan.SpeedGet', 'Scan.PropsGet')
PARAM_LIMITS = {'setpoint_A': (1e-11, 1e-8), 'p_gain_m': (5e-12, 1e-10),
                'time_constant_s': (.0001, .01), 'line_time_s': (.05, .3)}
CURRENT_LIMIT_A = 1e-6


def equivalent(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(equivalent(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=3e-5, abs_tol=1e-18)
    return a == b


def finite_bound(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise PermissionError(f'{label} outside Demo limits [{low}, {high}]')


def discover_channels(names, acquired=()):
    """Choose actual signal IDs; never assume that Z is always index 30."""
    normalized = [str(x).strip().lower() for x in names]
    def choose(accepted, label):
        matches = [i for i, n in enumerate(normalized) if n in accepted]
        existing = [i for i in matches if i in acquired]
        candidates = existing or matches
        if len(candidates) != 1:
            raise RuntimeError(f'Cannot uniquely identify {label} channel: {[(i, names[i]) for i in matches]}')
        return candidates[0]
    return {'current': choose({'current', 'current (a)', 'current (a) [a]'}, 'Current'),
            'z': choose({'z', 'z (m)', 'z position', 'z pos.', 'z position (m)'}, 'Z')}


def roi_frame(frame, roi):
    """Frame arrays use increasing X columns and increasing local Y rows.

    Nanonis up scans are retained in their returned grid order; both data
    directions use the same grid (no contrast-driven mirroring is performed).
    Local offsets rotate counterclockwise by the Scan.Frame angle.
    """
    # Extra provenance from the selector is metadata, never a motion parameter.
    x, y, size = float(roi['x']), float(roi['y']), float(roi['size'])
    finite_bound(x, 0, 1, 'ROI x'); finite_bound(y, 0, 1, 'ROI y'); finite_bound(size, .15, .5, 'ROI size')
    if not size/2 <= x <= 1-size/2 or not size/2 <= y <= 1-size/2:
        raise ValueError('ROI must fit entirely within the survey')
    dx, dy = (x-.5)*frame['width_m'], (y-.5)*frame['height_m']
    angle = math.radians(frame['angle_deg'])
    return {'cx_m': frame['cx_m']+dx*math.cos(angle)-dy*math.sin(angle),
            'cy_m': frame['cy_m']+dx*math.sin(angle)+dy*math.cos(angle),
            'width_m': frame['width_m']*size, 'height_m': frame['height_m']*size,
            'angle_deg': frame['angle_deg']}


def frame_dict(values):
    return dict(zip(('cx_m', 'cy_m', 'width_m', 'height_m', 'angle_deg'), values))


def props_set(values):
    return [1 if values[0] else 2, 1 if values[1] else 2, values[2]+1,
            values[4], values[6], values[9], values[-1]+1]


class DemoBackend:
    backend = 'nanonis_demo'

    @property
    def configuration_bounds(self):
        """A copy for policy planning; runtime validators retain fixed limits."""
        return dict(PARAM_LIMITS)

    def __init__(self, out_dir, host='127.0.0.1', port=6501, pixels=64, sample_interval_s=.05):
        if pixels not in (64, 128):
            raise ValueError('Demo resolution is bounded to 64 or 128')
        finite_bound(sample_interval_s, .02, 1, 'sample interval')
        self.out = Path(out_dir).resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out/'raw').mkdir(exist_ok=True); (self.out/'frames').mkdir(exist_ok=True)
        self.host, self.port, self.pixels, self.sample_interval_s = host, port, pixels, sample_interval_s
        self.identity = fresh_sim_identity(host, port)
        self.transport = Connection(host, port, timeout=7)
        self.transport.__enter__()
        self.client_port = self.transport.sock.getsockname()[1]
        self.lock = threading.RLock()
        self.initial = None; self.channels = None; self.survey_frame = None
        self.broken = False; self.closed = False; self.owned_scan = False; self.owned_approach = False
        self.retracted = False; self.prepared = False; self.sequence = 0; self.write_count = 0
        self.restore_values = {}; self.cleanup_result = None
        try:
            self._guard()
            self.event('identity_verified', identity=self.identity)
        except BaseException:
            self.transport.__exit__(); raise

    def event(self, kind, **data):
        row = {'time_unix': time.time(), 'backend': self.backend, 'kind': kind, **summarize(data)}
        with (self.out/'device_events.jsonl').open('a', encoding='utf8') as f:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')

    def _guard(self):
        return fresh_sim_identity(self.host, self.port, self.identity, self.client_port)

    def _call(self, name, args=None, *, write=False, restoring=False):
        args = [] if args is None else args
        with self.lock:
            if self.broken or self.closed:
                raise ConnectionError('Transport uncertain or closed; no automatic reconnect/retry')
            if name not in (WRITES if write else READS):
                raise PermissionError('Command is outside the explicit Demo allowlist')
            guard = self._guard() if write else None
            if write:
                if self.write_count >= (256 if restoring else 224):
                    raise PermissionError('Demo write budget exceeded')
                self._validate_write(name, args, restoring=restoring)
                self.write_count += 1
            spec = CATALOG[name]; body = encode(spec['inputs'], args)
            self.sequence += 1
            stem = f'{self.sequence:06d}_{name}'
            from .demo_wire import HEADER
            (self.out/'raw'/f'{stem}_request.bin').write_bytes(HEADER.pack(name.encode(), len(body), 1, 0)+body)
            self.event('request', command=name, args=args, write=write, restoring=restoring, guard=guard, raw_stem=stem)
            raw = None
            try:
                raw, elapsed = self.transport.exchange(name, body)
                (self.out/'raw'/f'{stem}_response.bin').write_bytes(self.transport.response_header+raw)
                values, warning = decode(spec['outputs'], raw)
                self.event('response', command=name, values=values, warning=warning, elapsed_ms=elapsed, raw_stem=stem)
                return values[0] if len(values) == 1 else values
            except InstrumentError as exc:
                self.event('device_error', command=name, error=str(exc), raw_stem=stem)
                raise
            except BaseException as exc:
                self.broken = True
                self.event('uncertain_transport', command=name, error=repr(exc), write=write, raw_stem=stem)
                raise

    def _validate_write(self, name, args, restoring=False):
        if restoring and name in self.restore_values and equivalent(args, self.restore_values[name]):
            return
        if name == 'AutoApproach.Open' and args == []: return
        if name in ('AutoApproach.OnOffSet', 'ZCtrl.OnOffSet') and args in ([0], [1]): return
        if name == 'ZCtrl.Withdraw' and args == [1, 5000]: return
        if name == 'Scan.Action' and args in ([0, 1], [1, 1]): return
        if name == 'ZCtrl.SetpntSet': finite_bound(args[0], *PARAM_LIMITS['setpoint_A'], 'setpoint'); return
        if name == 'ZCtrl.GainSet':
            finite_bound(args[0], *PARAM_LIMITS['p_gain_m'], 'P'); finite_bound(args[1], *PARAM_LIMITS['time_constant_s'], 'T')
            if not math.isclose(args[2], args[0]/args[1], rel_tol=1e-5): raise PermissionError('I must equal P/T')
            return
        if name == 'Scan.BufferSet' and self.channels is not None and args == [[self.channels['current'], self.channels['z']], self.pixels, self.pixels]: return
        if name == 'Scan.FrameSet':
            x, y, width, height, angle = args
            for value in (x, y): finite_bound(value, -1e-6, 1e-6, 'frame center')
            for value in (width, height): finite_bound(value, .5e-9, 30e-9, 'frame extent')
            finite_bound(angle, -360, 360, 'frame angle'); return
        if name == 'Scan.SpeedSet':
            if args[4] != 2 or args[5] != 1: raise PermissionError('Symmetric fixed line-time required')
            for value in args[2:4]: finite_bound(value, *PARAM_LIMITS['line_time_s'], 'line time')
            for value in args[:2]: finite_bound(value, 1e-12, 1e-5, 'scan speed')
            return
        if name == 'Scan.PropsSet' and args == [2, 2, 3, '', '', [], 3]: return
        raise PermissionError(f'Write does not match a bounded recipe: {name}')

    def _write(self, name, args, restoring=False):
        return self._call(name, args, write=True, restoring=restoring)

    def _idle(self):
        if self._call('Scan.StatusGet') != 0 or self._call('AutoApproach.OnOffGet') != 0:
            raise PermissionError('Existing scan or approach activity prevents configuration')

    def _wait(self, getter, expected, timeout=3):
        deadline = time.monotonic()+timeout
        while True:
            value = self._call(getter)
            if equivalent(value, expected): return value
            if time.monotonic() >= deadline: raise TimeoutError(f'ACK did not converge: {getter}: {value}')
            time.sleep(.1)

    def _state(self):
        return {name: self._call(name) for name in SETTINGS + ('Scan.StatusGet', 'Current.Get', 'ZCtrl.ZPosGet', 'Piezo.RangeGet', 'AutoApproach.OnOffGet')}

    def snapshot(self):
        s = self._state()
        return {'backend': self.backend, 'feedback_on': s['ZCtrl.OnOffGet'] == 1,
                'setpoint_A': s['ZCtrl.SetpntGet'], 'p_gain_m': s['ZCtrl.GainGet'][0],
                'time_constant_s': s['ZCtrl.GainGet'][1], 'line_time_s': s['Scan.SpeedGet'][2],
                'z_range_m': abs(s['Piezo.RangeGet'][2]), 'frame': frame_dict(s['Scan.FrameGet']),
                'scan_running': s['Scan.StatusGet'] == 1, 'approach_running': s['AutoApproach.OnOffGet'] == 1,
                'current_A': s['Current.Get'], 'z_m': s['ZCtrl.ZPosGet']}

    def probe(self):
        """Read-only protocol and state inspection; never calls reset()."""
        version = self._call('Util.VersionGet'); state = self._state()
        names = self._call('Signals.NamesGet')[2]
        channels = discover_channels(names, state['Scan.BufferGet'][1])
        result = {'backend': self.backend, 'identity': self.identity, 'version': version, 'state': state,
                  'channels': channels, 'channel_names': {k: names[v] for k, v in channels.items()}, 'writes': self.write_count}
        self.event('readonly_probe', result=result)
        return result

    def reset(self, seed=0, scenario='nominal'):
        if self.prepared: raise RuntimeError('One Demo episode per backend; close before a new session')
        self._idle(); self.initial = self._state()
        s = self.initial
        names = self._call('Signals.NamesGet')[2]
        self.channels = discover_channels(names, s['Scan.BufferGet'][1])
        speed = list(s['Scan.SpeedGet']); speed[4] += 1
        self.restore_values = {'ZCtrl.OnOffSet': [s['ZCtrl.OnOffGet']], 'ZCtrl.SetpntSet': [s['ZCtrl.SetpntGet']],
                               'ZCtrl.GainSet': list(s['ZCtrl.GainGet']), 'Scan.FrameSet': list(s['Scan.FrameGet']),
                               'Scan.BufferSet': [s['Scan.BufferGet'][1], s['Scan.BufferGet'][2], s['Scan.BufferGet'][3]],
                               'Scan.SpeedSet': speed, 'Scan.PropsSet': props_set(s['Scan.PropsGet'])}
        self.event('initial_snapshot', state=s, seed=seed, scenario=scenario)
        self.retract()
        self._write('Scan.PropsSet', [2, 2, 3, '', '', [], 3])
        props = self._call('Scan.PropsGet')
        if props[0] != 0 or props[1] != 0 or props[2] != 2: raise RuntimeError('Single-frame/autosave-off readback failed')
        frame = list(s['Scan.FrameGet']); frame[2:4] = [5e-9, 5e-9]
        self._write('Scan.FrameSet', frame); self._wait('Scan.FrameGet', frame)
        self._write('Scan.BufferSet', [[self.channels['current'], self.channels['z']], self.pixels, self.pixels])
        self._wait('Scan.BufferGet', [2, [self.channels['current'], self.channels['z']], self.pixels, self.pixels])
        self.configure({'setpoint_A': 5e-9, 'p_gain_m': 35e-12, 'time_constant_s': .001, 'line_time_s': .256})
        self.prepared = True; self.survey_frame = None
        result = self.snapshot(); self.event('reset_complete', snapshot=result)
        return result

    def approach(self):
        self._idle()
        if not self.prepared or not self.retracted: raise PermissionError('Approach requires this episode’s verified retraction')
        self._write('AutoApproach.Open', [])
        started = time.monotonic(); seen_running = False; readings = []
        self.owned_approach = True
        self._write('AutoApproach.OnOffSet', [1])
        try:
            while time.monotonic()-started < 45:
                status = self._call('AutoApproach.OnOffGet')
                current, z, feedback = self._call('Current.Get'), self._call('ZCtrl.ZPosGet'), self._call('ZCtrl.OnOffGet')
                row = {'elapsed_s': time.monotonic()-started, 'status': status, 'current_A': current, 'z_m': z, 'feedback_on': feedback}
                readings.append(row); seen_running |= status == 1
                if not math.isfinite(current) or not math.isfinite(z) or abs(current) >= CURRENT_LIMIT_A:
                    raise RuntimeError('Approach current/Z protection triggered')
                if seen_running and status == 0:
                    self.owned_approach = False
                    result = {'completed': feedback == 1, 'method': 'AutoApproach.OnOffSet', 'backend': self.backend,
                              'observed_running_then_stopped': True, 'elapsed_s': time.monotonic()-started, 'readings': readings}
                    self.event('approach_result', result=result)
                    if feedback != 1: raise RuntimeError('Auto-approach stopped without feedback; completion not established')
                    self.retracted = False
                    return result
                time.sleep(.1)
            raise TimeoutError('AutoApproach completion not verified within 45 s; ACK alone is not success')
        finally:
            self.event('approach_lifecycle', readings=readings)
            if self.owned_approach and not self.broken:
                self._write('AutoApproach.OnOffSet', [0], restoring=True); self._wait('AutoApproach.OnOffGet', 0)
                self.owned_approach = False

    def configure(self, params):
        if self.initial is None or not self.restore_values:
            raise PermissionError('reset() must capture original settings before configuration')
        self._idle()
        if set(params) - set(PARAM_LIMITS): raise ValueError('Unknown Demo configuration key')
        for key, value in params.items(): finite_bound(value, *PARAM_LIMITS[key], key)
        if 'setpoint_A' in params:
            self._write('ZCtrl.SetpntSet', [params['setpoint_A']]); self._wait('ZCtrl.SetpntGet', params['setpoint_A'])
        if {'p_gain_m', 'time_constant_s'} & set(params):
            p, t, _ = self._call('ZCtrl.GainGet'); p = params.get('p_gain_m', p); t = params.get('time_constant_s', t)
            values = [p, t, p/t]; self._write('ZCtrl.GainSet', values); self._wait('ZCtrl.GainGet', values)
        if 'line_time_s' in params:
            width = self._call('Scan.FrameGet')[2]; line = params['line_time_s']
            self._write('Scan.SpeedSet', [width/line, width/line, line, line, 2, 1.0])
            actual = self._call('Scan.SpeedGet')
            if any(abs(x-line) > .005 for x in actual[2:4]): raise RuntimeError('Line timing readback outside quantization tolerance')
        result = self.snapshot(); self.event('configured', params=params, snapshot=result)
        return result

    def sample(self, count=32):
        if type(count) is not int or not 4 <= count <= 128: raise ValueError('Sample count must be 4..128')
        self._idle()
        currents, heights, stamps = [], [], []
        before = self.snapshot()
        for _ in range(count):
            stamps.append(time.monotonic()); currents.append(self._call('Current.Get')); heights.append(self._call('ZCtrl.ZPosGet'))
            if not math.isfinite(currents[-1]) or not math.isfinite(heights[-1]) or abs(currents[-1]) >= CURRENT_LIMIT_A:
                self.event('sample_protection', current_A=currents, z_m=heights)
                raise RuntimeError('Fresh sample current/Z protection triggered')
            time.sleep(self.sample_interval_s)
        after = self.snapshot()
        for key in ('feedback_on', 'setpoint_A', 'p_gain_m', 'time_constant_s'):
            if not equivalent(before[key], after[key]): raise RuntimeError('Settings changed during stability window')
        result = {'current_A': currents, 'z_m': heights, 'dt_s': float(np.median(np.diff(stamps))),
                  'feedback_on': after['feedback_on'], 'setpoint_A': after['setpoint_A'], 'z_range_m': after['z_range_m'],
                  'backend': self.backend, 'window_id': uuid.uuid4().hex, 'sample_times_monotonic': stamps,
                  'started_s': stamps[0], 'ended_s': time.monotonic()}
        self.event('fresh_sample_window', window=result)
        return result

    def scan(self, kind):
        if not self.prepared:
            raise PermissionError('reset() must finish before acquisition')
        if kind not in ('survey', 'detail', 'confirm'): raise ValueError('Unknown scan kind')
        self._idle(); before = self._state()
        if before['ZCtrl.OnOffGet'] != 1: raise PermissionError('Scan requires feedback ON')
        if before['Scan.PropsGet'][0] != 0 or before['Scan.PropsGet'][2] != 2: raise PermissionError('Single-frame/autosave-off required')
        duration = before['Scan.BufferGet'][3]*sum(before['Scan.SpeedGet'][2:4])
        timeout = min(120, max(15, duration*1.5+10))
        lifecycle, seen_running = [], False; start = time.monotonic()
        self.owned_scan = True
        self._write('Scan.Action', [0, 1])
        try:
            while time.monotonic()-start <= timeout:
                status = self._call('Scan.StatusGet'); current = self._call('Current.Get')
                lifecycle.append(status); seen_running |= status == 1
                if not math.isfinite(current) or abs(current) >= CURRENT_LIMIT_A: raise RuntimeError('Scan current protection')
                if seen_running and status == 0: self.owned_scan = False; break
                time.sleep(.1)
            else: raise TimeoutError('No owned running-to-stopped scan transition')
            after = self._state()
            if any(not equivalent(before[k], after[k]) for k in SETTINGS): raise RuntimeError('Settings changed during acquisition')
            uid = f'{kind}_{uuid.uuid4().hex[:12]}'; arrays, paths = {}, {}
            for signal, channel in self.channels.items():
                for label, direction in [('forward', 1), ('backward', 0)]:
                    values = self._call('Scan.FrameDataGrab', [channel, direction])
                    cached = self._call('Scan.FrameDataGrab', [channel, direction])
                    array = np.asarray(values[4]['values'], dtype=np.float32).reshape(values[4]['shape'])
                    if values[-1] != 1 or values != cached: raise RuntimeError('Scan direction or stable buffer reread failed')
                    if array.shape != (self.pixels, self.pixels) or not np.isfinite(array).all(): raise RuntimeError('Incomplete/nonfinite scan frame')
                    key = f'{signal}_{label}'; path = self.out/'frames'/f'{uid}_{key}.npy'
                    np.save(path, array, allow_pickle=False); arrays[key] = array
                    paths[key] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'channel': channel, 'name': values[1]}
            frame = frame_dict(after['Scan.FrameGet'])
            result = {'id': uid, 'backend': self.backend, 'kind': kind, **arrays, 'frame': frame,
                      'setpoint_A': after['ZCtrl.SetpntGet'], 'z_range_m': abs(after['Piezo.RangeGet'][2]),
                      'p_gain_m': after['ZCtrl.GainGet'][0], 'time_constant_s': after['ZCtrl.GainGet'][1],
                      'line_time_s': after['Scan.SpeedGet'][2], 'feedback_on': after['ZCtrl.OnOffGet'] == 1,
                      'fresh': True, 'lifecycle': lifecycle, 'elapsed_s': time.monotonic()-start, 'raw_paths': paths,
                      'freshness_basis': 'owned ACK; observed 1 then 0; unchanged settings; finite full arrays; exact stable reread',
                      'orientation': 'Nanonis up-scan returned spatial grid; rows local +Y, columns local +X; no mirroring'}
            if kind == 'survey': self.survey_frame = dict(frame)
            metadata = {k:v for k,v in result.items() if k not in arrays}
            (self.out/'frames'/f'{uid}.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf8')
            self.event('fresh_scan', record=metadata)
            return result
        finally:
            self.event('scan_lifecycle', scan_kind=kind, lifecycle=lifecycle, seen_running=seen_running, elapsed_s=time.monotonic()-start)
            if self.owned_scan and not self.broken:
                self._write('Scan.Action', [1, 1], restoring=True); self._wait('Scan.StatusGet', 0); self.owned_scan = False

    def move_roi(self, roi):
        self._idle()
        if self.survey_frame is None: raise RuntimeError('A fresh survey is required before ROI movement')
        desired = roi_frame(self.survey_frame, roi)
        values = [desired[k] for k in ('cx_m', 'cy_m', 'width_m', 'height_m', 'angle_deg')]
        self._write('Scan.FrameSet', values); self._wait('Scan.FrameGet', values)
        self.event('roi_selected', roi=roi, survey_frame=self.survey_frame, detail_frame=desired)
        return self.snapshot()

    def retract(self):
        if self.initial is None or not self.restore_values:
            raise PermissionError('reset() must capture original settings before retraction')
        if self.owned_approach:
            self._write('AutoApproach.OnOffSet', [0], restoring=True); self._wait('AutoApproach.OnOffGet', 0); self.owned_approach = False
        if self.owned_scan:
            self._write('Scan.Action', [1, 1], restoring=True); self._wait('Scan.StatusGet', 0); self.owned_scan = False
        self._idle()
        # The reserved cleanup budget also covers termination at the action limit.
        self._write('ZCtrl.Withdraw', [1, 5000], restoring=True); self._wait('ZCtrl.OnOffGet', 0)
        z = self._call('ZCtrl.ZPosGet'); z_range = abs(self._call('Piezo.RangeGet')[2])
        endpoint = bool(math.isfinite(z) and math.isfinite(z_range) and z_range > 0
                        and .499*z_range <= abs(z) <= .501*z_range)
        self.retracted = endpoint
        result = {'retracted': endpoint, 'verified_endpoint': endpoint, 'method': 'ZCtrl.Withdraw',
                  'feedback_on': False, 'z_m': z, 'z_range_m': z_range,
                  'endpoint_basis': 'Demo numerical endpoint at half Piezo.RangeGet Z range; not physical calibration'}
        self.event('retracted', result=result)
        if not endpoint: raise RuntimeError('Withdraw response did not verify the Demo Z-range endpoint')
        return result

    def close(self):
        if self.closed: return self.cleanup_result
        result = {'restored': False, 'backend': self.backend, 'write_count': self.write_count}
        try:
            if self.broken: raise ConnectionError('Transport uncertain; no guessed restoration or retries')
            if self.initial is not None and self.restore_values:
                self.retract()
                for name in ('ZCtrl.SetpntSet', 'ZCtrl.GainSet', 'Scan.FrameSet', 'Scan.BufferSet', 'Scan.SpeedSet', 'Scan.PropsSet', 'ZCtrl.OnOffSet'):
                    self._write(name, self.restore_values[name], restoring=True)
                final = self._state()
                matches = {k: equivalent(self.initial[k], final[k]) for k in SETTINGS}
                result.update(restored=all(matches.values()) and final['Scan.StatusGet'] == 0 and final['AutoApproach.OnOffGet'] == 0,
                              matches=matches, initial=self.initial, final=final, z_position_restored=False,
                              note='Configuration restored; physical/coarse tip position is not claimed reversible')
                if not result['restored']: raise RuntimeError('Cleanup settings readback mismatch')
            else: result.update(restored=True, note='Read-only session; no settings changed')
        except BaseException as exc:
            result['error'] = repr(exc)
            raise
        finally:
            result['write_count'] = self.write_count
            self.cleanup_result = result; self.event('cleanup', result=result)
            (self.out/'cleanup.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
            self.transport.__exit__(); self.closed = True
        return result


def main():
    parser = argparse.ArgumentParser(description='Read-only Nanonis Demo identity/protocol probe')
    parser.add_argument('--probe', action='store_true', required=True)
    parser.add_argument('--out', required=True); parser.add_argument('--port', type=int, default=6501)
    args = parser.parse_args()
    client = DemoBackend(args.out, port=args.port)
    try: print(json.dumps(client.probe(), ensure_ascii=False, indent=2))
    finally: client.close()


if __name__ == '__main__':
    main()
