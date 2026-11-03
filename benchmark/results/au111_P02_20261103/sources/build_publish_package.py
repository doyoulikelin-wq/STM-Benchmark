"""Build a local immutable P02 publication snapshot. No hardware, remote or Git operations."""
import gzip
import hashlib
import json
import shutil
from pathlib import Path

C = Path(__file__).resolve().parents[1]
S = C.parent / 'session_02'
D = C / 'R06_diagnostic'
I = C / 'R06_pulse_P02_recovery_image_review'
O = I / 'after_vs_211'
DEST = Path('/Users/maxlin/Desktop/Nanonis/work/benchmark_skill_revision_20261101/repository/benchmark/results/au111_P02_20261103')
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

stage_roles = ['prepare_induction_P02', 'pulse_induction_P02', 'recovery_return_P02_01']
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

read_only = C / 'R06_pulse_P02/independent_readonly_recovery30'
status_review = json.loads((D / 'P02_status_transition_review.json').read_bytes())
for wire_record in status_review['native_response_status_wire']:
    source = Path(wire_record['response_body']['path'])
    copy(source, 'evidence/stages/pulse_induction_P02/wire/' + source.name)

for name in ('outcome.json', 'samples.json'):
    copy(read_only / name, f'evidence/independent_readonly30/{name}')
samples = json.loads((read_only / 'samples.json').read_bytes())
assert len(samples) == 57
for number, sample in enumerate(samples):
    path = Path(sample['snapshot'])
    assert path == read_only / f'read_{number:03d}' / 'snapshot.json'
    assert sha(path.read_bytes()) == sample['sha256']
    copy(path, f'evidence/independent_readonly30/read_{number:03d}/snapshot.json')
    copy(path.parent / 'events.jsonl', f'evidence/independent_readonly30/read_{number:03d}/events.jsonl.gz', True)

for role, frame in [('after_R06_I03_full', '211'), ('after_R06_P02_recovery_full', '212')]:
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

analysis_names = ['P02_prepare_native_phases.json', 'P02_actual_pulse_and_native_recovery.json',
 'P02_native_recovery_through364.json', 'P02_status_transition_review.json', 'P02_independent30_native_review.json',
 'P02_independent_return_native_phases.json', 'P02_independent_return_postroll.json',
 'P02_independent_return_postroll_v2.json', 'P02_location_erratum.json', 'P02_electrical_stages_through212.json',
 'P02_skill_practice_observation.json', 'after_P02_recovery_scan_native_phases.json', 'peak_neighborhoods_212.json',
 '212_peak_slow_axis.json', 'P02_native_waveform_provenance.json', 'after_I03_scan_native_phases.json']
for name in analysis_names:
    copy(D / name, 'evidence/native_audits/' + name)
for name in ['post_manual_review.json', 'actual_stage_binding_pre_image_check.json',
             'independent_recovery_adapter_offline_audit.json', 'independent_recovery_image_context.json']:
    copy(I / name, 'evidence/image_review/' + name)
for path in sorted(O.iterdir()):
    if path.suffix == '.json':
        copy(path, 'evidence/image_review/' + path.name)
    elif path.suffix == '.png':
        copy(path, 'figures/' + path.name)
copy(D / 'P02_native_waveform.png', 'figures/P02_native_waveform.png')
copy(C / 'R06_pulse_P02_image_review/prospective_image_review_plan.json', 'evidence/image_review/prospective_image_review_plan.json')
for path in sorted((C / 'R06_pulse_P02').glob('*.json')):
    if path.name.endswith('_native_receipt.json') or path.name.startswith('root_'):
        copy(path, 'evidence/root_and_receipts/' + path.name)
for name in ('induction_R06_P02.admission.json', 'induction_P02.ledger.json',
             'recovery_return_P02_01.admission.json', 'P02_recovery_full_scan_review.json'):
    copy(S / name, 'evidence/decisions/' + name)
for name in ('continuing_20261101_1939__pulse_04.claim', 'session_02__recovery_return_P02_01.claim'):
    copy(C.parent / 'globalclaims' / name, 'evidence/claims/' + name)

logger = S / 'logger_06'
for name in ('manifest.json', 'READY.json', 'start.claim', 'before.json', 'predecessor_and_root_admission.json', 'recording_segment_reservation.json'):
    copy(logger / name, 'evidence/recorder/' + name)
scan_review = json.loads((D / 'after_P02_recovery_scan_native_phases.json').read_bytes())
log_ref = scan_review['inputs']['logger_events']
with Path(log_ref['path']).open('rb') as stream:
    prefix = stream.read(log_ref['complete_prefix_bytes'])
assert sha(prefix) == log_ref['complete_prefix_sha256']
lines = prefix.splitlines(keepends=True)
filtered = b''.join(line for line in lines if json.loads(line).get('kind') == 'datalog_status')
start_events = [json.loads(line) for line in lines if json.loads(line).get('command') == 'DataLog.Start']
assert len(start_events) == 1
save_bytes('evidence/recorder/start_tcp_event.json', (json.dumps(start_events[0],indent=2)+'\n').encode())
for key in ('request_header','request_body','response_header','response_body'):
    wire_ref = start_events[0][key]
    source = logger / wire_ref['path']
    assert sha(source.read_bytes()) == wire_ref['sha256']
    copy(source, 'evidence/recorder/' + wire_ref['path'])
compressed = gzip.compress(filtered, compresslevel=9, mtime=0)
save_bytes('evidence/recorder/datalog_status_events.jsonl.gz', compressed)
records.append({'package_path':'evidence/recorder/datalog_status_events.jsonl.gz', 'source_path':log_ref['path'],
 'source_prefix_bytes':len(prefix), 'source_prefix_sha256':sha(prefix), 'encoding':'gzip_filtered_jsonl_kind_datalog_status',
 'selected_rows':len(filtered.splitlines()), 'selected_raw_sha256':sha(filtered), 'package_sha256':sha(compressed), 'package_bytes':len(compressed)})

receipt = json.loads((C / 'R06_pulse_P02/post212_native_receipt.json').read_bytes())
assert receipt['complete_through_index'] == 433
selected = sorted(set(range(332,340)) | set(range(347,365)) | set(range(378,389)) | {415,416,424,431,432,433})
for index in selected:
    name = f'dl_goal30_FIVE1102_SESSION_02_R06{index:05d}.dat'
    meta = receipt['files'][name]
    path = S / 'native_R06' / name
    assert meta['local_path'] == str(path) and meta['rows'] == 25000
    assert sha(path.read_bytes()) == meta['sha256'] and path.stat().st_size == meta['bytes']
    copy(path, 'raw/native/' + name + '.gz', True)

source_paths = [C / name for name in ['setpoint_R06_induction_P02_once.py', 'pulse_R06_induction_P02_once.py',
 'recover_return_R06_P02_elevensteps_once.py', 'scan_full50nm_fast_R06_after_P02_recovery_once.py',
 'induction_R06_P02_admission.py', 'action_bindings_R06_induction_P02.py']]
source_paths += [D / name for name in ['review_P02_setpoint_native.py', 'review_P02_guard_failure_native.py',
 'review_P02_independent30_native.py', 'review_P02_independent_return_native.py', 'review_P02_return_post_native.py',
 'review_P02_return_post_native_v2.py', 'review_after_P02_recovery_native_phases.py', 'review_native_phases.py',
 'review_212_peak_neighborhoods.py', 'map_212_native_scan_rows.py', 'plot_P02_native_waveform.py']]
source_paths += [I / name for name in ['compare_after_P02_recovery.py','render_full_dynamic_ranges.py',
 'render_pair_by_stage.py','landmark_displacement.py','exploratory_remote_shapes.py']]
for path in source_paths:
    copy(path, 'sources/' + path.name)
copy(Path(__file__), 'sources/build_publish_package.py')

coverage = {'scope':'Frozen R06 closed snapshot through433. Recorder remains active and terminal closure is pending.',
 'local_closed_native_blocks':433, 'local_closed_native_rows':433*25000, 'local_closed_native_seconds':433*12.5,
 'local_closed_native_bytes':sum(v['bytes'] for v in receipt['files'].values()), 'uploaded_native_block_indices':selected,
 'uploaded_native_block_count':len(selected), 'uploaded_native_rows':len(selected)*25000,
 'all_native_blocks_uploaded':False, 'whole_complete_211_and_212_SXM_uploaded':True,
 'selection':{'332–339':'Full preparation and final native observation', '347–364':'Pulse pre30, pulse, all extended recovery to independent30 audit boundary',
              '378–388':'Full separate return, final30 and28.91s postroll', '415,416,424':'All212>=1nA event bands', '431–433':'212 end and postscan observation'},
 'additional_local_only':'Remaining native DAT blocks and unselected getter wire packets. Their original paths and hashes remain in archived receipts and event records.',
 'raw_event_records':'All action event logs and all57 read-only snapshot/event logs are included. Actual writer wire request/response bytes are included. Recorder event log is a byte-exact selection of DataLog status lines from a verified frozen prefix.',
 'source_runnability':'Executed adapters are preserved for source audit. Their original pinned local dependencies and root approvals are required. They are not portable device entry points.',
 'counter_state':{'shared_pulses':4,'shared_pulse_limit':6,'repair_attempts':2,'requested_repair_attempts':5,'strict_induced_bad_repair_usable_cycles':0,'P02_new_repair_attempt':False}}
save_bytes('coverage.json', (json.dumps(coverage,ensure_ascii=False,indent=2)+'\n').encode())
save_bytes('source_index.json',(json.dumps({'records':records},ensure_ascii=False,indent=2)+'\n').encode())
print(DEST, len(records), len(selected))
