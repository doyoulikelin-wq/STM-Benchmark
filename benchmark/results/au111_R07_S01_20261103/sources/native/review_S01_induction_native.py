"""Offline R07 S01 actual200pA exposure. Full-frame success is never assumed."""
import contextlib,hashlib,importlib.util,io,json
from pathlib import Path
D=Path(__file__).resolve().parent;B=D/'review_native_phases.py'
B_SHA='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
assert hashlib.sha256(B.read_bytes()).hexdigest()==B_SHA
s=importlib.util.spec_from_file_location('S01_induction_native_base',B);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
m.RUN=m.S/'induction_R07_S01_full'
m.SCAN_SOURCE=m.C/'scan_full50nm_fast_R07_induction_S01_once.py'
m.SCAN_SHA='757d27ae1b250afdad5a9649f8837f81d7e9cd73806ab351479cb21855f86a66'
REFERENCE_PA=200.0000026702864
OLD_RECEIPT=D/'S01_speed_completed_through224_native_receipt.json'
OLD_RECEIPT_SHA='e27e6ab2585f4fade3fb755af054a2b2854c7196343c642f223f30c9d8b2ce19'
assert hashlib.sha256(OLD_RECEIPT.read_bytes()).hexdigest()==OLD_RECEIPT_SHA
old_receipt=json.loads(OLD_RECEIPT.read_text());prior_end=old_receipt['complete_through_index']*m.BLOCK
original_phase_plan=m.phase_plan;original_stats=m.stats


def phase_plan(*args):
    phases,brackets,why=original_phase_plan(*args)
    if phases[0][0]=='pre_Start_nominal_fixed':
        _,lo,hi=phases[0];m.require(lo==0 and prior_end<hi,'Prior speed receipt not before exposure')
        phases=[('prior_R07_history_mixed_setpoints',0,prior_end),
                ('speed_receipt_end_to_induction_Start',prior_end,hi)]+phases[1:]
    return phases,brackets,why


def stats(a,lo,hi,sp,limits):
    r=original_stats(a,lo,hi,REFERENCE_PA,limits)
    if hi>lo:
        v=a[lo:hi];r['fraction_current_within_requested200pA20pct_band']=float(m.np.mean((-1.2*REFERENCE_PA<=v[:,0])&(v[:,0]<=-.8*REFERENCE_PA)))
        r['Bias_not_minus1V_samples']=int(m.np.count_nonzero(v[:,1]!=-1.))
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
              'Actual exposure entry settings differ')
    m.phase_plan=phase_plan;m.stats=stats
    with contextlib.redirect_stdout(io.StringIO()) as capture:m.main()
    summary=json.loads(capture.getvalue().strip());p=Path(summary['path']);r=json.loads(p.read_text())
    r['wrapper_source']={'path':str(Path(__file__)),'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    r['base_reviewer_source']={'path':str(B),'sha256':B_SHA}
    r['setpoint_reference_pA']=REFERENCE_PA
    r['scope']='Actual R07 S01 exposure at200pA,109.649nm/s and doubled configured time constant. Prior history has mixed setpoints and is not reinterpreted as200pA.'
    r['inputs']['prior_speed_receipt']={'path':str(OLD_RECEIPT),'sha256':OLD_RECEIPT_SHA}
    bp=m.RUN/'before.json';r['inputs']['actual_induction_before']={'path':str(bp),'sha256':hashlib.sha256(bp.read_bytes()).hexdigest()}
    remove_target_descriptors(r['full'])
    for name,v in r['phases'].items():
        if name in ['prior_R07_history_mixed_setpoints','complete_archive_without_attribution']:remove_target_descriptors(v)
    for w in r['ten_second_windows']:
        if w['phase'] in ['prior_R07_history_mixed_setpoints','complete_archive_without_attribution']:remove_target_descriptors(w)
    r['limits'].extend(['The preceding R07 history includes100pA and200pA stages. Target-dependent algebra and occupancy have been removed from that history and the full-record aggregate.',
                        'The legacy minus120..minus80pA field is only a named historical descriptor. Requested current during this exposure is200pA with minus240..minus160pA comparison band.',
                        'An interrupted exposure is not a completed full image or matched restored-condition assessment. Actual outcome and recovery state remain distinct.'])
    p.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');summary['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();print(json.dumps(summary))


if __name__=='__main__':main()
