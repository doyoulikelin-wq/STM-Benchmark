"""Build a local S02 evidence snapshot only after completed original-setting217 review.

No instrument, network, repository or Skill operations. Original evidence is copied
byte-for-byte. Summary links are relative; original local paths remain provenance.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
C = P.parent
N = C.parent
S = N / 'session_02'
D = C / 'R07_diagnostic'
IMAGE = C / 'R07_S02_full02_image_review'
BEFORE = S / 'after_R07_S01_recovered_full'
EXPOSURE = S / 'induction_R07_S02_full02'
AFTER = S / 'after_R07_S02_restored_full'
ROLES = ['prepare_R07_S02', 'configure_R07_S02_gain', 'configure_R07_S02_speed',
         'induction_R07_S02_full', 'induction_R07_S02_full02', 'return_R07_S02',
         'restore_R07_S02_gain', 'restore_R07_S02_speed', 'after_R07_S02_restored_full']
PINS = {
    BEFORE / 'outcome.json': '6bba52bbcd957c4003995c2dc24562221004a007345675f8fa7105f0eb59e322',
    EXPOSURE / 'outcome.json': '7a26dbe770a131fc463698fc6713a0352075696c895276ad753509c1d9b3dbcd',
    S / 'induction_R07_S02_full/outcome.json': '3685f770960300f8cf9a0f358fd527f0eb92b170844b2b4a6bb2f6b42092772c',
    P / 'S02_return_sequence_rationale_correction.json': '944088f718fd91c2f3bb798e4a7dc8a662dffb6ce36c537e2f8c2789b70324fe',
    IMAGE / 'exposure_manual_review.json': '11d6ad409782d48032273b222d403f3c8409f80305e5e8ed1fffd351478c1ba3',
    D / 'S02_native_publication_index_before217.json': '54af14a8b327d309dddfd6e0af6afd747043fe9ad4f6e531d4e9a7ee148bfa18',
}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read(path):
    return json.loads(path.read_bytes())

def checked_ref(ref):
    path = Path(ref['path']).resolve()
    assert path.is_relative_to(N) and path.is_file(), path
    assert sha(path.read_bytes()) == ref['sha256'], path
    return path

def refs(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
            yield value
        for v in value.values():
            yield from refs(v)
    elif isinstance(value, list):
        for v in value:
            yield from refs(v)

def completed_frame(folder):
    out = read(folder / 'outcome.json')
    assert out['status'] == 'completed' and out['completed_frame_confirmed'] is True
    assert len(out['frames']) == 6
    q = read(folder / 'analysis/quality_report.json')['integrity']
    assert q['native_TCP_wire_bitmatch'] is True and q['matched_float32_values'] == 345600
    assert q['capture_outcome_sha256'] == sha((folder / 'outcome.json').read_bytes())
    return out

def rejected_attempt():
    folder = S / 'induction_R07_S02_full'
    out = read(folder / 'outcome.json')
    assert out['status'] == 'rejected_before_start'
    assert out['error'] == 'Missing or unordered R07 READY/start reservation'
    for k in ['start_attempted', 'start_acknowledged', 'owned_running_observed',
              'end_event_confirmed', 'execution_unknown', 'completed_frame_confirmed']:
        assert out[k] is False, k
    assert not (folder / 'events.jsonl').exists()
    assert not (folder / 'scan_start.claim').exists()
    assert not list((folder / 'wire').glob('*'))
    claim = N / 'claims/session_02__induction_R07_S02_full.claim'
    assert sha(claim.read_bytes()) == 'f7426c050d1be55dcf88dc4eee905ebd1304d8bffdea5b06c6d990728eb16a94'
    return claim

def validate_known_history():
    for path, digest in PINS.items():
        assert sha(path.read_bytes()) == digest, path
    rejected_attempt()
    completed_frame(BEFORE)
    completed_frame(EXPOSURE)
    for role, target in [('prepare_R07_S02', 2.000000026702864e-10),
                         ('return_R07_S02', 1.000000013351432e-10)]:
        o = read(S / role / 'outcome.json')
        assert o['status'] == 'completed' and o['attempted_sets'] == o['acknowledged_sets'] == 4
        assert o['final_target_A'] == target
    for role in ['configure_R07_S02_gain', 'configure_R07_S02_speed',
                 'restore_R07_S02_gain', 'restore_R07_S02_speed']:
        assert read(S / role / 'outcome.json')['status'] == 'configured_and_exact_readback_verified'
    correction = read(P / 'S02_return_sequence_rationale_correction.json')
    assert correction['actual_frozen_driver_and_wire_targets_pA'] == [200, 195.3125, 156.25, 125, 100]

def build(args):
    validate_known_history()
    completed_frame(AFTER)
    image_path = checked_ref({'path': str(args.final_image_review), 'sha256': args.final_image_sha256})
    native_index_path = checked_ref({'path': str(args.final_native_index), 'sha256': args.final_native_sha256})
    receipt_path = checked_ref({'path': str(args.final_receipt), 'sha256': args.final_receipt_sha256})
    image_review = read(image_path)
    assert type(image_review['full_task_usable']) is bool
    assert image_review['cycle_increment'] == 0 and image_review['completed_repair_attempt_increment'] == 0
    root_path = IMAGE / 'root_image_acceptance.json'
    assert sha(root_path.read_bytes()) == 'df65500e1cb1b83e2517b0a755d66ff7c1534ebdc6408356d73f37a56daaa1cc'
    root_review = read(root_path)
    assert checked_ref(root_review['manual_review']) == image_path
    assert root_review['agrees_full_task_usable'] == image_review['full_task_usable']
    assert sha((IMAGE / 'three_stage_comparison_v2/215_216_217_FB_frozen_contrast.png').read_bytes()) == '2effd5a4355cc7d62f1897cf76e4551f2381de8d88c568e37a09531a3fa5ebe8'
    # The final manual review must refer to both actual matched scans, not exposure216 alone.
    bound = {(str(Path(r['path']).resolve()), r['sha256']) for r in refs(image_review)}
    for folder in [BEFORE, AFTER]:
        for name in ['outcome.json', 'analysis/quality_report.json']:
            path = folder / name
            assert (str(path), sha(path.read_bytes())) in bound, path
    receipt = read(receipt_path)
    assert receipt['recording_segment_id'] == 'R07' and receipt['complete_through_index'] == 577
    selected = sorted(set(args.native_blocks))
    assert set(range(477, 500)) <= set(selected)
    assert all(1 <= i <= receipt['complete_through_index'] for i in selected)
    report = args.report.resolve()
    report_text = report.read_text()
    assert 'PENDING_217' not in report_text and '待217' not in report_text
    dest = args.output.resolve()
    assert dest.is_relative_to(P) and dest != P and not dest.exists()
    dest.mkdir(parents=True)
    records = []
    copied = {}

    def save(relative, raw):
        target = dest / relative
        assert target.resolve().is_relative_to(dest) and not target.exists(), relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        assert target.read_bytes() == raw

    def copy(source, relative, compress=False):
        source = source.resolve()
        assert source.is_file() and source.is_relative_to(N), source
        if relative in copied:
            assert copied[relative] == source
            return
        raw = source.read_bytes()
        content = gzip.compress(raw, compresslevel=9, mtime=0) if compress else raw
        save(relative, content)
        copied[relative] = source
        records.append({'source_path':str(source), 'source_sha256':sha(raw), 'source_bytes':len(raw),
                        'package_path':relative, 'package_sha256':sha(content), 'package_bytes':len(content),
                        'encoding':'gzip' if compress else 'identity'})

    writer_commands = {'Scan.Action', 'ZCtrl.Withdraw', 'ZCtrl.OnOffSet',
                       'ZCtrl.SetpntSet', 'ZCtrl.GainSet', 'Scan.SpeedSet'}
    def stage(folder, relative):
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix in ('.json', '.claim'):
                copy(path, relative + '/' + path.name)
        log = folder / 'events.jsonl'
        if not log.exists():
            assert folder.name == 'induction_R07_S02_full'
            return
        copy(log, relative + '/events.jsonl.gz', True)
        for event in map(json.loads, log.read_text().splitlines()):
            if event.get('kind') == 'tcp_exchange' and event.get('command') in writer_commands:
                for key in ['request_header', 'request_body', 'response_header', 'response_body']:
                    ref = event[key]
                    path = folder / ref['path']
                    assert sha(path.read_bytes()) == ref['sha256']
                    copy(path, relative + '/' + ref['path'])

    # The preceding S01 package holds older interventions; keep core215 locally usable.
    stage(BEFORE, 'evidence/stages/after_R07_S01_recovered_full')
    for role in ROLES:
        stage(S / role, 'evidence/stages/' + role)
    for role in ROLES:
        claim = N / 'claims' / ('session_02__' + role + '.claim')
        if claim.exists():
            copy(claim, 'evidence/reservations/' + claim.name)
    for folder, number in [(BEFORE, 215), (EXPOSURE, 216), (AFTER, 217)]:
        copy(folder / 'native' / f'BM261029_00{number}.sxm', f'raw/BM261029_00{number}.sxm')
        for subdir, suffixes in [('frames', None), ('analysis', {'.json', '.txt', '.npz'})]:
            for path in sorted((folder / subdir).rglob('*')):
                if path.is_file() and (suffixes is None or path.suffix in suffixes):
                    copy(path, f'evidence/scan{number}/{subdir}/' + str(path.relative_to(folder / subdir)))

    copy(C / 'R07_S01_recovered_image_review/post_manual_review.json', 'evidence/image_review/before215_manual.json')
    for path in sorted(IMAGE.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or 'DRAFT' in path.name or 'three_stage_comparison' in path.parts:
            continue
        relative = str(path.relative_to(IMAGE))
        if path.suffix == '.png': copy(path, 'figures/' + relative)
        elif path.suffix == '.json': copy(path, 'evidence/image_review/' + relative)
        elif path.suffix == '.py': copy(path, 'sources/image/' + relative)
    copy(image_path, 'evidence/image_review/final217_manual.json')

    indices = [D / 'S02_native_publication_index_before217.json', native_index_path]
    for index_path in indices:
        copy(index_path, 'evidence/native_audits/' + index_path.name)
        index = read(index_path)
        # Only explicit handoff groups are payload sources; embedded historic refs remain refs.
        for key, value in index.items():
            # Actual stage files already live under evidence/stages; selected DAT are
            # verified against the frozen receipt and compressed once below.
            if key in {'actual_scan_files', 'actual_source', 'selected_raw_blocks'}:
                continue
            candidates = value if isinstance(value, list) else [value]
            for ref in candidates:
                if not isinstance(ref, dict) or not {'path', 'sha256'} <= ref.keys(): continue
                path = checked_ref(ref)
                prefix = 'sources/native/' if path.suffix == '.py' else 'figures/' if path.suffix == '.png' else 'evidence/native_audits/'
                copy(path, prefix + path.name)
    copy(receipt_path, 'evidence/native_audits/final_native_receipt.json')
    for name in ['S02_completed_setup_return_config_minimal_native_selection.json',
                 'S02_restored217_derived_offline_regression.json']:
        copy(D / name, 'evidence/native_audits/' + name)
    copy(P / 'publication_selected_native_blocks.json', 'evidence/native_audits/publication_selected_native_blocks.json')
    for path in sorted(P.glob('*.json')):
        if any(token in path.name for token in ['INACTIVE', 'template', 'source_pins', 'publication_', 'candidate']): continue
        copy(path, 'evidence/root_and_bindings/' + path.name)
    for name in ['stage_binding.py', 'full02_binding.py', 'build_S02_full02_root_inputs_OFFLINE.py']:
        copy(P / name, 'sources/control/' + name)
    for name in ['setpoint_R07_scan_induction_S02_once.py', 'configure_R07_scan_induction_S02_once.py',
                 'scan_full50nm_fast_R07_induction_S02_once.py', 'scan_full50nm_fast_R07_induction_S02_full02_once.py',
                 'setpoint_R07_S02_after_rejected_scan_once.py', 'configure_R07_S02_after_rejected_scan_once.py',
                 'scan_full50nm_fast_R07_after_S02_full02_restored_once.py']:
        copy(C / name, 'sources/control/' + name)
    for name in ['gain_codec_support.py', 'user_guidance.json', 'user_scan_current_guidance_5nA_v2.json']:
        copy(C / 'R07_scan_induction' / name, ('sources/control/' if name.endswith('.py') else 'evidence/root_and_bindings/') + name)
    for name in ['manifest.json', 'READY.json', 'start.claim', 'recording_segment_reservation.json']:
        copy(S / 'logger_07' / name, 'evidence/recorder/' + name)
    for i in selected:
        name = f'dl_goal30_FIVE1102_SESSION_02_R07{i:05d}.dat'
        meta = receipt['files'][name]
        path = S / 'native_R07' / name
        assert meta['rows'] == 25000 and meta['sha256'] == sha(path.read_bytes())
        assert meta['bytes'] == path.stat().st_size
        assert meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal']
        copy(path, 'raw/native/' + name + '.gz', True)
    coverage = {
        'scope':'S02 completed changed-setting216 and restored original-setting217. Prior S01 retains its original failure. No new repair or confirmed dirty-repair cycle is inferred.',
        'prior_publication':'../au111_R07_S01_20261103/README.md',
        'local_closed_native_blocks':receipt['complete_through_index'],
        'native_dt_s':0.0005, 'channels':6, 'native_stop_observed':False, 'includes_terminal':False,
        'uploaded_native_block_indices':selected, 'uploaded_native_block_count':len(selected),
        'uploaded_native_rows':len(selected) * 25000, 'all_native_blocks_uploaded':False,
        'whole_complete_215_216_217_SXM_uploaded':True,
        'native_index':[dict(name=name, rows=meta['rows'], bytes=meta['bytes'], sha256=meta['sha256'], uploaded=int(name[-9:-4]) in selected) for name,meta in sorted(receipt['files'].items())],
        'counter_state':{'repair_attempts':2, 'requested_repair_attempts':5, 'remaining_repair_attempts':3,
                         'strict_induced_bad_repair_usable_cycles':0, 'shared_pulses':5, 'shared_pulse_limit':6,
                         'S02_local_scan_reservations':2, 'S02_rejected_before_TCP':1,
                         'S02_actual_induction_starts':1, 'S02_complete_induction_frames':1,
                         'cumulative_scan_induction_attempts':2, 'cumulative_complete_induction_frames':1,
                         'S02_repair_attempt_increment':0},
        'final217_full_task_usable':image_review['full_task_usable'],
        'final_image_review_sha256':sha(image_path.read_bytes()),
        'source_runnability':'Frozen sources are audit evidence and retain local pinned dependencies. They are not standalone control entry points.',
        'recording_scope':'Recorder ongoing at this cutoff. Selected DAT upload gaps are explicit and are not acquisition gaps.',
    }
    save('coverage.json', (json.dumps(coverage, indent=2) + '\n').encode())
    copy(report, 'README.md')
    copy(P / 'publication_image_index.md', 'IMAGE_INDEX.md')
    copy(Path(__file__), 'sources/build_publication_S02_OFFLINE.py')
    copy(P / 'verify_publication_S02_OFFLINE.py', 'verify_package.py')
    save('source_index.json', (json.dumps({'records':records}, indent=2) + '\n').encode())
    files = [{'path':str(path.relative_to(dest)), 'bytes':path.stat().st_size, 'sha256':sha(path.read_bytes())}
             for path in sorted(dest.rglob('*')) if path.is_file()]
    save('manifest.json', (json.dumps({'scope':'All payloads including nested manifests; only this outer manifest excluded.', 'files':files}, indent=2) + '\n').encode())
    return {'package':str(dest), 'payload_files':len(files), 'native_blocks':len(selected), 'manifest_sha256':sha((dest / 'manifest.json').read_bytes())}

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--check-known-inputs', action='store_true')
    cli.add_argument('--build-local', action='store_true')
    for flag in ['output', 'report', 'final-image-review', 'final-native-index', 'final-receipt']:
        cli.add_argument('--' + flag, type=Path)
    for flag in ['final-image-sha256', 'final-native-sha256', 'final-receipt-sha256']:
        cli.add_argument('--' + flag)
    cli.add_argument('--native-blocks', type=int, nargs='+')
    args = cli.parse_args()
    if args.check_known_inputs:
        validate_known_history()
        print(json.dumps({'known215_216_and_normal_restoration':True, 'final217_review_not_claimed':True, 'hardware':False}))
    elif args.build_local:
        for key in ['output', 'report', 'final_image_review', 'final_image_sha256', 'final_native_index',
                    'final_native_sha256', 'final_receipt', 'final_receipt_sha256', 'native_blocks']:
            assert getattr(args, key), key
        print(json.dumps(build(args)))
    else:
        print('Inactive local builder. Final217 image/native review and explicit frozen hashes required. No files written.')

if __name__ == '__main__':
    main()
