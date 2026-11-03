"""Pure local S02 continuation after the specific known pre-Start local rejection. No device access."""
import copy
import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time

C = Path(__file__).resolve().parents[1]
N = C.parent
S = N / 'session_02'
LOGGER = S / 'logger_07'
LOGGER_SHA = '1e127682ad19e005660ff2d2d82ef132d468d2e3e786fd6afa15cbb4650967d0'
BASE_SOURCE = C / 'scan_full50nm_fast_R07_after_S01_recovered_5nA_once.py'
BASE_SHA = '027d412a476808348b3fbe008ec668c16103dbb96654fa084f9e8077de3267e1'
BASE_DIR = S / 'after_R07_S01_recovered_full'
SEGMENT_PATH = C / 'segment07_observe_binding.py'
SEGMENT_SHA = '7f6aa581f719a09b9433b06f5ed3d57d38a8c60f2346a1c36775b7e21edd7dbe'
GUIDANCE = C / 'R07_scan_induction/user_guidance.json'
GUIDANCE_SHA = 'd7908618387509af4d0875919078343179a0875913c962d4618778d04cb26718'
SCAN_POLICY = C / 'R07_scan_induction/user_scan_current_guidance_5nA_v2.json'
SCAN_POLICY_SHA = 'b324208ce29f2c72817f84dc67aee3150caf303ca78b51fa5556399a29c79aab'
PRIOR_INDUCTION = S / 'induction_R07_S01_full'
PRIOR_INDUCTION_OUTCOME_SHA = '2fa06f2bfb0553ca4fb50f1f41903318a72527e105be482c25be7a81008b0a42'
FROZEN_RECOVERY_PROOF_SHA = '32e89087de187fa328abc4aa2cddbdd1b92583b1173ab9f8321a3d379623130a'
ORIGINAL_GAIN = [3.4123519981887895e-12, 4.29563588113524e-05, 7.943764757101235e-08]
INDUCTION_GAIN = [ORIGINAL_GAIN[0], 2*ORIGINAL_GAIN[1], ORIGINAL_GAIN[2]/2]
ORIGINAL_SPEED = [5.48245608911202e-08,5.48245608911202e-08,.9120000004768372,.9120000004768372,1,1.]
INDUCTION_SPEED = [2*ORIGINAL_SPEED[0],2*ORIGINAL_SPEED[1],ORIGINAL_SPEED[2]/2,ORIGINAL_SPEED[3]/2,1,1.]
I100 = 1.000000013351432e-10
I200 = 2.000000026702864e-10
EVENTS = {'prepare':'prepare_R07_S02','configure_gain':'configure_R07_S02_gain',
          'configure_speed':'configure_R07_S02_speed','induction':'induction_R07_S02_full02',
          'return':'return_R07_S02','restore_gain':'restore_R07_S02_gain',
          'restore_speed':'restore_R07_S02_speed','validation':'after_R07_S02_restored_full'}
ORDER = list(EVENTS)
SOURCE_NAMES = {'prepare':'setpoint_R07_scan_induction_S02_once.py',
                'return':'setpoint_R07_S02_after_rejected_scan_once.py',
                'configure_gain':'configure_R07_scan_induction_S02_once.py',
                'configure_speed':'configure_R07_scan_induction_S02_once.py',
                'restore_gain':'configure_R07_S02_after_rejected_scan_once.py',
                'restore_speed':'configure_R07_S02_after_rejected_scan_once.py',
                'induction':'scan_full50nm_fast_R07_induction_S02_full02_once.py',
                'validation':'scan_full50nm_fast_R07_after_S02_full02_restored_once.py'}
PULSE_CLAIMS = {2:'239de8300a9beb82d1cc6d8aacbdad73120c9a75bd82a4ebb3700ec8ed6487f6',
 3:'d1bba497813b3e496d6172805f71e3c62963ace37158ce9f2cec8e81ae6706ec',
 4:'cffc21a6480e6a16b05caafdd53f63de9e126b4dc75e147c8c38ebd88ea85167',
 5:'f0faa4842dd0bc71c54169e0bd5dc74e497f1befc0d99ee09b382f4ec33c5d23'}
ADMISSION_PATH = ADMISSION_SHA = REVIEW_PATH = REVIEW_SHA = None
ORIGINAL_ADMISSION = C / 'R07_scan_induction_S02/S02_root_admission.json'
ORIGINAL_ADMISSION_SHA = '8e12a499e74e8e10e7a8f4f02da7cb26812d09b25a6914949ea63bcbcd8d3f62'
REJECTED_DIR = S / 'induction_R07_S02_full'
REJECTED_SOURCE = C / 'scan_full50nm_fast_R07_induction_S02_once.py'
REJECTED_SOURCE_SHA = '3f5fd5e0c1ab792b089952d82f45eab4d19ab44f5de927197c8e1b1108332aee'
REJECTED_PINS = {'/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/induction_R07_S02_full/outcome.json': '3685f770960300f8cf9a0f358fd527f0eb92b170844b2b4a6bb2f6b42092772c', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/induction_R07_S02_full/manifest.json': 'a89671b6d4aab1c3ed33c7a8983754078d183aaf598305f7bd8e431f472f18b0', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/session_02/induction_R07_S02_full/attempt_binding.json': 'e9ac830cab8b6106bf01460e4d587777f9fdfb1d3214403e7c80375bf8d277e4', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/claims/session_02__induction_R07_S02_full.claim': 'f7426c050d1be55dcf88dc4eee905ebd1304d8bffdea5b06c6d990728eb16a94'}



def require(ok, text):
    if not ok: raise RuntimeError(text)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_bytes())
def stamp(): return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'monotonic_ns':time.monotonic_ns()}
def local(p):
    p=Path(p).absolute()
    require(p==p.resolve() and p.is_relative_to(N) and not any(x.lower() in ('volumes','win_users') for x in p.parts),'Exact batch-local path required')
    return p
def ref(p): return {'path':str(local(p)),'sha256':sha(p)}
def artifact(r, expected=None):
    p=local(r['path']);require(expected is None or p==expected,'Wrong evidence path')
    require(sha(p)==r['sha256'],'Changed evidence '+str(p));return load(p)


def segment():
    require(sha(SEGMENT_PATH)==SEGMENT_SHA,'R07 segment source changed')
    spec=importlib.util.spec_from_file_location('S02_R07_segment',SEGMENT_PATH)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def expected_fields(base, stage, after=False):
    require(stage in EVENTS,'Unknown stage')
    v=copy.deepcopy(base)
    index=ORDER.index(stage)+(1 if after else 0)
    # Boundaries of the explicitly ordered finite sequence.
    current=I100 if index==0 or index>=5 else I200
    gain=INDUCTION_GAIN if 2<=index<6 else ORIGINAL_GAIN
    speed=INDUCTION_SPEED if 3<=index<7 else ORIGINAL_SPEED
    v['ZCtrl.SetpntGet']=[current];v['ZCtrl.GainGet']=list(gain)
    v['Scan.SpeedGet']=list(speed);v['FolMe.SpeedGet']=[speed[0],0]
    return v


def refs_valid(value):
    """Verify captured immutable refs, never re-run an earlier mutable admission."""
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value:
            require(sha(local(value['path']))==value['sha256'],'Captured history reference changed')
        for child in value.values():refs_valid(child)
    elif isinstance(value,list):
        for child in value:refs_valid(child)


def completed_baseline(logger_sha):
    """Current complete post-S01 frame plus actual failed exposure/recovery history."""
    require(logger_sha==LOGGER_SHA and sha(BASE_SOURCE)==BASE_SHA,'Current recovered baseline source differs')
    sb=segment();manifest=load(BASE_DIR/'manifest.json');out=load(BASE_DIR/'outcome.json')
    recorded=load(BASE_DIR/'logger_ready_bound.json');ready=load(LOGGER/'READY.json')
    start=load(BASE_DIR/'scan_start.claim');ack=load(BASE_DIR/'scan_start_ack.json')
    sb.verify_logger_identity(recorded,logger_sha);sb.verify_logger_identity(ready,logger_sha)
    require(recorded==ready,'Current baseline belongs to another recording Start')
    require(manifest.get('session_id')=='session_02' and manifest.get('event_id')=='after_R07_S01_recovered_full'
            and manifest.get('source_sha256')==BASE_SHA
            and all(manifest.get(k)==v for k,v in sb.consumer_metadata(logger_sha).items()),'Current baseline identity differs')
    require(out.get('status')=='completed' and out.get('completed_frame_confirmed') is True and len(out.get('frames',[]))==6
            and out.get('execution_unknown',False) is False,'Current recovered full baseline not completed')
    require(start['command']==ack['command']=='Scan.Action' and start['args']==[0,0]
            and ack['values']==[] and not ack.get('warning') and start['source_sha256']==BASE_SHA,'Current baseline Start/ACK differs')
    proof_path=BASE_DIR/'fresh_recording_evidence.json'
    require(sha(proof_path)==FROZEN_RECOVERY_PROOF_SHA,'Immutable actual S01 recovery proof changed')
    proof=load(proof_path);refs_valid(proof)
    recovery=proof['S01_independent_recovery_prerequisites']
    require(recovery['stage']=='after_R07_S01_recovered_full' and recovery['prerequisites_known_ended'] is True
            and recovery['exposure_kind']=='incomplete_S01_then_independent_Home_configuration_move_fine_recovery'
            and recovery['strict_cycle_increment']==0,'Wrong prior independent recovery chain')
    require(proof['native_start_identity']==ready['native_start_identity']
            and start['monotonic_ns']>=recovery['latest_end_monotonic_ns']
            and out['end_event']['monotonic_ns']>=start['monotonic_ns'],'Current baseline timing differs')
    require(recovery['interrupted_exposure']['outcome.json']==ref(PRIOR_INDUCTION/'outcome.json')
            and sha(PRIOR_INDUCTION/'outcome.json')==PRIOR_INDUCTION_OUTCOME_SHA,'Actual prior S01 failure changed')
    prior=load(PRIOR_INDUCTION/'outcome.json')
    require(prior['status']=='incomplete' and prior['completed_frame_confirmed'] is False
            and prior['execution_unknown'] is False and prior['start_acknowledged'] is True
            and prior['stop_acknowledged'] is True and prior['withdraw_acknowledged'] is True
            and prior['withdraw_Off1_home_confirmed'] is True,'Prior exposure is unresolved or reclassified')
    # This is the original captured 214 history, not its old current-inventory guard.
    earlier_proof=artifact(recovery['baseline']['fresh_recording_evidence.json'])
    frozen=artifact(earlier_proof['frozen_history']);refs_valid(frozen)
    require(frozen['historical_counts']['shared_pulses']==5 and frozen['recording_gap_preserved'] is True,
            'Earlier history/count/gap changed')
    for p,digest in frozen['source_pins'].items():require(sha(local(p))==digest,'Earlier action source changed')
    return {name:ref(BASE_DIR/name) for name in ('manifest.json','outcome.json','logger_ready_bound.json',
                'scan_start.claim','scan_start_ack.json','fresh_recording_evidence.json')}


def history():
    actual=set((N/'globalclaims').glob('continuing_20261101_1939__pulse_*.claim'))
    expected={N/'globalclaims'/f'continuing_20261101_1939__pulse_{k:02d}.claim':v for k,v in PULSE_CLAIMS.items()}
    require(actual==set(expected),'Pulse counter/history changed')
    for p,digest in expected.items():require(sha(p)==digest,'Pulse claim changed')
    return {str(k):ref(p) for k,p in zip(sorted(PULSE_CLAIMS),sorted(expected))}


def known_prestart_rejection():
    """This exact failed local admission had no TCP events or Start claim."""
    require(sha(ORIGINAL_ADMISSION)==ORIGINAL_ADMISSION_SHA and sha(REJECTED_SOURCE)==REJECTED_SOURCE_SHA,
            'Original admission or rejected source changed')
    for path,digest in REJECTED_PINS.items():require(sha(local(path))==digest,'Rejected-attempt immutable evidence changed')
    require({p.name for p in REJECTED_DIR.iterdir()}=={'outcome.json','manifest.json','attempt_binding.json','wire'}
            and (REJECTED_DIR/'wire').is_dir() and not any((REJECTED_DIR/'wire').iterdir()),
            'First attempt contains unexpected transport/action evidence')
    out=load(REJECTED_DIR/'outcome.json');manifest=load(REJECTED_DIR/'manifest.json')
    require(out['status']=='rejected_before_start' and out['error']=='Missing or unordered R07 READY/start reservation'
            and all(out[k] is False for k in ('start_attempted','start_acknowledged','owned_running_observed','end_event_confirmed','execution_unknown','completed_frame_confirmed')),
            'First attempt is sent, unknown, or not this pre-Start path rejection')
    reservation=artifact(load(REJECTED_DIR/'attempt_binding.json'))
    require(reservation['event_id']==manifest['event_id']=='induction_R07_S02_full'
            and reservation['source_sha256']==manifest['source_sha256']==REJECTED_SOURCE_SHA
            and manifest['induction_admission']==ref(ORIGINAL_ADMISSION),'Rejected event/source/admission differs')
    return {'outcome':ref(REJECTED_DIR/'outcome.json'),'manifest':ref(REJECTED_DIR/'manifest.json'),
            'attempt_binding':ref(REJECTED_DIR/'attempt_binding.json'),'reservation':load(REJECTED_DIR/'attempt_binding.json'),
            'known_no_Scan_Start_sent':True,'known_no_TCP_events_or_wire_files':True,
            'local_reservation_consumed':True,'physical_scan_exposures_consumed':0,'monotonic_ns':out['monotonic_ns']}


def admission(path,digest):
    p=local(path);require(sha(p)==digest,'Admission hash mismatch');d=load(p)
    require(d['schema']=='local-au111-R07-scan-induction-S02-full02-v1' and d['session_id']=='session_02'
            and d['recording_segment_id']=='R07' and d['action_id']=='S02','Wrong induction identity')
    require(d['allow_one_finite_induction_frame'] is True and d['baseline_task_usable'] is True
            and d['exclusive_root_writer'] is True,'Root finite induction/baseline choice missing')
    rejected=known_prestart_rejection()
    require(d['original_admission']==ref(ORIGINAL_ADMISSION) and d['known_prestart_rejection']==rejected
            and d['local_scan_reservation_budget']=={'already_consumed':1,'new_attempts':1,'maximum_total':2,'reset':False}
            and d['S02_physical_scan_exposures_before']==0,'Known rejection or non-replay reservation budget differs')
    original=load(ORIGINAL_ADMISSION)
    for key in ('session_id','action_id','candidate','baseline','baseline_quality','baseline_manual_review','pulse_budget','scan_induction_budget','prior_scan_induction','full_repair_attempts_before','strict_cycles_before','fixed_xy_m','user_guidance','scan_current_policy','logger_source_sha256'):
        require(d[key]==original[key],'Continuation changes original physical scope/history '+key)
    for stage in ORDER[:3]:require(d['sources'][stage]==original['sources'][stage],'Completed setup source changed')
    require(d['pulse_budget']=={'used':5,'maximum':6,'reset':False} and d['induction_frame_budget']==1,
            'No reset or unbounded scan-induction budget')
    require(d['prior_scan_induction']=={'outcome':ref(PRIOR_INDUCTION/'outcome.json'),'attempts_consumed':1,'completed_frames':0,'replayed':False}
            and d['scan_induction_budget']=={'prior_attempts':1,'new_attempts':1,'maximum_total':2,'reset':False}
            and d['full_repair_attempts_before']==2 and d['strict_cycles_before']==0,'Prior S01/counts not preserved')
    require(d['scan_current_policy']=={'path':str(SCAN_POLICY),'sha256':SCAN_POLICY_SHA}
            and sha(SCAN_POLICY)==SCAN_POLICY_SHA,'Wrong scan-only runtime guidance')
    require(d['user_guidance']=={'path':str(GUIDANCE),'sha256':GUIDANCE_SHA} and sha(GUIDANCE)==GUIDANCE_SHA,'Wrong user guidance')
    require(d['baseline_source']=={'path':str(BASE_SOURCE),'sha256':BASE_SHA} and sha(BASE_SOURCE)==BASE_SHA,'Baseline source changed')
    require(d['logger_source_sha256']==LOGGER_SHA,'Wrong R07 logger source')
    require(d['candidate']=={'current_A':I200,'gain':INDUCTION_GAIN,'speed':INDUCTION_SPEED,'SafeTip':0,
                            'frame_m':[50e-9,50e-9],'pixels':[240,240],'Bias_V':-1.},'Candidate differs')
    base=completed_baseline(LOGGER_SHA)
    require(d['baseline']==base,'Baseline refs differ from actual R07 full frame')
    q=artifact(d['baseline_quality'],BASE_DIR/'analysis/quality_report.json')['integrity']
    require(q['completed_outcome'] is True and q['native_TCP_wire_bitmatch'] is True
            and q['matched_float32_values']==345600,'Baseline matrix incomplete')
    manual=artifact(d['baseline_manual_review'])
    require(manual.get('full_task_usable') is True
            and manual.get('baseline_outcome')==ref(BASE_DIR/'outcome.json')
            and manual.get('baseline_quality')==d['baseline_quality'],'Actual complete baseline functional review missing')
    require(type(d['fixed_xy_m']) is list and len(d['fixed_xy_m'])==2
            and all(type(x) in (int,float) and math.isfinite(x) for x in d['fixed_xy_m']),'Fixed finite starting XY required')
    history()
    return d


def stage_source(d,stage):
    r=d['sources'][stage];p=C/SOURCE_NAMES[stage]
    require(r['path']==str(p) and sha(p)==r['sha256'],'Wrong or changed stage source')
    return r


def stage_claim(stage):
    folder='claims' if stage in ('induction','validation') else 'globalclaims'
    return N/folder/('session_02__'+EVENTS[stage]+'.claim')


def claim_inventory(d,stage):
    """Freeze earlier reservations, permit only this finite sequence's claims."""
    frozen=d['prior_claim_inventory']
    require(type(frozen) is list and len({r['path'] for r in frozen})==len(frozen),'Invalid prior claim inventory')
    paths={local(r['path']) for r in frozen}
    require(all(p.parent in (N/'claims',N/'globalclaims') and p.suffix=='.claim' for p in paths),'Claim inventory scope differs')
    require(not any(stage_claim(k) in paths for k in ORDER[3:]),'Future continuation claim pre-exists admission')
    require(all(stage_claim(k) in paths for k in ORDER[:3]),'Completed setup claims must remain frozen in prior inventory')
    for r in frozen:artifact(r)
    actual={p for folder in ('claims','globalclaims') for p in (N/folder).glob('*.claim')}
    allowed={stage_claim(k) for k in ORDER[:ORDER.index(stage)+1]}
    require(paths.issubset(actual) and actual.issubset(paths|allowed),'Unexpected new or removed writer reservation')
    for k in ORDER[:ORDER.index(stage)+1]:
        p=stage_claim(k)
        if p not in actual:continue
        record=load(p)
        require(record['event_id']==EVENTS[k] and record['source_sha256']==stage_source(d,k)['sha256']
                and record['output']==str(S/EVENTS[k]),'S02 reservation differs')
    return {'prior_claim_inventory':frozen,'finite_stage_claims':{k:ref(stage_claim(k))
            for k in ORDER[:ORDER.index(stage)+1] if stage_claim(k).exists()}}


def completed_stage(d,stage):
    folder=S/EVENTS[stage];out=load(folder/'outcome.json');manifest=load(folder/'manifest.json')
    src=stage_source(d,stage)
    require(manifest['source_sha256']==src['sha256'] and manifest['recording_segment_id']=='R07'
            and manifest['logger_source_sha256']==LOGGER_SHA,'Predecessor source/recording differs')
    expected_admission=ref(ORIGINAL_ADMISSION) if stage in ORDER[:3] else {'path':str(ADMISSION_PATH),'sha256':ADMISSION_SHA}
    require(manifest.get('induction_admission')==expected_admission,'Predecessor admission differs')
    require(out.get('execution_unknown',False) is False and out.get('writer_outcome_unknown',False) is False,'Unknown predecessor write')
    if stage in ('prepare','return'):
        require(out['status']=='completed' and out['mode']==stage and out['attempted_sets']==out['acknowledged_sets']==4,'Four-step predecessor not complete')
        require(out['final_target_A']==(I200 if stage=='prepare' else I100),'Wrong final setpoint')
        files=['outcome.json','manifest.json','after.json','final30_statistics.json','final30_samples.json']
        targets=[I100,1.2499999646475857e-10,1.5624999905039516e-10,1.953125022824409e-10,I200]
        if stage=='return':targets.reverse()
        for k in range(1,5):
            claim=load(folder/f'step_{k:02d}.claim')
            require(claim['command']=='ZCtrl.SetpntSet' and claim['args']==[targets[k]]
                    and claim['previous_target_A']==targets[k-1] and claim['index']==k
                    and claim['mode']==stage,'Actual setpoint sequence differs')
            ack=load(folder/f'step_{k:02d}_ack.json');require(ack['command']=='ZCtrl.SetpntSet' and ack['values']==[] and not ack.get('warning'),'Setpoint ACK missing')
            files.extend([f'step_{k:02d}.claim',f'step_{k:02d}_ack.json'])
        require(set(folder.glob('step_*.claim'))=={folder/f'step_{k:02d}.claim' for k in range(1,5)},'Unexpected setpoint claim')
        rows=load(folder/'final30_samples.json');stats=load(folder/'final30_statistics.json')
        require(len(rows)>1 and rows[-1]['t']-rows[0]['t']>=30.
                and stats['last5s_all_sampled_current_in_band'] is True and stats['Z_gates_passed'] is True,
                'Original post30 completion missing')
    elif stage in ('induction','validation'):
        require(out['status']=='completed' and out['completed_frame_confirmed'] is True and len(out['frames'])==6,'Normal full induction/validation not complete; independent recovery needed')
        claim=load(folder/'scan_start.claim');ack=load(folder/'scan_start_ack.json')
        require(claim['command']=='Scan.Action' and claim['args']==[0,0]
                and ack['command']=='Scan.Action' and ack['values']==[] and not ack.get('warning'),'Normal scan Start/ACK missing')
        files=['outcome.json','manifest.json','scan_start.claim','scan_start_ack.json','after_frames.json']
    else:
        command='ZCtrl.GainSet' if stage.endswith('gain') else 'Scan.SpeedSet'
        require(out['status']=='configured_and_exact_readback_verified' and out['writer_outcome_unknown'] is False
                and out['acknowledged_writers']==[command],'Configuration predecessor not complete')
        ack=load(folder/'configuration_0_ack.json');require(ack['command']==command and ack['values']==[] and not ack.get('warning'),'Configuration ACK missing')
        claim=load(folder/'configuration_0.claim')
        require(set(folder.glob('configuration_*.claim'))=={folder/'configuration_0.claim'},'Unexpected configuration claim')
        target=expected_fields({},stage,after=True)
        args=target['ZCtrl.GainGet'] if stage.endswith('gain') else target['Scan.SpeedGet'][:4]+[2,target['Scan.SpeedGet'][5]]
        require(claim['command']==command and claim['args']==args,'Actual configuration command differs')
        files=['outcome.json','manifest.json','configuration_0.claim','configuration_0_ack.json','before.json','after.json']
    if stage not in ('induction','validation'):
        after=load(folder/'after.json')['values']
        require(all(after[k]==v for k,v in expected_fields({},stage,after=True).items()),'Predecessor full target readback differs')
        require(after['ZCtrl.OnOffGet']==[1] and after['ZCtrl.StatusGet']==[2] and after['Scan.StatusGet']==[0],
                'Predecessor was not idle On2 after known action')
    return {'event':EVENTS[stage],'outcome':out,'source':src,'refs':{f:ref(folder/f) for f in files}}


def validate_stage(path,digest,stage,review_path,review_digest):
    global ADMISSION_PATH,ADMISSION_SHA,REVIEW_PATH,REVIEW_SHA
    ADMISSION_PATH,ADMISSION_SHA=local(path),digest
    REVIEW_PATH,REVIEW_SHA=local(review_path),review_digest
    require(stage in ORDER[3:],'Continuation cannot repeat completed preparation/configuration')
    d=admission(path,digest);stage_source(d,stage)
    inventory=claim_inventory(d,stage)
    review=artifact({'path':str(REVIEW_PATH),'sha256':review_digest})
    require(review['schema']=='local-au111-R07-S02-full02-stage-review-v1' and review['stage']==stage
            and review['allow_stage'] is True and review['no_unresolved_writer'] is True,'Stage review does not choose this one action')
    require(review['induction_admission']=={'path':str(ADMISSION_PATH),'sha256':digest},'Review admission mismatch')
    artifact(review['native_review']);require(review['native_review_passed'] is True,'Root native recovery review missing')
    prior={}
    previous_end=load(BASE_DIR/'outcome.json')['monotonic_ns']
    for previous in ORDER[:ORDER.index(stage)]:
        prior[previous]=completed_stage(d,previous)
        require(prior[previous]['outcome']['monotonic_ns']>=previous_end,'Stage chronology differs')
        previous_end=prior[previous]['outcome']['monotonic_ns']
    latest=max([load(BASE_DIR/'outcome.json')['monotonic_ns'],known_prestart_rejection()['monotonic_ns']]+[x['outcome']['monotonic_ns'] for x in prior.values()])
    require(type(review['monotonic_ns']) is int and latest<=review['monotonic_ns']<=time.monotonic_ns(),'Review precedes latest known stage end')
    expected_prior={k:x['refs']['outcome.json'] for k,x in prior.items()}
    require(review['predecessor_outcomes']==expected_prior,'Root review does not bind exact prior outcomes')
    return {'stage':EVENTS[stage],'prerequisites_known_ended':True,'admission':d,'admission_ref':ref(ADMISSION_PATH),'root_stage_review':ref(REVIEW_PATH),
            'baseline':d['baseline'],'baseline_quality':d['baseline_quality'],'baseline_manual_review':d['baseline_manual_review'],
            'known_prior_prestart_rejection':known_prestart_rejection(),'original_admission':ref(ORIGINAL_ADMISSION),
            'prior_stages':prior,'claim_inventory':inventory,'latest_end_monotonic_ns':latest,'stage_review_monotonic_ns':review['monotonic_ns']}


def scanner_evidence(stage,logger,logger_sha,admission_path,admission_sha,review_path,review_sha):
    require(Path(logger)==LOGGER and logger_sha==LOGGER_SHA,'Wrong scan recorder')
    key={EVENTS['induction']:'induction',EVENTS['validation']:'validation'}.get(stage)
    require(key is not None,'Only these S02 scan roles')
    return validate_stage(admission_path,admission_sha,key,review_path,review_sha)


def claim_path(stage):return N/'globalclaims'/('session_02__'+EVENTS[stage]+'.claim')
def reserve_stage(session,action,stage,output,source_sha,fresh_sha):
    require(session=='session_02' and action=='S02' and Path(output)==S/EVENTS[stage],'Stage identity mismatch')
    p=local(claim_path(stage));p.parent.mkdir(exist_ok=True)
    record={**stamp(),'session_id':session,'action_id':action,'recording_segment_id':'R07','stage':stage,
            'event_id':EVENTS[stage],'output':str(output),'source_sha256':source_sha,'fresh_snapshot_sha256':fresh_sha,
            'induction_admission':{'path':str(ADMISSION_PATH),'sha256':ADMISSION_SHA},'root_stage_review':{'path':str(REVIEW_PATH),'sha256':REVIEW_SHA},
            'one_attempt_no_release':True,'pulse_budget_not_reset':True}
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write((json.dumps(record,indent=2)+'\n').encode());stream.flush();os.fsync(stream.fileno())
    fd=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return ref(p)


def paths(session,action,stage,output,logger,fresh,source,source_sha,logger_sha):
    require(session=='session_02' and action=='S02' and local(output)==S/EVENTS[stage] and not Path(output).exists(),'Exact new S02 output required')
    require(local(logger)==LOGGER and logger_sha==LOGGER_SHA and sha(source)==source_sha,'Source/logger differs')
    require(not claim_path(stage).exists(),'Stage already claimed; no replay')
    require(local(fresh).is_file(),'Fresh readback required')
    d=admission(ADMISSION_PATH,ADMISSION_SHA);require(stage_source(d,stage)['sha256']==source_sha,'Stage source not chosen')
    fresh_values=load(fresh)['values']
    require(len(fresh_values['FolMe.XYPosGet'])==2 and all(math.isfinite(x) and abs(x-y)<=2e-12
            for x,y in zip(fresh_values['FolMe.XYPosGet'],d['fixed_xy_m'])),'Fresh fixed XY differs')
