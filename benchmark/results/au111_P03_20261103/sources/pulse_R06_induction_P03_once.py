"""Offline plan by default: one explicitly selected -6.0V induction,20ms/Hold pulse at prepared1nA.
No setpoint/scan/move/On/retry. Root alone selects and executes each segment.
"""
import argparse,copy,hashlib,importlib.util,json,math,os,signal,statistics,struct,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
SOURCE=HERE/'scan_full50nm_fast_R06_baseline_once.py'
SOURCE_SHA='f55c58f30a29d9f5ebf908c49298e81d857878e4c1954b1e3a895a4f4803558d'
if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SOURCE_SHA:raise RuntimeError('Frozen read envelope changed')
spec=importlib.util.spec_from_file_location('pulse50_read_envelope',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
b=m.b
ORIGINAL_SOURCE=ROOT/'pulse_fullcycle_1nA_20ms_hold_once.py'
ORIGINAL_SOURCE_SHA='1ec66cf6ebb83c7a8450880536cbfa5e71d806143b8d3874d2435158e19b1b40'
if hashlib.sha256(ORIGINAL_SOURCE.read_bytes()).hexdigest()!=ORIGINAL_SOURCE_SHA:raise RuntimeError('Original action source changed')
BINDINGS_SOURCE = HERE / 'action_bindings_R06_induction_P03.py'
BINDINGS_SHA = 'e7e3fcad26d11e3da24fd31b0c652cf1d472f2234aad76ebba85cbf4b67a4165'
if hashlib.sha256(BINDINGS_SOURCE.read_bytes()).hexdigest() != BINDINGS_SHA:
    raise RuntimeError('Frozen local action bindings changed')
_binding_spec = importlib.util.spec_from_file_location('five_session_action_bindings', BINDINGS_SOURCE)
ab = importlib.util.module_from_spec(_binding_spec)
_binding_spec.loader.exec_module(ab)
EXPECTED=copy.deepcopy(m.EXPECTED)
SETPOINT=struct.unpack('>f',struct.pack('>f',1e-9))[0]
EXPECTED['ZCtrl.SetpntGet']=[SETPOINT]
PULSE=None;WITHDRAW=('ZCtrl.Withdraw',[1,2000])
SESSION=ACTION=ORDINAL=None
IDLE=['Scan.StatusGet','AutoApproach.OnOffGet','BiasSpectr.StatusGet','ZSpectr.StatusGet','FolMe.PSOnOffGet']
LEDGER=RESERVATION=None
FEEDBACK_READY_MAX_S=2.0  # Root-selected bounded getter wait; not a physical safety threshold.
b.require(b.p.COMMANDS['Bias.Pulse']['inputs']==['I','f','f','H','H'] and b.p.COMMANDS['Bias.Pulse']['outputs']==[],'Pulse codec changed')


def band(i):return b.finite(i) and -1.25e-9<=i<=-.75e-9
def abnormal(i):return not b.finite(i) or not -2e-9<=i<=-.25e-9
def ledger_guard(path,digest,xy=None):
    return ab.ledger_guard(path,digest,SESSION,ACTION,ORDINAL,PULSE,xy)

def reserve(digest,output,fresh_sha):
    return ab.reserve_pulse(LEDGER,digest,SESSION,ACTION,ORDINAL,PULSE,output,fresh_sha,hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def trend(rows):
    b.require(len(rows)>=20,'Too few I/Z observations')
    end=rows[-1]['t'];cut=end-10.;start=max(0,next((i for i,r in enumerate(rows) if r['t']>=cut),0)-1)
    w=rows[start:];span=w[-1]['t']-w[0]['t'];b.require(span>=10. and max(y['t']-x['t'] for x,y in zip(w,w[1:]))<=1.,'Insufficient contiguous last10s Z observations')
    ts=[r['t']-w[0]['t'] for r in w];zs=[r['Z_m']-w[0]['Z_m'] for r in w];mt,mz=statistics.mean(ts),statistics.mean(zs)
    slope=sum((t-mt)*(z-mz) for t,z in zip(ts,zs))/sum((t-mt)**2 for t in ts)
    rms=math.sqrt(statistics.mean((z-mz-slope*(t-mt))**2 for t,z in zip(ts,zs)))
    currents=[r['I_A'] for r in w]
    return {'window_s':span,'samples':len(w),'Z_slope_m_per_s':slope,'Z_detrended_RMS_m':rms,
        'Z_span_m':max(zs)-min(zs),'I_mean_A':statistics.mean(currents),'I_std_A':statistics.pstdev(currents),
        'I_min_A':min(currents),'I_max_A':max(currents),'brackets_last10s':True}


class Client(b.Client):
    def __init__(self,s):super().__init__(s);self.timeout=.5;self.permit=None;self.used=set()
    def call(self,n,args=None,timeout=.5):
        args=[] if args is None else args
        if (n in m.READ_ARGS and args==m.READ_ARGS[n]) or (n=='LockIn.ModOnOffGet' and args in ([1],[2])):pass
        else:
            b.require((n,args) in (PULSE,WITHDRAW) and self.permit==(n,args) and n not in self.used,'Unclaimed/repeated/unreviewed writer')
            b.require(timeout==(2. if n==PULSE[0] else 2.5),'Writer timeout changed')
            self.used.add(n);self.permit=None
        self.connect_bound();return b.p.NanonisClient.call(self,n,args,timeout)


class Run(m.Run):
    def __init__(self,output,logger,fresh,fresh_sha,ledger_sha,source_sha,logger_source_sha):
        self.store=b.Store(output);self.client=Client(self.store)
        self.logger,self.fresh,self.fresh_sha=Path(logger),Path(fresh),fresh_sha
        self.session,self.action,self.event=SESSION,ACTION,'pulse_induction_'+ACTION
        self.source_sha,self.logger_source_sha=source_sha,logger_source_sha
        self.abort=False;self.ready=self.logger_start=None
        self.last_logger_elapsed=self.logger_progress_time=None
        self.ledger_sha=ledger_sha;self.xy=None;self.attempted=False;self.native_end=False;self.ambiguous=False
        self.deadline=time.monotonic()+95.;self.all_rows={}
    def q(self,*a,**kw):
        b.require(not self.ambiguous,'Unknown writer outcome; no subsequent command')
        return super().q(*a,**kw)
    def capture(self,label,full=True,cleanup=False):
        start=b.stamp();v=self.poll(label,full=full,cleanup=cleanup)
        if full:self.store.save(label+'.json',{'start':start,'end':b.stamp(),'values':v,'sequential_not_atomic':True})
        return v
    def guard(self,v,full=False,entry=False):
        b.require(v['Bias.Get']==[-1.] and v['ZCtrl.SetpntGet']==[SETPOINT] and v['SafeTip.OnOffGet']==[0],'Need -1V/1nA/SafeOff')
        b.require(v['ZCtrl.OnOffGet']==[1] and v['ZCtrl.StatusGet']==[2] and all(v[n]==[0] for n in IDLE),'Not known On2/allidle')
        b.require(b.finite(v['Current.Get'][0]) and abs(v['Current.Get'][0])<4e-9,'Sampled4nA/nonfinite gate; not a physical bound')
        hi,lo=EXPECTED['ZCtrl.LimitsGet'];z=v['ZCtrl.ZPosGet'][0]
        b.require(b.finite(z) and lo+5e-9<=z<=hi-5e-9,'Z endpoint margin below5nm')
        xy=v['FolMe.XYPosGet'];b.require(len(xy)==2 and all(b.finite(x) for x in xy),'Invalid XY')
        if self.xy is not None:b.require(all(abs(x-y)<=2e-12 for x,y in zip(xy,self.xy)),'XY changed')
        if full:
            for n in m.FROZEN:b.require(v[n]==EXPECTED[n],'Changed frozen configuration: '+n)
        if entry:b.require(band(v['Current.Get'][0]),'Outside1nA +/-25% signed band')
    def hold_readiness_guard(self,v,full=False,entry=False):
        # Only the explicitly observed OnOff1/Status3 transition is eligible to wait.
        # All other original immediate-after state/current/XY/Z/configuration checks stay exact.
        b.require(v['Bias.Get']==[-1.] and v['ZCtrl.SetpntGet']==[SETPOINT] and v['SafeTip.OnOffGet']==[0],'Need -1V/1nA/SafeOff')
        b.require(v['ZCtrl.OnOffGet']==[1] and v['ZCtrl.StatusGet']==[3] and all(v[n]==[0] for n in IDLE),'Not known On1/Hold3/allidle')
        b.require(b.finite(v['Current.Get'][0]) and abs(v['Current.Get'][0])<4e-9,'Sampled4nA/nonfinite gate; not a physical bound')
        hi,lo=EXPECTED['ZCtrl.LimitsGet'];z=v['ZCtrl.ZPosGet'][0]
        b.require(b.finite(z) and lo+5e-9<=z<=hi-5e-9,'Z endpoint margin below5nm')
        xy=v['FolMe.XYPosGet'];b.require(len(xy)==2 and all(b.finite(x) for x in xy),'Invalid XY')
        if self.xy is not None:b.require(all(abs(x-y)<=2e-12 for x,y in zip(xy,self.xy)),'XY changed')
        if full:
            for n in m.FROZEN:b.require(v[n]==EXPECTED[n],'Changed frozen configuration: '+n)
        if entry:b.require(band(v['Current.Get'][0]),'Outside1nA +/-25% signed band')
    def await_feedback_ready(self,immediate):
        b.require(self.native_end and not self.ambiguous and not self.client._closed,
                  'Readiness wait requires known pulse end and usable transport; no reads after unknown ACK')
        ack_path=self.store.root/'pulse_ack.json'
        ack=json.loads(ack_path.read_bytes())
        b.require(ack['values']==[] and not ack.get('warning'),'Known zero-error pulse ACK required')
        ack_s=ack['monotonic_ns']/1e9
        deadline=min(ack_s+FEEDBACK_READY_MAX_S,self.deadline)
        rows=[];ready=False;error=None;v=immediate
        try:
            while True:
                self.check_abort()
                now=time.monotonic()
                rows.append({'observation_index':len(rows),'host_monotonic_s':now,
                             'elapsed_from_ACK_s':now-ack_s,'values':v,'sequential_not_atomic':True})
                b.require(0<=now-ack_s<=FEEDBACK_READY_MAX_S and now<=deadline,'Feedback readiness exceeded2s from known ACK')
                if v['ZCtrl.OnOffGet']==[1] and v['ZCtrl.StatusGet']==[2]:
                    self.guard(v,full=True)
                    b.require(self.deadline-time.monotonic()>=30.,'Original95s deadline cannot fit complete post30s')
                    ready=True
                    return {'status':'known_On2_ready','elapsed_from_ACK_s':now-ack_s,
                            'getter_observations':len(rows),'Hold_observations':sum(r['values']['ZCtrl.StatusGet']==[3] for r in rows),
                            'post30s_not_yet_started':True,'total_deadline_not_reset':True}
                self.hold_readiness_guard(v,full=True)
                self.logger_guard(0.,post_budget=45.,profile=True)
                b.require(time.monotonic()<deadline and self.deadline-time.monotonic()>=30.,
                          'Readiness wait exhausted2s or original95s post-observation budget')
                time.sleep(min(.05,max(0.,deadline-time.monotonic())))
                b.require(time.monotonic()<deadline,'Feedback readiness Hold timeout; no On or pulse replay')
                v=self.capture('feedback_readiness_%03d'%len(rows),full=True)
        except BaseException as exc:
            error=str(exc);raise
        finally:
            self.store.save('feedback_readiness.json',{'known_ACK':{'path':str(ack_path),'sha256':hashlib.sha256(ack_path.read_bytes()).hexdigest()},
                'max_wait_s':FEEDBACK_READY_MAX_S,'ready':ready,'error':error,'observations':rows,
                'readonly':True,'writes':[],'Hold_is_waiting_not_stable':True,'post30s_excludes_readiness_time':True,
                'original_overall_deadline_monotonic_s':self.deadline,'engineering_time_budget_not_physical_safety_limit':True})
    def fresh_guard(self):
        raw=self.fresh.read_bytes();b.require(hashlib.sha256(raw).hexdigest()==self.fresh_sha,'Fresh snapshot hash changed')
        record=json.loads(raw);age=(time.monotonic_ns()-record['end']['monotonic_ns'])/1e9
        b.require(0<=age<=180.,'Prepared snapshot >180s; fresh read required')
        self.guard(record['values'],full=True,entry=True);self.xy=list(record['values']['FolMe.XYPosGet'])
        ledger_guard(LEDGER,self.ledger_sha,self.xy);self.store.save('root_fresh_snapshot.json',record)
    def write_once(self,pair,label):
        b.require(not self.ambiguous,'Unknown previous writer')
        if pair==PULSE:
            b.require(not self.attempted,'Pulse already attempted');self.attempted=True
            self.store.save('session_reservation.json',reserve(self.ledger_sha,self.store.root,self.fresh_sha))
        else:b.require(self.native_end,'No Withdraw before known pulse end')
        self.store.save(label+'.claim',{**b.stamp(),'command':pair[0],'args':pair[1],'at_most_once':True,'ledger_sha256':self.ledger_sha})
        fd=os.open(self.store.root,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        self.client.permit=pair;self.ambiguous=True
        result=self.client.call(*pair,timeout=2. if pair==PULSE else 2.5)
        self.store.save(label+'_ack.json',{**b.stamp(),**result})
        b.require(result['values']==[] and not result.get('warning'),'Nonempty/warning ACK')
        self.ambiguous=False
        if pair==PULSE:self.native_end=True
    def observe(self,label,pre):
        start=time.monotonic();rows=[];good=bad=previous=None;last_full=last_logger=-1e9
        try:
            while time.monotonic()-start<30.:
                full=time.monotonic()-last_full>=2.;v=self.capture(label+'_%03d'%len(rows),full=full)
                self.guard(v,full=full,entry=pre);now=time.monotonic();i,z=v['Current.Get'][0],v['ZCtrl.ZPosGet'][0]
                if full:last_full=now
                b.require(previous is None or now-previous<=1.,'I/Z observation gap >1s')
                good=(now if good is None else good) if band(i) else None
                bad=(now if bad is None else bad) if abnormal(i) else None
                rows.append({'t':now,'I_A':i,'Z_m':z});previous=now
                if not pre:b.require(bad is None or now-bad<1.,'Persistent significant current anomaly')
                if now-last_logger>=2.:
                    self.logger_guard(0.,post_budget=100. if pre else 45.,profile=True);last_logger=time.monotonic()
                time.sleep(.1)
            metrics=trend(rows);metrics.update(elapsed_s=time.monotonic()-start,final_band_s=0. if good is None else previous-good)
            self.store.save(label+'_summary.json',metrics)
            b.require(metrics['final_band_s']>=5.,'Final5s current band not established')
            b.require(abs(metrics['Z_slope_m_per_s'])<=10e-12 and metrics['Z_detrended_RMS_m']<=10e-12,'Last10s Z trend/RMS review gate failed')
            return metrics
        finally:self.all_rows[label]=rows;self.store.save(label+'_samples.json',{'rows':rows,'timing':'sequential monotonic client observations, not raw native samples'})
    def cleanup_pulse(self,out):
        if not self.native_end or self.ambiguous or self.client._closed:
            out['cleanup_withheld']='No known native end or transport/writer unknown; no subsequent command';return
        deadline=time.monotonic()+15.;since=None;count=0;rows=[]
        try:
            while time.monotonic()<deadline-7.:
                v=self.capture('exception_recheck_%02d'%count,full=True,cleanup=True);rows.append(v)
                for n in IDLE:b.require(v[n]==[0],'Concurrent action; no Withdraw')
                for n in m.FROZEN:b.require(v[n]==EXPECTED[n],'Changed configuration; no Withdraw')
                b.require(all(abs(x-y)<=2e-12 for x,y in zip(v['FolMe.XYPosGet'],self.xy)),'XY changed; no Withdraw')
                b.require((v['ZCtrl.OnOffGet'],v['ZCtrl.StatusGet']) in [([1],[2]),([0],[1])],'Unknown feedback recovery')
                if not abnormal(v['Current.Get'][0]):out['fault_not_persistent']=True;return
                now=time.monotonic();since=now if since is None else since;count+=1
                if count>=4 and now-since>=1.:break
                time.sleep(.15)
            b.require(count>=4 and since is not None and time.monotonic()-since>=1.,'Persistent current fault not confirmed')
            out['withdraw_attempted']=True;self.write_once(WITHDRAW,'persistent_fault_withdraw')
            since=previous=None;n=0
            while time.monotonic()<deadline:
                v=self.capture('withdraw_verify_%03d'%n,full=False,cleanup=True);now=time.monotonic();n+=1
                good=all(v[k]==[0] for k in IDLE) and v['ZCtrl.OnOffGet']==[0] and v['ZCtrl.StatusGet']==[1] and v['SafeTip.OnOffGet']==[0]
                good=good and b.finite(v['Current.Get'][0]) and abs(v['Current.Get'][0])<10e-12 and b.finite(v['ZCtrl.ZPosGet'][0]) and abs(v['ZCtrl.ZPosGet'][0]-EXPECTED['ZCtrl.HomePropsGet'][1])<1e-12
                since=(now if since is None or (previous is not None and now-previous>1.) else since) if good else None;previous=now
                if since is not None and now-since>=3.:out['withdraw_Off1Home_confirmed']=True;return
                time.sleep(.15)
            raise RuntimeError('No3s sampled Off1/Home')
        except BaseException as exc:out['cleanup_error']=str(exc)
        finally:self.store.save('exception_rechecks.json',{'values':rows})
    def execute(self):
        out={'status':'not_started','session_id':self.session,'action_id':self.action,'pulse_ordinal':ORDINAL,'automatic_On':False,'automatic_retry':False,'return_to100pA_performed':False,'effect':'unknown'}
        try:
            self.store.save('manifest.json',{**b.stamp(),**plan(),'session_id':self.session,'action_id':self.action,**m.sb.consumer_metadata(self.logger_source_sha),'segment06_baseline':m.sb.completed_baseline(self.logger_source_sha),'induction_admission':{'path':str(ab.ADMISSION_PATH),'sha256':ab.ADMISSION_SHA},'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'ledger_sha256':self.ledger_sha})
            self.store.save('stage_admission.json',ab.reserve_stage(self.session,self.action,'pulse',self.store.root,self.source_sha,self.fresh_sha))
            self.fresh_guard();self.logger_guard(0.,post_budget=135.,profile=True)
            before=self.capture('before');self.guard(before,True,True)
            out['pre_metrics']=self.observe('pre30s',True)
            immediate=self.capture('immediate_before');self.guard(immediate,True,True)
            self.logger_guard(0.,post_budget=100.,profile=True);ledger_guard(LEDGER,self.ledger_sha,self.xy);self.check_abort()
            self.write_once(PULSE,'pulse')
            immediate=self.capture('immediate_after');out['feedback_readiness']=self.await_feedback_ready(immediate)
            out['post_metrics']=self.observe('post30s',False)
            after=self.capture('after30s');self.guard(after,True,True)
            out.update(status='single_pulse_knownend_30s_observed',fixed_xy_m=self.xy,Z_change_m=after['ZCtrl.ZPosGet'][0]-before['ZCtrl.ZPosGet'][0])
        except BaseException as exc:
            out.update(status='uncertain_or_recovery_failed' if self.attempted else 'rejected_before_pulse',error=str(exc))
            if self.attempted:self.cleanup_pulse(out)
        finally:
            out.update(pulse_attempted=self.attempted,native_end_confirmed=self.native_end,writer_outcome_unknown=self.ambiguous,
                session_claim_exists=RESERVATION.exists(),requires_root_review=True)
            self.client.close();self.store.save('outcome.json',{**b.stamp(),**out})
        return out


def plan():
    return {'recording_segment_id':m.sb.SEGMENT,'logger_directory':str(m.sb.LOGGER_DIR),'requires_completed_recording_baseline':str(ROOT/m.sb.SESSION/'baseline_segment06_full'),'usable_baseline':'Actual212 after_R06_P02_recovery_full must be complete/native-bitmatched and task-usable with recorded C1 local changes; old mound and affected C2/D4 remain explicit limitations','original_source_sha256':ORIGINAL_SOURCE_SHA,'origin':'task_usable_baseline_induction','stage_intent':'induction_attempt','induction_effect':'not_assessed','repair_episode_active':False,'induced_bad_state_confirmed':False,'induced_cycle_complete':False,'induction_admission':None,'candidate_only_not_selected':[-6.0,.020],'scope':'one R06 P03 induction continuing ordinal5 pulse; no automatic voltage ladder; plan creates no files/socket/claim','normal_writer':PULSE,'conditional_writer':WITHDRAW,
        'geometry':'50nm square,240x240,.912s each direction; all frozen fields except prepared1nA retained',
        'source':str(Path(__file__).resolve()),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'read_envelope_source':str(SOURCE),'read_envelope_sha256':SOURCE_SHA,'static_reference_sha256':m.REF_SHA,'setpoint_f32_A':SETPOINT,
        'ledger':str(LEDGER),'unique_session_claim':str(RESERVATION),'strict_pulse_transition':None if ORDINAL is None else [ORDINAL-1,ORDINAL],'allowed_volts':[-6.0],'wire_encoding':{'requested_args':ab.ra.REQUEST,'args_f32':ab.ra.WIRE,'voltage_hex':struct.pack('>f',-6.0).hex(),'duration_hex':struct.pack('>f',.020).hex()},'duration_s':.020,'legacy_pulse_count_included':3,'prior_P02_induction_pulses':1,'pulse_attempts_before':4,'cap':6,'review_after_no_improvement':2,
        'pre_post_observation_s':[30,30],'final_current_window_s':5,'Z_bracketed_window_s':10,'max_abs_Z_slope_m_per_s':10e-12,'max_Z_detrended_RMS_m':10e-12,
        'stability_limit':'New engineering review thresholds, unvalidated as physical limits or proof of no creep; full traces saved.',
        'feedback_readiness':{'max_s':2.0,'from':'persisted known waiting ACK','eligible_wait_state':'OnOff1/Status3 only; every other original full guard exact','writes':[],'overall_deadline_s':95,'post30s_starts_only_after_real_On2':True,'engineering_not_physical_threshold':True,'deadline_semantics':'On2 acceptance must be within2s from ACK. Original getter/group timeouts remain; an in-progress group may finish beyond2s and is then rejected. Not a hard-real-time stop guarantee.'},
        'recovery':'Waiting zero-error Pulse ACK confirms native end only; a bounded getter-only Hold-to-On2 transition precedes the unchanged full30s guards. No On, retry or automatic return100pA.',
        'cleanup':'Known end and idle unchanged state, repeated significant current outside[-2,-.25]nA >=1s and>=4checks permits one Withdraw/3sOff1Home. Unknown writer: no subsequent command.',
        'recording':'Independent21600nominal/6channels/2kHz/source+session bound; fresh<=2s and native progress/profile; >=135s before pre30s and>=100s immediately before pulse.',
        'measurement_limits':'IVC100-1G-4K nominal range/bandwidth known from model; installed chain calibration and overload recovery unverified. Sampled4nA gate is not compliance or peak bound; software floor about-9.99948nA is censored.',
        'causality':'100pA->1nA preparation + pulse +100pA return are separately recorded compound protocol; no Pulse-only attribution, chemical-clean/contact or repair-cycle claim'}


def main():
    global PULSE,SESSION,ACTION,ORDINAL,LEDGER,RESERVATION
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--execute',action='store_true')
    for n in ['output','logger','fresh-snapshot','ledger']:ap.add_argument('--'+n,type=Path)
    for n in ['fresh-sha256','ledger-sha256','session','action','source-sha256','logger-source-sha256']:ap.add_argument('--'+n)
    ap.add_argument('--volts',type=float,choices=[-6.0])
    ap.add_argument('--pulse-ordinal',type=int,choices=[5])
    ap.add_argument('--episode-admission',type=Path)
    ap.add_argument('--episode-admission-sha256')
    args=ap.parse_args()
    SESSION,ACTION,ORDINAL=args.session,args.action,args.pulse_ordinal
    PULSE=None if args.volts is None else ('Bias.Pulse',[1,.020,args.volts,1,2])
    LEDGER=RESERVATION=None
    if not args.execute:print(json.dumps(plan(),indent=2));return 0
    b.require(all([args.output,args.logger,args.fresh_snapshot,args.fresh_sha256,args.ledger,args.ledger_sha256,SESSION,ACTION,ORDINAL,args.source_sha256,args.logger_source_sha256]) and PULSE is not None,'Explicit single choice/ordinal/session/action/local hashes required')
    b.require(args.episode_admission and args.episode_admission_sha256,'Explicit frozen induction admission required')
    ab.bind_admission(args.episode_admission,args.episode_admission_sha256,'pulse')
    ab.paths(SESSION,ACTION,'pulse',args.output,args.logger,args.fresh_snapshot,Path(__file__),args.source_sha256,args.logger_source_sha256)
    LEDGER=ROOT/SESSION/'induction_P03.ledger.json';RESERVATION=ab.reservation_path(ORDINAL)
    ledger_guard(args.ledger,args.ledger_sha256)
    run=Run(args.output,args.logger,args.fresh_snapshot,args.fresh_sha256,args.ledger_sha256,args.source_sha256,args.logger_source_sha256)
    handlers={s:signal.signal(s,lambda *_:setattr(run,'abort',True)) for s in [signal.SIGINT,signal.SIGTERM]}
    try:out=run.execute()
    finally:
        for s,h in handlers.items():signal.signal(s,h)
    print(json.dumps(out,indent=2));return 0 if out['status']=='single_pulse_knownend_30s_observed' else 1


if __name__=='__main__':raise SystemExit(main())
