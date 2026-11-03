"""Local evidence only. Independent Home move and fine engagement after S01 failure/restoration."""
import hashlib,importlib.util,json,time
from pathlib import Path
C=Path(__file__).resolve().parents[1];N=C.parent;S=N/'session_02'
H=C/'R07_scan_induction/offhome_recovery_binding.py';H_SHA='5d795aa0044b91d3cc642f21271872bddab3f4161bcdc77b7136d3a03be03a9d'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(H)!=H_SHA:raise RuntimeError('Home restoration binding changed')
sp=importlib.util.spec_from_file_location('known_S01_Home_restoration',H);h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
require=h.require;local=h.local;artifact=h.artifact;ref=h.ref;load=h.load
RESTORER=C/'recover_R07_S01_OffHome_once.py';RESTORER_SHA='f8c16650b97f9296b5ed59dbde86e44d889474992ae70f71dcb611e46770bafd'
MOVE_SOURCE=C/'move_R07_after_S01_home02_once.py';MOVE_OUTPUT=C/'move_R07_after_S01_home02'
MOVE_CLAIM=N/'claims/session_02__R07_after_S01_home_move02.claim'
FINE_SOURCE=C/'engage_finez_R07_03_100pA_once.py';FINE_OUTPUT=C/'engage_R07_03'
FINE_CLAIM=N/'claims/session_02__R07_fine_on03.claim'
BASE=load(N/'read_001_initial/snapshot.json')['values'];TARGET=[-25e-9,-25e-9]

def completed_restoration():
    require(sha(RESTORER)==RESTORER_SHA,'Restoration source changed')
    original=load(h.INDUCTION/'manifest.json')['induction_admission'];failed=h.known_failed_induction(original)
    previous=failed['outcome']['monotonic_ns'];xy=failed['home']['FolMe.XYPosGet'];refs={};last_choice=None
    for stage in h.STAGES:
        f=S/h.EVENTS[stage];out=load(f/'outcome.json');mf=load(f/'manifest.json');after=load(f/'after.json')['values'];choice=artifact(mf['root_choice'])
        n,args,timeout=h.command(stage);claim=load(f/'configuration_0.claim');ack=load(f/'configuration_0_ack.json')
        require(out['status']=='Home_configuration_knownACK_exact_readback' and out['writer_outcome_unknown'] is False
                and out['acknowledged_writers']==[n] and out['sampled_post_stable_s']>=5.,'Home restoration stage incomplete')
        require(mf['source_sha256']==RESTORER_SHA and mf['original_S01_admission']==original
                and mf['recording_segment_id']=='R07' and mf['logger_source_sha256']==h.normal.LOGGER_SHA,'Restoration provenance differs')
        require(choice['stage']==stage and choice['source_sha256']==RESTORER_SHA and choice['allow_one_configuration'] is True
                and choice['failed_induction_outcome']==failed['refs']['outcome.json'],'Root restoration choice differs')
        require(claim['command']==ack['command']==n and claim['args']==args and ack['values']==[] and not ack.get('warning'),'Home setter ACK differs')
        require(previous<=choice['monotonic_ns']<claim['monotonic_ns']<out['monotonic_ns'],'Home recovery chronology differs')
        require(all(after[k]==v for k,v in h.expected_fields({},stage,True).items()),'Home exact restoration target differs');h.check_home(after,BASE)
        require(all(abs(a-b)<=2e-12 for a,b in zip(after['FolMe.XYPosGet'],xy)),'XY moved during configuration restoration')
        reservation=load(h.claim_path(stage));require(reservation['source_sha256']==RESTORER_SHA and reservation['root_choice']==mf['root_choice'],'Recovery reservation differs')
        refs[stage]={x:ref(f/x) for x in ('outcome.json','manifest.json','configuration_0.claim','configuration_0_ack.json','after.json')}
        refs[stage]['global_claim']=ref(h.claim_path(stage));previous=out['monotonic_ns'];last_choice=choice
    # Preserve the last root inventory and its one current-restoration reservation; allow only our prospective independent move.
    old={local(r['path']) for r in last_choice['prior_claim_inventory']}
    for r in last_choice['prior_claim_inventory']:artifact(r)
    allowed=old|{h.claim_path('current')};actual={p for d in ('claims','globalclaims') for p in (N/d).glob('*.claim')}
    require(actual==allowed or actual==allowed|{MOVE_CLAIM},'New competing writer or deleted history after restoration')
    return {'original_failed_induction':failed,'restoration':refs,'latest_end_monotonic_ns':previous,'source_xy_m':xy,
            'pulse_used_preserved':5,'pulse_maximum_preserved':6,'no_induction_budget_reset':True}

def completed_move():
    proof=completed_restoration();f=MOVE_OUTPUT;out=load(f/'outcome.json');mf=load(f/'manifest.json');after=load(f/'after.json')
    claim=load(f/'move.claim');ack=load(f/'move_ack.json');reservation=load(MOVE_CLAIM)
    require(out['status']=='home_target_verified_5s_stationary' and out['writer_outcome_unknown'] is False
            and out['asynchronous_move_ACK'] is True and out['stable5s_confirmed'] is True and out['stable_after_s']>=5.
            and out['stop_attempted'] is False,'Post-restoration Home move not known complete')
    require(mf['source_sha256']==sha(MOVE_SOURCE)==reservation['source_sha256']
            and claim['command']==ack['command']=='FolMe.XYPosSet' and claim['args']==TARGET+[0]
            and ack['values']==[] and not ack.get('warning'),'Post-restoration Home move source/ACK differs')
    require(proof['latest_end_monotonic_ns']<claim['monotonic_ns']<ack['monotonic_ns']<after['end']['monotonic_ns']<out['monotonic_ns'],'Home move order differs')
    v=after['values'];h.check_home(v,BASE)
    require(all(abs(x+25e-9)<=20e-12 for x in v['FolMe.XYPosGet']) and v['FolMe.XYPosGet']==out['actual_target_m'],'Home corner readback differs')
    require(all(v[k]==value for k,value in h.expected_fields({},'current',True).items()),'Original configuration no longer exact')
    proof.update(home_move={x:ref(f/x) for x in ('outcome.json','manifest.json','move.claim','move_ack.json','after.json','target_stable.json','logger_ready_bound.json')},
                 latest_end_monotonic_ns=out['monotonic_ns'],source_xy_m=v['FolMe.XYPosGet'])
    return proof

def choice(path,digest,kind,source_sha):
    p=local(path);require(sha(p)==digest,'Root recovery choice changed');d=load(p)
    require(d['schema']=='R07-after-S01-independent-reengagement-v1' and d['stage']==kind and d['allow_one_stage'] is True
            and d['exclusive_root_writer'] is True and d['no_unresolved_writer'] is True,'Independent root recovery choice required')
    source=MOVE_SOURCE if kind=='home_move02' else FINE_SOURCE
    require(kind in ('home_move02','fine03') and d['source_sha256']==source_sha==sha(source),'Selected source differs')
    proof=completed_restoration() if kind=='home_move02' else completed_move()
    require(d['restoration_outcomes']=={k:v['outcome.json'] for k,v in proof['restoration'].items()}
            and d['source_xy_m']==proof['source_xy_m'] and d['target_m']==TARGET,'Exact restored state/root target differs')
    if kind=='fine03':require(d['home_move_outcome']==proof['home_move']['outcome.json'],'Fine03 must follow actual independent Home move')
    artifact(d['native_review']);require(d['native_review_passed'] is True and proof['latest_end_monotonic_ns']<=d['monotonic_ns']<=time.monotonic_ns(),'Root native review must follow latest known end')
    return d,proof
