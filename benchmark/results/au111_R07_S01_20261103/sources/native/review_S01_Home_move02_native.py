"""Local native continuity and actual wire proof for independent post-S01 Home move02."""
from pathlib import Path
import hashlib,importlib.util,json,struct
D=Path(__file__).resolve().parent;B=D/'review_native_phases.py'
assert hashlib.sha256(B.read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
s=importlib.util.spec_from_file_location('Home_move02_base',B);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
h,np=m.h,m.np;M=m.C/'move_R07_after_S01_home02';source=m.C/'move_R07_after_S01_home02_once.py'
h.require(h.sha(source.read_bytes())=='9b486103aae6f0a7310ba860d7901593004d80e7e124a69ab7736fb109cf859d','Move source changed')
refs={}
def read(p):
    j,r=h.read_json(p);refs[str(p)]=r;return j
rr=read(D/'S01_Home_move02_completed_through284_native_receipt.json')
h.require(refs[str(D/'S01_Home_move02_completed_through284_native_receipt.json')]['sha256']=='09cf390650ff851bb008c858a5e3fad43d56f0905aaaa6fb95dfd9a999da6fe8','Receipt changed')
previous=read(D/'S01_Home_current_completed_through270_native_receipt.json');out=read(M/'outcome.json');before=read(M/'before.json');after=read(M/'after.json');stable=read(M/'target_stable.json');mf=read(M/'manifest.json')
h.require(out['status']=='home_target_verified_5s_stationary' and not out['writer_outcome_unknown'] and out['asynchronous_move_ACK'] and not out['stop_attempted'] and stable['stable_s']>=5.,'Move not known complete')
ready=read(m.L/'READY.json');h.require(read(M/'logger_ready_bound.json')==ready and rr['native_start_identity']==previous['native_start_identity']==ready['native_start_identity'],'Recorder identity differs')
for name,digest in m.LOGGER_IDENTITY_PINS.items():h.require(h.sha((m.L/name).read_bytes())==digest,'Recorder proof changed')
h.require(mf['source_sha256']==h.sha(source.read_bytes()),'Manifest source differs')
expected=json.loads((m.S/'recovery_R07_S01_H01_current/after.json').read_text())['values']
for state in [before['values'],after['values']]:
    for k in ['ZCtrl.SetpntGet','ZCtrl.GainGet','Scan.SpeedGet','FolMe.SpeedGet','Bias.Get','SafeTip.OnOffGet']:h.require(state[k]==expected[k],'Restored setting differs')
    h.require(state['ZCtrl.OnOffGet']==[0] and state['ZCtrl.StatusGet']==[1] and abs(state['Current.Get'][0])<10e-12 and abs(state['ZCtrl.ZPosGet'][0]-123.69999069505866e-9)<1e-12,'Not verified Off/Home')
h.require(after['values']['FolMe.XYPosGet']==out['actual_target_m'] and all(abs(x+25e-9)<20e-12 for x in out['actual_target_m']),'Wrong final corner')
ev,er=m.events(M/'events.jsonl',{'tcp_exchange'});writers=[e for e in ev if e['command'] in ['FolMe.XYPosSet','FolMe.Stop','ZCtrl.OnOffSet','ZCtrl.Withdraw']]
h.require(len(writers)==1 and writers[0]['command']=='FolMe.XYPosSet' and writers[0]['args']==[-25e-9,-25e-9,0],'Unexpected move writer sequence')
e=writers[0]
for key in ['request_header','request_body','response_header','response_body']:
    r=e[key];raw=(M/r['path']).read_bytes();h.require(h.sha(raw)==r['sha256'] and len(raw)==r['bytes'],'Wire changed')
h.require(e['status']=='ok' and not e.get('warning') and (M/e['request_body']['path']).read_bytes()==struct.pack('>ddI',-25e-9,-25e-9,0) and (M/e['response_body']['path']).read_bytes()==bytes(8),'Move ACK/body differs')
lev,lr=m.events(m.L/'events.jsonl',{'datalog_status'});anchors=m.log_anchors(lev,ready['native_start_identity'])
def bound(lo,hi):
    v=m.bracket(anchors,lo,hi);h.require(v is not None,'Missing counter bracket');return v
b0=bound(before['start']['monotonic_ns'],before['end']['monotonic_ns']);bw=bound(round(e['start_perf']*1e9),round(e['end_perf']*1e9));ba=bound(after['start']['monotonic_ns'],after['end']['monotonic_ns'])
first=270*m.BLOCK;last=284*m.BLOCK;arrays=[];files=[]
for num in range(271,285):
    name=f'{m.PREFIX}{num:05d}.dat';meta=rr['files'][name];p=h.local(m.S/'native_R07'/name);raw=p.read_bytes()
    h.require(str(p)==meta['local_path'] and meta['rows']==m.BLOCK and h.sha(raw)==meta['sha256'] and len(raw)==meta['bytes'] and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Raw block mismatch')
    arrays.append(h.parse_block(raw,m.BLOCK));files.append({'path':str(p),'sha256':meta['sha256']})
a=np.concatenate(arrays);del arrays;limits=sorted(v*1e9 for v in before['values']['ZCtrl.LimitsGet'])
def desc(lo,hi):
    r=m.stats(a,lo-first,hi-first,100.,limits);r['zero_based_sample_half_open']=[lo,hi];r['native_seconds_half_open']=[lo*m.DT,hi*m.DT]
    if hi>lo:
        v=a[lo-first:hi-first];j=lo+int(np.argmin(v[:,0]));r['minimum_I_location']={'block':j//m.BLOCK+1,'row_zero_based':j%m.BLOCK};r['all_abs_current_below10pA']=bool(np.all(abs(v[:,0])<10.));r['all_native_Z_Home']=bool(np.all(abs(v[:,2]-123.69999069505866)<.001));r['Bias_not_minus1V_samples']=int(np.count_nonzero(v[:,1]!=-1.))
        for d in r['abs_I_sample_exceedances_pA'].values():
            if d['longest_native_seconds_half_open']:d['longest_native_seconds_half_open']=[t+first*m.DT for t in d['longest_native_seconds_half_open']]
        if r['Z_changes']['pair_first_native_s'] is not None:r['Z_changes']['pair_first_native_s']+=first*m.DT
    return r
partitions=[('prior270_end_to_move_entry',first,b0['before']['sample']),('entry_before_move',b0['before']['sample'],bw['before']['sample']),('move_and_target_5s_confirmation',bw['before']['sample'],ba['after']['sample']),('post_move_closed_window',ba['after']['sample'],last)]
h.require(all(lo<=hi for _,lo,hi in partitions) and sum(hi-lo for _,lo,hi in partitions)==last-first,'Invalid phase partition')
result={'source_sha256':h.sha(Path(__file__).read_bytes()),'control_source':{'path':str(source),'sha256':h.sha(source.read_bytes())},'sources':refs,'raw_sources':files,'events':er,'logger_events':lr,'known_outcome':out,'actual_writer':e,'counter_brackets':{'entry':b0,'move':bw,'after':ba},'phases':{k:desc(lo,hi) for k,lo,hi in partitions},'limits':['Known asynchronous XY ACK plus subsequent actual target and5s stationary checks establish the endpoint. No high-rate XY channel verifies the interpolated path.','All native low-current/Home observations occur with known Off1. This is not tunnelling recovery, conditioning or image-quality proof.','Original S01 failure and all previous reservations remain unchanged.']}
p=D/'S01_Home_move02_native_review.json'
with p.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(p,h.sha(p.read_bytes()))
for k,v in result['phases'].items():print(k,v['native_seconds_half_open'],'I',v['samples']['Current_pA']['min'],v['samples']['Current_pA']['max'],'Home',v['all_native_Z_Home'],'lowI',v['all_abs_current_below10pA'],'Biasother',v['Bias_not_minus1V_samples'])
