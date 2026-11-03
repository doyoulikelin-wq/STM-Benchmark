"""Build a local immutable P03 publication snapshot. No hardware, remote or Git operations."""
import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

C = Path(__file__).resolve().parents[1]
S = C.parent / 'session_02'
D = C / 'R06_diagnostic'
I = C / 'R06_pulse_P03_image_review'
O = I / 'after_vs_212'
cli = argparse.ArgumentParser(description=__doc__)
cli.add_argument('--build-local', action='store_true')
cli.add_argument('--output', type=Path)
cli.add_argument('--image-review-sha256')
cli.add_argument('--report', type=Path)
cli.add_argument('--receipt', type=Path)
cli.add_argument('--receipt-sha256')
args = cli.parse_args()
if not args.build_local:
    print('Plan only. Requires actual complete image assessment and frozen native receipt. No output written.')
    raise SystemExit(0)
assert args.output and args.image_review_sha256 and args.receipt and args.receipt_sha256 and args.report
DEST = args.output.resolve()
assert DEST.is_relative_to(C) and DEST != C, 'Only a new local staging directory, never the repository'
assert hashlib.sha256((I/'post_manual_review.json').read_bytes()).hexdigest() == args.image_review_sha256
assert hashlib.sha256(args.receipt.read_bytes()).hexdigest() == args.receipt_sha256
image_review = json.loads((I/'post_manual_review.json').read_bytes())
actual_scan = S/'after_R06_P03_full'
assert json.loads((actual_scan/'outcome.json').read_bytes())['status'] == 'completed'

assert not DEST.exists(), 'New package only'
DEST.mkdir(parents=True)
records = []

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def save_bytes(relative, raw):
    target = DEST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists(), relative
    target.write_bytes(raw)
    assert target.read_bytes() == raw
    return target

def copy(source, relative, compress=False):
    source = source.resolve()
    assert source.is_file() and source.is_relative_to(C.parent), source
    raw = source.read_bytes()
    content = gzip.compress(raw, compresslevel=9, mtime=0) if compress else raw
    target = save_bytes(relative, content)
    records.append({'package_path':relative, 'source_path':str(source), 'source_bytes':len(raw),
                    'source_sha256':sha(raw), 'encoding':'gzip' if compress else 'identity',
                    'package_sha256':sha(content), 'package_bytes':len(content)})
    if compress:
        assert gzip.decompress(target.read_bytes()) == raw

stage_roles = ['prepare_induction_P03', 'pulse_induction_P03', 'return_induction_P03']
for role in stage_roles:
    source = S / role
    for path in sorted(source.iterdir()):
        if path.is_file() and path.suffix in ('.json', '.claim'):
            copy(path, f'evidence/stages/{role}/{path.name}')
    copy(source / 'events.jsonl', f'evidence/stages/{role}/events.jsonl.gz', True)
    # Retain actual writer request/response bytes independently of summary ACK records.
    events = [json.loads(line) for line in (source / 'events.jsonl').read_text().splitlines()]
    writes = [e for e in events if e.get('kind') == 'tcp_exchange' and e.get('command') in ('ZCtrl.SetpntSet', 'Bias.Pulse')]
    for event in writes:
        for key in ('request_header', 'request_body', 'response_header', 'response_body'):
            ref = event[key]
            path = source / ref['path']
            assert sha(path.read_bytes()) == ref['sha256']
            copy(path, f'evidence/stages/{role}/{ref["path"]}')

for role, frame in [('after_R06_P02_recovery_full', '212'), ('after_R06_P03_full', '213')]:
    folder = S / role
    copy(folder / 'native' / f'BM261029_00{frame}.sxm', f'raw/BM261029_00{frame}.sxm')
    for name in ('manifest.json', 'outcome.json', 'scan_start.claim', 'scan_start_ack.json',
                 'logger_ready_bound.json', 'fresh_recording_evidence.json'):
        copy(folder / name, f'evidence/scan{frame}/{name}')
    for name in ('quality_report.json', 'quick_summary.json', 'header_original_latin1.txt'):
        copy(folder / 'analysis' / name, f'evidence/scan{frame}/analysis/{name}')
    for path in sorted((folder / 'native').glob('*receipt*.json')):
        copy(path, f'evidence/scan{frame}/native/{path.name}')
    copy(folder / 'events.jsonl', f'evidence/scan{frame}/events.jsonl.gz', True)

analysis_names = ['P03_prepare_native_phases.json', 'P03_prepare_postroll.json',
 'P03_native_pre_pulse_post.json', 'P03_pulse_postroll.json', 'P03_pulse_transition_timeline.json',
 'P03_return_native_phases.json', 'P03_between_stages_native_review.json',
 'P03_native_waveform_provenance.json', 'after_P03_scan_native_phases.json',
 'after_P02_recovery_scan_native_phases.json', 'P03_return_to_scan_and_post_native_review.json',
 'peak_neighborhoods_213.json', '213_peak_slow_axis.json', 'P03_post213_through_terminal_native_review.json']
for name in analysis_names:
    copy(D / name, 'evidence/native_audits/' + name)
for name in ['post_manual_review.json', 'actual_normal_lifecycle_pre_image_check.json',
             'normal_adapter_offline_checks.json', 'normal_post_adapter_context.json']:
    copy(I / name, 'evidence/image_review/' + name)
for path in sorted(O.iterdir()):
    if path.suffix == '.json':
        copy(path, 'evidence/image_review/' + path.name)
    elif path.suffix == '.png':
        copy(path, 'figures/' + path.name)
copy(D / 'P03_native_waveform.png', 'figures/P03_native_waveform.png')
copy(C/'R06_pulse_P03/after213_completed_ui.png', 'screenshots/after213_completed_ui.png')
copy(C/'R06_pulse_P03/final_stopped_ui.png', 'screenshots/final_stopped_ui.png')
copy(C/'R06_pulse_P03/mechanism_and_last_pulse_review_OFFLINE.md', 'evidence/mechanism_memo_original.txt')
for source, name in [(S/'pulse_induction_P02/outcome.json','original_failed_pulse_outcome.json'),
                     (C/'R06_pulse_P02/independent_readonly_recovery30/outcome.json','independent_readonly30_outcome.json'),
                     (S/'recovery_return_P02_01/outcome.json','independent_return_outcome.json')]:
    copy(source, 'evidence/prior_P02/'+name)
copy(I / 'prospective_image_review_plan.json', 'evidence/image_review/prospective_image_review_plan.json')
for path in sorted((C / 'R06_pulse_P03').glob('*.json')):
    if path.name.endswith('_native_receipt.json') or path.name.startswith('root_'):
        copy(path, 'evidence/root_and_receipts/' + path.name)
for name in ('induction_R06_P03.admission.json', 'induction_P03.ledger.json',
             'induction_R06_P03_return_review.json', 'induction_R06_P03_scan_review.json'):
    copy(S / name, 'evidence/decisions/' + name)
for name in ('continuing_20261101_1939__pulse_05.claim',):
    copy(C.parent / 'globalclaims' / name, 'evidence/claims/' + name)

# Preserve independently reconciled closure alongside the original interrupted outcome.
for name in ('receipt.json','review.json','terminal_evidence.json','incremental_receipt_at_start.json'):
    copy(C/'R06_terminal_native_review'/name, 'evidence/terminal/'+name)
for name in ('close_observer_frozen_inputs.json','close_own_observer_after_P03_actual_review.json',
             'close_own_observer_after_P03_offline_audit.json','close_own_observer_after_P03_actual_review_complete.json','terminal_ui_filename_observation.json'):
    copy(C/'R06_pulse_P03'/name, 'evidence/terminal/'+name)
copy(C/'stop_R06_root_signal.json', 'evidence/terminal/stop_R06_root_signal.json')
for role in ('read_080_R06_stopped_a','read_081_R06_stopped_b'):
    copy(C/role/'snapshot.json', 'evidence/terminal/'+role+'_snapshot.json')
logger = S / 'logger_06'
for name in ('manifest.json', 'READY.json', 'start.claim', 'before.json', 'predecessor_and_root_admission.json', 'recording_segment_reservation.json', 'outcome.json'):
    copy(logger / name, 'evidence/recorder/' + name)
scan_review = json.loads((D / 'after_P03_scan_native_phases.json').read_bytes())
terminal_evidence = json.loads((C/'R06_terminal_native_review/terminal_evidence.json').read_bytes())
log_ref = terminal_evidence['logger_refs']['events.jsonl']
prefix = Path(log_ref['path']).read_bytes()
assert len(prefix) == log_ref['bytes'] and sha(prefix) == log_ref['sha256']
assert prefix.endswith(b'\n')
lines = prefix.splitlines(keepends=True)
filtered = b''.join(line for line in lines if json.loads(line).get('kind') == 'datalog_status')
for command, event_name in [('DataLog.Start','start'),('DataLog.Stop','stop')]:
    command_events = [json.loads(line) for line in lines if json.loads(line).get('command') == command]
    assert len(command_events) == 1
    save_bytes(f'evidence/recorder/{event_name}_tcp_event.json', (json.dumps(command_events[0],indent=2)+'\n').encode())
    for key in ('request_header','request_body','response_header','response_body'):
        wire_ref = command_events[0][key]
        source = logger / wire_ref['path']
        assert sha(source.read_bytes()) == wire_ref['sha256']
        copy(source, 'evidence/recorder/' + wire_ref['path'])
compressed = gzip.compress(filtered, compresslevel=9, mtime=0)
save_bytes('evidence/recorder/datalog_status_events.jsonl.gz', compressed)
records.append({'package_path':'evidence/recorder/datalog_status_events.jsonl.gz', 'source_path':log_ref['path'],
 'source_prefix_bytes':len(prefix), 'source_prefix_sha256':sha(prefix), 'encoding':'gzip_filtered_jsonl_kind_datalog_status',
 'selected_rows':len(filtered.splitlines()), 'selected_raw_sha256':sha(filtered), 'package_sha256':sha(compressed), 'package_bytes':len(compressed)})

receipt = json.loads(args.receipt.read_bytes())
assert receipt['recording_segment_id'] == 'R06'
selected_set = set()
for name in ['P03_prepare_native_phases.json','P03_native_pre_pulse_post.json','P03_return_native_phases.json']:
    audit = json.loads((D/name).read_bytes())
    for block in audit.get('native_sources',audit.get('native_blocks',[])):
        selected_set.add(int(Path(block['path']).stem[-5:]))
for name in ['P03_prepare_postroll.json','P03_pulse_postroll.json']:
    for block in json.loads((D/name).read_bytes())['native_blocks']:
        selected_set.add(int(Path(block['path']).stem[-5:]))
# Keep the actual single large213 peak and all qualifying event bands as selected raw evidence.
peak_audit=json.loads((D/'213_peak_slow_axis.json').read_bytes())
for event in peak_audit['abs_current_thresholds_pA']['1000']['events']:
    selected_set.add(event['peak']['peak']['block'])
selected_set.update([561,590,591])
# Keep complete pulse/return phases plus last three closed blocks for postscan evidence.
selected_set.update(range(receipt['complete_through_index']-2,receipt['complete_through_index']+1))
selected = sorted(selected_set)
for index in selected:
    name = f'dl_goal30_FIVE1102_SESSION_02_R06{index:05d}.dat'
    meta = receipt['files'][name]
    path = S / 'native_R06' / name
    assert meta['local_path'] == str(path) and meta['rows'] == (receipt['terminal_rows'] if index == receipt['complete_through_index'] else 25000)
    assert sha(path.read_bytes()) == meta['sha256'] and path.stat().st_size == meta['bytes']
    copy(path, 'raw/native/' + name + '.gz', True)

source_paths = [C / name for name in ['setpoint_R06_induction_P03_once.py', 'pulse_R06_induction_P03_once.py',
 'scan_full50nm_fast_R06_after_induction_P03_once.py',
 'induction_R06_P03_admission.py', 'action_bindings_R06_induction_P03.py']]
source_paths += [D / name for name in ['review_P03_setpoint_native.py', 'review_P03_pulse_native.py',
 'review_P03_prepare_post_native.py', 'review_P03_pulse_post_native.py', 'review_P03_pulse_transition.py',
 'review_P03_between_stages_native.py', 'review_after_P03_native_phases.py', 'review_native_phases.py',
 'plot_P03_native_waveform.py', 'review_P03_return_to_scan_native.py', 'review_213_peak_neighborhoods.py',
 'map_213_native_scan_rows.py', 'review_P03_post213_terminal_native.py']]
source_paths += [I / name for name in ['compare_after_P03.py','render_full_dynamic_ranges.py',
 'render_pair_by_stage.py','landmark_displacement.py']]
source_paths += [C/'archive_audit_terminal_R06.py', C/'R06_pulse_P03/close_own_observer_after_P03.py',
                 C/'R06_pulse_P03/test_close_own_observer_after_P03_offline.py']
for path in source_paths:
    copy(path, 'sources/' + path.name)
copy(Path(__file__), 'sources/build_publish_package.py')

coverage = {'scope':'Final independently confirmed R06 terminal archive, with the earlier591-block full213 snapshot retained separately.',
 'frozen_receipt':{'path':str(args.receipt),'sha256':args.receipt_sha256},
 'terminal_rows':receipt['terminal_rows'], 'native_stop_observed':receipt['native_stop_observed'],
 'local_closed_native_blocks':receipt['complete_through_index'],
 'local_closed_native_rows':sum(v['rows'] for v in receipt['files'].values()),
 'local_closed_native_seconds':sum(v['rows'] for v in receipt['files'].values())*.0005,
 'local_closed_native_bytes':sum(v['bytes'] for v in receipt['files'].values()),
 'uploaded_native_block_indices':selected, 'uploaded_native_block_count':len(selected),
 'uploaded_native_rows':sum(receipt['files'][f'dl_goal30_FIVE1102_SESSION_02_R06{i:05d}.dat']['rows'] for i in selected),
 'all_native_blocks_uploaded':False, 'whole_complete_212_and_213_SXM_uploaded':True,
 'selection':'Complete preparation, pulse pre/post30 and return action block ranges. Immediate postroll blocks, every full213 >=1nA event block including561, postscan590/591 and terminal613..615. All intervening gaps are numerically reviewed with local raw-source hashes. Raw DAT outside the enumerated selection remain local.',
 'additional_local_only':'Remaining full native DAT and unselected getter wire packets remain at original indexed local sources.',
 'raw_event_records':'All action and both complete scan event logs are included with actual writer request/response bytes. Recorder status events are copied from the full final SHA-verified log. The unique DataLog.Start and DataLog.Stop exchanges and their actual wire bytes are included.',
 'source_runnability':'Executed sources retain original pinned local dependencies. Published copies are version-audit evidence.',
 'counter_state':{'shared_pulses':5,'shared_pulse_limit':6,'repair_attempts':2,'requested_repair_attempts':5,'remaining_repair_attempts':3,'strict_induced_bad_repair_usable_cycles':0,'P03_new_repair_attempt':False},
 'readiness_actual_execution':'First complete observation was On2 atACK+107.614ms. Hold wait branch was not exercised and remains mock-only validation.',
 'image_assessment_sha256':args.image_review_sha256}
save_bytes('coverage.json', (json.dumps(coverage,ensure_ascii=False,indent=2)+'\n').encode())
copy(args.report, 'README.md')
copy(C/'R06_pulse_P03/verify_package.py', 'verify_package.py')
save_bytes('source_index.json',(json.dumps({'records':records},ensure_ascii=False,indent=2)+'\n').encode())
payload = [{'path':str(path.relative_to(DEST)), 'bytes':path.stat().st_size,
            'sha256':sha(path.read_bytes())} for path in sorted(DEST.rglob('*')) if path.is_file()]
save_bytes('manifest.json', (json.dumps({'scope':'Every payload file including every nested manifest. This outer manifest alone is excluded from itself.', 'files':payload},indent=2)+'\n').encode())
print(DEST, len(records), len(selected), sha((DEST/'manifest.json').read_bytes()))
