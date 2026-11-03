"""Root-only one-shot SIGINT to the owned R06 observer after completed scan 213.

No instrument, network, GUI or live control modules are imported. A successful
signal request is not proof that logger cleanup or native file closure completed.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

C = Path(__file__).resolve().parents[1]
N = C.parent
S = N / 'session_02'
LOGGER = S / 'logger_06'
SCANNER = S / 'after_R06_P03_full'
SCANNER_SOURCE = C / 'scan_full50nm_fast_R06_after_induction_P03_once.py'
SCANNER_SHA = '2d92acb42fb7f0324b5d1063194f77f634f39ca63b88c4e00b1cf58be064c0ee'
PINS_PATH = C / 'R06_pulse_P03/close_observer_frozen_inputs.json'
PINS_SHA = '79223e530c6ac0e439f8722b5ad7470401adfbffe50e32474ca386e7535a7359'
STOP_CLAIM = C / 'stop_R06_root_signal.json'
LOGGER_PID = 57780
SCANNER_PID = 72085
MAX_STATUS_AGE_NS = 2000000000  # Same as the original R06 close helper.


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def local(path):
    p = Path(path).absolute()
    require(p == p.resolve() and p.is_relative_to(N), 'Exact local path required')
    require('win_users' not in p.parts and 'Volumes' not in p.parts, 'No mounted source')
    return p


def reference(ref):
    p = local(ref['path'])
    require(sha(p) == ref['sha256'], 'Changed root evidence ' + str(p))
    return load(p)


def static_history():
    require(sha(PINS_PATH) == PINS_SHA, 'Frozen input table changed')
    pins = load(PINS_PATH)
    for rel, digest in pins.items():
        require(sha(local(N / rel)) == digest, 'Changed historical input ' + rel)
    actual = {str(p.relative_to(N)) for p in (N / 'globalclaims').glob('continuing_20261101_1939__pulse_*.claim')}
    expected = {p for p in pins if p.startswith('globalclaims/')}
    require(actual == expected and len(actual) == 4, 'Pulse history changed since ordinal 5')
    for stage, mode, target in [('prepare_induction_P03', 'prepare', 9.999999717180685e-10),
                                ('return_induction_P03', 'return', 1.000000013351432e-10),
                                ('recovery_return_P02_01', 'recover_return', 1.000000013351432e-10)]:
        v = load(S / stage / 'outcome.json')
        require(v['status'] == 'completed' and v['mode'] == mode, 'Setpoint stage incomplete')
        require(v['attempted_sets'] == v['acknowledged_sets'] == 11 and v['final_target_A'] == target,
                'Actual eleven-step stage differs')
    p03 = load(S / 'pulse_induction_P03/outcome.json')
    require(p03['status'] == 'single_pulse_knownend_30s_observed' and p03['pulse_ordinal'] == 5,
            'P03 normal completion missing')
    require(p03['pulse_attempted'] is True and p03['native_end_confirmed'] is True
            and p03['writer_outcome_unknown'] is False and p03['post_metrics']['elapsed_s'] >= 30,
            'P03 ended/observed evidence missing')
    require(p03['automatic_On'] is False and p03['automatic_retry'] is False, 'P03 replay/On differs')
    readiness = load(S / 'pulse_induction_P03/feedback_readiness.json')
    require(readiness['ready'] is True and readiness['error'] is None and readiness['writes'] == [],
            'P03 readiness not complete')
    p02 = load(S / 'pulse_induction_P02/outcome.json')
    require(p02['status'] == 'uncertain_or_recovery_failed' and p02['native_end_confirmed'] is True
            and p02['writer_outcome_unknown'] is False and p02['pulse_ordinal'] == 4,
            'Original P02 failure/known end must remain')
    recovery = load(C / 'R06_pulse_P02/independent_readonly_recovery30/outcome.json')
    require(recovery['status'] == 'completed_readonly_30s_original_guards' and recovery['readonly'] is True
            and recovery['writes'] == [] and recovery['duration_s'] >= 30, 'Independent recovery missing')
    for stage in ('repair_A05', 'induction_R06_I02', 'induction_R06_I03'):
        v = load(S / stage / 'outcome.json')
        require(v['native_end_confirmed'] is True and v['writer_outcome_unknown'] is False,
                'Prior shaper ending is unknown')
    for stage, number in [('after_R06_P02_recovery_full', 212), ('after_R06_P03_full', 213)]:
        v = load(S / stage / 'outcome.json')
        require(v['status'] == 'completed' and v['completed_frame_confirmed'] is True,
                'Full scan not completed')
        require(v['native_file_path'].endswith(f'BM261029_{number:05d}.sxm'), 'Wrong completed scan')
    scan = load(SCANNER / 'outcome.json')
    quality = load(SCANNER / 'analysis/quality_report.json')['integrity']
    require(quality['completed_outcome'] is True and quality['native_TCP_wire_bitmatch'] is True
            and quality['matched_float32_values'] == 345600, '213 full image integrity missing')
    receipt = load(SCANNER / 'native_sxm_receipt.json')
    require(receipt['outcome_sha256'] == sha(SCANNER / 'outcome.json')
            and receipt['source_double_read_sha_equal'] is True and receipt['local_reread_sha_equal'] is True,
            '213 native archive receipt mismatch')
    require(sha(local(receipt['destination'])) == receipt['sha256'], 'Archived 213 changed')
    return scan, pins


def decision_guard(path, digest, scan):
    p = local(path)
    require(sha(p) == digest, 'Root decision hash mismatch')
    d = load(p)
    require(d['schema'] == 'local-au111-R06-P03-close-observer-v1', 'Wrong decision schema')
    for key in ('allow_stop', 'task_usable', 'no_further_action_chosen', 'sole_writer_confirmed'):
        require(d[key] is True, 'Root decision does not permit close ' + key)
    require(d['final_stage'] == 'after_R06_P03_full' and d['scan_number'] == 213, 'Wrong final frame')
    require(d['logger_pid'] == LOGGER_PID and d['scanner_pid'] == SCANNER_PID, 'Wrong process decision')
    require(d['scanner_source'] == {'path': str(SCANNER_SOURCE), 'sha256': SCANNER_SHA}, 'Wrong scanner source')
    require(type(d['monotonic_ns']) is int and scan['monotonic_ns'] <= d['monotonic_ns'] <= time.monotonic_ns(),
            'Decision must follow completed scan')
    require(isinstance(d['reason'], str) and d['reason'].strip(), 'Decision reason required')
    reference(d['image_review'])
    reference(d['native_review'])
    return d


def process_command(pid):
    r = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
    require(r.returncode in (0, 1), 'ps could not establish process identity')
    if r.returncode == 1:
        require(not r.stdout.strip() and not r.stderr.strip(), 'Ambiguous process lookup')
        return None
    require(bool(r.stdout.strip()), 'Empty process command')
    return r.stdout.strip()


def process_guard():
    launch = load(C / 'R06_logger_launch.json')
    require(launch['pid'] == LOGGER_PID, 'Wrong owned logger PID')
    require(all(not any(ch.isspace() for ch in arg) for arg in launch['args']), 'Ambiguous launch arguments')
    require(str(C / 'logger_fullcycle_segment06_observe_once.py') in launch['args'], 'Wrong logger source')
    command = process_command(LOGGER_PID)
    require(command == ' '.join(launch['args']), 'Logger PID no longer has exact launch identity')
    require(process_command(SCANNER_PID) is None, 'Scanner PID still live')
    require(not (LOGGER / 'outcome.json').exists(), 'Logger already finished')
    return command


def fresh_logger_observations():
    p = LOGGER / 'events.jsonl'
    with p.open('rb') as f:
        size = f.seek(0, 2)
        start = max(0, size - 300000)
        f.seek(start)
        chunks = f.read().split(b'\n')
    if start:
        chunks = chunks[1:]
    rows = [json.loads(line) for line in chunks[:-1] if line]
    status = next(e for e in reversed(rows) if e.get('kind') == 'datalog_status')
    junction = next(e for e in reversed(rows) if e.get('kind') == 'dynamic_state_poll')
    now = time.monotonic_ns()
    require(all(0 <= now - e['monotonic_ns'] < MAX_STATUS_AGE_NS for e in (status, junction)),
            'Logger/state evidence is stale')
    ready = load(LOGGER / 'READY.json')
    require(status['parsed']['start'] == ready['native_start_identity'] and not status['parsed']['stop'],
            'Logger native identity changed/stopped')
    values = junction['values']
    require(all(values[k] == [0] for k in ('Scan.StatusGet', 'BiasSpectr.StatusGet',
                                         'ZSpectr.StatusGet', 'AutoApproach.OnOffGet')), 'Junction action active')
    require(values['ZCtrl.OnOffGet'] == [1] and values['ZCtrl.StatusGet'] == [2], 'Feedback not known On2')
    require(values['Bias.Get'] == [-1.0] and values['ZCtrl.SetpntGet'] == [1.000000013351432e-10]
            and values['SafeTip.OnOffGet'] == [0], 'Final recorded working point differs')
    require(all(math.isfinite(values[k][0]) for k in ('Current.Get', 'ZCtrl.ZPosGet')), 'Nonfinite state')
    return status, junction


def run(decision_path, decision_sha):
    require(not STOP_CLAIM.exists(), 'Stop already claimed; no second signal')
    scan, pins = static_history()
    decision = decision_guard(decision_path, decision_sha, scan)
    command = process_guard()
    status, junction = fresh_logger_observations()
    receipt = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), monotonic_ns=time.monotonic_ns(),
                   pid=LOGGER_PID, verified_command=command, scanner_pid_confirmed_absent=SCANNER_PID,
                   reason=decision['reason'], decision={'path': str(local(decision_path)), 'sha256': decision_sha},
                   source={'path': str(Path(__file__).resolve()), 'sha256': sha(__file__)},
                   original_close_source_sha256=pins['continuation_slow_20261102/R06_repair/close_own_observer.py'],
                   action='SIGINT owned R06 logger', signal=int(signal.SIGINT),
                   latest_status=status, latest_junction_observation=junction,
                   no_junction_writer_active=True, pulse_attempts_total=5,
                   native_logger_closure_not_yet_confirmed=True, no_automatic_retry=True)
    with STOP_CLAIM.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.kill(LOGGER_PID, signal.SIGINT)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--decision-json', required=True)
    parser.add_argument('--decision-sha256', required=True)
    opts = parser.parse_args()
    require(opts.execute and sha(__file__) == opts.source_sha256, 'Exact executed source SHA required')
    receipt = run(opts.decision_json, opts.decision_sha256)
    print(json.dumps({'utc': receipt['utc'], 'stop_claim': str(STOP_CLAIM), 'signal_sent': True}))


if __name__ == '__main__':
    main()
