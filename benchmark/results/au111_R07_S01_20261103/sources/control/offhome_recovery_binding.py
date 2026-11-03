"""Pure local gate for a separately selected S01 known-Stop/Withdraw Home recovery write."""
import copy,hashlib,importlib.util,json,math,os,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;C=HERE.parent;N=C.parent;S=N/'session_02'
BIND=C/'R07_scan_induction/stage_binding.py';BIND_SHA='99c52ed7bc9d235db39d41af01635a5cbc922b3d16b22cc605ac5e3b4073fac8'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(BIND)!=BIND_SHA:raise RuntimeError('Frozen normal S01 binding changed')
sp=importlib.util.spec_from_file_location('S01_Home_original_binding',BIND);normal=importlib.util.module_from_spec(sp);sp.loader.exec_module(normal)
require=normal.require;local=normal.local;load=normal.load;ref=normal.ref;artifact=normal.artifact
STAGES=['gain','speed','current'];EVENTS={k:'recovery_R07_S01_H01_'+k for k in STAGES}
DRIVER=C/'recover_R07_S01_OffHome_once.py'
INDUCTION=S/normal.EVENTS['induction']
ROOT_PATH=ROOT_SHA=None

def expected_fields(base,stage,after=False):
    require(stage in STAGES,'Only exact finite Home restoration stages')
    boundary=STAGES.index(stage)+int(after);v=copy.deepcopy(base)
    v['ZCtrl.SetpntGet']=[normal.I100 if boundary>=3 else normal.I200]
    v['ZCtrl.GainGet']=list(normal.ORIGINAL_GAIN if boundary>=1 else normal.INDUCTION_GAIN)
    v['Scan.SpeedGet']=list(normal.ORIGINAL_SPEED if boundary>=2 else normal.INDUCTION_SPEED)
    v['FolMe.SpeedGet']=[v['Scan.SpeedGet'][0],0]
    return v

def command(stage):
    v=expected_fields({},stage,True)
    if stage=='gain':return 'ZCtrl.GainSet',v['ZCtrl.GainGet'],.7
    if stage=='speed':return 'Scan.SpeedSet',v['Scan.SpeedGet'][:4]+[2,v['Scan.SpeedGet'][5]],.7
    return 'ZCtrl.SetpntSet',v['ZCtrl.SetpntGet'],.5

def claim_path(stage):return N/'globalclaims'/('session_02__'+EVENTS[stage]+'.claim')
def check_home(v,expected):
    require(v['ZCtrl.OnOffGet']==[0] and v['ZCtrl.StatusGet']==[1],'Need Off1')
    require(all(v[k]==[0] for k in ('Scan.StatusGet','AutoApproach.OnOffGet','BiasSpectr.StatusGet','ZSpectr.StatusGet','FolMe.PSOnOffGet')),'Other module active')
    require(math.isfinite(v['Current.Get'][0]) and abs(v['Current.Get'][0])<10e-12,'Need Home low current')
    require(math.isfinite(v['ZCtrl.ZPosGet'][0]) and abs(v['ZCtrl.ZPosGet'][0]-expected['ZCtrl.HomePropsGet'][1])<1e-12,'Need absolute Home')
    require(len(v['FolMe.XYPosGet'])==2 and all(math.isfinite(x) for x in v['FolMe.XYPosGet']),'Finite XY pair required')

def known_failed_induction(original):
    normal.ADMISSION_PATH=local(original['path']);normal.ADMISSION_SHA=original['sha256']
    d=normal.admission(normal.ADMISSION_PATH,normal.ADMISSION_SHA)
    prior={k:normal.completed_stage(d,k) for k in ('prepare','configure_gain','configure_speed')}
    out=load(INDUCTION/'outcome.json');mf=load(INDUCTION/'manifest.json')
    require(out['status']=='incomplete' and out['completed_frame_confirmed'] is False and out['execution_unknown'] is False,'Only original known failed finite induction')
    require(all(out.get(k) is True for k in ('start_acknowledged','owned_running_observed','stop_acknowledged','withdraw_acknowledged','withdraw_Off1_home_confirmed')),'Induction Stop/Withdraw not known complete')
    require(mf['source_sha256']==normal.stage_source(d,'induction')['sha256'] and mf['induction_admission']==original
            and mf['recording_segment_id']=='R07' and mf['logger_source_sha256']==normal.LOGGER_SHA,'Wrong failed induction source/admission')
    names=['outcome.json','manifest.json','withdraw_confirmed.json','logger_ready_bound.json'];times=[]
    for label,n,args in [('scan_start','Scan.Action',[0,0]),('failed_owned_scan_stop','Scan.Action',[1,0]),('failure_withdraw','ZCtrl.Withdraw',[1,2000])]:
        c=load(INDUCTION/(label+'.claim'));ack=load(INDUCTION/(label+'_ack.json'))
        require(c['command']==ack['command']==n and c['args']==args and c['source_sha256']==mf['source_sha256']
                and ack['values']==[] and not ack.get('warning'),'Unknown failed induction command/ACK')
        names.extend([label+'.claim',label+'_ack.json']);times.append(c['monotonic_ns'])
    require(prior['configure_speed']['outcome']['monotonic_ns']<times[0]<times[1]<times[2]<out['monotonic_ns'],'Induction cleanup chronology differs')
    h=load(INDUCTION/'withdraw_confirmed.json');require(h['sampled_duration_s']>=3.,'Home not sampled for original3s')
    require(load(INDUCTION/'logger_ready_bound.json')==load(normal.LOGGER/'READY.json'),'Another native recorder instance')
    return {'refs':{x:ref(INDUCTION/x) for x in names},'known_prior_stages':prior,'outcome':out,'home':h['values']}

def admission(path,digest,stage,base,source_sha):
    global ROOT_PATH,ROOT_SHA
    ROOT_PATH,ROOT_SHA=local(path),digest;require(sha(ROOT_PATH)==digest,'Home recovery choice SHA differs');d=load(ROOT_PATH)
    require(d['schema']=='R07-S01-OffHome-single-recovery-v1' and d['stage']==stage and d['allow_one_configuration'] is True
            and d['exclusive_root_writer'] is True and d['no_unresolved_writer'] is True,'Explicit independent Home recovery choice required')
    require(d['source_sha256']==source_sha==sha(DRIVER) and d['no_more_induction_attempts'] is True
            and d['pulse_budget']=={'used':5,'maximum':6,'reset':False},'Exact source and preserved finite budgets required')
    require(d['expected_before']==expected_fields({},stage) and d['expected_after']==expected_fields({},stage,True)
            and d['only_write']==list(command(stage)[:2]),'Only exact original restoration permitted')
    proof=known_failed_induction(d['original_S01_admission'])
    require(d['failed_induction_outcome']==proof['refs']['outcome.json'],'Wrong original failure')
    latest=proof['outcome']['monotonic_ns'];fixed=proof['home']['FolMe.XYPosGet'];previous={}
    check_home(proof['home'],base)
    for k in STAGES[:STAGES.index(stage)]:
        folder=S/EVENTS[k];out=load(folder/'outcome.json');mf=load(folder/'manifest.json');after=load(folder/'after.json')['values']
        require(out['status']=='Home_configuration_knownACK_exact_readback' and out['writer_outcome_unknown'] is False
                and out['acknowledged_writers']==[command(k)[0]] and out['sampled_post_stable_s']>=5.,'Prior Home stage not complete')
        require(mf['source_sha256']==source_sha and mf['original_S01_admission']==d['original_S01_admission'],'Prior Home stage provenance differs')
        c=load(folder/'configuration_0.claim');a=load(folder/'configuration_0_ack.json');n,args,timeout=command(k)
        require(c['command']==a['command']==n and c['args']==args and a['values']==[] and not a.get('warning'),'Prior Home setter ACK differs')
        require(all(after[x]==y for x,y in expected_fields({},k,True).items()),'Prior Home target differs');check_home(after,base)
        require(out['monotonic_ns']>latest,'Home recovery ordering differs');latest=out['monotonic_ns'];fixed=after['FolMe.XYPosGet'];previous[k]=ref(folder/'outcome.json')
    require(d['prior_home_outcomes']==previous and d['fixed_xy_m']==fixed,'Exact preceding Home state required')
    artifact(d['native_review']);require(d['native_review_passed'] is True and latest<=d['monotonic_ns']<=time.monotonic_ns(),'Root native review must follow known completion')
    rows=d['prior_claim_inventory'];old={local(r['path']) for r in rows}
    require(len(old)==len(rows) and all(p.parent in (N/'claims',N/'globalclaims') and p.suffix=='.claim' for p in old),'Invalid frozen claim inventory')
    require(claim_path(stage) not in old,'Recovery stage already reserved')
    for r in rows:artifact(r)
    actual={p for folder in ('claims','globalclaims') for p in (N/folder).glob('*.claim')}
    require(actual==old,'New or removed writer claim since root review')
    require(not (S/EVENTS[stage]).exists(),'Stage output already exists; no replay')
    return {'root_choice':ref(ROOT_PATH),'choice':d,'original_failed_induction':proof,'latest_known_end_monotonic_ns':latest}

def reserve(stage,source_sha,root_ref):
    record={**normal.stamp(),'event_id':EVENTS[stage],'stage':stage,'source_sha256':source_sha,'root_choice':root_ref,
            'output':str(S/EVENTS[stage]),'one_attempt_no_release':True,'pulse_and_induction_budgets_not_reset':True}
    p=claim_path(stage);fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write((json.dumps(record,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno())
    fd=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return ref(p)
