"""Pure local binding for exactly session_02 recording R07; no device/network imports.
Recording identity never changes episode, action, stage or pulse claim keys.
"""
import datetime,hashlib,json,os,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
SESSION='session_02'
SEGMENT='R07'
LOGGER_DIR=ROOT/SESSION/'logger_07'
PREVIOUS_DIR=ROOT/SESSION/'logger_06'
LOGGER_SOURCE=HERE/'logger_fullcycle_segment07_observe_once.py'
PREVIOUS_SOURCE=HERE/'logger_fullcycle_segment06_observe_once.py'
PREVIOUS_SOURCE_SHA='527e5b5f3a7d542415c9efda6506818f64a8a910848766c34d37508fbed53184'
START_RESERVATION=ROOT/'recording_claims'/'session_02__R07.start.claim'


ADMISSION_PATH = HERE / 'segment07_observe_root_admission.json'
BASENAME = 'dl_goal30_FIVE1102_SESSION_02_R07'
# Pin the audited predecessor at this specific recording boundary.
R06_EVIDENCE = {
    'previous_ready': (ROOT / 'session_02/logger_06/READY.json', '463890eb80aae4f6889e35d1c5c8db72c96f5a74fba28b01180b56f956cc7b10'),
    'previous_start_claim': (ROOT / 'session_02/logger_06/start.claim', '8bf28a7714098f399911fc67ee20f7fca7c8b4b0da13ffb033b186fea8412e0f'),
    'previous_outcome': (ROOT / 'session_02/logger_06/outcome.json', 'a1a64947f61fcc8f0d33a69cba82f4cff14a37bedf19b12dee37c9c4f63eb426'),
    'previous_stop_evidence': (ROOT / 'continuation_slow_20261102/stop_R06_root_signal.json', '799e2af57176de1a92cf8e4d202c953b63a27c581b7103b97ea9d645049a8b6f'),
    'previous_native_archive_audit': (ROOT / 'continuation_slow_20261102/R06_terminal_native_review/review.json', '76e4693972ebc267e9379d5c0a04c1c6a29c96a272974d4d8757a4e1d9525700'),
    'previous_terminal_receipt': (ROOT / 'continuation_slow_20261102/R06_terminal_native_review/receipt.json', 'a85e34f4c6bdb25e1a795dcf079573f5a6422f6260a5f91e2dc766d769ad09d8'),
    'previous_terminal_evidence': (ROOT / 'continuation_slow_20261102/R06_terminal_native_review/terminal_evidence.json', 'da0be50b026e8a745ee194901b665edcc183099e0edc9c88ad0a35cab122714a'),
}
HISTORICAL_COUNTS = {'completed_full_attempts': 2, 'strict_successful_cycles': 0, 'remaining': 3, 'documented_pulses': 5, 'shared_shaper_Starts': 3}

def require(ok,message):
    if not ok:raise RuntimeError(message)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(p):
    p=Path(p).absolute();require(p==p.resolve() and p.is_relative_to(ROOT) and not any(x.lower() in ('volumes','win_users') for x in p.parts),'Exact non-symlink batch-local path required');return p

def paths(session,logger):
    require(session==SESSION and local(logger)==LOGGER_DIR,'Only session_02/logger_07 is allowed by this variant')

def metadata(source_sha):
    return {'session_id':SESSION,'recording_segment_id':SEGMENT,'source_path':str(LOGGER_SOURCE),'source_sha256':source_sha,'role':'fullcycle_native_logger'}

def consumer_metadata(logger_sha):
    return {'recording_segment_id':SEGMENT,'logger_directory':str(LOGGER_DIR),'logger_source_path':str(LOGGER_SOURCE),'logger_source_sha256':logger_sha}

def verify_logger_identity(record,logger_sha):
    require(all(record.get(k)==v for k,v in metadata(logger_sha).items()),'Logger source/session/segment/role binding mismatch')

def artifact(ref,expected=None):
    p=local(ref['path']);require(expected is None or p==expected,'Evidence path mismatch')
    require(p.is_file() and sha(p)==ref['sha256'],'Evidence missing or hash mismatch')
    return json.loads(p.read_bytes())

def admission(path,digest,source_sha,basename,mode):
    path = local(path)
    require(path == ADMISSION_PATH and sha(path) == digest, 'Expected root R07 admission path and hash')
    j=json.loads(path.read_bytes())
    require(j['schema']=='recording-segment07-observation-admission-v1' and j['session_id']==SESSION and j['recording_segment_id']==SEGMENT,'Admission identity mismatch')
    require(j['allow_one_start'] is True and j['exclusive_root_writer'] is True and j['all_junction_actions_known_ended'] is True,'Root oneStart/ownership/known-end admission missing')
    require(j['previous_native_archive_complete'] is True and j['unresolved_previous_recording_state'] is False,'Previous recording unresolved or archive incomplete')
    require(j['new_logger_source_sha256']==source_sha and j['new_native_basename']==basename and j['new_mode']==mode,'Admission/source/basename/mode mismatch')
    require(isinstance(j['reason'],str) and j['reason'].strip(),'Rollover reason required')
    require(basename == BASENAME and mode == 'engaged_observation', 'Invalid R07 basename or entry mode')
    require(j['historical_counts_through_R06'] == HISTORICAL_COUNTS and j['new_full_baseline_required'] is True
            and j['unrecorded_interval_preserved'] is True, 'Preserve history, recording gap and new baseline requirement')
    require(j['previous_stop_kind'] == 'intentional_owned_stop', 'Expected intentional R06 closure')
    for key, (expected_path, expected_hash) in R06_EVIDENCE.items():
        require(j[key] == {'path': str(expected_path), 'sha256': expected_hash}, 'Incorrect R06 evidence reference: ' + key)
    receipt = artifact(j['previous_terminal_receipt'])
    terminal = artifact(j['previous_terminal_evidence'])
    require(receipt['complete_through_index'] == 615 and receipt['all_blocks_including_last_archived'] is True
            and receipt['total_rows_per_channel'] == 15362600 and terminal['independent_native_stop_confirmed'] is True
            and terminal['DataLog_Stop_acknowledged'] is True, 'R06 terminal evidence incomplete')
    require(sha(PREVIOUS_SOURCE)==PREVIOUS_SOURCE_SHA,'Legacy logger source changed')
    ready=artifact(j['previous_ready'],PREVIOUS_DIR/'READY.json')
    start=artifact(j['previous_start_claim'],PREVIOUS_DIR/'start.claim')
    artifact(j['previous_outcome'],PREVIOUS_DIR/'outcome.json')
    require(j['previous_stop_kind'] in ('intentional_owned_stop','native_timed_end'),'Explicit predecessor stop kind required')
    stop_evidence=artifact(j['previous_stop_evidence']);require(isinstance(stop_evidence,dict) and bool(stop_evidence),'Hash-bound stop/termination evidence required; two stopped readbacks remain decisive')
    archive=artifact(j['previous_native_archive_audit'])
    require(isinstance(archive,dict) and bool(archive),'Nonempty previous native audit required; root explicitly reviews its completion')
    require(all(doc.get('recording_segment_id')=='R06' and doc.get('source_path')==str(PREVIOUS_SOURCE) and doc.get('role')=='fullcycle_native_logger' for doc in (ready,start)),'Previous R06 source/segment/role mismatch')
    require(ready['ready'] is True and ready['source_sha256']==PREVIOUS_SOURCE_SHA and ready['session_id']==SESSION and Path(ready['output_directory']).resolve()==PREVIOUS_DIR,'Previous READY identity mismatch')
    require(ready['start_claim']['sha256']==j['previous_start_claim']['sha256'] and start['command']=='DataLog.Start' and start['args']==[] and start['source_sha256']==PREVIOUS_SOURCE_SHA and start['session_id']==SESSION,'Previous Start provenance mismatch')
    require(basename!=ready.get('basename'),'Never reuse previous native basename')
    refs=j['stop_snapshots'];require(len(refs)==2 and refs[0]['path']!=refs[1]['path'],'Two independent stop snapshots required')
    a,b=[artifact(ref) for ref in refs];v=a['values']['DataLog.StatusGet'];w=b['values']['DataLog.StatusGet']
    require(len(v)==10 and v==w and v[1]==ready['native_start_identity'] and bool(v[6]) and bool(v[8]) and type(v[9]) is int and v[9]>=0,'Previous sameStart/stopped/terminal status not confirmed')
    t0=a['end']['monotonic_ns'];t1=b['start']['monotonic_ns'];require(t1-t0>=1e9 and b['end']['monotonic_ns']<=time.monotonic_ns(),'Stop readback spacing or clock invalid')
    require(terminal['terminal_raw'] == v and v[1] == '2026/11/3 11:28:40'
            and v[6] == '2026/11/3 13:36:41', 'R06 terminal readback differs from complete audit')
    fresh = artifact(j['fresh_state'])
    age_s = (time.monotonic_ns() - fresh['end']['monotonic_ns']) / 1e9
    require(0 <= age_s <= 180 and fresh['values']['DataLog.StatusGet'] == v,
            'Current readback stale or another recording state intervened')
    return {'admission_path':str(path),'admission_sha256':digest,'root_admission':j,'previous_raw_stopped_status':v,
            'gap_policy':'New full baseline required; raw recording gap retained. Root archive attestation is hash-bound, not re-parsed by logger.'}

def reserve_start(binding,source_sha,basename):
    path=local(START_RESERVATION);path.parent.mkdir(parents=True,exist_ok=True)
    record={**metadata(source_sha),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'monotonic_ns':time.monotonic_ns(),
            'command':'DataLog.Start','args':[],'basename':basename,'admission_sha256':binding['admission_sha256'],'one_attempt_no_release':True,'not_a_junction_action_or_budget_reset':True}
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write((json.dumps(record,sort_keys=True,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return {'path':str(path),'sha256':sha(path)}


def completed_baseline(logger_sha):
    """New full baseline under R07; this is completion/provenance, not image quality."""
    directory=ROOT/SESSION/'baseline_segment07_full'
    manifest=json.loads((directory/'manifest.json').read_bytes())
    out=json.loads((directory/'outcome.json').read_bytes())
    recorded=json.loads((directory/'logger_ready_bound.json').read_bytes())
    ready=json.loads((LOGGER_DIR/'READY.json').read_bytes())
    start=json.loads((directory/'scan_start.claim').read_bytes())
    verify_logger_identity(recorded,logger_sha);verify_logger_identity(ready,logger_sha)
    require(recorded==ready,'Baseline belongs to another recording start')
    require(manifest.get('session_id')==SESSION and manifest.get('event_id')=='baseline_segment07_full' and all(manifest.get(k)==v for k,v in consumer_metadata(logger_sha).items()),'Baseline segment/role mismatch')
    require(out.get('status')=='completed' and out.get('completed_frame_confirmed') is True and len(out.get('frames',[]))==6,'New full R07 baseline not completed')
    require(start.get('command')=='Scan.Action' and start.get('args')==[0,0] and start['monotonic_ns']>=json.loads((LOGGER_DIR/'start.claim').read_bytes())['monotonic_ns'],'Baseline does not follow R07 Start')
    require(out['end_event']['monotonic_ns']>=start['monotonic_ns'],'Baseline end precedes Start')
    return {name:{'path':str(directory/name),'sha256':sha(directory/name)} for name in ('manifest.json','outcome.json','logger_ready_bound.json','scan_start.claim')}
