"""Root-only read-only buffer preservation. Default plan opens no socket; no native writes exist."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1]
SOURCE=C/'scan_full50nm_fast_R07_induction_S01_once.py'
SOURCE_SHA='757d27ae1b250afdad5a9649f8837f81d7e9cd73806ab351479cb21855f86a66'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(SOURCE)!=SOURCE_SHA:raise RuntimeError('Pinned protocol/scanner context changed')
spec=importlib.util.spec_from_file_location('R07_buffer_readonly_context',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
b=m.b
EXPECTED=copy.deepcopy(m.EXPECTED)
EXPECTED['ZCtrl.GainGet']=[3.4123519981887895e-12,4.29563588113524e-05,7.943764757101235e-08]
OUT=C/'R07_scan_induction/partial_buffer_after_S01_gain_before_speed'
EVIDENCE=C/'R07_scan_induction/S01_partial_buffer_after_gain_evidence.json'
EVIDENCE_SHA='d312facd4f9a3bec8ff760c3e44ee8c421bf9e1975ddf984de0d7028f3bfd248'
GETTERS=list(dict.fromkeys(m.FAST+['Scan.FrameGet','Scan.BufferGet','Scan.SpeedGet','DataLog.StatusGet']))
FULL=list(dict.fromkeys(GETTERS+m.FROZEN))

class ReadOnlyClient(b.Client):
    def call(self,command,args=None,timeout=.5):
        args=[] if args is None else args
        allowed=(command in m.READ_ARGS and args==m.READ_ARGS[command]
                 and command in {('LockIn.ModOnOffGet' if k.startswith('LockIn.ModOnOffGet[') else k) for k in FULL})
        allowed=allowed or (command=='LockIn.ModOnOffGet' and args in ([1],[2]))
        allowed=allowed or (command=='Scan.FrameDataGrab' and args in [[c,d] for c in b.CHANNELS for d in (1,0)])
        b.require(allowed,'Read-only capture rejected unlisted command/args')
        self.connect_bound()
        return b.p.NanonisClient.call(self,command,args,timeout)

def local_evidence():
    b.require(sha(EVIDENCE)==EVIDENCE_SHA,'Partial-scan evidence changed')
    j=json.loads(EVIDENCE.read_bytes());docs={}
    for name,ref in j['refs'].items():
        p=Path(ref['path']).resolve()
        b.require(p.is_relative_to(m.ROOT) and 'win_users' not in p.parts and sha(p)==ref['sha256'],'Changed/nonlocal known-stop evidence')
        docs[name]=json.loads(p.read_bytes())
    out=docs['outcome.json']
    b.require(out['status']=='incomplete' and out['completed_frame_confirmed'] is False
              and out['execution_unknown'] is False and out['stop_acknowledged'] is True
              and out['withdraw_acknowledged'] is True and out['withdraw_Off1_home_confirmed'] is True,
              'Require known stopped/withdrawn partial scan, never unknown writer')
    for claim,ack,command,args in [('failed_owned_scan_stop.claim','failed_owned_scan_stop_ack.json','Scan.Action',[1,0]),
                                   ('failure_withdraw.claim','failure_withdraw_ack.json','ZCtrl.Withdraw',[1,2000])]:
        b.require(docs[claim]['command']==command and docs[claim]['args']==args
                  and docs[ack]['command']==command and docs[ack]['values']==[] and not docs[ack].get('warning'),
                  'Known zero-error stop/withdraw ACK required')
    manifest=docs['manifest.json']
    b.require(manifest['event_id']=='induction_R07_S01_full' and manifest['source_sha256']==SOURCE_SHA
              and manifest['recording_segment_id']=='R07','Wrong incomplete S01 identity')
    claim,ack=docs['scan_start.claim'],docs['scan_start_ack.json']
    b.require(claim['command']==ack['command']=='Scan.Action' and claim['args']==[0,0]
              and ack['values']==[] and not ack.get('warning') and claim['source_sha256']==SOURCE_SHA,
              'Original S01 Start/ACK identity differs')
    gain=docs['gain_outcome.json'];gain_manifest=docs['gain_manifest.json']
    b.require(gain['status']=='Home_configuration_knownACK_exact_readback' and gain['stage']=='gain'
              and gain['event_id']=='recovery_R07_S01_H01_gain' and gain['writer_outcome_unknown'] is False
              and gain['feedback_remained_Off1'] is True and gain['sampled_post_stable_s']>=5.
              and gain['acknowledged_writers']==['ZCtrl.GainSet'], 'Known gain-only recovery completion required')
    b.require(gain_manifest['source_sha256']=='f8c16650b97f9296b5ed59dbde86e44d889474992ae70f71dcb611e46770bafd'
              and gain_manifest['event_id']=='recovery_R07_S01_H01_gain' and gain_manifest['recording_segment_id']=='R07',
              'Exact gain recovery identity required')
    gc,ga=docs['gain_configuration_0.claim'],docs['gain_configuration_0_ack.json']
    b.require(gc['command']==ga['command']=='ZCtrl.GainSet' and gc['args']==EXPECTED['ZCtrl.GainGet']
              and gc['source_sha256']==gain_manifest['source_sha256'] and ga['values']==[] and not ga.get('warning'),
              'Actual original-gain claim and known ACK required')
    b.require(gain['monotonic_ns']>=out['monotonic_ns'] and docs['gain_logger_ready_bound.json']==docs['R07_READY'],
              'Gain recovery chronology/recording differs')
    gain_after=docs['gain_after.json']['values']
    for key in m.FROZEN:
        b.require(gain_after[key]==EXPECTED[key],'Gain recovery readback changed: '+key)
    b.require(gain_after['ZCtrl.OnOffGet']==[0] and gain_after['ZCtrl.StatusGet']==[1]
              and gain_after['Scan.StatusGet']==[0]
              and gain_after['FolMe.XYPosGet']==docs['withdraw_confirmed.json']['values']['FolMe.XYPosGet'],
              'Gain recovery must remain Off1, stationary and scan0')
    fresh=docs['fresh096']
    b.require(fresh['start']['monotonic_ns']>=gain['monotonic_ns']
              and fresh['end']['monotonic_ns']>=fresh['start']['monotonic_ns'],
              'Fresh096 must follow known gain recovery')
    # An unused Current.CalibrGet warning is preserved in the source snapshot.
    # Every getter used by this capture must be available and error-free.
    b.require(not any(k in fresh.get('errors',{}) for k in FULL),'Required fresh096 getter failed')
    state_guard(fresh['values'],docs,True)
    b.require(not (m.sb.LOGGER_DIR/'outcome.json').exists(),'R07 logger ended')
    return docs

def state_guard(v,docs,full=False):
    b.require(v['ZCtrl.OnOffGet']==[0] and v['ZCtrl.StatusGet']==[1] and v['Scan.StatusGet']==[0],
              'Capture requires known Off1 and scan0')
    b.require(abs(v['ZCtrl.ZPosGet'][0]-EXPECTED['ZCtrl.HomePropsGet'][1])<1e-12
              and b.finite(v['Current.Get'][0]) and abs(v['Current.Get'][0])<10e-12,'Require withdrawn Home/low current')
    for k in ['AutoApproach.OnOffGet','BiasSpectr.StatusGet','ZSpectr.StatusGet','FolMe.PSOnOffGet']:
        b.require(v[k]==[0],'Concurrent native action during buffer capture')
    for k in ['Bias.Get','ZCtrl.SetpntGet','SafeTip.OnOffGet','Scan.FrameGet','Scan.BufferGet','Scan.SpeedGet']:
        b.require(v[k]==EXPECTED[k],'Buffer/config identity changed: '+k)
    b.require(v['FolMe.XYPosGet']==docs['withdraw_confirmed.json']['values']['FolMe.XYPosGet'],'XY changed after known partial stop')
    status=v['DataLog.StatusGet']
    b.require(len(status)==10 and status[1]==docs['R07_READY']['native_start_identity'] and not status[6],
              'R07 native logger identity changed/stopped')
    if full:
        for k in m.FROZEN:b.require(v[k]==EXPECTED[k],'Frozen config changed: '+k)

def capture(client,store,docs):
    def snapshot(label,full=False):
        t=time.monotonic();v={}
        for k in FULL if full else GETTERS:
            b.require(time.monotonic()-t<=2.,'Read-only snapshot group exceeded2s')
            command='LockIn.ModOnOffGet' if k.startswith('LockIn.ModOnOffGet[') else k
            args=[int(k.split('[')[1][:-1])] if k.startswith('LockIn.ModOnOffGet[') else m.READ_ARGS.get(k,[])
            response=client.call(command,args,.5);b.require(not response.get('warning'),'Native getter warning')
            v[k]=response['values']
        store.save(label+'.json',{'values':v,'duration_s':time.monotonic()-t,'sequential_not_atomic':True})
        state_guard(v,docs,full)
        b.require(time.monotonic()-t<=2.,'Read-only snapshot group exceeded2s')
        return v
    snapshot('before',True);records=[]
    for channel in b.CHANNELS:
        for direction in (1,0):
            snapshot(f'before_{channel}_{direction}')
            response=client.call('Scan.FrameDataGrab',[channel,direction],2.)
            b.require(not response.get('warning'),'Native FrameDataGrab warning')
            n,name,nr,nc,matrix,scan_direction=response['values'];body=store.last_response_body
            b.require(nr==nc==240 and matrix['shape']==[240,240] and len(matrix['values'])==57600,'Unexpected buffer dimensions')
            offset=12+n;raw=body[offset:offset+57600*4]
            b.require(len(raw)==57600*4 and len(body)==offset+len(raw)+12,'Unexpected matrix wire size')
            b.require(scan_direction==0 and struct.unpack('>IIi',body[-12:])==(0,0,0),'Unexpected matrix direction/status trailer')
            numbers=struct.unpack('>57600f',raw);finite=[x for x in numbers if b.finite(x)]
            rec={**b.stamp(),'channel_index':channel,'data_direction':direction,'scan_direction':scan_direction,
                 'channel_name':name,'rows':nr,'columns':nc,'finite_values':len(finite),'total_values':57600,
                 'minimum_finite':min(finite) if finite else None,'maximum_finite':max(finite) if finite else None,
                 'matrix':store.save_bytes(f'frames/channel_{channel}_{direction}.f32be',raw),
                 'wire_sequence':store.sequence,'format':'Unchanged IEEE754 float32 big-endian bytes',
                 'buffer_can_mix_current_and_prior_scan':True,'current_scan_row_mask':None,
                 'native_SXM_or_completed_frame':False,'acquisition_time_or_native_frame_id':None}
            store.save(f'frames/channel_{channel}_{direction}.json',rec);records.append(rec)
            snapshot(f'after_{channel}_{direction}')
    snapshot('after',True)
    return records

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--execute',action='store_true');ap.add_argument('--source-sha256');args=ap.parse_args()
    if not args.execute:
        print(json.dumps({'scope':'Preserve six potentially mixed S01 partial scan buffers at known200pA/2speed/originalgain Off1Home after gain restore, readonly only','output':str(OUT),
                          'commands':FULL+['Scan.FrameDataGrab(0,30,89 x F/B)'],'native_writes':[],
                          'known_Off1_Home_and_scan0_required':True,'full_frame_claim':False,'execution':False}));return 0
    b.require(args.source_sha256==sha(Path(__file__)),'Explicit exact reader source hash required')
    docs=local_evidence();b.require(not OUT.exists(),'New immutable capture output required')
    store=b.Store(OUT);client=ReadOnlyClient(store);result={'status':'capture_failed','native_writes':0,'completed_scan':False,'mixed_buffer_possible':True,'current_scan_row_mask':None}
    try:
        store.save('manifest.json',{'source_sha256':sha(Path(__file__)),'known_stop_evidence':{'path':str(EVIDENCE),'sha256':EVIDENCE_SHA},'R07_READY':json.loads(EVIDENCE.read_bytes())['refs']['R07_READY'],'limitations':'Every returned plane may mix old and new rows. The interrupted S01 UI label is not a completed native frame identity. Baseline full214 remains separate. Raw nonfinite samples retained. No automatically valid row mask.'})
        result['frames']=capture(client,store,docs);result['status']='six_raw_buffers_preserved_readonly'
    except BaseException as exc:result['error']=type(exc).__name__+': '+str(exc)
    finally:client.close();store.save('outcome.json',{**b.stamp(),**result})
    print(json.dumps({k:v for k,v in result.items() if k!='frames'}));return 0 if result['status']=='six_raw_buffers_preserved_readonly' else 1
if __name__=='__main__':raise SystemExit(main())
