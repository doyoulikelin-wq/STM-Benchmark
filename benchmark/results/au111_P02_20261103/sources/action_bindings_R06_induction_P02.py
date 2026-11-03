"""Pure local validation/claims. No instrument, socket, subprocess, or network imports."""
import importlib.util
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
SEGMENT_BINDING=HERE/'segment06_observe_binding.py'
SEGMENT_BINDING_SHA='b86f4f0d40fa0eb8cdf9f06f904beb2fc8477e98f5761c1b433d65f3b84f515f'
if hashlib.sha256(SEGMENT_BINDING.read_bytes()).hexdigest()!=SEGMENT_BINDING_SHA:raise RuntimeError('Segment binding changed')
_spec=importlib.util.spec_from_file_location('action_segment06_observe_binding',SEGMENT_BINDING)
sb=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(sb)
ORIGINAL=ROOT/'action_bindings.py'
ORIGINAL_SHA='8e4ff0a546073eac21bf76cf1655195ca9c1a5ee2f4b11e74345dee36d4c1bb0'
if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()!=ORIGINAL_SHA:raise RuntimeError('Original action binding changed')
PRIOR=ROOT.parent/'stm_tip_validation_20261101_1939'
EPISODE='continuing_20261101_1939'
POLICY=Path('/Users/maxlin/.codex/skills/stm-au111-tip-conditioning/assets/local-au111.profile.json')
POLICY_SHA='6ac687710951e08adaaee10212a6910e8287e898e2777e29c8a3758bb74fb945'
LEGACY={PRIOR/'conditioning_session_001_pulse01.claim':'e5e9c8352950310b1255f717690b1db88d20ea92abe26fc2db5a9b98f10089e1',PRIOR/'pulse_001/outcome.json':'895775b2d8816481343c04afd39c71811a1d604f59dfb7a2d1d72ac7396efb58',PRIOR/'conditioning_session_001.result.json':'782d9e365066f40500cbb23c065307448153eb9d1e25a8752ecfb90df96fc590'}

def require(ok,msg):
    if not ok:raise RuntimeError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'monotonic_ns':time.monotonic_ns()}
def local(p):
    p=Path(p).absolute();require(p==p.resolve() and p.is_relative_to(ROOT) and 'win_users' not in p.parts and '/Volumes/' not in str(p),'Exact non-symlink NEW local path required');return p

def paths(session,action,stage,output,logger,fresh,source,source_sha,logger_source_sha):
    require(session==sb.SESSION,'Only session_02/R06 P02 induction variant')
    require(action=='P02','Invalid action id')
    require(stage in ('prepare','pulse','return'),'Invalid stage')
    expected=ROOT/session/(stage+'_induction_'+action)
    require(local(output)==expected and not expected.exists(),'Exact new session/stage output required')
    sb.paths(session,logger);require(Path(logger).is_dir(),'Exact R06 logger directory required')
    local(fresh);require(Path(fresh).is_file(),'Fresh snapshot missing')
    require(sha(local(source))==source_sha,'Executable source SHA mismatch')
    require(sha(sb.LOGGER_SOURCE)==logger_source_sha,'R06 logger source SHA mismatch')
    admitted=admission(stage)
    record=json.loads(Path(fresh).read_bytes());xy=record['values']['FolMe.XYPosGet']
    require(len(xy)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in xy) and all(abs(x-y)<=2e-12 for x,y in zip(xy,admitted['fixed_xy_m'])),'Fresh XY differs from frozen induction target')
    bad=artifact(admitted['baseline_outcome']);require(record['start']['monotonic_ns']>=bad['end_event']['monotonic_ns'],'Fresh snapshot precedes usable baseline full frame')
    return expected

def exclusive(path,record):
    path=local(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write((json.dumps(record,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return record

def reserve_stage(session,action,stage,output,source_sha,fresh_sha):
    require(Path(output).resolve()==ROOT/session/(stage+'_induction_'+action),'Stage output mismatch')
    return exclusive(ROOT/'globalclaims'/f'{session}__{stage}_induction_{action}.claim',{
        **stamp(),'session_id':session,'action_id':action,'stage':stage,'output':str(output),
        'source_sha256':source_sha,'fresh_snapshot_sha256':fresh_sha,
        'purpose':'induction_attempt','induction_effect':'not_assessed','admission_not_execution_proof':True})

def artifact(ref,expected=None):
    p=local(ref['path']);require(expected is None or p==expected,'Artifact path mismatch')
    require(p.is_file() and sha(p)==ref['sha256'],'Missing/changed artifact');return json.loads(p.read_bytes())

def reservation_path(ordinal):
    require(type(ordinal) is int and ordinal==4,'Only first R06 P02 induction continuing pulse ordinal4 permitted')
    return ROOT/'globalclaims'/f'{EPISODE}__pulse_{ordinal:02d}.claim'


ADMISSION_SOURCE=HERE/'induction_R06_P02_admission.py'
ADMISSION_SOURCE_SHA='f6e466b49339d5c0c57f22863ed9b89bffb461341a422f068d1425eba0016239'
if sha(ADMISSION_SOURCE)!=ADMISSION_SOURCE_SHA:raise RuntimeError('Induction admission source changed')
_spec2=importlib.util.spec_from_file_location('repair_R06_A02_admission',ADMISSION_SOURCE)
ra=importlib.util.module_from_spec(_spec2);_spec2.loader.exec_module(ra)
ADMISSION_PATH=ADMISSION_SHA=None
def bind_admission(path,digest,stage):
    global ADMISSION_PATH,ADMISSION_SHA
    result=ra.validate(path,digest,stage);ADMISSION_PATH=Path(path);ADMISSION_SHA=digest;return result
def admission(stage):
    require(ADMISSION_PATH is not None and ADMISSION_SHA is not None,'Explicit induction admission required')
    return ra.validate(ADMISSION_PATH,ADMISSION_SHA,stage)

def ledger_guard(path,digest,session,action,ordinal,pulse,xy=None):
    require(session=='session_02' and action=='P02' and ordinal==4,'Only this P02 induction ordinal4 choice')
    reservation=reservation_path(ordinal);require(not reservation.exists(),'Pulse ordinal4 already reserved; no replay')
    admitted=admission('pulse');p=local(path)
    require(p==ROOT/session/'induction_P02.ledger.json' and sha(p)==digest,'Canonical ledger/hash mismatch');v=json.loads(p.read_bytes())
    require(v['schema']=='local-au111-R06-P02-induction-pulse-v1' and v['episode_id']==EPISODE and v['case_id']==ra.CASE and v['session_id']==session and v['action_id']==action,'Ledger identity differs')
    require(v['induction_admission']=={'path':str(ADMISSION_PATH),'sha256':ADMISSION_SHA},'Ledger admission differs')
    for key in ('profile','required_safetip','pulse_attempts_before','pulse_ordinal','consecutive_no_improvement_before','action','fixed_xy_m','target_id','origin'):
        require(v[key]==admitted[key],'Ledger differs from frozen admission: '+key)
    require(v['pulse_attempts_before']==3 and v['pulse_ordinal']==4 and v['max_pulses_total']==6 and v['review_after_consecutive_no_improvement']==2,'No pulse counter reset')
    require(v['action']['command']==pulse[0] and v['action']['args']==pulse[1],'Runtime choice differs from frozen decision')
    prep=artifact(v['preparation_outcome'],ROOT/session/'prepare_induction_P02/outcome.json');manifest=artifact(v['preparation_manifest'],ROOT/session/'prepare_induction_P02/manifest.json')
    f32=struct.unpack('>f',struct.pack('>f',1e-9))[0]
    require(prep.get('status')=='completed' and prep.get('mode')=='prepare' and prep.get('final_target_A')==f32 and prep.get('attempted_sets')==11 and prep.get('acknowledged_sets')==11,'Prepare not independently complete')
    require(manifest['source_sha256']==sha(HERE/'setpoint_R06_induction_P02_once.py') and manifest['induction_admission']==v['induction_admission'] and manifest['session_id']==session and manifest['action_id']==action and manifest['recording_segment_id']=='R06','Preparation belongs to different evidence/action')
    review=ra.native_review(v['preparation_native_review'],v['preparation_outcome'],prep['monotonic_ns'])
    require(review['allow_one_pulse'] is True and review['preparation_manifest']==v['preparation_manifest'],'Root must independently review preparation and choose one pulse')
    if xy is not None:require(len(xy)==2 and all(abs(x-y)<=2e-12 for x,y in zip(xy,v['fixed_xy_m'])),'Fresh XY differs from admission')
    return v

def reserve_pulse(path,digest,session,action,ordinal,pulse,output,fresh_sha,source_sha):
    ledger_guard(path,digest,session,action,ordinal,pulse)
    return exclusive(reservation_path(ordinal),{**stamp(),'episode_id':EPISODE,'case_id':ra.CASE,'session_id':session,'action_id':action,
        'pulse_ordinal':ordinal,'pulse_attempts_before':3,'pulse_attempts_reserved':4,
        'ledger_path':str(path),'ledger_sha256':digest,'output':str(output),'source_sha256':source_sha,
        'fresh_snapshot_sha256':fresh_sha,'command':pulse[0],'args':pulse[1],
        'induction_admission_sha256':ADMISSION_SHA,'claim_consumes_budget_even_if_ACK_unknown':True,'legacy_pulse_count_included':3,'purpose':'induction_attempt','induction_effect':'not_assessed','repair_episode_active':False})
