"""Offline-only R07 recovered full baseline02 and preceding fine02 creep audit."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
D = Path(__file__).resolve().parent
BASE = D / 'review_native_phases.py'
BASE_SHA = '778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA
spec = importlib.util.spec_from_file_location('r07_baseline02_native_base', BASE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.RUN = m.S / 'baseline_segment07_full02'
m.SCAN_SOURCE = m.C / 'scan_full50nm_fast_R07_baseline02_once.py'
m.SCAN_SHA = '15fd5c8ad0b2b31aca2c351c5fcb9660d880d3a19e7cd4614e37324e87b653d5'
FINE = D / 'relocation_and_fine02_native_review.json'
FINE_SHA = 'ead50cc4c46080a539fc45219ec4c61867e9fd98c93a04ba549c43019f1b815b'
assert hashlib.sha256(FINE.read_bytes()).hexdigest() == FINE_SHA
fine = json.loads(FINE.read_text())
fine_end = fine['fine02_after_bracket']['after']['sample']
original_phase_plan = m.phase_plan


def phase_plan(*args):
    phases, brackets, reason = original_phase_plan(*args)
    m.require(reason == 'known_completed_native_WaitEnd',
              'This wrapper is only for actual complete baseline02 with bounded known end')
    name, start, end = phases[0]
    m.require(name == 'pre_Start_nominal_fixed' and start == 0 and 0 < fine_end < end,
              'Fine02 recovery does not precede this scan Start')
    return [('prior_R07_history_through_fine02_after_readback', 0, fine_end),
            ('fine02_recovery_to_baseline02_Start', fine_end, end)] + phases[1:], brackets, reason


def main():
    out = json.loads((m.RUN / 'outcome.json').read_text())
    m.require(out['status'] == 'completed' and out['completed_frame_confirmed'] is True,
              'No full-baseline interpretation for a running or interrupted frame')
    m.phase_plan = phase_plan
    with contextlib.redirect_stdout(io.StringIO()) as captured:
        m.main()
    summary = json.loads(captured.getvalue().strip())
    path = Path(summary['path'])
    result = json.loads(path.read_text())
    result['wrapper_source'] = {'path': str(Path(__file__)),
                                'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    result['base_reviewer_source'] = {'path': str(BASE), 'sha256': BASE_SHA}
    result['inputs']['fine02_relocation_review'] = {'path': str(FINE), 'sha256': FINE_SHA}
    result['scope'] = 'R07 actual complete recovered baseline02 plus all native history. Prior interrupted scan and fine01 failure remain separate and unchanged.'
    result['limits'].append('The pre-Start record includes real prior actions. Only the separately labelled fine02 recovery-to-Start interval is treated as fixed-corner recovery. Current band occupancy does not establish zero Z creep.')
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    summary['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
