
"""Close the exact owned R07 DataLog observer once after completed217."""
from pathlib import Path
import datetime
import hashlib
import json
import math
import os
import signal
import subprocess
import time

c = Path("/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102")
n = c.parent
logger = n / 'session_02/logger_07'
launch = json.loads((c / 'R07_logger_launch.json').read_text())
source = c / 'logger_fullcycle_segment07_observe_once.py'
assert hashlib.sha256(source.read_bytes()).hexdigest() == '1e127682ad19e005660ff2d2d82ef132d468d2e3e786fd6afa15cbb4650967d0'
assert launch['pid'] == 74698
assert all(not any(ch.isspace() for ch in arg) for arg in launch['args'])
command = subprocess.check_output(['ps', '-p', '74698', '-o', 'command='], text=True).strip()
assert command == ' '.join(launch['args'])
assert str(source) in launch['args']
assert not (logger / 'outcome.json').exists()
scan_path = n / 'session_02/after_R07_S02_restored_full/outcome.json'
scan = json.loads(scan_path.read_text())
assert scan['status'] == 'completed' and scan['completed_frame_confirmed'] is True
acceptance = c / 'R07_S02_full02_image_review/root_image_acceptance.json'
assert hashlib.sha256(acceptance.read_bytes()).hexdigest() == 'df65500e1cb1b83e2517b0a755d66ff7c1534ebdc6408356d73f37a56daaa1cc'
with (logger / 'events.jsonl').open('rb') as stream:
    size = stream.seek(0, 2)
    start = max(0, size - 300000)
    stream.seek(start)
    chunks = stream.read().split(b'\n')
if start:
    chunks = chunks[1:]
rows = [json.loads(line) for line in chunks[:-1] if line]
status = next(row for row in reversed(rows) if row.get('kind') == 'datalog_status')
junction = next(row for row in reversed(rows) if row.get('kind') == 'dynamic_state_poll')
now = time.monotonic_ns()
assert all(0 <= now - row['monotonic_ns'] < 2000000000 for row in (status, junction))
assert status['parsed']['start'] == '2026/11/3 13:45:34' and not status['parsed']['stop']
v = junction['values']
assert all(v[name] == [0] for name in ['Scan.StatusGet', 'BiasSpectr.StatusGet', 'ZSpectr.StatusGet', 'AutoApproach.OnOffGet'])
assert v['ZCtrl.OnOffGet'] == [1] and v['ZCtrl.StatusGet'] == [2]
assert v['SafeTip.OnOffGet'] == [0] and v['Bias.Get'] == [-1.0]
assert v['ZCtrl.SetpntGet'] == [1.000000013351432e-10]
assert all(math.isfinite(v[name][0]) for name in ['Current.Get', 'ZCtrl.ZPosGet'])
receipt = {
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'monotonic_ns': now, 'pid': 74698, 'verified_command': command,
    'source': str(Path(__file__)), 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'reason': 'Complete216 induction and restored217 assessment finished; current nanoscale task usable. Await experimenter quantitative next recipe and clipping criteria. Close this recording segment after documented recovery.',
    'root_acceptance': str(acceptance), 'root_acceptance_sha256': hashlib.sha256(acceptance.read_bytes()).hexdigest(),
    'action': 'SIGINT owned R07 logger', 'signal': int(signal.SIGINT),
    'latest_status': status, 'latest_junction_observation': junction,
    'junction_writer_active': False, 'native_stop_confirmed_by_signal_alone': False,
}
with (c / 'stop_R07_root_signal.json').open('x') as stream:
    json.dump(receipt, stream, ensure_ascii=False, indent=2)
    stream.flush()
    os.fsync(stream.fileno())
os.kill(74698, signal.SIGINT)
print(json.dumps({'signal_requested': True, 'utc': receipt['utc']}))
