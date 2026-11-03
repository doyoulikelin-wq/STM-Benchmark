#!/usr/bin/env python3
"""Root-invoked SMB read/local archive only; default plan performs no share access.
Exactly session_02/logger_07 R07. No TCP/control/CUA imports or device commands.
Two independently saved stopped readbacks and a frozen source are required.
"""
import argparse,datetime,hashlib,io,json,math,os,re,struct
from pathlib import Path,PureWindowsPath
import numpy as np
C=Path(__file__).resolve().parent;ROOT=C.parent;SESSION=ROOT/'session_02';LOGGER=SESSION/'logger_07'
LOGGER_SOURCE=C/'logger_fullcycle_segment07_observe_once.py'
LOGGER_SHA = '1e127682ad19e005660ff2d2d82ef132d468d2e3e786fd6afa15cbb4650967d0'
SHARE=ROOT.parent/'stm_tip_benchmark_goal_20261030/win_users/Public/stm-benchmark-goal-20261030/native'
COLS=['Current (A)','Bias (V)','Z (m)','Z Control signal (A)','Z Error signal (A)','Z SafeTip signal (A)']
DT=.0005;BLOCK_ROWS=25000
PARENT=C/'archive_audit_terminal_R06.py'
PARENT_SHA = '9b43b40de4585c94777fad345eba314ed6f1a5da55e17edf62ef20d64e91b1ff'
ROOT_REPORTED_OWNER_PID = 74698
EXPECTED_START = '2026/11/3 13:45:34'
EXPECTED_BASENAME='dl_goal30_FIVE1102_SESSION_02_R07'
IDENTITY_PINS = {'READY.json': 'c1c50e68c637cba2e77e6292ab84d764aec7af0475caf7e4aa4c36ba13acc3b7', 'manifest.json': '3352882ed403b994728a8105553e424f65f26616d198ba88ee43e194dd368ecf', 'start.claim': 'a5e32acb30c306329267c0a3a90fa169dbd7be92342cd6bd8a13baf4dba36df7'}

def require(ok,msg):
    if not ok:raise RuntimeError(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}
def local(p):
    p=Path(p).absolute();require(p==p.resolve() and p.is_relative_to(ROOT) and 'win_users' not in p.parts and '/Volumes/' not in str(p),'Exact batch-local path required');return p

def store_new(p,raw):
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    require(p.read_bytes()==raw,'New local file reread differs')

def save(p,j):store_new(p,(json.dumps(j,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode());return ref(p)

def status_decode(body):
    off=0;out=[]
    def num(fmt):
        nonlocal off
        v=struct.unpack_from(fmt,body,off)[0];off+=struct.calcsize(fmt);return v
    def string():
        nonlocal off
        n=num('>i');require(n>=0 and off+n<=len(body),'Malformed string');out.extend([n,body[off:off+n].decode()]);off+=n
    string();out.extend([num('>H'),num('>H'),num('>f')]);string();string();out.append(num('>i'))
    require(body[off:]==bytes(8),'Nonzero/malformed native response error suffix');return out

def exchange(directory,event):
    require(event.get('status')=='ok' and not event.get('warning'),'Unknown/error exchange cannot prove completion')
    for name in ['request_header','request_body','response_header','response_body']:
        e=event[name];p=local(directory/e['path']);require(p.is_relative_to(directory),'Wire path escaped record')
        raw=p.read_bytes();require(len(raw)==e['bytes'] and sha(raw)==e['sha256'],'Wire byte/hash mismatch')
    return (directory/event['response_body']['path']).read_bytes()

def snapshot(p,digest):
    p=local(p);raw=p.read_bytes();require(sha(raw)==digest,'Stop snapshot SHA mismatch');v=json.loads(raw)
    events=[json.loads(line) for line in (p.parent/'events.jsonl').read_text().splitlines() if line.strip()]
    calls=[e for e in events if e.get('kind')=='tcp_exchange']
    require(all(e['command'].endswith('Get') for e in calls),'Stop evidence contains a non-read command')
    status=[e for e in calls if e['command']=='DataLog.StatusGet'];require(len(status)==1,'Exactly one native status exchange per full snapshot required')
    require(status_decode(exchange(p.parent,status[0]))==v['values']['DataLog.StatusGet'],'Native wire differs from snapshot')
    return v

def terminal_evidence(a,ah,b,bh):
    require(sha(PARENT.read_bytes())==PARENT_SHA,'Frozen terminal archive parent changed')
    for name,digest in IDENTITY_PINS.items():require(sha((LOGGER/name).read_bytes())==digest,'Actual R07 immutable identity changed: '+name)
    require(sha(LOGGER_SOURCE.read_bytes())==LOGGER_SHA,'R07 logger source changed')
    ready=json.loads((LOGGER/'READY.json').read_bytes());start=json.loads((LOGGER/'start.claim').read_bytes());manifest=json.loads((LOGGER/'manifest.json').read_bytes());outcome=json.loads((LOGGER/'outcome.json').read_bytes())
    for j in [ready,start,manifest,outcome]:require(j['session_id']=='session_02' and j['recording_segment_id']=='R07' and j['source_path']==str(LOGGER_SOURCE) and j['source_sha256']==LOGGER_SHA and j['role']=='fullcycle_native_logger','R07 source/session/segment/role changed')
    require(ready['ready'] is True and Path(ready['output_directory']).resolve()==LOGGER and ready['native_duration_s']==21600,'R07 READY mismatch')
    require(ready['start_claim']['sha256']==sha((LOGGER/'start.claim').read_bytes()) and start['command']=='DataLog.Start' and start['args']==[],'Start claim mismatch')
    claim_path=Path(ready['start_claim']['path']);claim_path=claim_path if claim_path.is_absolute() else LOGGER/claim_path
    require(claim_path.resolve()==LOGGER/'start.claim','Start claim path is not the exact R07 logger claim')
    require(ready['native_start_identity']==EXPECTED_START and ready['basename']==EXPECTED_BASENAME,'Different R07 actual Start/basename')
    profile=ready['profile'];require(profile['DataLog.ChsGet']==[6,[0,24,30,98,99,100]] and profile['DataLog.PropsGet'][:5]==[1,6,0,0.,1],'Wrong native recording profile')
    require(profile['Util.RTFreqGet']==[20000.] and profile['Util.RTOversamplGet']==[10] and profile['Util.AcqPeriodGet']==[.019999999552965164],'Wrong timing profile')
    av,bv=snapshot(a,ah),snapshot(b,bh);x=av['values']['DataLog.StatusGet'];y=bv['values']['DataLog.StatusGet']
    require(Path(a)!=Path(b) and len(x)==10 and x==y and y[1]==ready['native_start_identity'] and bool(y[6]),'Need two same full stopped statuses from owned start')
    gap=(bv['start']['monotonic_ns']-av['end']['monotonic_ns'])/1e9;require(gap>=1.,'Stopped readbacks less than1s apart')
    basename=ready['basename'];require(re.fullmatch(r'[A-Za-z0-9_]+',basename) is not None,'Unreviewed basename characters')
    match=re.fullmatch(re.escape(basename)+r'(\d{5})\.dat',PureWindowsPath(y[8]).name);require(match is not None,'Terminal filename does not match READY basename')
    last=int(match[1]);counter=y[9];require(1<=last<=1000 and type(counter) is int and 0<=counter<=BLOCK_ROWS,'Unreviewed terminal index/counter')
    elapsed=y[2]*3600+y[3]*60+y[4];require(math.isfinite(elapsed) and elapsed>0,'Invalid final native elapsed')
    events=[json.loads(line) for line in (LOGGER/'events.jsonl').read_text().splitlines() if line.strip()]
    writes=[e for e in events if e.get('kind')=='tcp_exchange' and not e['command'].endswith('Get')]
    require([e['command'] for e in writes] in (['DataLog.ChsSet','DataLog.PropsSet','DataLog.Start'],['DataLog.ChsSet','DataLog.PropsSet','DataLog.Start','DataLog.Stop']),'Unexpected writer count/order in R07 recorder')
    require(exchange(LOGGER,writes[2])==bytes(8),'Start not zero-error acknowledged')
    stop=[e for e in writes if e['command']=='DataLog.Stop'];stop_ack=False
    if stop and stop[0].get('status')=='ok' and not stop[0].get('warning'):stop_ack=exchange(LOGGER,stop[0])==bytes(8)
    return {'recording_segment_id':'R07','root_reported_owner_pid':ROOT_REPORTED_OWNER_PID,'pid_not_independently_verified_or_controlled':True,'immutable_identity_pins':IDENTITY_PINS,'logger_directory':str(LOGGER),'logger_source':ref(LOGGER_SOURCE),'ready':ready,'terminal_raw':y,'terminal_index':last,'terminal_rows':counter,'nominal_elapsed':elapsed,'snapshot_refs':[ref(Path(a)),ref(Path(b))],
        'snapshot_gap_s':gap,'logger_refs':{name:ref(LOGGER/name) for name in ['READY.json','start.claim','manifest.json','outcome.json','events.jsonl']},
        'original_outcome':outcome,'writer_names':[e['command'] for e in writes],'DataLog_Stop_acknowledged':stop_ack,'independent_native_stop_confirmed':True,
        'termination_label':'explicit_Stop_recorded' if stop else 'no_Stop_writer_recorded; native_timed_end_candidate',
        'qualification':'Full stopped readbacks reconcile the native terminal identity. Original outcome is preserved. No junction or return success inferred.'}

def parse(raw,expected_rows):
    lines=raw.decode('ascii').splitlines();k=lines.index('[DATA]')
    require(sum(x=='[DATA]' for x in lines)==1 and lines[k+1].split('\t')==COLS,'Native six-channel header changed')
    period=[x.split('\t',1)[1] for x in lines[:k] if x.startswith('Sample Period (ms)\t')]
    require(len(period)==1 and float(period[0])==.5,'Need exact header0.5ms, not an analog bandwidth claim')
    rows=[s for s in lines[k+2:] if s.strip()];require(len(rows)==expected_rows and all(len(s.split('\t'))==6 for s in rows),'Native block row/column mismatch')
    data=np.loadtxt(io.StringIO('\n'.join(rows)),delimiter='\t',ndmin=2) if rows else np.empty((0,6))
    require(data.shape==(expected_rows,6) and np.isfinite(data).all(),'Nonfinite or malformed native samples')
    return data

def archive(evidence,output,source=SHARE):
    output=local(output);require(not output.exists(),'New audit output only; never overwrite failed or completed audit')
    source=Path(source);require(source==SHARE,'Only reviewed native source directory allowed')
    output.mkdir();dest=SESSION/'native_R07';dest.mkdir(exist_ok=True)
    save(output/'terminal_evidence.json',evidence)
    prior=SESSION/'native_receipt_R07.json'
    if prior.exists():store_new(output/'incremental_receipt_at_start.json',prior.read_bytes())
    files={};total=0;mins=np.full(6,np.inf);maxs=np.full(6,-np.inf);floor=0;levels={str(x):0 for x in [400,1000,4000]};newfiles=0
    for index in range(1,evidence['terminal_index']+1):
        name=evidence['ready']['basename']+f'{index:05d}.dat';p=source/name
        first=p.read_bytes();second=p.read_bytes();require(len(first)==len(second) and sha(first)==sha(second),'Native source changed between two reads: '+name)
        expected=evidence['terminal_rows'] if index==evidence['terminal_index'] else BLOCK_ROWS
        values=parse(first,expected);target=dest/name
        if target.exists():require(target.read_bytes()==first,'Previously archived local bytes differ: '+name)
        else:store_new(target,first);newfiles+=1
        total+=len(values)
        if len(values):mins=np.minimum(mins,values.min(axis=0));maxs=np.maximum(maxs,values.max(axis=0))
        floor+=int(np.count_nonzero(np.abs(values[:,0]+9.9994768e-9)<=1e-18))
        for level in levels:levels[level]+=int(np.count_nonzero(np.abs(values[:,0])>=float(level)*1e-12))
        files[name]={'local_path':str(target),'source_path':str(p),'sha256':sha(first),'bytes':len(first),'rows':len(values),'finite_scalars':int(values.size),'two_source_reads_same_sha':True,'local_reread_matches':True,'terminal':index==evidence['terminal_index']}
    require(total>0 and abs(evidence['nominal_elapsed']/2-total*DT)<=1e-5,'Rows differ from observed2x native elapsed convention; do not guess missing terminal rows')
    receipt={'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':ref(Path(__file__)),'session_id':'session_02','recording_segment_id':'R07','files':files,'native_start_identity':evidence['terminal_raw'][1],'native_stop_observed':evidence['terminal_raw'][6],
        'complete_through_index':evidence['terminal_index'],'all_blocks_including_last_archived':True,'all_sha_bytes_rows_header_columns_finite_verified':True,'terminal_rows':evidence['terminal_rows'],'total_rows_per_channel':total,'dt_s':DT,'terminal_evidence':ref(output/'terminal_evidence.json')}
    save(output/'receipt.json',receipt)
    result={'scope':'Complete R07 native archive through independently confirmed terminal. Root-only source read, local new writes; no device commands.',
        'receipt':ref(output/'receipt.json'),'source':ref(Path(__file__)),'block_count':len(files),'new_files':newfiles,'total_rows_per_channel':total,'finite_scalars':total*6,'sample_header_dt_s':DT,'row_duration_s':total*DT,
        'native_nominal_elapsed_units':evidence['nominal_elapsed'],'native_half_elapsed_minus_row_duration_s':evidence['nominal_elapsed']/2-total*DT,'all_expected_indices_sha_bytes_rows_header_columns_finite_verified':True,
        'per_channel_min':dict(zip(COLS,mins.tolist())),'per_channel_max':dict(zip(COLS,maxs.tolist())),'abs_I_ge_pA_samples':levels,'historical_software_floor_matching_samples':floor,
        'qualification':['The stored0.5ms interval is not the analog bandwidth or true-peak bound.','Whole-record extrema mix preparations, interventions and scans; no phase attribution or image-quality verdict is implied.','No missing numbered block detected; this does not prove hardware timestamp/analog no-drop behavior.','Original outcome and incremental receipt are not overwritten. Segment gap/new baseline must be recorded separately.']}
    save(output/'review.json',result);return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--execute',action='store_true');ap.add_argument('--source-sha256')
    for n in ['snapshot-a','snapshot-b']:ap.add_argument('--'+n,type=Path);ap.add_argument('--'+n+'-sha256')
    ap.add_argument('--output',type=Path,default=C/'R07_terminal_native_review');a=ap.parse_args()
    if not a.execute:
        print(json.dumps({'plan_only':True,'socket_opened':False,'share_accessed':False,'session':'session_02','recording_segment':'R07','root_reported_owner_pid':ROOT_REPORTED_OWNER_PID,'pid_is_provenance_only':True,'native_start_identity':EXPECTED_START,'basename':EXPECTED_BASENAME,'immutable_identity_pins':IDENTITY_PINS,'parent_source_sha256':PARENT_SHA,'logger_source_sha256':LOGGER_SHA,'source_directory':str(SHARE),'output':str(a.output),'requires':'two complete hash-bound read-only snapshots with same full stopped status>=1s; known source/start/READY; dynamic terminal index/rows; double source SHA read + local xb/reread +6channel finite0.5ms audit','device_commands':[]},indent=2));return 0
    require(a.source_sha256==sha(Path(__file__).read_bytes()),'Executing script SHA mismatch')
    require(all([a.snapshot_a,a.snapshot_b,a.snapshot_a_sha256,a.snapshot_b_sha256]),'Both independent snapshot paths/hashes required')
    e=terminal_evidence(a.snapshot_a,a.snapshot_a_sha256,a.snapshot_b,a.snapshot_b_sha256)
    result=archive(e,a.output);print(json.dumps({'review':str(a.output/'review.json'),'sha256':ref(a.output/'review.json')['sha256'],'blocks':result['block_count'],'rows':result['total_rows_per_channel'],'seconds':result['row_duration_s']},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
