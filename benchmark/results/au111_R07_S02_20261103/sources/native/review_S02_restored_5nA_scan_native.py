"""Offline R07 restored100pA full-frame attempt under prospective5nA runtime policy. Success never assumed."""
import argparse,contextlib,hashlib,importlib.util,io,json,sys
from pathlib import Path
D=Path(__file__).resolve().parent;B=D/'review_native_phases.py'
B_SHA='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
assert hashlib.sha256(B.read_bytes()).hexdigest()==B_SHA
s=importlib.util.spec_from_file_location('S01_induction_native_base',B);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
m.RUN=m.S/'after_R07_S02_restored_full'
m.SCAN_SOURCE=m.C/'scan_full50nm_fast_R07_after_S02_full02_restored_once.py'
m.SCAN_SHA='187c80bf513083aa0822e516fd6ce338e24c0b23b883d6f7d2f86455d2d90396'
REFERENCE_PA=100.0000013351432
OLD_RECEIPT=OLD_RECEIPT_SHA=STAGE_AUDIT_REF=prior_end=None
original_phase_plan=m.phase_plan;original_stats=m.stats


def phase_plan(*args):
    phases,brackets,why=original_phase_plan(*args)
    if phases[0][0]=='pre_Start_nominal_fixed':
        _,lo,hi=phases[0];m.require(lo==0 and prior_end<hi,'Prior fine03 receipt not before restored scan')
        phases=[('prior_R07_history_mixed_setpoints',0,prior_end),
                ('S02_restore_speed_receipt_end_to_validation_Start',prior_end,hi)]+phases[1:]
    return phases,brackets,why


def stats(a,lo,hi,sp,limits):
    r=original_stats(a,lo,hi,REFERENCE_PA,limits)
    if hi>lo:
        v=a[lo:hi];r['fraction_current_within_requested100pA20pct_band']=float(m.np.mean((-1.2*REFERENCE_PA<=v[:,0])&(v[:,0]<=-.8*REFERENCE_PA)))
        r['Bias_not_minus1V_samples']=int(m.np.count_nonzero(v[:,1]!=-1.))
        mask=m.np.abs(v[:,0])>5000.;edges=m.np.diff(m.np.r_[False,mask,False].astype(int));starts=m.np.flatnonzero(edges==1);ends=m.np.flatnonzero(edges==-1)
        index=int(m.np.argmax(ends-starts)) if len(starts) else None
        r['abs_I_gt5000pA_sample_descriptor']={'samples':int(mask.sum()),'groups':len(starts),'longest_samples':int(ends[index]-starts[index]) if index is not None else 0,'longest_native_s_half_open':[float((lo+starts[index])*m.DT),float((lo+ends[index])*m.DT)] if index is not None else None}
    return r


def remove_target_descriptors(r):
    r.pop('fraction_current_within_requested100pA20pct_band',None)
    for k in ['control_minus_setpoint','error_minus_control_minus_setpoint','error_minus_setpoint_minus_control']:
        r.get('algebraic_descriptors_pA',{}).pop(k,None)
    r['actual_setpoint_not_constant_in_this_history']=True


def main():
    global OLD_RECEIPT,OLD_RECEIPT_SHA,STAGE_AUDIT_REF,prior_end
    custom=argparse.ArgumentParser(add_help=False)
    custom.add_argument('--prior-receipt',type=Path,required=True)
    custom.add_argument('--prior-receipt-sha256',required=True)
    custom.add_argument('--prior-stage-audit',type=Path,required=True)
    custom.add_argument('--prior-stage-audit-sha256',required=True)
    selected,remaining=custom.parse_known_args();sys.argv=[sys.argv[0]]+remaining
    OLD_RECEIPT=m.h.local(selected.prior_receipt);OLD_RECEIPT_SHA=selected.prior_receipt_sha256
    m.require(m.h.sha(OLD_RECEIPT.read_bytes())==OLD_RECEIPT_SHA,'Chosen prior receipt changed')
    rr=json.loads(OLD_RECEIPT.read_text())
    m.require(rr['recording_segment_id']=='R07' and rr['native_start_identity']=='2026/11/3 13:45:34','Wrong prior recorder')
    speed,STAGE_AUDIT_REF=m.h.read_json(selected.prior_stage_audit)
    m.require(STAGE_AUDIT_REF['sha256']==selected.prior_stage_audit_sha256
              and speed['source_sha256']=='aa4584c37fd905ae5b97e8f3b7d368cd65a6d66b3164e81513f4b77f16ecf766'
              and speed['stage']=='restore_speed'
              and speed['known_outcome']['status']=='configured_and_exact_readback_verified','Actual complete restore-speed audit required')
    for record in speed['native_sources']:
        meta=rr['files'][Path(record['path']).name]
        m.require(meta['sha256']==record['sha256'] and meta['rows']==record['rows'],'Prior restore-speed native prefix changed')
    prior_end=rr['complete_through_index']*m.BLOCK
    m.require(speed['boundaries']['after']['after']['sample']<=prior_end,'Prior receipt misses actual restoration end')
    before=json.loads((m.RUN/'before.json').read_text())['values']
    m.require(before['ZCtrl.SetpntGet']==[REFERENCE_PA*1e-12]
              and before['Scan.SpeedGet'][2:4]==[.9120000004768372,.9120000004768372]
              and before['ZCtrl.GainGet']==[3.4123519981887895e-12,4.29563588113524e-5,7.943764757101235e-8],
              'Actual restored scan entry settings differ')
    m.phase_plan=phase_plan;m.stats=stats
    with contextlib.redirect_stdout(io.StringIO()) as capture:m.main()
    summary=json.loads(capture.getvalue().strip());p=Path(summary['path']);r=json.loads(p.read_text())
    r['wrapper_source']={'path':str(Path(__file__)),'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    r['base_reviewer_source']={'path':str(B),'sha256':B_SHA}
    r['setpoint_reference_pA']=REFERENCE_PA
    r['scope']='Actual R07 post-S02 restored-condition scan at100pA,54.8246nm/s and original configured time constant. The prospective runtime5nA condition does not reclassify any earlier outcome.'
    r['inputs']['prior_S02_restore_speed_receipt']={'path':str(OLD_RECEIPT),'sha256':OLD_RECEIPT_SHA}
    r['inputs']['actual_restore_speed_native_audit']=STAGE_AUDIT_REF
    bp=m.RUN/'before.json';r['inputs']['actual_restored_scan_before']={'path':str(bp),'sha256':hashlib.sha256(bp.read_bytes()).hexdigest()}
    remove_target_descriptors(r['full'])
    for name,v in r['phases'].items():
        if name in ['prior_R07_history_mixed_setpoints','complete_archive_without_attribution']:remove_target_descriptors(v)
    for w in r['ten_second_windows']:
        if w['phase'] in ['prior_R07_history_mixed_setpoints','complete_archive_without_attribution']:remove_target_descriptors(w)
    r['limits'].extend(['The preceding R07 history includes100pA and200pA stages. Target-dependent algebra and occupancy have been removed from that history and the full-record aggregate.',
                        'The requested current during this scan is100pA. Absolute400/1000/4000/5000pA native descriptors are not instantaneous hardware protection or slow-current time-aligned triggers.',
                        'Only actual full completion plus matrix provenance can establish a complete frame. If interrupted, actual incomplete outcome and independent cleanup remain distinct.'])
    policy=m.C/'R07_scan_induction/user_scan_current_guidance_5nA_v2.json'
    m.require(m.h.sha(policy.read_bytes())=='b324208ce29f2c72817f84dc67aee3150caf303ca78b51fa5556399a29c79aab','Runtime policy changed')
    r['inputs']['prospective_scan_runtime_policy']={'path':str(policy),'sha256':m.h.sha(policy.read_bytes())}
    p.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');summary['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();print(json.dumps(summary))


if __name__=='__main__':main()
