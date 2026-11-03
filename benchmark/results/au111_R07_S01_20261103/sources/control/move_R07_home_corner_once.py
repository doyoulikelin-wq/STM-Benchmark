"""One independent Home XY move. Plan by default. No On, speed setter, scan or coarse command."""
import argparse,copy,hashlib,importlib.util,json,math,os,signal,struct,sys,time,types
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
SOURCE=HERE/'scan_full50nm_fast_R07_baseline_once.py'
SOURCE_SHA='afc4e361af8bbb9d6d6a59baad2ef5ade4d1151bee125047fca6545bdd9cdc95'
ORIGINAL_MOVE=HERE/'move_R06_induction_I03_once.py'
ORIGINAL_MOVE_SHA='6ce4fb1c56fa27281e9fb57dcb8c26002ebafd67c91fe09c2f38ada503cf436d'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(name,path,digest):
    if sha(path)!=digest:raise RuntimeError('Pinned source changed: '+str(path))
    spec=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
m=load('R07_home_move_envelope',SOURCE,SOURCE_SHA);b=m.b
REF=HERE/'read_085_R07_after_fine01/snapshot.json'
REF_SHA='bc4f45ba1f81cbf9dc05295e24646a40a5538f65b2e897262d984ea51ce05629'
FINE=HERE/'engage_R07_01'
FINE_SOURCE=HERE/'engage_finez_R07_100pA_once.py'
FINE_SOURCE_SHA='5586d4c64d9bbb6a188dc5f966c7b100371aa540126a0cf0f1961299ef2e4477'
RECOVERY_PINS={'/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/engage_R07_01/outcome.json': '840cc3888bb1a5b06811d2b2fe8bfac13c710e41321df4a72131cbe0368449c3', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/engage_R07_01/manifest.json': 'd547f824d564ab72cda5cef8ec83a3cffe21741657b96d1a6d8aa063a709eaf3', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/engage_R07_01/feedback_on.claim': '4b7386fb02e9105c50852dbb1ed0ee3b55092ffb125bd35814a9b9dd0bb48c0d', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/engage_R07_01/feedback_on_ack.json': 'ace1806df70f2af8791bf19a23eeb09e0aaa1d98f636e9a6ca0be1c431e032f0', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/engage_R07_01/failure_withdraw.claim': '05ff679758f6c97e59eea8b923e1c4080415332d455e6a71cb4fed479ddd2a05', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/engage_R07_01/failure_withdraw_ack.json': '0d277acd56ffe8c1179d91feb2de9ec981eeaf027b9cdc6759dc7a10a20955af', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/engage_R07_01/logger_instance_bound.json': '9e05585e65470b698a11e4b602a1d6fa87f740674e0ea6dabecdc2291f5aaee6', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/claims/session_02__R07_fine_on01.claim': '87cbe97631d9001c016160860f597fe57d76789d5987e3de5c125af14bd0b64a', '/Users/maxlin/Desktop/Nanonis/work/stm_tip_five_sessions_20261102/continuation_slow_20261102/read_085_R07_after_fine01/snapshot.json': 'bc4f45ba1f81cbf9dc05295e24646a40a5538f65b2e897262d984ea51ce05629'}
HISTORY=HERE/'R07_fine_recovery/prior_home_move_claim_inventory.json'
HISTORY_SHA='7beed326d47082f2bd3cd951d87155360a95e16864aa90dca06a840519fc1341'
LOGGER=HERE.parent/'session_02/logger_07'
LOGGER_SHA='1e127682ad19e005660ff2d2d82ef132d468d2e3e786fd6afa15cbb4650967d0'
OUTPUT=HERE/'move_R07_home01'
MOVE_CLAIM=HERE.parent/'claims/session_02__R07_home_move01.claim'
TARGET=[-25e-9,-25e-9]
MAX_DISTANCE=50e-9
TARGET_TOL,STILL_TOL=20e-12,2e-12
PRIVATE_COMMANDS=copy.deepcopy(b.p.COMMANDS)
for name,inputs in [('FolMe.XYPosSet',['d','d','I']),('FolMe.Stop',[])]:
    schema={'inputs':inputs,'outputs':[],'access':'write'}
    if name not in PRIVATE_COMMANDS:PRIVATE_COMMANDS[name]=schema
    b.require(all(PRIVATE_COMMANDS[name][k]==v for k,v in schema.items()),'Move writer codec differs')
_private_globals=dict(b.p.NanonisClient.call.__globals__);_private_globals['COMMANDS']=PRIVATE_COMMANDS
PRIVATE_CALL=types.FunctionType(b.p.NanonisClient.call.__code__,_private_globals,b.p.NanonisClient.call.__name__,b.p.NanonisClient.call.__defaults__,b.p.NanonisClient.call.__closure__)

def in_domain(xy):return len(xy)==2 and all(b.finite(x) and -25e-9-TARGET_TOL<=x<=25e-9+TARGET_TOL for x in xy)
def ref(p):return {'path':str(p),'sha256':sha(p)}
def local(p):
    p=Path(p).absolute();b.require(p==p.resolve() and p.is_relative_to(HERE.parent),'Exact local path required');return p
def artifact(r):
    p=local(r['path']);b.require(sha(p)==r['sha256'],'Changed referenced file');return json.loads(p.read_bytes())
def prior_recovery():
    b.require(sha(FINE_SOURCE)==FINE_SOURCE_SHA and sha(ORIGINAL_MOVE)==ORIGINAL_MOVE_SHA,'Pinned action source changed')
    for p,h in RECOVERY_PINS.items():b.require(sha(p)==h,'Fine cleanup evidence changed '+p)
    b.require(sha(HISTORY)==HISTORY_SHA,'Prior claims inventory changed')
    rows=json.loads(HISTORY.read_bytes())['claims'];old={Path(r['path']) for r in rows}
    actual={p for folder in ('claims','globalclaims') for p in (HERE.parent/folder).glob('*.claim')}
    b.require(actual==old or actual==old|{MOVE_CLAIM},'Unexpected writer reservation or removed history')
    for r in rows:artifact(r)
    if MOVE_CLAIM.exists():
        claim=json.loads(MOVE_CLAIM.read_bytes());b.require(claim['source_sha256']==sha(Path(__file__)) and claim['target_m']==TARGET,'Wrong own move claim')
    out=json.loads((FINE/'outcome.json').read_bytes());manifest=json.loads((FINE/'manifest.json').read_bytes())
    b.require(out['status']=='failed_after_known_On_ack' and out['stable'] is False and out['on_zero_error_ack'] is True
              and out['withdraw_attempted'] is True and out['withdraw_home_confirmed'] is True and not out.get('withdraw_error'),'Fine01 not known withdrawn')
    b.require(manifest['source_sha256']==FINE_SOURCE_SHA,'Wrong fine01 source')
    times=[]
    for label,command,args in [('feedback_on','ZCtrl.OnOffSet',[1]),('failure_withdraw','ZCtrl.Withdraw',[1,2000])]:
        c=json.loads((FINE/(label+'.claim')).read_bytes());a=json.loads((FINE/(label+'_ack.json')).read_bytes())
        b.require(c['command']==command and c['args']==args and a['values']==[] and not a.get('warning'),'Fine01 unknown ACK')
        times.extend([c['monotonic_ns'],a['monotonic_ns']])
    r=json.loads(REF.read_bytes());b.require(all(a<b for a,b in zip(times,times[1:])) and times[-1]<out['monotonic_ns']<r['start']['monotonic_ns'],'Fine01 known-end ordering differs')
    return {'fine01_outcome':ref(FINE/'outcome.json'),'history':ref(HISTORY),'pulse_used_preserved':5,'pulse_maximum_preserved':6,'fine01_failure_preserved':True}
def selection(path,digest):
    p=local(path);b.require(sha(p)==digest,'Root choice changed');d=json.loads(p.read_bytes());proof=prior_recovery()
    b.require(d['schema']=='R07-home-move01-choice-v1' and d['allow_one_home_move'] is True and d['no_unresolved_writer'] is True,'Root choice missing')
    b.require(d['target_m']==TARGET and d['source_xy_m']==json.loads(REF.read_bytes())['values']['FolMe.XYPosGet'],'Fixed source/target differs')
    b.require(d['fine01_outcome']==proof['fine01_outcome'] and d['native_review_passed'] is True,'Prior known cleanup/native choice missing');artifact(d['native_review'])
    b.require(json.loads((FINE/'outcome.json').read_bytes())['monotonic_ns']<=d['monotonic_ns']<=time.monotonic_ns(),'Root choice predates known cleanup')
    return d,proof

def plan():
    return {'offline_plan_only':True,'target_m':TARGET,'source_sha256':sha(Path(__file__)),'output':str(OUTPUT),'logger':str(LOGGER),'claim':str(MOVE_CLAIM),
      'normal_writers':[['FolMe.XYPosSet',TARGET+[0]]],'conditional_writer':'one FolMe.Stop only after known XY ACK and fresh unchanged idle absoluteHome state',
      'speed_get_unchanged':m.EXPECTED['FolMe.SpeedGet'],'no_speed_setter':True,'max_distance_m':MAX_DISTANCE,
      'home_entry':'Off1 / absoluteHome within1pm / |I|<10pA / allidle and exact original configuration / 5s sampled stationary',
      'target_tolerance_m':TARGET_TOL,'sampled_stationary_tolerance_m':STILL_TOL,'post_target_sampled_stationary_s':5.,
      'deadline':'distance/originalspeed+3s; overall60s; original Stop verification2s','reference':ref(REF),
      'scope_change_from_original_move':'Home state and low-current guards replace tunneling guards. No gain/speed/feedback/XY second target or automatic fine engagement.',
      'unknown_writer':'Zero subsequent command, no replay','native_interpolation_not_verified':True,'no_new_repair_episode_or_budget_reset':True}

class Client(b.Client):
    def __init__(self,store,target):super().__init__(store);self.timeout=.5;self.target=target;self.permit=None;self.used=set()
    def call(self,n,args=None,timeout=.5):
        args=[] if args is None else args
        if (n in m.READ_ARGS and args==m.READ_ARGS[n]) or (n=='LockIn.ModOnOffGet' and args in ([1],[2])):pass
        else:
            pair=(n,args);key=(n,tuple(args));allowed=[('FolMe.XYPosSet',self.target+[0]),('FolMe.Stop',[])]
            b.require(pair in allowed and self.permit==pair and key not in self.used and timeout==.7,'Unclaimed/repeated/unreviewed writer')
            self.used.add(key);self.permit=None
        self.connect_bound();return PRIVATE_CALL(self,n,args,timeout)

class Run(m.Run):
    def __init__(self,a,admitted):
        self.store=b.Store(a.output);self.client=Client(self.store,list(TARGET))
        self.session,self.event='session_02','move_R07_home01';self.logger=a.logger
        self.fresh,self.fresh_sha=a.fresh_snapshot,a.fresh_sha256;self.source_sha=a.source_sha256;self.logger_source_sha=LOGGER_SHA
        self.admission_path,self.admission_sha=a.admission,a.admission_sha256;self.admitted=admitted
        self.target=list(TARGET);self.xy=None;self.speed=list(m.EXPECTED['FolMe.SpeedGet'])
        b.require(self.speed[1]==0 and self.speed[0]>0,'Exact original custom0 speed required')
        self.abort=False;self.deadline=None;self.ready=self.logger_start=None;self.last_logger_elapsed=self.logger_progress_time=None
        self.ambiguous=self.xy_ack=self.stop_attempted=self.stop_ack=self.reached=self.stable=self.move_attempted=False;self.phase='pre'
    def q(self,*a,**kw):
        b.require(not self.ambiguous,'Unknown writer ACK: zero subsequent commands');return super().q(*a,**kw)
    def capture(self,label,full=True,cleanup=False):
        start=b.stamp();v=self.poll(label,full,cleanup)
        if full:self.store.save(label+'.json',{'start':start,'end':b.stamp(),'values':v,'sequential_not_atomic':True})
        return v
    def guard(self,v,full=False,entry=False):
        b.require(v['ZCtrl.OnOffGet']==[0] and v['ZCtrl.StatusGet']==[1],'Feedback must remain Off1')
        for k in ['Scan.StatusGet','AutoApproach.OnOffGet','BiasSpectr.StatusGet','ZSpectr.StatusGet','FolMe.PSOnOffGet']:b.require(v[k]==[0],'Concurrent action')
        b.require(b.finite(v['Current.Get'][0]) and abs(v['Current.Get'][0])<10e-12,'Home move low-current gate')
        b.require(b.finite(v['ZCtrl.ZPosGet'][0]) and abs(v['ZCtrl.ZPosGet'][0]-m.EXPECTED['ZCtrl.HomePropsGet'][1])<1e-12,'Not absolute Home')
        b.require(in_domain(v['FolMe.XYPosGet']),'XY outside50nm frame')
        if self.phase=='pre' and self.xy is not None:b.require(all(abs(x-y)<=STILL_TOL for x,y in zip(v['FolMe.XYPosGet'],self.xy)),'Source XY moved before dispatch')
        if full:
            for k in m.FROZEN:b.require(v[k]==m.EXPECTED[k],'Frozen configuration changed '+k)
    def fresh_guard(self):
        local(self.fresh);b.require(sha(self.fresh)==self.fresh_sha,'Fresh snapshot SHA differs');j=json.loads(self.fresh.read_bytes())
        age=(time.monotonic_ns()-j['end']['monotonic_ns'])/1e9
        b.require(0<=age<=180 and self.admitted['monotonic_ns']<=j['start']['monotonic_ns']<=j['end']['monotonic_ns'],'Fresh must follow root choice and be<=180s')
        self.guard(j['values'],True,True);b.require(all(abs(x-y)<=STILL_TOL for x,y in zip(j['values']['FolMe.XYPosGet'],self.admitted['source_xy_m'])),'Fresh source differs');self.xy=list(j['values']['FolMe.XYPosGet']);self.store.save('root_fresh_snapshot.json',j)
    def write(self,pair,label,cleanup=False):
        b.require(not self.ambiguous,'Previous writer unknown')
        if not cleanup:self.check_abort()
        if pair[0]=='FolMe.Stop':b.require(self.xy_ack and not self.stop_attempted,'No blind/repeated Stop');self.stop_attempted=True
        if pair[0]=='FolMe.XYPosSet':b.require(not self.move_attempted,'XY already attempted');self.move_attempted=True
        self.store.save(label+'.claim',{**b.stamp(),'command':pair[0],'args':pair[1],'at_most_once':True,'source_sha256':self.source_sha,'admission_sha256':self.admission_sha})
        fd=os.open(self.store.root,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        self.client.permit=pair;self.ambiguous=True
        result=self.client.call(*pair,timeout=.7);self.store.save(label+'_ack.json',{**b.stamp(),**result})
        b.require(result['values']==[] and not result.get('warning'),'Nonempty/warning writer ACK')
        self.ambiguous=False
        if pair[0]=='FolMe.XYPosSet':self.xy_ack=True
        if pair[0]=='FolMe.Stop':self.stop_ack=True
    def observe(self,seconds,deadline,pre=False):
        good=previous=last_xy=None;last_full=last_logger=-1e9;count=0;rows=[]
        try:
            while time.monotonic()<deadline:
                full=time.monotonic()-last_full>=2.;v=self.capture(('pre' if pre else 'target' if self.reached else 'motion')+'_%04d'%count,full);self.guard(v,full,pre)
                now=time.monotonic();b.require(now<=deadline and (previous is None or now-previous<=1.),'Observation deadline/gap exceeded')
                xy=v['FolMe.XYPosGet'];i=v['Current.Get'][0]
                if full:last_full=now
                at_target=pre or all(abs(x-y)<=TARGET_TOL for x,y in zip(xy,self.target))
                still=last_xy is not None and all(abs(x-y)<=STILL_TOL for x,y in zip(xy,last_xy))
                ok=at_target and still  # Every sample already passed absoluteHome/low-current guard.
                good=(now if good is None else good) if ok else None;count+=1
                rows.append({'t':now,'I_A':i,'Z_m':v['ZCtrl.ZPosGet'][0],'XY_m':xy,'at_target':at_target,'sampled_stationary':still})
                if now-last_logger>=1.:self.logger_guard(0.,post_budget=30.,profile=full);last_logger=time.monotonic()
                if good is not None and now-good>=seconds and count>=3:return v,now-good,count
                previous,last_xy=now,list(xy);time.sleep(.1)
            raise RuntimeError('Target/current stability deadline reached')
        finally:self.store.save(('pre' if pre else 'target' if self.reached else 'motion')+'_samples.json',{'rows':rows,'high_frequency_XY_path_verified':False})
    def stop_on_error(self,out):
        if self.ambiguous or not self.xy_ack or self.client._closed or self.stop_attempted:
            out['cleanup_withheld']='Unknown writer/no known XY ACK/closed transport/already attempted Stop';return
        try:
            v=self.capture('before_conditional_stop',True,True)
            self.guard(v,True,False)
            self.write(('FolMe.Stop',[]),'conditional_stop',True)
            end=time.monotonic()+2.;since=last=None;count=0
            while time.monotonic()<end:
                xy=self.q('FolMe.XYPosGet',cleanup=True);now=time.monotonic();b.require(in_domain(xy),'Stopped XY outside domain');count+=1
                same=last is not None and all(abs(x-y)<=STILL_TOL for x,y in zip(xy,last))
                since=(now if since is None else since) if same else None
                self.store.event('after_Stop_position',XY_m=xy)
                if since is not None and now-since>=.3 and count>=3:out['Stop_ACK_plus_sampled_stationary_confirmed']=True;return
                last=list(xy);time.sleep(.1)
            raise RuntimeError('No sampled stationary position after Stop')
        except BaseException as exc:out['conditional_Stop_error']=str(exc)
    def execute(self):
        out={'status':'not_started','stage_intent':'independent_home_move_to_prior_corner','automatic_On':False,'automatic_Withdraw':False,'automatic_retry':False,'pulse_count_reset':False}
        self.deadline=time.monotonic()+60.
        try:
            admission,proof=selection(self.admission_path,self.admission_sha)
            b.require(admission==self.admitted,'Root choice changed');self.store.save('admission_bound.json',admission)
            self.store.save('manifest.json',{**b.stamp(),**plan(),'offline_plan_only':False,'source_sha256':self.source_sha,'target_m':self.target,'prior_recovery':proof,'admission_sha256':self.admission_sha,**m.sb.consumer_metadata(LOGGER_SHA)})
            self.fresh_guard();self.logger_guard(0.,post_budget=90.,profile=True)
            v=self.capture('before');self.guard(v,True,True)
            distance=math.dist(v['FolMe.XYPosGet'],self.target);b.require(0<distance<=MAX_DISTANCE,'Need0<distance<=50nm')
            self.observe(5.,time.monotonic()+10.,True)
            v=self.capture('immediate_before_move');self.guard(v,True,True);self.logger_guard(0.,post_budget=60.,profile=True)
            distance=math.dist(v['FolMe.XYPosGet'],self.target);b.require(0<distance<=MAX_DISTANCE,'Fresh distance outside0..50nm')
            budget=distance/v['FolMe.SpeedGet'][0]+3.;end=time.monotonic()+budget
            self.store.save('fixed_endpoints.json',{'source_m':v['FolMe.XYPosGet'],'target_m':self.target,'distance_m':distance,'deadline_s':budget,'native_interpolation_not_verified':True})
            record={**b.stamp(),'event_id':self.event,'target_m':self.target,'admission_sha256':self.admission_sha,'output':str(self.store.root),'source_sha256':self.source_sha,'one_attempt_no_release':True,'old_pulse_used':5,'pulse_budget_unchanged':True}
            fd=os.open(MOVE_CLAIM,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write((json.dumps(record,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno())
            fd=os.open(MOVE_CLAIM.parent,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
            self.store.save('move_reservation.json',ref(MOVE_CLAIM))
            self.phase='motion';self.write(('FolMe.XYPosSet',self.target+[0]),'move')
            v,span,count=self.observe(.2,end);self.reached=True
            self.store.save('target_confirmed.json',{**b.stamp(),'values':v,'sampled_stationary_s':span,'samples':count})
            v,span,count=self.observe(5.,min(self.deadline,time.monotonic()+10.));self.stable=True
            self.store.save('target_stable.json',{**b.stamp(),'values':v,'stable_s':span,'samples':count})
            v=self.capture('after');self.guard(v,True,True)
            b.require(all(abs(x-y)<=TARGET_TOL for x,y in zip(v['FolMe.XYPosGet'],self.target)),'Target changed at final read')
            out.update(status='home_target_verified_5s_stationary',actual_target_m=v['FolMe.XYPosGet'],target_m=self.target,distance_m=distance,stable_after_s=span)
        except BaseException as exc:
            out.update(status='uncertain_no_retry' if self.move_attempted or self.ambiguous else 'rejected_before_move',error=str(exc));self.stop_on_error(out)
        finally:
            out.update(move_attempted=self.move_attempted,asynchronous_move_ACK=self.xy_ack,writer_outcome_unknown=self.ambiguous,stop_attempted=self.stop_attempted,stop_ACK=self.stop_ack,target_confirmed=self.reached,stable5s_confirmed=self.stable,high_frequency_XY_path_verified=False)
            self.client.close();self.store.save('outcome.json',{**b.stamp(),**out})
        return out

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--execute',action='store_true')
    for k in ['output','logger','fresh-snapshot','admission']:ap.add_argument('--'+k,type=Path)
    for k in ['source-sha256','fresh-sha256','admission-sha256']:ap.add_argument('--'+k)
    a=ap.parse_args()
    if not a.execute:print(json.dumps(plan(),indent=2));return 0
    b.require(all(vars(a).values()),'All explicit bindings required')
    b.require(local(a.output)==OUTPUT and not a.output.exists() and not MOVE_CLAIM.exists(),'Exact new output and unused move claim required')
    b.require(local(a.logger)==LOGGER and sha(Path(__file__))==a.source_sha256,'Logger/source differs')
    admitted,_=selection(a.admission,a.admission_sha256)
    run=Run(a,admitted);handlers={s:signal.signal(s,lambda *_:setattr(run,'abort',True)) for s in (signal.SIGINT,signal.SIGTERM)}
    try:out=run.execute()
    finally:
        for s,h in handlers.items():signal.signal(s,h)
    print(json.dumps(out,indent=2));return 0 if out['status']=='home_target_verified_5s_stationary' else 1
if __name__=='__main__':raise SystemExit(main())
