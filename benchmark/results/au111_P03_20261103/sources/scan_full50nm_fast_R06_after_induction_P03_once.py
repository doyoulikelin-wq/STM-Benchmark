#!/usr/bin/env python3
"""Plan-only by default. One unchanged 50 nm / 240-square DOWN R06 complete post-induction P03 composite scan, offline import.

Root is the sole hardware writer. No configuration writes, On, retries or reconnect.
400 pA and 2 nm are software review gates, NOT instantaneous protection.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import copy
from pathlib import Path
import signal
import struct
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SEGMENT_BINDING = HERE / 'segment06_observe_binding.py'
SEGMENT_BINDING_SHA = 'b86f4f0d40fa0eb8cdf9f06f904beb2fc8477e98f5761c1b433d65f3b84f515f'
if hashlib.sha256(SEGMENT_BINDING.read_bytes()).hexdigest()!=SEGMENT_BINDING_SHA:raise RuntimeError('Segment binding changed')
_segment_spec=importlib.util.spec_from_file_location('scan_segment06_observe_binding',SEGMENT_BINDING)
sb=importlib.util.module_from_spec(_segment_spec);_segment_spec.loader.exec_module(sb)
ORIGINAL_VARIANT = HERE / 'scan_full50nm_fast_R06_after_induction_I03_once.py'
ORIGINAL_VARIANT_SHA = 'd039b5fc37d47672f0319e050615b7e3294273b3215259b0aac1923da61bc591'
if hashlib.sha256(ORIGINAL_VARIANT.read_bytes()).hexdigest()!=ORIGINAL_VARIANT_SHA:raise RuntimeError('Frozen scanner parent changed')
PRIOR = ROOT.parent / 'stm_tip_validation_20261101_1939'
OLD = ROOT.parent / 'stm_tip_benchmark_goal_20261030'
BASE = OLD / 'scan_acquire_context.py'
BASE_SHA = '3201ed49266ac4280ea9dcbda53973c453f9530f075b4993b717cfbd57985c42'
PROTOCOL = ROOT.parent / 'stm_tip_control_test_20261028/protocol.py'
CATALOG = PROTOCOL.with_name('catalog.json')
REF = ROOT / 'read_001_initial/snapshot.json'
REF_SHA = '9de72fc487ed050909cd0e8f1ba5f1dd328f5b314d9ee82ad12337f7229e5a71'
UP_SOURCE = PRIOR / 'scan_current50nm_once.py'
UP_SOURCE_SHA = 'ec0497327ece6bc8ae4d6bd67f855bb5df1a6bdef59762e488c1bbe4ba096427'
DOWN_SOURCE = PRIOR / 'scan_current50nm_down_once.py'
DOWN_SOURCE_SHA = '2b73c8a8b84750a7e8f18c0284521bb62b0586e3e0d8a0aa24d87f5a836066b1'
LOGGER_SOURCE = sb.LOGGER_SOURCE
LOGGER_DURATION = 21600
LOGGER_WALL_ESTIMATE = 10800.
HASHES = {UP_SOURCE: UP_SOURCE_SHA, DOWN_SOURCE: DOWN_SOURCE_SHA, BASE: BASE_SHA, REF: REF_SHA,
          PROTOCOL: 'cb89eba6d0417b37b86ed593b9d85d96650ae5978d7d1e919b6a291e9ab2b742',
          CATALOG: 'f7637754438751ca52253f0884632d499202111140e945efaeaedbbb38a184ac'}
for path, digest in HASHES.items():
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError('Pinned source/reference changed: ' + str(path))
spec = importlib.util.spec_from_file_location('validation50_exact_base', BASE)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
INITIAL = json.loads(REF.read_bytes())['values']
EXPECTED = copy.deepcopy(INITIAL)
EXPECTED['Scan.FrameGet'] = [0., 0., 5.000000058430487e-8, 5.000000058430487e-8, 0.]
EXPECTED['Scan.BufferGet'] = [3, [0, 30, 89], 240, 240]
# Initial snapshot is a static anchor, never a substitute for each attempt's fresh read.
DYNAMIC = {'Current.Get', 'ZCtrl.ZPosGet', 'ZCtrl.OnOffGet', 'ZCtrl.StatusGet',
           'Scan.StatusGet', 'FolMe.XYPosGet', 'SafeTip.SignalGet',
           'DataLog.StatusGet', 'DataLog.ChsGet', 'DataLog.PropsGet'}
FROZEN = [k for k in EXPECTED if k not in DYNAMIC]
FAST = ['Current.Get', 'ZCtrl.ZPosGet', 'ZCtrl.OnOffGet', 'ZCtrl.StatusGet',
        'Scan.StatusGet', 'Bias.Get', 'ZCtrl.SetpntGet', 'SafeTip.OnOffGet',
        'AutoApproach.OnOffGet', 'BiasSpectr.StatusGet', 'ZSpectr.StatusGet',
        'FolMe.PSOnOffGet', 'FolMe.XYPosGet', 'SafeTip.SignalGet']
READ_ARGS = dict(b.READ_ARGS)
READ_ARGS['FolMe.XYPosGet'] = [0]
b.p.COMMANDS['AutoApproach.OnOffGet'] = {'inputs': [], 'outputs': ['H'], 'access': 'read'}
for k, code in [('Util.RTFreqGet', 'f'), ('Util.RTOversamplGet', 'i'), ('Util.AcqPeriodGet', 'f')]:
    schema = {'inputs': [], 'outputs': [code], 'access': 'read'}
    if k not in b.p.COMMANDS:
        b.p.COMMANDS[k] = schema
    b.require(b.p.COMMANDS[k] == schema, 'Utility codec changed: ' + k)
for k in ['AutoApproach.OnOffGet', 'Util.RTFreqGet', 'Util.RTOversamplGet', 'Util.AcqPeriodGet']:
    READ_ARGS[k] = []
for k in FROZEN:
    actual = 'LockIn.ModOnOffGet' if k.startswith('LockIn.ModOnOffGet[') else k
    b.require(b.p.COMMANDS[actual]['access'] == 'read', 'Unexpected getter ' + k)
WRITES = [('Scan.Action', [0, 0]), ('Scan.Action', [1, 0]), ('ZCtrl.Withdraw', [1, 2000])]
b.require(b.p.COMMANDS['ZCtrl.Withdraw']['inputs'] == ['I', 'i'], 'Withdraw codec changed')
b.require(EXPECTED['Scan.BufferGet'] == [3, [0, 30, 89], 240, 240], 'Buffer reference changed')
b.require(EXPECTED['Scan.FrameGet'] == [0., 0., 5.000000058430487e-8, 5.000000058430487e-8, 0.], 'Frame reference changed')
b.require(EXPECTED['Scan.PropsGet'][:3] == [0, 0, 0], 'Need finite scan / autosave all')
NOMINAL = EXPECTED['Scan.BufferGet'][3] * sum(EXPECTED['Scan.SpeedGet'][2:4])
b.require(437.7 < NOMINAL < 437.8, 'Unexpected nominal duration')
CURRENT_ABORT = 400e-12
Z_MARGIN = 2e-9
POST_BUDGET = 30.0  # Six <=2s reads + full configuration + >=5s native post-roll.
SCAN_SLACK = 15.0
FULL_INTERVAL = 2.0
ENTRY_SAMPLE_BAND = (-150e-12, -50e-12)
ENTRY_MEAN_BAND = (-125e-12, -75e-12)
ENTRY_MIN_SPAN = 5.0
ENTRY_MAX_TOTAL = 10.0
ENTRY_MAX_GAP = 1.0
ENTRY_POLICY = HERE / 'diagnostic_scan_entry_policy_review.json'
ENTRY_POLICY_SHA = '57d717802af38762868489c2eb014e8c6637f48b7b34d069b9a17c0b50c67b88'
if hashlib.sha256(ENTRY_POLICY.read_bytes()).hexdigest() != ENTRY_POLICY_SHA:
    raise RuntimeError('Prospective diagnostic entry policy changed')


R06_SCOPE = HERE / 'R06_repair_user_scope.json'
R06_SCOPE_SHA = '649f6cda871e9dd59964baf767eb2112ab3efbbad671e0c0a8b3d44d3431aa20'
if hashlib.sha256(R06_SCOPE.read_bytes()).hexdigest() != R06_SCOPE_SHA:
    raise RuntimeError('R06 scope changed')

LOGGER_SOURCE_SHA = '527e5b5f3a7d542415c9efda6506818f64a8a910848766c34d37508fbed53184'
PULSE_CLAIM = ROOT / 'globalclaims/continuing_20261101_1939__pulse_05.claim'


def recording_proof(logger, logger_sha):
    sb.paths(sb.SESSION, logger)
    b.require(logger_sha == LOGGER_SOURCE_SHA == sb.sha(LOGGER_SOURCE), 'Expected frozen R06 logger')
    b.require(not (logger / 'outcome.json').exists(), 'R06 logger ended')
    ready_path = logger / 'READY.json'
    start_path = logger / 'start.claim'
    ready = json.loads(ready_path.read_bytes())
    start = json.loads(start_path.read_bytes())
    reservation_ref = json.loads((logger / 'recording_segment_reservation.json').read_bytes())
    reservation = sb.artifact(reservation_ref, sb.START_RESERVATION)
    for record in (ready, start, reservation):
        sb.verify_logger_identity(record, logger_sha)
    b.require(reservation['basename'] == ready['basename'] == sb.BASENAME and
              start['command'] == reservation['command'] == 'DataLog.Start' and
              start['args'] == reservation['args'] == [], 'Wrong native recording claim')
    b.require(ready['ready'] is True and ready['output_directory'] == str(logger) and
              ready['start_claim']['sha256'] == sb.sha(start_path) and
              reservation['monotonic_ns'] <= start['monotonic_ns'] <= ready['monotonic_ns'],
              'Missing or unordered R06 READY/start reservation')
    b.require(ready['native_status']['start'] == ready['native_start_identity'] and
              bool(ready['native_start_identity']) and not ready['native_status']['stop'] and
              ready['profile']['DataLog.PropsGet'][6] == sb.BASENAME, 'R06 native identity/profile mismatch')
    return {'ready_path': str(ready_path), 'ready_sha256': sb.sha(ready_path),
            'native_start_identity': ready['native_start_identity'], 'earliest_snapshot_ns': ready['monotonic_ns'],
            'start_sha256': sb.sha(start_path), 'segment_reservation': reservation_ref}


SETPOINT_SOURCE = HERE / 'setpoint_R06_induction_P03_once.py'
SETPOINT_SHA = 'c329771b2f63c43b1f5401fcabe21cba44bd08b199d5fa6010c3356dd4809745'
PULSE_SOURCE = HERE / 'pulse_R06_induction_P03_once.py'
PULSE_SHA = '90f18c29721c0b7605fcfe2904d9d4d394f2f4e83e38019265220b587126995c'
ADMISSION_SOURCE = HERE / 'induction_R06_P03_admission.py'
ADMISSION_SOURCE_SHA = '9247d49650db85bfc68ea52baba17bfff9e88ab19fe6bc380ae0057d3bb6cb44'
ACTION_BINDING = HERE / 'action_bindings_R06_induction_P03.py'
ACTION_BINDING_SHA = 'e7e3fcad26d11e3da24fd31b0c652cf1d472f2234aad76ebba85cbf4b67a4165'
POST_REVIEW = ROOT / sb.SESSION / 'induction_R06_P03_scan_review.json'
POST_REVIEW_SHA = None
FIXED_XY = [-2.5000000292152436e-8, -2.5000000292152436e-8]
BASELINE_REFS = {'manifest.json': {'path': '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/after_R06_P02_recovery_full/manifest.json', 'sha256': 'b31e48d7c61e91599d1e2485fc57b32e96c2e276944ceb3e47714a184bdddea4'}, 'outcome.json': {'path': '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/after_R06_P02_recovery_full/outcome.json', 'sha256': 'a9cf0bbff16181b8367ace00fc21193f0bf936b4a62ec98039ef7f3e304fa983'}, 'quality_report.json': {'path': '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/after_R06_P02_recovery_full/analysis/quality_report.json', 'sha256': '7f7199e8ccd0be0cb8699a9e2d7df2a83334f2fc1384f47c48def49156d344bb'}, 'scan_start.claim': {'path': '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/after_R06_P02_recovery_full/scan_start.claim', 'sha256': '1d37583e21889ca0ccce21c3de173d39f123dde1562b57d38ed7b7dd90e1b66e'}, 'logger_ready_bound.json': {'path': '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/after_R06_P02_recovery_full/logger_ready_bound.json', 'sha256': '463890eb80aae4f6889e35d1c5c8db72c96f5a74fba28b01180b56f956cc7b10'}}


def ref(path):
    return {'path': str(path), 'sha256': sb.sha(path)}


def frozen_admission_module():
    for path, digest in ((SETPOINT_SOURCE, SETPOINT_SHA), (PULSE_SOURCE, PULSE_SHA),
                         (ADMISSION_SOURCE, ADMISSION_SOURCE_SHA), (ACTION_BINDING, ACTION_BINDING_SHA)):
        b.require(sb.sha(path) == digest, 'P03 frozen source changed')
    spec = importlib.util.spec_from_file_location('post_P03_local_evidence_only', ADMISSION_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stage_records(role, source, digest, admission_ref, ready):
    directory = ROOT / sb.SESSION / role
    names = ['manifest.json', 'outcome.json', 'logger_ready_bound.json', 'before.json']
    refs = {name: ref(directory / name) for name in names}
    docs = {name: sb.artifact(value) for name, value in refs.items()}
    mf, out = docs['manifest.json'], docs['outcome.json']
    b.require(mf['source'] == str(source) and mf['source_sha256'] == digest
              and mf['induction_admission'] == admission_ref, 'P03 stage source/admission differs')
    b.require(mf['session_id'] == out['session_id'] == sb.SESSION
              and mf['action_id'] == out['action_id'] == 'P03'
              and all(mf.get(k) == v for k, v in sb.consumer_metadata(LOGGER_SOURCE_SHA).items())
              and docs['logger_ready_bound.json'] == ready, 'P03 stage belongs to another recording/action')
    b.require(mf['monotonic_ns'] <= out['monotonic_ns'], 'Stage chronology differs')
    return directory, refs, docs


def known_setpoint_stage(mode, admission_ref, ready):
    directory, refs, docs = stage_records(mode + '_induction_P03', SETPOINT_SOURCE, SETPOINT_SHA, admission_ref, ready)
    mf, out = docs['manifest.json'], docs['outcome.json']
    targets = [struct.unpack('>f', struct.pack('>f', p * 1e-12))[0]
               for p in [100 * 1.25**k for k in range(11)] + [1000.]]
    if mode == 'return':
        targets.reverse()
    b.require(out['status'] == 'completed' and out['mode'] == mf['mode'] == mode
              and out['attempted_sets'] == out['acknowledged_sets'] == 11
              and out['final_target_A'] == targets[-1]
              and not out.get('execution_unknown', False), 'Incomplete/unknown P03 setpoint stage')
    b.require(mf['targets_including_unwritten_initial_A'] == targets, 'P03 setpoint sequence changed')
    actual_claims = set(directory.glob('step_*.claim'))
    b.require(actual_claims == {directory / f'step_{k:02d}.claim' for k in range(1, 12)}, 'Not exactly eleven setpoint claims')
    previous = mf['monotonic_ns']
    for index, target in enumerate(targets[1:], 1):
        claim_name, ack_name = f'step_{index:02d}.claim', f'step_{index:02d}_ack.json'
        refs[claim_name], refs[ack_name] = ref(directory / claim_name), ref(directory / ack_name)
        claim, ack = sb.artifact(refs[claim_name]), sb.artifact(refs[ack_name])
        b.require(claim['command'] == 'ZCtrl.SetpntSet' and claim['args'] == [target]
                  and claim['previous_target_A'] == targets[index-1] and claim['index'] == index
                  and claim['mode'] == mode and claim['source_sha256'] == SETPOINT_SHA
                  and claim['float32_hex'] == struct.pack('>f', target).hex()
                  and claim['at_most_once'] is True and ack['values'] == [] and not ack.get('warning'),
                  'P03 setpoint command/ACK differs')
        b.require(previous <= claim['monotonic_ns'] <= out['monotonic_ns'], 'Setpoint claim sequence differs')
        previous = claim['monotonic_ns']
    for name in ('after.json', 'final30_statistics.json', 'final30_samples.json'):
        refs[name] = ref(directory / name)
        docs[name] = sb.artifact(refs[name])
    stats = docs['final30_statistics.json']
    b.require(stats == out['final_statistics'] and stats['last5s_all_sampled_current_in_band'] is True
              and stats['Z_gates_passed'] is True and stats['duration_s'] >= 10
              and abs(stats['Z_slope_pm_s']) <= 10 and stats['Z_detrended_rms_pm'] <= 10,
              'Setpoint final sampled recovery failed')
    rows = docs['final30_samples.json']
    b.require(rows[-1]['t'] - rows[0]['t'] >= 30, 'Complete thirty-second setpoint observation missing')
    final = docs['after.json']
    b.require(final == out['final_sampled_state'] and previous <= final['end']['monotonic_ns'] <= out['monotonic_ns'],
              'Final setpoint readback differs or predates steps')
    v = final['values']
    b.require(v['ZCtrl.SetpntGet'] == [targets[-1]] and v['FolMe.XYPosGet'] == FIXED_XY,
              'Final setpoint/XY mismatch')
    for key in FROZEN:
        if key != 'ZCtrl.SetpntGet':
            b.require(v[key] == EXPECTED[key], 'Setpoint final frozen field differs: ' + key)
    b.require(v['ZCtrl.OnOffGet'] == [1] and v['ZCtrl.StatusGet'] == [2] and v['Scan.StatusGet'] == [0]
              and all(v[k] == [0] for k in ('SafeTip.OnOffGet','AutoApproach.OnOffGet','BiasSpectr.StatusGet','ZSpectr.StatusGet','FolMe.PSOnOffGet')),
              'Setpoint final controller/action state differs')
    return refs, docs


def evidence_for_scan(logger, logger_sha):
    proof = recording_proof(logger, logger_sha)
    ra = frozen_admission_module()
    ready = json.loads((logger / 'READY.json').read_bytes())
    b.require(isinstance(POST_REVIEW_SHA, str) and len(POST_REVIEW_SHA) == 64, 'Explicit independent post-return review SHA required')
    post_ref = {'path': str(POST_REVIEW), 'sha256': POST_REVIEW_SHA}
    post = sb.artifact(post_ref, POST_REVIEW)
    admission_ref = post['induction_admission']
    admission = sb.artifact(admission_ref, ra.ADMISSION)
    b.require(admission['schema'] == 'R06-P03-induction-admission-v1' and admission['action_id'] == 'P03'
              and admission['episode_id'] == ra.EPISODE and admission['fixed_xy_m'] == FIXED_XY
              and admission['pulse_attempts_before'] == 4 and admission['pulse_ordinal'] == 5
              and admission['max_pulses_total'] == 6 and admission['pulse_count_reset'] is False,
              'P03 identity/cumulative budget changed')
    baseline_docs = {key: sb.artifact(value) for key, value in BASELINE_REFS.items()}
    b.require(admission['baseline_outcome'] == BASELINE_REFS['outcome.json']
              and admission['baseline_quality'] == BASELINE_REFS['quality_report.json'], 'Actual212 baseline differs')
    ra.baseline_proof(admission)  # Pure local proof; never history_guard/validate after an actual pulse.
    prepare_refs, prepare = known_setpoint_stage('prepare', admission_ref, ready)
    pulse_dir, pulse_refs, pulse = stage_records('pulse_induction_P03', PULSE_SOURCE, PULSE_SHA, admission_ref, ready)
    mf, out = pulse['manifest.json'], pulse['outcome.json']
    for name in ('session_reservation.json','pulse.claim','pulse_ack.json','feedback_readiness.json','post30s_samples.json','post30s_summary.json','after30s.json'):
        pulse_refs[name] = ref(pulse_dir / name)
        pulse[name] = sb.artifact(pulse_refs[name])
    shared_ref = ref(PULSE_CLAIM)
    shared = sb.artifact(shared_ref, PULSE_CLAIM)
    claim, ack = pulse['pulse.claim'], pulse['pulse_ack.json']
    ledger_ref = {'path': str(ROOT / sb.SESSION / 'induction_P03.ledger.json'), 'sha256': mf['ledger_sha256']}
    ledger = sb.artifact(ledger_ref)
    b.require(ledger['induction_admission'] == admission_ref and ledger['preparation_outcome'] == prepare_refs['outcome.json']
              and ledger['preparation_manifest'] == prepare_refs['manifest.json'], 'Pulse does not bind this complete preparation')
    prep_review = ra.native_review(ledger['preparation_native_review'], prepare_refs['outcome.json'], prepare['outcome.json']['monotonic_ns'])
    b.require(prep_review['allow_one_pulse'] is True and prep_review['preparation_manifest'] == prepare_refs['manifest.json'],
              'Independent native review/one-pulse choice missing')
    b.require(shared == pulse['session_reservation.json'] and shared['source_sha256'] == PULSE_SHA
              and shared['session_id'] == sb.SESSION and shared['action_id'] == 'P03' and shared['episode_id'] == ra.EPISODE
              and shared['pulse_ordinal'] == shared['pulse_attempts_reserved'] == 5 and shared['pulse_attempts_before'] == 4
              and shared['output'] == str(pulse_dir) and shared['ledger_sha256'] == claim['ledger_sha256'] == mf['ledger_sha256']
              and shared['induction_admission_sha256'] == admission_ref['sha256']
              and shared['command'] == claim['command'] == 'Bias.Pulse' and shared['args'] == claim['args'] == ra.REQUEST
              and shared['purpose'] == 'induction_attempt' and claim['at_most_once'] is True,
              'Known single pulse provenance/cumulative ordinal differs')
    b.require(out['status'] == 'single_pulse_knownend_30s_observed' and out['pulse_attempted'] is True
              and out['native_end_confirmed'] is True and out['writer_outcome_unknown'] is False
              and out['pulse_ordinal'] == 5 and out['fixed_xy_m'] == FIXED_XY
              and ack['values'] == [] and not ack.get('warning'), 'P03 pulse completion/ACK ambiguous')
    b.require(pulse['post30s_summary.json'] == out['post_metrics'] and out['post_metrics']['elapsed_s'] >= 30,
              'Pulse thirty-second post observation missing')
    readiness = pulse['feedback_readiness.json']
    observations = readiness['observations']
    b.require(readiness['known_ACK'] == pulse_refs['pulse_ack.json'] and readiness['max_wait_s'] == 2.
              and readiness['ready'] is True and readiness['error'] is None and readiness['readonly'] is True
              and readiness['writes'] == [] and readiness['Hold_is_waiting_not_stable'] is True
              and readiness['post30s_excludes_readiness_time'] is True and observations,
              'Known independent Hold-to-On2 readiness evidence missing')
    sp = importlib.util.spec_from_file_location('P03_scan_readonly_guard_checks', PULSE_SOURCE)
    pm = importlib.util.module_from_spec(sp);sp.loader.exec_module(pm)
    check = object.__new__(pm.Run);check.xy = FIXED_XY
    ack_s = ack['monotonic_ns'] / 1e9
    previous = ack_s
    for index, row in enumerate(observations):
        v = row['values']
        b.require(row['observation_index'] == index and previous <= row['host_monotonic_s']
                  and 0 <= row['elapsed_from_ACK_s'] <= 2.
                  and row['elapsed_from_ACK_s'] == row['host_monotonic_s'] - ack_s,
                  'Readiness observation identity/time differs')
        if index == len(observations)-1:
            pm.Run.guard(check,v,full=True)
        else:
            pm.Run.hold_readiness_guard(check,v,full=True)
        previous = row['host_monotonic_s']
    ready_out = out['feedback_readiness']
    b.require(ready_out['status'] == 'known_On2_ready' and ready_out['getter_observations'] == len(observations)
              and ready_out['Hold_observations'] == len(observations)-1
              and ready_out['elapsed_from_ACK_s'] == observations[-1]['elapsed_from_ACK_s']
              and ready_out['post30s_not_yet_started'] is True and ready_out['total_deadline_not_reset'] is True,
              'Readiness outcome does not match saved actual state observations')
    post_rows = pulse['post30s_samples.json']['rows']
    b.require(post_rows and post_rows[0]['t'] >= observations[-1]['host_monotonic_s']
              and pulse['after30s.json']['start']['monotonic_ns'] / 1e9 >= post_rows[-1]['t'],
              'Post30 observation predates actual feedback readiness')
    pm.Run.guard(check,pulse['after30s.json']['values'],full=True,entry=True)
    return_refs, returned = known_setpoint_stage('return', admission_ref, ready)
    return_review_ref = post['return_native_review']
    b.require(Path(return_review_ref['path']) == ra.RETURN_REVIEW, 'Independent return review path differs')
    return_review = ra.native_review(return_review_ref, pulse_refs['outcome.json'], out['monotonic_ns'])
    b.require(return_review['allow_one_return'] is True, 'Independent return choice missing')
    native = ra.native_review(post_ref, return_refs['outcome.json'], returned['outcome.json']['monotonic_ns'])
    b.require(native['allow_one_scan'] is True and native['event_id'] == 'after_R06_P03_full'
              and native['preparation_outcome'] == prepare_refs['outcome.json']
              and native['pulse_outcome'] == pulse_refs['outcome.json'] and native['fixed_xy_m'] == FIXED_XY
              and native['no_unplanned_intervention_since_baseline'] is True,
              'Root must separately select this matched full scan after known independent return')
    order = [baseline_docs['outcome.json']['monotonic_ns'], prepare['manifest.json']['monotonic_ns'],
             prepare['outcome.json']['monotonic_ns'], prep_review['monotonic_ns'], mf['monotonic_ns'],
             shared['monotonic_ns'], claim['monotonic_ns'], ack['monotonic_ns'], out['monotonic_ns'],
             return_review['monotonic_ns'], returned['manifest.json']['monotonic_ns'],
             returned['outcome.json']['monotonic_ns'], native['monotonic_ns']]
    b.require(order == sorted(order), 'P03 preparation/pulse/return/native choice chronology differs')
    proof.update(earliest_snapshot_ns=native['monotonic_ns'], matched_baseline=BASELINE_REFS,
                 action={'preparation': prepare_refs, 'pulse': pulse_refs, 'return': return_refs},
                 action_start=shared_ref, completed_action_XY_m=FIXED_XY,
                 induction_admission=admission_ref, pulse_ledger=ledger_ref,
                 preparation_native_review=ledger['preparation_native_review'],
                 return_native_review=return_review_ref, post_return_native_review=post_ref,
                 intervention='100pA_to_1nA_preparation_then_one_-6V_20ms_hold_pulse_then_independent_return100pA',
                 pulse_ordinal=5, quality_claim=None)
    return proof


def guard(v, full=False, entry=False):
    b.require(v['ZCtrl.OnOffGet'] == [1] and v['ZCtrl.StatusGet'] == [2], 'Feedback not On/2')
    b.require(v['Bias.Get'] == [-1.] and v['ZCtrl.SetpntGet'] == EXPECTED['ZCtrl.SetpntGet'], 'Bias/setpoint changed')
    current, z = v['Current.Get'][0], v['ZCtrl.ZPosGet'][0]
    b.require(b.finite(current) and abs(current) < CURRENT_ABORT, 'Sampled current nonfinite or >=400pA software gate')
    hi, lo = EXPECTED['ZCtrl.LimitsGet']
    b.require(b.finite(z) and lo + Z_MARGIN <= z <= hi - Z_MARGIN, 'Z crossed 2nm endpoint software margin')
    b.require(v['SafeTip.OnOffGet'] == [0], 'SafeTip no longer Off')
    for k in ['AutoApproach.OnOffGet', 'BiasSpectr.StatusGet', 'ZSpectr.StatusGet', 'FolMe.PSOnOffGet']:
        b.require(v[k] == [0], 'Concurrent/unknown native action: ' + k)
    b.require(all(b.finite(x) for x in v['FolMe.XYPosGet']), 'Nonfinite XY')
    if full:
        for k in FROZEN:
            b.require(v[k] == EXPECTED[k], 'Exact frozen field changed: ' + k)
    if entry:
        b.require(v['Scan.StatusGet'] == [0], 'Scan nonrunning state required before admission (0 alone cannot exclude pause)')
        b.require(-120e-12 <= current <= -80e-12, 'Entry current outside signed -120..-80pA')



def diagnostic_entry_guard(v, full=False):
    # Scan admission only. Original guard(entry=True) remains untouched for cleanup.
    guard(v, full=full, entry=False)
    b.require(v['Scan.StatusGet'] == [0],
              'Scan nonrunning state required before admission (0 alone cannot exclude pause)')
    b.require(ENTRY_SAMPLE_BAND[0] <= v['Current.Get'][0] <= ENTRY_SAMPLE_BAND[1],
              'Diagnostic entry current outside signed -150..-50pA')


def local_path(path):
    p = Path(path).resolve()
    b.require(p.is_relative_to(ROOT) and 'win_users' not in p.parts, 'Only local paths inside this new batch')
    return p


def attempt_paths(session, event, output, logger):
    b.require(session == sb.SESSION, 'Only session_02/R06 allowed by this variant')
    b.require(event == 'after_R06_P03_full', 'Only the R06 full post-induction P03 composite event is allowed')
    session_root = ROOT / session
    b.require(local_path(output) == session_root / event, 'Output must match the fixed session/event identity')
    sb.paths(session,logger)
    return ROOT / 'claims' / (session + '__' + event + '.claim')


def reserve_attempt(session, event, output, logger, source, source_sha, fresh, fresh_sha, logger_sha):
    path = attempt_paths(session, event, output, logger)
    b.require(hashlib.sha256(Path(source).read_bytes()).hexdigest() == source_sha, 'Executing source SHA mismatch')
    path.parent.mkdir(exist_ok=True)
    payload = {**b.stamp(), 'session_id': session, 'event_id': event, 'output': str(Path(output).resolve()),
        'source': str(source), 'source_sha256': source_sha, 'fresh_snapshot': str(fresh),
        'fresh_snapshot_sha256': fresh_sha, 'logger': str(logger), **sb.consumer_metadata(logger_sha),
        'attempt_reserved_not_execution_proof': True, 'no_retry_or_reservation_release': True}
    raw = (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        d = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(d)
        finally: os.close(d)
    except BaseException:
        # Never remove a reservation after any partial persistence.
        raise
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}


class Client(b.Client):
    def __init__(self, store):
        super().__init__(store)
        self.timeout = .5
        self.permit = None
        self.used = set()

    def call(self, command, args=None, timeout=.5):
        args = [] if args is None else args
        if command in READ_ARGS and args == READ_ARGS[command]:
            pass
        elif command == 'LockIn.ModOnOffGet' and args in ([1], [2]):
            pass
        elif command == 'Scan.WaitEndOfScan' and args == [300]:
            pass
        elif command == 'Scan.FrameDataGrab' and len(args) == 2 and args[0] in b.CHANNELS and args[1] in (0, 1):
            pass
        else:
            key = (command, tuple(args))
            b.require((command, args) in WRITES and self.permit == (command, args) and key not in self.used,
                      'Unclaimed/repeated/unreviewed write')
            self.used.add(key)
            self.permit = None
        self.connect_bound()
        return b.p.NanonisClient.call(self, command, args, timeout)


class Run:
    def __init__(self, output, logger, fresh, fresh_sha, session, event, source_sha, logger_source_sha):
        attempt_paths(session, event, output, logger)
        self.session, self.event = session, event
        self.source_path, self.source_sha = Path(__file__), source_sha
        self.logger_source_sha = logger_source_sha
        self.store = b.Store(output)
        self.client = Client(self.store)
        self.logger, self.fresh, self.fresh_sha = Path(logger), Path(fresh), fresh_sha
        self.abort = False
        self.start_attempted = self.start_ack = self.owned = False
        self.stop_attempted = self.end_confirmed = self.unknown_execution = False
        self.deadline = self.scan_start = None
        self.last_logger_elapsed = None
        self.logger_progress_time = None
        self.ready = self.logger_start = None

    def check_abort(self):
        b.require(not self.abort and not (self.store.root / 'ABORT').exists(), 'Operator abort')
        if self.deadline is not None:
            b.require(time.monotonic() < self.deadline, 'Bounded scan deadline reached')

    def q(self, name, args=None, timeout=.5, cleanup=False):
        if not cleanup:
            self.check_abort()
        if name.startswith('LockIn.ModOnOffGet['):
            args = [int(name[-2])]
            name = 'LockIn.ModOnOffGet'
        if args is None:
            args = READ_ARGS.get(name, [])
        result = self.client.call(name, args, timeout)
        b.require(not result.get('warning'), 'Native warning: ' + name)
        return result['values']

    def poll(self, label, full=False, cleanup=False):
        start = time.monotonic()
        v = {}
        for k in dict.fromkeys(FAST + (FROZEN if full else [])):
            b.require(time.monotonic() - start <= 2., 'Getter-group 2s software budget exhausted')
            v[k] = self.q(k, cleanup=cleanup)
        elapsed = time.monotonic() - start
        self.store.event(label, values=v, duration_s=elapsed, sequential_not_atomic=True)
        b.require(elapsed <= 2., 'Sequential getter group exceeded 2s software budget')
        return v

    def write(self, command, args, label, timeout=.5):
        self.store.save(label + '.claim', {**b.stamp(), 'command': command, 'args': args,
            'at_most_once': True, 'source_sha256': self.source_sha,
            'static_reference_sha256': REF_SHA, 'session_id': self.session, 'event_id': self.event})
        fd = os.open(self.store.root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.client.permit = (command, args)
        try:
            result = self.client.call(command, args, timeout)
            self.store.save(label + '_ack.json', result)
            b.require(result['values'] == [] and not result.get('warning'), 'Nonempty/warning write ACK')
        except BaseException:
            self.unknown_execution = True
            raise

    def fresh_guard(self):
        proof = evidence_for_scan(self.logger, self.logger_source_sha)
        self.store.save('fresh_recording_evidence.json', proof)
        local_path(self.fresh)
        raw = self.fresh.read_bytes()
        b.require(hashlib.sha256(raw).hexdigest() == self.fresh_sha, 'Fresh snapshot hash mismatch')
        v = json.loads(raw)
        b.require(proof['earliest_snapshot_ns'] <= v['start']['monotonic_ns'] <= v['end']['monotonic_ns'],
                  'Fresh snapshot predates R06 evidence or has an invalid interval')
        status = v['values']['DataLog.StatusGet']
        b.require(len(status) == 10 and status[1] == proof['native_start_identity'] and not status[6],
                  'Snapshot native logger differs from ongoing R06')
        age = (time.monotonic_ns() - v['end']['monotonic_ns']) / 1e9
        b.require(0 <= age <= 180, 'Fresh snapshot must be <=180s old; fresh live polling still required')
        diagnostic_entry_guard(v['values'], full=True)
        self.store.save('root_fresh_snapshot.json', v)
        self.store.event('root_snapshot_binding', source=str(self.fresh), sha256=self.fresh_sha, age_s=age)

    def logger_guard(self, remaining_scan_s, post_budget=POST_BUDGET, profile=False):
        sb.paths(self.session,self.logger)
        b.require(not (self.logger / 'outcome.json').exists(), 'Independent logger already ended')
        if self.ready is None:
            b.require(hashlib.sha256(LOGGER_SOURCE.read_bytes()).hexdigest() == self.logger_source_sha,
                      'Independent logger source hash mismatch')
            manifest_raw = (self.logger / 'manifest.json').read_bytes()
            manifest = json.loads(manifest_raw)
            sb.verify_logger_identity(manifest,self.logger_source_sha)
            b.require(manifest.get('source_sha256') == self.logger_source_sha
                      and manifest.get('session_id') == self.session, 'Logger manifest source/session mismatch')
            self.store.save('logger_manifest_bound.json', manifest)
            self.ready = json.loads((self.logger / 'READY.json').read_bytes())
            self.logger_start = json.loads((self.logger / 'start.claim').read_bytes())
            b.require(self.ready['ready'] is True and Path(self.ready['output_directory']).resolve() == self.logger.resolve()
                      and hashlib.sha256((self.logger / 'start.claim').read_bytes()).hexdigest() == self.ready['start_claim']['sha256'],
                      'Logger READY/start-claim provenance mismatch')
            b.require(self.ready['native_duration_s'] == LOGGER_DURATION, 'Need fixed21600 nominal logger')
            b.require(self.ready['profile']['DataLog.ChsGet'] == [6, [0, 24, 30, 98, 99, 100]], 'Logger channels changed')
            props = self.ready['profile']['DataLog.PropsGet']
            b.require(props[:5] == [1, 6, 0, 0., 1], 'Logger timed21600 nominal / averaging / block profile changed')
            b.require(set(self.ready['profile']) == {'DataLog.ChsGet', 'DataLog.PropsGet', 'Util.RTFreqGet',
                      'Util.RTOversamplGet', 'Util.AcqPeriodGet'}, 'Unreviewed logger profile keys')
            for k in ['Util.RTFreqGet', 'Util.RTOversamplGet', 'Util.AcqPeriodGet']:
                b.require(self.ready['profile'][k] == EXPECTED[k], 'Logger sampling profile differs')
            for binding in (self.ready, self.logger_start):
                sb.verify_logger_identity(binding,self.logger_source_sha)
                b.require(binding.get('source_sha256') == self.logger_source_sha
                          and binding.get('session_id') == self.session, 'Logger READY/start source/session mismatch')
            b.require(self.logger_start.get('command') == 'DataLog.Start' and self.logger_start.get('args') == [],
                      'Logger start claim is not one DataLog.Start')
            self.store.save('logger_ready_bound.json', self.ready)
        with (self.logger / 'events.jsonl').open('rb') as f:
            size = f.seek(0, 2)
            f.seek(max(0, size - 200000))
            tail = f.read().splitlines()
        event = None
        for line in reversed(tail):
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if item.get('kind') == 'datalog_status':
                event = item
                break
        b.require(event is not None and 0 <= (time.monotonic_ns() - event['monotonic_ns']) / 1e9 <= 2.,
                  'No fresh <=2s independent native logger event')
        raw = self.q('DataLog.StatusGet')
        for state in [raw, event['raw_values']]:
            b.require(len(state) == 10 and state[1] == self.ready['native_start_identity'] and not state[6],
                      'Logger ended/replaced or status malformed')
        if profile:
            for name in self.ready['profile']:
                b.require(self.q(name) == self.ready['profile'][name], 'Active logger profile changed')
        elapsed = raw[2] * 3600 + raw[3] * 60 + raw[4]
        age = (time.monotonic_ns() - self.logger_start['monotonic_ns']) / 1e9
        b.require(b.finite(elapsed) and elapsed >= 0 and age >= 0, 'Nonfinite/backward logger clock')
        now = time.monotonic()
        if self.last_logger_elapsed is None or elapsed > self.last_logger_elapsed:
            self.logger_progress_time = now
        elif elapsed < self.last_logger_elapsed:
            raise RuntimeError('Native logger elapsed clock regressed')
        b.require(now - self.logger_progress_time < 3., 'No native logger elapsed progress for 3s')
        self.last_logger_elapsed = elapsed
        remaining = min((LOGGER_DURATION - elapsed) / 2., LOGGER_WALL_ESTIMATE - age)
        required = max(0., remaining_scan_s) + post_budget
        b.require(remaining >= required, 'Logger estimated remaining coverage below scan + post-read budget')
        self.store.event('logger_ongoing', native_status=raw, logger_event_monotonic_ns=event['monotonic_ns'],
            client_age_s=age, estimated_remaining_s=remaining, required_s=required,
            historical_half_wall_factor_assumed=True, uninterrupted_samples_not_proven=True)

    def entry_stability(self):
        # Use the first window only. No reset, sample exclusion, smoothing or retry.
        begun = previous = time.monotonic()
        samples = []
        accepted = False
        error = None
        try:
            while True:
                b.require(time.monotonic() - begun <= ENTRY_MAX_TOTAL,
                          'Diagnostic entry exceeded 10s total budget')
                poll_started = time.monotonic()
                v = self.poll('entry_stability')
                now = time.monotonic()
                samples.append({'poll_started_monotonic_s': poll_started,
                    'poll_completed_monotonic_s': now, 'signed_current_A': v['Current.Get'][0]})
                b.require(now - begun <= ENTRY_MAX_TOTAL, 'Diagnostic entry exceeded 10s total budget')
                b.require(now - previous <= ENTRY_MAX_GAP, 'Entry stability sampling gap >1s')
                previous = now
                diagnostic_entry_guard(v)
                self.logger_guard(NOMINAL + SCAN_SLACK)
                b.require(time.monotonic() - begun <= ENTRY_MAX_TOTAL,
                          'Diagnostic entry exceeded 10s total budget')
                span = now - samples[0]['poll_completed_monotonic_s']
                if span >= ENTRY_MIN_SPAN:
                    mean = sum(x['signed_current_A'] for x in samples) / len(samples)
                    b.require(ENTRY_MEAN_BAND[0] <= mean <= ENTRY_MEAN_BAND[1],
                              'Diagnostic entry whole-window mean outside signed -125..-75pA')
                    accepted = True
                    self.store.event('entry_stability_confirmed', sampled_duration_s=span,
                        signed_current_band_A=list(ENTRY_SAMPLE_BAND), whole_window_mean_A=mean,
                        whole_window_mean_band_A=list(ENTRY_MEAN_BAND), sample_count=len(samples),
                        first_contiguous_window_only=True, no_excluded_samples=True)
                    return
                time.sleep(.1)
        except BaseException as exc:
            error = str(exc)
            raise
        finally:
            currents = [x['signed_current_A'] for x in samples]
            finite = bool(currents) and all(b.finite(x) for x in currents)
            mean = sum(currents) / len(currents) if finite else None
            self.store.save('diagnostic_entry_summary.json', {**b.stamp(), 'accepted': accepted,
                'error': error, 'policy_sha256': ENTRY_POLICY_SHA, 'samples': samples,
                'sample_count': len(samples), 'minimum_A': min(currents) if finite else None,
                'maximum_A': max(currents) if finite else None, 'mean_A': mean,
                'population_std_A': (sum((x - mean)**2 for x in currents) / len(currents))**.5 if finite else None,
                'sampled_span_s': samples[-1]['poll_completed_monotonic_s'] - samples[0]['poll_completed_monotonic_s'] if samples else 0.,
                'total_elapsed_s': time.monotonic() - begun,
                'sample_time_note': 'Sequential getter group completion is a slow sampling proxy, not hardware timestamps or a peak bound.',
                'limits': {'each_sample_A': list(ENTRY_SAMPLE_BAND), 'whole_window_mean_A': list(ENTRY_MEAN_BAND),
                           'minimum_span_s': ENTRY_MIN_SPAN, 'maximum_total_s': ENTRY_MAX_TOTAL, 'maximum_gap_s': ENTRY_MAX_GAP},
                'first_window_only': True, 'excluded_samples': 0, 'software_engineering_admission_not_protection': True})

    def frames(self):
        rows, cols = EXPECTED['Scan.BufferGet'][3], EXPECTED['Scan.BufferGet'][2]
        records = []
        for channel in b.CHANNELS:
            for direction in (1, 0):
                state = self.poll('pre_frame_guard')
                guard(state)
                b.require(state['Scan.StatusGet'] == [0], 'A new scan began before frame read')
                self.logger_guard(0, post_budget=5 + (6 - len(records)) * 2.5, profile=True)
                values = self.q('Scan.FrameDataGrab', [channel, direction], timeout=2.)
                body = self.store.last_response_body
                n, name, nr, nc, matrix, scan_direction = values
                b.require([nr, nc] == [rows, cols] and matrix['shape'] == [rows, cols], 'Frame dimensions mismatch')
                b.require(scan_direction == 0 and len(matrix['values']) == rows * cols, 'Wrong direction/matrix count')
                offset = 12 + n
                raw = body[offset:offset + rows * cols * 4]
                b.require(len(raw) == rows * cols * 4 and len(body) == offset + len(raw) + 12,
                          'Unexpected full matrix body/trailer length')
                b.require(struct.unpack('>IIi', body[-12:]) == (0, 0, 0), 'Unexpected direction/status trailer')
                nums = struct.unpack('>' + str(rows * cols) + 'f', raw)
                count = sum(b.finite(x) for x in nums)
                rec = {**b.stamp(), 'channel_index': channel, 'data_direction': direction, 'channel_name': name,
                    'rows': rows, 'columns': cols, 'scan_direction': scan_direction,
                    'finite_values': count, 'total_values': rows * cols, 'wire_sequence': self.store.sequence,
                    'format': 'original IEEE754 float32 big-endian row-major bytes',
                    'matrix': self.store.save_bytes(f'frames/channel_{channel}_{direction}.f32be', raw),
                    'minimum': min(nums), 'maximum': max(nums), 'acquisition_time': None, 'tcp_frame_id': None}
                self.store.save(f'frames/channel_{channel}_{direction}.json', rec)
                records.append(rec)
                b.require(count == rows * cols, 'Nonfinite completed matrix (raw saved unchanged)')
        return records

    def cleanup(self, out):
        out['requires_native_check'] = True
        if self.unknown_execution or getattr(self.client, '_closed', False) or not (self.start_ack and self.owned):
            out['cleanup_omitted'] = 'Unknown execution/transport or no acknowledged-and-observed ownership; no competing writes'
            return
        try:
            state = self.poll('cleanup_control_state', full=True, cleanup=True)
            for k in ['AutoApproach.OnOffGet', 'BiasSpectr.StatusGet', 'ZSpectr.StatusGet', 'FolMe.PSOnOffGet']:
                b.require(state[k] == [0], 'Concurrent native action; no cleanup write')
            b.require((state['ZCtrl.OnOffGet'], state['ZCtrl.StatusGet']) in [([1], [2]), ([0], [1])],
                      'Unknown/native recovery state; no competing cleanup')
            b.require(state['Scan.StatusGet'] in ([0], [1]), 'Unknown scan status')
            b.require(state['Scan.FrameGet'] == EXPECTED['Scan.FrameGet'] and state['Scan.BufferGet'] == EXPECTED['Scan.BufferGet'],
                      'Frame/buffer ownership changed; no cleanup write')
            if not self.end_confirmed:
                b.require(not self.stop_attempted, 'Stop already attempted')
                self.stop_attempted = True
                self.write('Scan.Action', [1, 0], 'failed_owned_scan_stop')
                out['stop_acknowledged'] = True
            else:
                b.require(state['Scan.StatusGet'] == [0], 'A new scan began after witnessed end; no cleanup write')
                out['stop_omitted_after_witnessed_end'] = True
            post = self.poll('post_stop', full=True, cleanup=True)
            b.require(post['Scan.StatusGet'] == [0], 'Scan did not become nonrunning after acknowledged Stop')
            for k in FROZEN:
                b.require(post[k] == EXPECTED[k], 'Configuration changed; no Withdraw: ' + k)
            for k in ['AutoApproach.OnOffGet', 'BiasSpectr.StatusGet', 'ZSpectr.StatusGet', 'FolMe.PSOnOffGet']:
                b.require(post[k] == [0], 'Concurrent native action after Stop')
            self.store.save('after_failure.json', {'values': post})
            if post['ZCtrl.OnOffGet'] == [0] and post['ZCtrl.StatusGet'] == [1]:
                out['withdraw_omitted'] = 'Already Off/1; no additional movement'
                return
            b.require(post['ZCtrl.OnOffGet'] == [1] and post['ZCtrl.StatusGet'] == [2], 'Feedback execution state unclear')
            try:
                guard(post, full=True, entry=True)
                out.update(withdraw_needed=False, feedback_retained_sampled_On2=True,
                           post_stop_stability_duration_not_proven=True)
                return
            except RuntimeError as exc:
                out['withdraw_reason'] = str(exc)
            current, z = post['Current.Get'][0], post['ZCtrl.ZPosGet'][0]
            hi, lo = EXPECTED['ZCtrl.LimitsGet']
            needs_withdraw = (not b.finite(current) or not -120e-12 <= current <= -80e-12
                or not b.finite(z) or not lo + Z_MARGIN <= z <= hi - Z_MARGIN)
            b.require(needs_withdraw, 'No identified current/Z failure permits Withdraw; manual state review')
            self.write('ZCtrl.Withdraw', [1, 2000], 'failure_withdraw', timeout=2.5)
            out['withdraw_acknowledged'] = True
            deadline, since, previous = time.monotonic() + 8., None, None
            while time.monotonic() < deadline:
                v = self.poll('withdraw_verification', cleanup=True)
                now = time.monotonic()
                good = (v['Scan.StatusGet'] == [0] and v['ZCtrl.OnOffGet'] == [0] and v['ZCtrl.StatusGet'] == [1]
                    and all(v[k] == [0] for k in ['AutoApproach.OnOffGet', 'BiasSpectr.StatusGet', 'ZSpectr.StatusGet', 'FolMe.PSOnOffGet'])
                    and v['SafeTip.OnOffGet'] == [0] and v['Bias.Get'] == EXPECTED['Bias.Get']
                    and b.finite(v['Current.Get'][0]) and abs(v['Current.Get'][0]) < 10e-12
                    and b.finite(v['ZCtrl.ZPosGet'][0]) and abs(v['ZCtrl.ZPosGet'][0] - EXPECTED['ZCtrl.HomePropsGet'][1]) < 1e-12)
                if not good:
                    since = None
                elif since is None or (previous is not None and now - previous > 1.):
                    since = now
                previous = now
                if since is not None and now - since >= 3.:
                    self.store.save('withdraw_confirmed.json', {'values': v, 'sampled_duration_s': now - since})
                    out['withdraw_Off1_home_confirmed'] = True
                    return
                time.sleep(.1)
            raise RuntimeError('Withdraw ACK without 3s sampled Off1/Home confirmation')
        except BaseException as exc:
            out['cleanup_error'] = str(exc)

    def execute(self):
        out = {'status': 'not_started', 'completed_frame_confirmed': False, 'native_file_archived': False,
               'native_file_post_audit_required': True, 'clean_tip_or_repair_claim': False}
        try:
            self.store.save('attempt_binding.json', reserve_attempt(self.session, self.event, self.store.root,
                self.logger, self.source_path, self.source_sha, self.fresh, self.fresh_sha, self.logger_source_sha))
            self.store.save('manifest.json', {**b.stamp(), **plan(), 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'fresh_snapshot_path': str(self.fresh), 'fresh_snapshot_sha256': self.fresh_sha,
                'session_id': self.session, 'event_id': self.event, **sb.consumer_metadata(self.logger_source_sha)})
            self.fresh_guard()
            before = self.poll('before', full=True)
            diagnostic_entry_guard(before, full=True)
            self.store.save('before.json', {'values': before})
            self.logger_guard(NOMINAL + SCAN_SLACK + ENTRY_MAX_TOTAL, profile=True)
            self.entry_stability()
            immediate = self.poll('immediate_before', full=True)
            diagnostic_entry_guard(immediate, full=True)
            self.store.save('immediate_before_start.json', {'values': immediate})
            self.logger_guard(NOMINAL + SCAN_SLACK, profile=True)
            xy = immediate['FolMe.XYPosGet']
            self.store.save('native_start_positioning.json', {'observed_prestart_XY_m': xy,
                'nominal_start_XY_m': [-25e-9, 25e-9], 'nominal_end_XY_m': [-25e-9, -25e-9],
                'straight_line_start_distance_m': sum((a-c)**2 for a,c in zip(xy, [-25e-9,25e-9]))**.5,
                'path_not_measured': True, 'note': 'Scan.Start may natively position to full-frame start. No independent move writer.'})
            self.check_abort()
            self.start_attempted = True
            self.scan_start = time.monotonic()
            self.deadline = self.scan_start + NOMINAL + SCAN_SLACK
            self.write('Scan.Action', [0, 0], 'scan_start')
            self.start_ack = True
            initial = self.poll('running_observed')
            b.require(initial['Scan.StatusGet'] == [1], 'Start ACK but running not observed; ownership unconfirmed')
            self.owned = True
            guard(initial)
            last_full = -1e9
            while True:
                self.check_abort()
                full = time.monotonic() - last_full >= FULL_INTERVAL
                v = self.poll('scan_guard', full=full)
                guard(v, full=full)
                if full:
                    last_full = time.monotonic()
                self.logger_guard(max(0., self.deadline - time.monotonic()), profile=full)
                b.require(v['Scan.StatusGet'] in ([0], [1]), 'Unexpected scan status')
                b.require(self.deadline - time.monotonic() >= .8, 'No time for bounded WaitEnd')
                values = self.q('Scan.WaitEndOfScan', [300], timeout=.8)
                elapsed = time.monotonic() - self.scan_start
                self.store.event('wait_end', values=values, elapsed_s=elapsed)
                b.require(len(values) == 3 and values[0] in (0, 1) and isinstance(values[2], str), 'Malformed WaitEnd')
                if values[0] == 0:
                    b.require(elapsed >= .9 * NOMINAL and values[1] == len(values[2].encode('utf-8'))
                              and values[2].lower().endswith('.sxm'), 'Premature/unnamed/malformed native completion path')
                    end = {**b.stamp(), 'values': values, 'elapsed_s': elapsed}
                    self.end_confirmed = True
                    self.deadline = None
                    break
                b.require(v['Scan.StatusGet'] == [1], 'Nonrunning/pause without witnessed completion; incomplete')
            after = self.poll('after', full=True)
            guard(after, full=True)
            b.require(after['Scan.StatusGet'] == [0], 'Scan running after witnessed end')
            self.store.save('after.json', {'values': after})
            self.logger_guard(0., profile=True)
            frames = self.frames()
            final = self.poll('after_frames', full=True)
            guard(final, full=True)
            b.require(final['Scan.StatusGet'] == [0], 'Another scan began during frame reads')
            self.store.save('after_frames.json', {'values': final})
            post_start = time.monotonic()
            while time.monotonic() - post_start < 5.:
                state = self.poll('post_roll_guard')
                guard(state)
                b.require(state['Scan.StatusGet'] == [0], 'A new scan began during post-roll')
                self.logger_guard(0., post_budget=0., profile=True)
                time.sleep(.1)
            self.store.save('native_audit_required.json', {**b.stamp(), 'native_file_path': end['values'][2],
                'scan': 'Archive native SXM locally; SHA/size/header REC/ACQ/frame + all 345600 f32 words compare, including orientation.',
                'logger': 'After finite native end: archive EVERY DAT block with receipt, verify headers/channels/dt/finite samples; map per-file coverage of start/end/post-roll; no gapfree or true peak claim.',
                'logger_directory': str(self.logger), 'logger_start_identity': self.ready['native_start_identity'],
                'scan_start_claim': 'scan_start.claim', 'native_end_event': end,
                'samples_expected_per_scan_plane': 57600, 'total_scan_values': 345600,
                'native_coverage_independently_verified': False})
            out.update(status='completed', completed_frame_confirmed=True, end_event=end,
                native_file_path=end['values'][2], frames=frames, nominal_seconds=NOMINAL,
                elapsed_seconds=time.monotonic() - self.scan_start, post_frame_logger_observation_s=time.monotonic() - post_start)
        except BaseException as exc:
            self.deadline = None
            out.update(status='incomplete' if self.start_attempted else 'rejected_before_start', error=str(exc),
                start_attempted=self.start_attempted, start_acknowledged=self.start_ack, owned_running_observed=self.owned,
                end_event_confirmed=self.end_confirmed, execution_unknown=self.unknown_execution)
            if self.start_attempted:
                self.cleanup(out)
        finally:
            self.client.close()
            self.store.save('outcome.json', {**b.stamp(), **out})
        print(json.dumps(b.clean({k: v for k, v in out.items() if k != 'frames'}), indent=2))
        return 0 if out['status'] == 'completed' else 1


def plan():
    return {'scope': 'one new-batch 50nm full DOWN scan; no configuration change / On / tip-conditioning / retry',
        'session_ids': [sb.SESSION], 'recording_segment_id':sb.SEGMENT, 'logger_directory':str(sb.LOGGER_DIR),
        'segment_binding_source_sha256':SEGMENT_BINDING_SHA, 'original_variant_sha256':ORIGINAL_VARIANT_SHA,
        'event_roles': ['after_R06_P03_full'],
        'purpose': 'Complete same-settings post-P03 composite image after actual212, complete11-step1nA preparation, known single ordinal5 pulse, independent complete11-step100pA return, and separate root native review. No pulse-only causal attribution or predetermined degradation.',
        'setpoint_source': str(SETPOINT_SOURCE), 'setpoint_source_sha256': SETPOINT_SHA,
        'pulse_source': str(PULSE_SOURCE), 'pulse_source_sha256': PULSE_SHA,
        'feedback_readiness_proof':'Actual known ACK, recorded Hold-only wait <=2s acceptance, real On2 with original guards, then separate complete post30s',
        'post_return_review': str(POST_REVIEW), 'explicit_post_return_review_sha256_required': True,
        'logger_source_sha256': LOGGER_SOURCE_SHA,
        'claim': 'NEW/claims/session__event.claim O_EXCL+file/directory fsync; never reused or released',
        'source_binding': 'Explicit execution source SHA + initial anchor + fresh snapshot SHA + current session logger source/manifest/READY/start claim',
        'logger_source': str(LOGGER_SOURCE), 'native_logger_duration_nominal': LOGGER_DURATION,
        'derived_from_down': str(DOWN_SOURCE), 'derived_down_sha256': DOWN_SOURCE_SHA,
        'derived_from': str(UP_SOURCE), 'derived_source_sha256': UP_SOURCE_SHA, 'scan_direction': 0,
        'nominal_start_XY_m': [-25e-9, 25e-9], 'nominal_end_XY_m': [-25e-9, -25e-9],
        'direction_note': 'Down: high Y to low Y. Forward/backward data selector stays 1/0 and is independent of scan_direction. Actual XY remains recorded in live polls and final readbacks; raw SXM orientation audited separately.',
        'static_reference': str(REF), 'static_reference_sha256': REF_SHA, 'frozen_fields': FROZEN,
        'dynamic_fields_recorded_not_frozen': sorted(DYNAMIC), 'unavailable_reference': {'Current.CalibrGet': 'Gain index invalid; not fabricated'},
        'host': b.HOST, 'port': b.PORT, 'source_ip': b.SOURCE_IP, 'interface': b.INTERFACE,
        'frame': EXPECTED['Scan.FrameGet'], 'buffer': EXPECTED['Scan.BufferGet'], 'speed': EXPECTED['Scan.SpeedGet'],
        'nominal_frame_s': NOMINAL, 'software_deadline_s': NOMINAL + SCAN_SLACK,
        'entry': 'One diagnostic-only prospective policy: fresh <=180s / before / every first-window sample / immediate-before signed -150..-50pA On2; first contiguous >=5s, total<=10s, gap<=1s, arithmetic mean of ALL samples -125..-75pA. No reset/exclusion/retry; root confirms no paused native scan. Original cleanup still uses -120..-80pA.',
        'separate_R05_diagnostic_entry_exception_applies': False,
        'R06_scope': {'path': str(R06_SCOPE), 'sha256': R06_SCOPE_SHA},
        'entry_policy': {'path': str(ENTRY_POLICY), 'sha256': ENTRY_POLICY_SHA},
        'only_writes': WRITES, 'full_configuration_interval_s': FULL_INTERVAL, 'ordinary_query_timeout_s': .5,
        'wait_ms': 300, 'wait_transport_timeout_s': .8, 'frame_query_timeout_s': 2.,
        'frame_timeout_reason': '240x240 f32=230400 bytes/plane (~1.85ms ideal 1Gbps); 2s includes local host/network margin and audit delay. Not a throughput guarantee; failure never retries. Six <=2s reads plus guards within30s post budget.',
        'software_review_gates': {'sampled_abs_current_abort_A': CURRENT_ABORT, 'physical_Z_endpoint_margin_m': Z_MARGIN},
        'SafeTip': 'Off, exact before/during/after; stored threshold inactive; software polls cannot catch transients',
        'logger': 'Independent21600nominal extrapolated10800wall; admission >= frame +15s scan slack +30s postread margin (+10s entry), persistent <=2s status freshness and native progressing elapsed, same identity/profile throughout and>=5s postroll. Historical rate is an estimate, file audit mandatory.',
        'completion': 'One successful Start ACK AND observed running; native successful WaitEnd with named SXM at>=90% nominal, unchanged config/nonrunning, six finite240-square planes. Native archive/coverage still pending separate audit.',
        'cleanup': 'Unknown Start ACK / closed transport / unobserved ownership => zero Stop/Withdraw. Known owned failure: fresh known On2 orOff1/no competing native actions and same frame/buffer => oneStop even status0 (maypaused). Withdraw only after StopACK/nonrunning, all frozen fields unchanged and knownOn2 failing current/Z admission; oneWithdraw, 3s Off1/Home confirmation. No Stop after nativeEnd; never stop newlyrunning scan.',
        'limitations': 'Root sole writer; per-session/event durable reservation, no general device mutex or native frameID. TCP states sequential not atomic; timing/fsync may exceed software budgets. Native state0 alone is not proof of idle. No true transient peak, uninterrupted waveform, clean or cycle claim.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    global POST_REVIEW_SHA
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--output', type=Path)
    ap.add_argument('--logger', type=Path)
    ap.add_argument('--fresh-snapshot', type=Path)
    ap.add_argument('--fresh-sha256')
    ap.add_argument('--session')
    ap.add_argument('--event')
    ap.add_argument('--source-sha256')
    ap.add_argument('--logger-source-sha256')
    ap.add_argument('--post-review-sha256')
    args = ap.parse_args()
    if not args.execute:
        print(json.dumps(plan(), indent=2))
        return 0
    b.require(all([args.output, args.logger, args.fresh_snapshot, args.fresh_sha256, args.session,
                   args.event, args.source_sha256, args.logger_source_sha256, args.post_review_sha256]), 'Explicit source/fresh/logger/session/event bindings required')
    POST_REVIEW_SHA = args.post_review_sha256
    b.require(args.event != 'configure_full', 'Scanner cannot use configuration role')
    attempt_paths(args.session, args.event, args.output, args.logger)
    b.require(not args.output.exists() and args.logger.is_dir(), 'New output and existing independent session logger required')
    b.require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256, 'Executing source SHA mismatch')
    local_path(args.fresh_snapshot)
    run = Run(args.output, args.logger, args.fresh_snapshot, args.fresh_sha256, args.session, args.event,
              args.source_sha256, args.logger_source_sha256)
    handlers = {sig: signal.signal(sig, lambda *_: setattr(run, 'abort', True)) for sig in [signal.SIGINT, signal.SIGTERM]}
    try:
        return run.execute()
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    raise SystemExit(main())
