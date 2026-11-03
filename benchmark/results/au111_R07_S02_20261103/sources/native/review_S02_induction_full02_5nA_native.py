"""Offline R07 S02 actual200pA full-frame exposure under prospective5nA runtime policy. Success never assumed."""
import contextlib,hashlib,importlib.util,io,json
from pathlib import Path
D=Path(__file__).resolve().parent;B=D/'review_native_phases.py'
B_SHA='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
assert hashlib.sha256(B.read_bytes()).hexdigest()==B_SHA
s=importlib.util.spec_from_file_location('S01_induction_native_base',B);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
m.RUN=m.S/'induction_R07_S02_full02'
m.SCAN_SOURCE=m.C/'scan_full50nm_fast_R07_induction_S02_full02_once.py'
m.SCAN_SHA='fc4592c0b16257d0c6f1fab4a484681235dbcb99bbbed7be03108c4131448319'
REFERENCE_PA=200.0000026702864
OLD_RECEIPT=D/'S02_configured_idle_through451_native_receipt.json'
OLD_RECEIPT_SHA='120a80295d784da1c6f7745649abb3e99505e3ac44764c607ce5b6a739166a9c'
assert hashlib.sha256(OLD_RECEIPT.read_bytes()).hexdigest()==OLD_RECEIPT_SHA
old_receipt=json.loads(OLD_RECEIPT.read_text());prior_end=old_receipt['complete_through_index']*m.BLOCK
original_phase_plan=m.phase_plan;original_stats=m.stats


def phase_plan(*args):
    phases,brackets,why=original_phase_plan(*args)
    if phases[0][0]=='pre_Start_nominal_fixed':
        _,lo,hi=phases[0];m.require(lo==0 and prior_end<hi,'Prior fine03 receipt not before restored scan')
        phases=[('prior_R07_history_mixed_setpoints',0,prior_end),
                ('S02_idle451_end_to_induction_Start',prior_end,hi)]+phases[1:]
    return phases,brackets,why


def stats(a,lo,hi,sp,limits):
    r=original_stats(a,lo,hi,REFERENCE_PA,limits)
    if hi>lo:
        v=a[lo:hi];r['fraction_current_within_requested200pA20pct_band']=float(m.np.mean((-1.2*REFERENCE_PA<=v[:,0])&(v[:,0]<=-.8*REFERENCE_PA)))
        r['Bias_not_minus1V_samples']=int(m.np.count_nonzero(v[:,1]!=-1.))
        mask=m.np.abs(v[:,0])>5000.;edges=m.np.diff(m.np.r_[False,mask,False].astype(int));starts=m.np.flatnonzero(edges==1);ends=m.np.flatnonzero(edges==-1)
        index=int(m.np.argmax(ends-starts)) if len(starts) else None
        r['abs_I_gt5000pA_sample_descriptor']={'samples':int(mask.sum()),'groups':len(starts),'longest_samples':int(ends[index]-starts[index]) if index is not None else 0,'longest_native_s_half_open':[float((lo+starts[index])*m.DT),float((lo+ends[index])*m.DT)] if index is not None else None}
    return r


def remove_target_descriptors(r):
    r.pop('fraction_current_within_requested200pA20pct_band',None)
    for k in ['control_minus_setpoint','error_minus_control_minus_setpoint','error_minus_setpoint_minus_control']:
        r.get('algebraic_descriptors_pA',{}).pop(k,None)
    r['actual_setpoint_not_constant_in_this_history']=True


def main():
    before=json.loads((m.RUN/'before.json').read_text())['values']
    m.require(before['ZCtrl.SetpntGet']==[REFERENCE_PA*1e-12]
              and before['Scan.SpeedGet'][2:4]==[.4560000002384186,.4560000002384186]
              and before['ZCtrl.GainGet']==[3.4123519981887895e-12,8.59127176227048e-5,3.9718823785506174e-8],
              'Actual S02 induction entry settings differ')
    m.phase_plan=phase_plan;m.stats=stats
    with contextlib.redirect_stdout(io.StringIO()) as capture:m.main()
    summary=json.loads(capture.getvalue().strip());p=Path(summary['path']);r=json.loads(p.read_text())
    r['wrapper_source']={'path':str(Path(__file__)),'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    r['base_reviewer_source']={'path':str(B),'sha256':B_SHA}
    r['setpoint_reference_pA']=REFERENCE_PA
    r['scope']='Actual R07 S02 induction exposure at200pA,109.649nm/s and doubled configured time constant. The prospective runtime5nA condition does not reclassify any earlier outcome.'
    r['inputs']['prior_S02_idle451_receipt']={'path':str(OLD_RECEIPT),'sha256':OLD_RECEIPT_SHA}
    bp=m.RUN/'before.json';r['inputs']['actual_S02_induction_before']={'path':str(bp),'sha256':hashlib.sha256(bp.read_bytes()).hexdigest()}
    remove_target_descriptors(r['full'])
    for name,v in r['phases'].items():
        if name in ['prior_R07_history_mixed_setpoints','complete_archive_without_attribution']:remove_target_descriptors(v)
    for w in r['ten_second_windows']:
        if w['phase'] in ['prior_R07_history_mixed_setpoints','complete_archive_without_attribution']:remove_target_descriptors(w)
    r['limits'].extend(['The preceding R07 history includes100pA and200pA stages. Target-dependent algebra and occupancy have been removed from that history and the full-record aggregate.',
                        'The requested current during this scan is200pA. The historical minus120..minus80pA field is not the target-specific comparison. Absolute400/1000/4000/5000pA native descriptors are not instantaneous hardware protection or slow-current time-aligned triggers.',
                        'Only actual full completion plus matrix provenance can establish a complete frame. If interrupted, actual incomplete outcome and independent cleanup remain distinct.'])
    policy=m.C/'R07_scan_induction/user_scan_current_guidance_5nA_v2.json'
    m.require(m.h.sha(policy.read_bytes())=='b324208ce29f2c72817f84dc67aee3150caf303ca78b51fa5556399a29c79aab','Runtime policy changed')
    r['inputs']['prospective_scan_runtime_policy']={'path':str(policy),'sha256':m.h.sha(policy.read_bytes())}
    p.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');summary['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();print(json.dumps(summary))


if __name__=='__main__':main()
