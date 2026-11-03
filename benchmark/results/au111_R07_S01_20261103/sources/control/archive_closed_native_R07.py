"""Plan by default; root-only SMB read/local copy of already closed R07 blocks.
No instrument API, socket, writer, terminal-block copy, or change to prior segment receipts.
"""
from pathlib import Path, PureWindowsPath
import argparse, datetime, hashlib, json, os, re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SESSION = ROOT / 'session_02'
LOGGER = SESSION / 'logger_07'
DEST = SESSION / 'native_R07'
RECEIPT = SESSION / 'native_receipt_R07.json'
SHARE = ROOT.parent / 'stm_tip_benchmark_goal_20261030/win_users/Public/stm-benchmark-goal-20261030/native'
LOGGER_SOURCE = HERE / 'logger_fullcycle_segment07_observe_once.py'
LOGGER_SHA = '1e127682ad19e005660ff2d2d82ef132d468d2e3e786fd6afa15cbb4650967d0'
SOURCE = HERE / 'archive_closed_native_R06.py'
SOURCE_SHA = 'eae862781ff9970456eb52bfa3bf5a366d46a026039fa8f0162c23e9f00c13ff'
EXPECTED_START = '2026/11/3 13:45:34'
EXPECTED_BASENAME = 'dl_goal30_FIVE1102_SESSION_02_R07'
IDENTITY_PINS = {'READY.json': 'c1c50e68c637cba2e77e6292ab84d764aec7af0475caf7e4aa4c36ba13acc3b7', 'manifest.json': '3352882ed403b994728a8105553e424f65f26616d198ba88ee43e194dd368ecf', 'start.claim': 'a5e32acb30c306329267c0a3a90fa169dbd7be92342cd6bd8a13baf4dba36df7'}
CHANNELS = ['Current (A)', 'Bias (V)', 'Z (m)', 'Z Control signal (A)', 'Z Error signal (A)', 'Z SafeTip signal (A)']

def require(ok, message):
    if not ok: raise RuntimeError(message)

def sha(data): return hashlib.sha256(data).hexdigest()

def plan():
    return {'execution': 'local plan only; no share access', 'session_id': 'session_02', 'recording_segment_id': 'R07',
        'logger': str(LOGGER), 'destination': str(DEST), 'receipt': str(RECEIPT),
        'logger_source_sha256': LOGGER_SHA, 'parent_source_sha256': SOURCE_SHA,
        'closed_rule': 'Only indices strictly below the latest observed saved-path index; last block is always excluded, including after Stop.',
        'scope': 'One bounded copy pass. No instrument commands. Numeric finite, stage attribution and full terminal archive remain separate audits.'}

def identity(record):
    expected = {'session_id':'session_02', 'recording_segment_id':'R07', 'source_path':str(LOGGER_SOURCE),
                'source_sha256':LOGGER_SHA, 'role':'fullcycle_native_logger'}
    require(all(record.get(k) == v for k,v in expected.items()), 'R07 logger identity mismatch')

def start_reference_path(ready):
    p=Path(ready['start_claim']['path'])
    p=p if p.is_absolute() else LOGGER/p
    require(p.resolve()==LOGGER/'start.claim','Start claim path outside exact logger claim')
    return p.resolve()

def context():
    require(EXPECTED_START != 'R07_START_NOT_YET_FROZEN' and set(IDENTITY_PINS) == {'READY.json','manifest.json','start.claim'}, 'Actual R07 start identity must be frozen before use')
    require(sha(SOURCE.read_bytes()) == SOURCE_SHA and sha(LOGGER_SOURCE.read_bytes()) == LOGGER_SHA, 'Source pin mismatch')
    for p in (LOGGER, DEST, RECEIPT):
        require(p == p.resolve() and p.is_relative_to(ROOT), 'Exact local output path required')
    ready_bytes = (LOGGER/'READY.json').read_bytes(); ready = json.loads(ready_bytes)
    manifest_bytes = (LOGGER/'manifest.json').read_bytes(); manifest = json.loads(manifest_bytes)
    start_bytes = (LOGGER/'start.claim').read_bytes(); start = json.loads(start_bytes)
    for record in (ready, manifest, start): identity(record)
    require(ready.get('ready') is True and ready.get('output_directory') == str(LOGGER), 'Wrong READY directory/state')
    require(ready['start_claim']['sha256'] == sha(start_bytes) and start_reference_path(ready) == LOGGER/'start.claim', 'Start claim binding mismatch')
    require(start.get('command') == 'DataLog.Start' and start.get('args') == [], 'Not a DataLog.Start claim')
    with (LOGGER/'events.jsonl').open('rb') as f:
        size=f.seek(0,2); f.seek(max(0,size-200000)); lines=f.read().splitlines()
    events=[]
    for line in lines:
        try: events.append(json.loads(line))
        except ValueError: pass
    event=next((e for e in reversed(events) if e.get('kind')=='datalog_status'),None)
    require(event is not None, 'No native status event')
    state=event['raw_values']
    require(len(state)==10 and state[1]==ready['native_start_identity'], 'Native start identity mismatch')
    require(isinstance(ready['basename'],str) and re.fullmatch(r'[A-Za-z0-9_]+',ready['basename']), 'Unexpected native basename')
    match=re.fullmatch(re.escape(ready['basename'])+r'(\d{5})\.dat',PureWindowsPath(state[8]).name)
    require(match is not None and int(match[1])>=1, 'Native saved-path index mismatch')
    require(ready['native_start_identity'] == EXPECTED_START and ready['basename'] == EXPECTED_BASENAME, 'Different owned R07 Start/basename')
    actual_pins = {'READY.json':sha(ready_bytes),'manifest.json':sha(manifest_bytes),'start.claim':sha(start_bytes)}
    require(actual_pins == IDENTITY_PINS, 'Immutable logger identity changed')
    last=int(match[1])
    evidence={'READY_sha256':sha(ready_bytes),'manifest_sha256':sha(manifest_bytes),'start_claim_sha256':sha(start_bytes)}
    return ready,event,state,last,evidence

def parse_full(data):
    text=data.decode('ascii').replace('\r\n','\n')
    require('Sample Period (ms)\t5.000E-1' in text, 'Native sample period differs')
    lines=text.split('[DATA]\n',1)[1].splitlines()
    require(lines[0].split('\t')==CHANNELS,'Native six-channel header differs')
    rows=[line for line in lines[1:] if line.strip()]
    require(len(rows)==25000 and all(len(row.split('\t'))==6 for row in rows),'Closed full block dimensions differ')
    return len(rows)

def archive():
    ready,event,state,last,evidence=context(); limit=last-1
    receipt=json.loads(RECEIPT.read_bytes()) if RECEIPT.exists() else {'files':{}}
    if 'native_start_identity' in receipt:
        require(receipt.get('native_start_identity')==state[1] and receipt.get('recording_segment_id')=='R07'
                and receipt.get('logger_identity_evidence')==evidence,'Existing receipt belongs to another logger/start')
        require(receipt['complete_through_index']<=limit,'Native index regressed')
    DEST.mkdir(exist_ok=True); new=0
    for index in range(1,limit+1):
        filename=f"{ready['basename']}{index:05d}.dat"; target=DEST/filename
        if filename in receipt['files']:
            require(target.is_file() and sha(target.read_bytes())==receipt['files'][filename]['sha256'],'Existing local block changed')
            continue
        source=SHARE/filename; data=source.read_bytes(); digest=sha(data); rows=parse_full(data)
        require(sha(source.read_bytes())==digest,'Closed source changed across two reads')
        if target.exists(): require(target.read_bytes()==data,'Unreceipted local block differs')
        else:
            with target.open('xb') as f:f.write(data); f.flush(); os.fsync(f.fileno())
        require(sha(target.read_bytes())==digest,'Local copied block hash differs')
        receipt['files'][filename]={'local_path':str(target),'source_path':str(source),'sha256':digest,'bytes':len(data),'rows':rows,
            'source_double_read_sha_equal':True,'local_reread_sha_equal':True,'closed_basis_event_utc':event['utc'],
            'last_path_index_at_copy':last,'terminal_block':False,'numeric_finite_and_phase_audit_pending':True}
        new+=1
    receipt.update(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),session_id='session_02',recording_segment_id='R07',
        native_start_identity=state[1],native_stop_observed=state[6] or None,last_status_event=event,complete_through_index=limit,
        all_blocks_including_last_archived=False,logger_identity_evidence=evidence,logger_source_sha256=LOGGER_SHA,
        script_sha256=sha(Path(__file__).read_bytes()),terminal_copy_policy='Always excluded; separate confirmed-stop terminal archive required')
    temporary=RECEIPT.with_suffix('.json.tmp')
    with temporary.open('x') as f:json.dump(receipt,f,ensure_ascii=False,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temporary,RECEIPT)
    return {'new_files':new,'total_files':len(receipt['files']),'closed_through':limit,'terminal_copied':False,'receipt':str(RECEIPT)}

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--execute',action='store_true'); ap.add_argument('--source-sha256')
    args=ap.parse_args()
    if not args.execute: print(json.dumps(plan(),indent=2)); return
    require(args.source_sha256==sha(Path(__file__).read_bytes()),'Explicit current source SHA required')
    print(json.dumps(archive(),indent=2))

if __name__=='__main__':main()
