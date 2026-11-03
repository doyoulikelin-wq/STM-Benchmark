"""Verify this publication snapshot locally, including every nested manifest payload."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

manifest = json.loads((ROOT / 'manifest.json').read_bytes())
listed = {item['path'] for item in manifest['files']}
actual = {str(path.relative_to(ROOT)) for path in ROOT.rglob('*') if path.is_file() and path != ROOT / 'manifest.json'}
assert listed == actual, {'missing': sorted(actual-listed), 'extra': sorted(listed-actual)}
assert len(listed) == len(manifest['files'])
for item in manifest['files']:
    path = ROOT / item['path']
    assert path.resolve().is_relative_to(ROOT)
    raw = path.read_bytes()
    assert len(raw) == item['bytes'] and sha(raw) == item['sha256'], str(path)

index = json.loads((ROOT / 'source_index.json').read_bytes())['records']
source_lookup = {}
for item in index:
    raw = (ROOT / item['package_path']).read_bytes()
    assert sha(raw) == item['package_sha256'] and len(raw) == item['package_bytes']
    if item['encoding'] == 'identity':
        assert sha(raw) == item['source_sha256'] and len(raw) == item['source_bytes']
        source_lookup.setdefault(item['source_path'], set()).add(item['source_sha256'])
    elif item['encoding'] == 'gzip':
        decoded = gzip.decompress(raw)
        assert sha(decoded) == item['source_sha256'] and len(decoded) == item['source_bytes']
        source_lookup.setdefault(item['source_path'], set()).add(item['source_sha256'])
    else:
        assert item['encoding'] == 'gzip_filtered_jsonl_kind_datalog_status'
        decoded = gzip.decompress(raw)
        assert sha(decoded) == item['selected_raw_sha256']
        assert len(decoded.splitlines()) == item['selected_rows']
        assert all(json.loads(line)['kind'] == 'datalog_status' for line in decoded.splitlines())

resolved = []
external = set()
def inspect(value, origin):
    if isinstance(value, dict):
        path, digest = value.get('path'), value.get('sha256')
        if isinstance(path, str) and isinstance(digest, str) and len(digest) == 64 and Path(path).is_absolute():
            if path in source_lookup:
                assert digest in source_lookup[path], (origin, path, digest)
                resolved.append((origin, path))
            else:
                external.add((path, digest))
        for child in value.values():
            inspect(child, origin)
    elif isinstance(value, list):
        for child in value:
            inspect(child, origin)

for path in ROOT.rglob('*.json'):
    if path.name not in ('manifest.json', 'source_index.json') or path.parent != ROOT:
        inspect(json.loads(path.read_bytes()), str(path.relative_to(ROOT)))
nested = sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob('manifest.json') if p != ROOT / 'manifest.json')
assert set(nested) <= listed
coverage = json.loads((ROOT / 'coverage.json').read_bytes())
assert len(list((ROOT / 'raw/native').glob('*.dat.gz'))) == coverage['uploaded_native_block_count']
assert set(range(477, 500)) <= set(coverage['uploaded_native_block_indices'])
assert coverage['counter_state']['repair_attempts'] == 2
assert coverage['counter_state']['strict_induced_bad_repair_usable_cycles'] == 0
assert coverage['counter_state']['shared_pulses'] == 5
assert coverage['counter_state']['S02_rejected_before_TCP'] == 1
assert coverage['counter_state']['S02_actual_induction_starts'] == 1
assert not coverage['includes_terminal']
for number in [215, 216, 217]:
    assert (ROOT / 'raw' / f'BM261029_00{number}.sxm').is_file()
    q = json.loads((ROOT / f'evidence/scan{number}/analysis/quality_report.json').read_bytes())['integrity']
    assert q['native_TCP_wire_bitmatch'] and q['matched_float32_values'] == 345600
rejected = json.loads((ROOT / 'evidence/stages/induction_R07_S02_full/outcome.json').read_bytes())
assert rejected['status'] == 'rejected_before_start'
assert not any(rejected[k] for k in ['start_attempted', 'start_acknowledged', 'execution_unknown'])
correction = json.loads((ROOT / 'evidence/root_and_bindings/S02_return_sequence_rationale_correction.json').read_bytes())
assert correction['actual_frozen_driver_and_wire_targets_pA'] == [200, 195.3125, 156.25, 125, 100]
assert 'PENDING_217' not in (ROOT / 'README.md').read_text()
print(json.dumps({'passed':True, 'payload_files':len(listed), 'nested_manifests_verified':nested,
                  'source_copies_verified':len(index), 'recursive_embedded_source_refs_verified':len(resolved),
                  'external_historical_reference_pairs_retained':len(external),
                  'compressed_native_blocks_verified':coverage['uploaded_native_block_count'],
                  'network_or_hardware':False}, indent=2))
