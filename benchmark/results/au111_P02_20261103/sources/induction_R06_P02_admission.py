"""Pure local P02 evidence admission. No device/network use or automatic stage chain.
One continuing ordinal4 pulse may be selected only after independently complete preparation.
"""
import hashlib,importlib.util,json,math,struct,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;SESSION=ROOT/'session_02'
def load(name,p,h):
    if hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise RuntimeError('Frozen source changed: '+str(p))
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
PRECEDENT=HERE/'induction_R03_P01_admission.py';PRECEDENT_SHA='b90279908c07e814d78a837a22e10ca845f944285b3beae7c2aa9b5bf971f0b6'
if hashlib.sha256(PRECEDENT.read_bytes()).hexdigest()!=PRECEDENT_SHA:raise RuntimeError('Original P01 admission changed')
ib=load('P02_local_history',HERE/'induction_R06_I03_target_binding.py','ae6178a457ecb5d71c7c205217d9074472edea4dc3caddfa8ec1a83a143e291a')
sb=load('P02_R06_recording',HERE/'segment06_observe_binding.py','b86f4f0d40fa0eb8cdf9f06f904beb2fc8477e98f5761c1b433d65f3b84f515f')
require,sha,local,artifact=ib.require,ib.sha,ib.local,ib.artifact
def ref(p):return {'path':str(p),'sha256':sha(p)}
ADMISSION=SESSION/'induction_R06_P02.admission.json'
EPISODE='continuing_20261101_1939';CASE='R06_usable211_induction_P02'
BASELINE_EVENT='after_R06_I03_full';BASELINE=SESSION/BASELINE_EVENT
SCAN_SOURCE=HERE/'scan_full50nm_fast_R06_after_induction_I03_once.py'
SCAN_SHA='d039b5fc37d47672f0319e050615b7e3294273b3215259b0aac1923da61bc591'
LOGGER=SESSION/'logger_06';LOGGER_SHA='527e5b5f3a7d542415c9efda6506818f64a8a910848766c34d37508fbed53184'
IMAGE_PLAN=HERE/'R06_pulse_P02_image_review/prospective_image_review_plan.json';IMAGE_PLAN_SHA='993009578a95d550b9a18b729306bec06c525c7ecd1f147f09336958b41679a3'
FUNCTIONAL_REVIEW={'path':str(HERE/'R06_induction_I03/post_manual_review.json'),'sha256':'e8314818e93b3dec4bbe4d28e4a3cf963195f9ae9ea71e402a62aa9bcca71cd7'}
COUNTER_REVIEW={'path':str(HERE/'R03_A02_legacy_counter_review.json'),'sha256':'ee7742d9e430188d0c34e2491abfecf0b2ba21926200db0fb8ad25be83a6cc8b'}
POLICY=Path('/Users/maxlin/.codex/skills/stm-au111-tip-conditioning/assets/local-au111.profile.json');POLICY_SHA='6ac687710951e08adaaee10212a6910e8287e898e2777e29c8a3758bb74fb945'
HISTORY=dict(ib.HISTORY)
HISTORY.update({
 ROOT/'globalclaims/session_02__R06_induction_I03__shaper_01.claim':'61c9446ab4a0947760165474f7fa66c0c24bdce1c35e99cb33480ce5d4b10e2b',
 SESSION/'induction_R06_I03/outcome.json':'c9d1bf159647440ad03884055ef7b8de0098efe7cf3fac99096e90036bc53e7d',
 ROOT/'globalclaims/session_02__R06_induction_I03_move.claim':'092a3be0a2d1f5fe23862076e8b9154a7890f34c490dbfaaa56aa871ce6c2237',
 SESSION/'move_R06_I03/outcome.json':'672350e12cde3629246939a33b1bfe1e69fce3df7a4f12942d1cd783d90aa0ce',
 SESSION/'prepare_induction_P01/outcome.json':'b67d4b160ef2dde97db01c7bc5aa8441faf2a73d3d4f0149e9f881c2778ec9d9',
 SESSION/'recover_prepare_induction_P01_01/outcome.json':'122a3f9c36d66cad1392f44e95dbf0678c0c55bd906a3ea64b903253a022d938',
})
REQUEST=[1,.020,-5.7,1,2];WIRE=[1,struct.unpack('>f',struct.pack('>f',.020))[0],struct.unpack('>f',struct.pack('>f',-5.7))[0],1,2]
ACTION={'command':'Bias.Pulse','args':REQUEST,'resting_bias_V':-1.,'preparation_current_A':1e-9,'imaging_current_A':100e-12}
RETURN_REVIEW=SESSION/'induction_R06_P02_return_review.json';RETURN_REVIEW_SHA=None
def corner(xy):return isinstance(xy,list) and len(xy)==2 and all(type(x) in (int,float) and math.isfinite(x) and abs(x+25e-9)<=2e-12 for x in xy)
def history_guard(stage,digest):
    require(sha(POLICY)==POLICY_SHA and sha(IMAGE_PLAN)==IMAGE_PLAN_SHA,'Local policy or image criteria changed')
    for p,h in HISTORY.items():require(sha(p)==h,'Historical pulse/shaper/move/preparation record changed')
    claims=ROOT/'globalclaims';expected={claims/(EPISODE+'__pulse_02.claim'),claims/(EPISODE+'__pulse_03.claim')};claim4=claims/(EPISODE+'__pulse_04.claim')
    if stage=='return':expected.add(claim4)
    require(set(claims.glob(EPISODE+'__pulse_*.claim'))==expected,'Cumulative pulse history changed; no reset or replay')
    require(set(claims.glob(EPISODE+'__shaper_*.claim'))=={claims/(EPISODE+'__shaper_01.claim')},'Preserve A05 repair Start count1')
    require(set(claims.glob('session_02__R06_induction_*__shaper_*.claim'))=={claims/'session_02__R06_induction_I02__shaper_01.claim',claims/'session_02__R06_induction_I03__shaper_01.claim'},'Preserve two independent mechanical induction Starts')
    require(not (SESSION/'pulse_induction_P01').exists(),'Unexpected old P01 pulse execution; reconcile first')
    old=json.loads((SESSION/'prepare_induction_P01/outcome.json').read_bytes());recovery=json.loads((SESSION/'recover_prepare_induction_P01_01/outcome.json').read_bytes())
    require(old['status']=='stopped_no_further_sets' and old['attempted_sets']==old['acknowledged_sets']==6 and old['execution_unknown'] is False,'P01 preparation history changed')
    require(recovery['status']=='completed','P01 independent recovery unresolved')
    if stage=='return':
        claim=json.loads(claim4.read_bytes());require(claim['output']==str(SESSION/'pulse_induction_P02') and claim['pulse_ordinal']==4 and claim['episode_id']==EPISODE and claim['induction_admission_sha256']==digest and claim['purpose']=='induction_attempt','Return must belong to this known P02 pulse')
def load_scanner():return load('P02_complete211_source',SCAN_SOURCE,SCAN_SHA)
def baseline_proof(j):
    scan=load_scanner();prior=scan.evidence_for_scan(LOGGER,LOGGER_SHA)
    mf=json.loads((BASELINE/'manifest.json').read_bytes());start=json.loads((BASELINE/'scan_start.claim').read_bytes());ready=json.loads((LOGGER/'READY.json').read_bytes());sb.verify_logger_identity(ready,LOGGER_SHA)
    require(json.loads((BASELINE/'logger_ready_bound.json').read_bytes())==ready and mf['source_sha256']==SCAN_SHA and mf['session_id']=='session_02' and mf['event_id']==BASELINE_EVENT and all(mf.get(k)==v for k,v in sb.consumer_metadata(LOGGER_SHA).items()),'211 capture source/recording differs')
    out=artifact(j['baseline_outcome'],BASELINE/'outcome.json');q=artifact(j['baseline_quality'],BASELINE/'analysis/quality_report.json');g=q['integrity']
    require(out['status']=='completed' and out['completed_frame_confirmed'] is True and len(out['frames'])==6 and start['command']=='Scan.Action' and start['args']==[0,0] and prior['earliest_snapshot_ns']<=start['monotonic_ns']<=out['end_event']['monotonic_ns']<=out['monotonic_ns'],'Complete211 after known I03 required')
    require(g['native_TCP_wire_bitmatch'] is True and g['matched_float32_values']==345600 and g['capture']==str(BASELINE) and g['capture_outcome_sha256']==j['baseline_outcome']['sha256'] and g['completed_outcome'] is True and q['grid']['pixels']==q['grid']['lines']==240 and q['grid']['scan_direction']=='down','Complete211 native/TCP integrity required')
    p=local(q['source']['path']);require(p==BASELINE/'native/BM261029_00211.sxm' and p.name==out['native_file_path'].split(chr(92))[-1] and sha(p)==q['source']['sha256'],'Actual211 native identity differs')
    for name in ('before.json','after.json','after_frames.json'):
        v=json.loads((BASELINE/name).read_bytes())['values'];require(all(v[k]==scan.EXPECTED[k] for k in scan.FROZEN),'211 frozen fields differ')
    final=json.loads((BASELINE/'after_frames.json').read_bytes())['values'];require(corner(final['FolMe.XYPosGet']) and corner(j['fixed_xy_m']),'P02 has no XY writer; current211 corner required')
    return out,q
def native_review(ref_,expected_outcome,min_ns):
    r=artifact(ref_)
    require(r['recording_segment_id']=='R06' and r['logger_ready']==ref(LOGGER/'READY.json') and r['outcome']==expected_outcome and r['poststage_recovery_reviewed'] is True and r['unresolved_recording_gap'] is False and r['unresolved_native_execution'] is False and r['unresolved_recovery'] is False and r['range_events_reviewed'] is True and r['reason'] and r['sources'],'Current R06 native/recovery review missing')
    for source in r['sources']:artifact(source)
    receipt=artifact(r['native_receipt']);files=receipt['files']
    require(files and all(name.startswith('dl_goal30_FIVE1102_SESSION_02_R06') and name.endswith('.dat') and info['source_double_read_sha_equal'] is True and info['local_reread_sha_equal'] is True for name,info in files.items()),'Closed R06 native interval required')
    require(min_ns<=r['reviewed_through_monotonic_ns']<=r['monotonic_ns']<=time.monotonic_ns(),'Native review predates relevant stage or is future')
    return r
def validate(path,digest,stage='prepare'):
    require(stage in ('prepare','pulse','return'),'Unknown stage');require(local(path)==ADMISSION and sha(path)==digest,'Exact P02 admission/hash required');j=json.loads(Path(path).read_bytes())
    require(j['schema']=='R06-P02-induction-admission-v1' and j['case_id']==CASE and j['episode_id']==EPISODE and j['session_id']=='session_02' and j['action_id']=='P02' and j['recording_segment_id']=='R06','P02 identity differs')
    require(j['root_reviewed_one_induction'] is True and j['exclusive_root_writer'] is True and j['stop_requested'] is False and j['unresolved_previous_execution'] is False and j['manual_intervention_since_baseline'] is False and j['no_unplanned_intervention_since_baseline'] is True,'Ownership/interval unresolved')
    require(j['origin']=='task_usable_baseline_induction' and j['stage_intent']=='induction_attempt' and j['induction_effect']=='not_assessed' and j['repair_episode_active'] is False and j['induced_bad_state_confirmed'] is False and j['induced_cycle_complete'] is False and j['post_induction_full_required'] is True and j['post_induction_event']=='after_R06_P02_full' and j['no_automatic_repeat_or_escalation'] is True,'No predeclared dirtiness, repair or automatic chain')
    expected_counts={'max_pulses_total':6,'review_after_consecutive_no_improvement':2,'pulse_attempts_before':3,'pulse_ordinal':4,'consecutive_no_improvement_before':1,'documented_repair_Starts':1,'documented_induction_Starts':2,'documented_induction_moves':2,'max_preparations_this_case':1,'max_pulses_this_case':1,'max_returns_this_case':1}
    require(all(type(j[k]) is int and j[k]==v for k,v in expected_counts.items()) and j['pulse_count_reset'] is False,'Preserve exact history and one preparation/pulse/return budget')
    require(j['profile']=='local-au111' and j['required_safetip']=='off' and j['action']==ACTION and j['wire_encoding']=={'args_f32':WIRE,'duration_hex':struct.pack('>f',.020).hex(),'voltage_hex':struct.pack('>f',-5.7).hex()},'Only frozen original -5.7V20msHold recipe')
    require(j['history_evidence']=={str(p):h for p,h in HISTORY.items()} and j['functional_image_plan']=={'path':str(IMAGE_PLAN),'sha256':IMAGE_PLAN_SHA} and j['baseline_frame_event']==BASELINE_EVENT and j['reason'] and j['target_id'],'Frozen history/task/target reason missing')
    history_guard(stage,digest);out,q=baseline_proof(j)
    require(j['baseline_functional_review']==FUNCTIONAL_REVIEW,'Root211 functional source differs');review=artifact(FUNCTIONAL_REVIEW)
    require(review['baseline_outcome']==j['baseline_outcome'] and review['baseline_quality']==j['baseline_quality'] and review['native_SXM']==q['source'] and review['task_usable'] is True and review['task_scope'] and review['reason'] and review['limitations'] and review['trace_retrace_evidence'],'Actual211 remote task usability required, local mound remains a limitation')
    nr=native_review(j['history_and_native_review'],j['baseline_outcome'],out['end_event']['monotonic_ns'])
    require(out['monotonic_ns']<=j['monotonic_ns'] and nr['monotonic_ns']<=j['monotonic_ns']<=time.monotonic_ns(),'Root admission predates baseline/native review')
    require(j['legacy_counter_review']==COUNTER_REVIEW,'Prior pulse counter review changed');counter=artifact(COUNTER_REVIEW)
    require(counter['pulse_attempts_total']==3 and counter['through_pulse_ordinal']==3 and counter['pulse3_image_effect']=='unknown_manual_interruption' and counter['does_not_claim_pulse3_ineffective'] is True,'Keep historical pulse3 effect unknown')
    if stage=='return':
        rr={'path':str(RETURN_REVIEW),'sha256':RETURN_REVIEW_SHA};pulse_ref=ref(SESSION/'pulse_induction_P02/outcome.json');po=artifact(pulse_ref)
        require(po['status']=='single_pulse_knownend_30s_observed' and po['native_end_confirmed'] is True and po['writer_outcome_unknown'] is False,'Return requires known P02 completion/recovery')
        review=native_review(rr,pulse_ref,po['monotonic_ns']);require(review['allow_one_return'] is True,'Independent root return choice required')
    return j
