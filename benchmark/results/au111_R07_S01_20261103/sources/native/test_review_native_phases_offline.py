"""Local provenance and phase-accounting regression for the R07 native reviewer."""
import ast
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
from unittest.mock import patch

D = Path(__file__).resolve().parent
C = D.parent
SOURCE = D / 'review_native_phases.py'
checks = []
attempts = []

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def blocked(*args, **kwargs):
    attempts.append('network')
    raise AssertionError('Network disabled')

with contextlib.ExitStack() as sandbox:
    for name in ('socket', 'create_connection', 'getaddrinfo'):
        sandbox.enter_context(patch.object(socket, name, blocked))
    spec = importlib.util.spec_from_file_location('r07_native_review_local', SOURCE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    parent = (C/'R06_diagnostic/review_native_phases.py').read_text().replace('R06','R07').replace('logger_06','logger_07').replace('segment06','segment07')
    def functions(text):
        return {n.name:ast.dump(n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    old,new=functions(parent),functions(SOURCE.read_text())
    assert all(new[k] == v for k,v in old.items() if k != 'main')
    checks.append('All parser, bracket, phase and numerical functions match executed R06 after identity labels')
    assert sha(C/'logger_fullcycle_segment07_observe_once.py') == m.LOGGER_SHA
    assert sha(m.SCAN_SOURCE) == m.SCAN_SHA
    for name, digest in m.LOGGER_IDENTITY_PINS.items():
        assert sha(m.L/name) == digest
    ready=json.loads((m.L/'READY.json').read_bytes())
    manifest=json.loads((m.RUN/'manifest.json').read_bytes())
    bound=json.loads((m.RUN/'logger_ready_bound.json').read_bytes())
    assert ready==bound and ready['native_start_identity']=='2026/11/3 13:45:34'
    assert manifest['event_id']=='baseline_segment07_full' and manifest['source_sha256']==m.SCAN_SHA
    checks.append('Actual R07 sources, immutable identity and running baseline manifest bind correctly')
    receipt=json.loads((m.S/'native_receipt_R07.json').read_bytes())
    assert receipt['recording_segment_id']=='R07' and receipt['native_start_identity']==ready['native_start_identity']
    assert receipt['complete_through_index']>=9
    for index in range(1,10):
        name=f'{m.PREFIX}{index:05d}.dat'
        record=receipt['files'][name]
        path=m.h.local(m.S/'native_R07'/name)
        raw=path.read_bytes()
        assert sha(path)==record['sha256'] and len(raw)==record['bytes']
        assert record['rows']==25000 and m.h.parse_block(raw,25000).shape==(25000,6)
    checks.append('First nine actual locally archived R07 blocks pass SHA, 0.5ms header, six-column finite parsing')
    anchors=[{'monotonic_ns':i*10**9,'sample':i*2000,'native_s':float(i)} for i in range(26)]
    start={'command':'Scan.Action','args':[0,0],'source_sha256':m.SCAN_SHA,'monotonic_ns':10*10**9}
    ack={'values':[],'warning':''}
    rows=[{'kind':'running_observed','monotonic_ns':10_200_000_000,'duration_s':.1,'values':{'Scan.StatusGet':[1]}},
          {'kind':'scan_guard','monotonic_ns':19_300_000_000,'duration_s':.1,'values':{'Scan.StatusGet':[1]}}]
    outcome={'status':'completed','completed_frame_confirmed':True,'end_event':{'monotonic_ns':19_800_000_000}}
    phases,brackets,why=m.phase_plan(outcome,rows,start,ack,anchors,50000)
    assert why=='known_completed_native_WaitEnd' and set(brackets)=={'start','end'}
    assert phases[0][1]==0 and phases[-1][2]==50000
    assert all(phases[i][2]==phases[i+1][1] for i in range(len(phases)-1))
    assert sum(hi-lo for _,lo,hi in phases)==50000
    checks.append('Synthetic completed frame partitions all rows once including before and after')
    phases,brackets,why=m.phase_plan(outcome,rows,start,ack,anchors[:15],50000)
    assert why=='missing native counter bracket for end'
    checks.append('Missing ending counter evidence preserves unattributed record')
    phases,brackets,why=m.phase_plan(outcome,rows,start,None,anchors,50000)
    assert why=='scanner Start/ACK missing or ambiguous'
    checks.append('Unknown Start ACK cannot produce a complete attributed frame')
    a=m.np.zeros((60000,6));a[:,0]=-100;a[:,1]=-1;a[:,2]=-100;a[50001,0]=-1000
    stats=m.stats(a,50000,60000,100,[-123,123])
    assert stats['minimum_I_location']=={'block':3,'row_zero_based':1}
    assert stats['abs_I_sample_exceedances_pA']['1000']['longest_native_seconds_half_open']==[25.0005,25.001]
    checks.append('Absolute block and threshold event time are preserved for a later phase window')
assert not attempts
out={'passed':True,'source_sha256':sha(SOURCE),'checks':checks,'network_attempts':attempts,
     'scope':'Only existing local files, in-memory phase fixtures and arithmetic. Main analysis entry not run before actual known completion.'}
p=D/'review_native_phases_offline_audit.json'
with p.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(p,sha(p),len(checks))
