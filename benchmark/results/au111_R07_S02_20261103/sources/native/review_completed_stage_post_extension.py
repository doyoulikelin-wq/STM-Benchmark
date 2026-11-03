"""Offline append-only native post-window for an already audited completed R07 configuration stage."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

D=Path(__file__).resolve().parent
B=D/'review_native_phases.py'
B_SHA='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
assert hashlib.sha256(B.read_bytes()).hexdigest()==B_SHA
spec=importlib.util.spec_from_file_location('R07_stage_post_base',B)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
h,np=m.h,m.np

def main():
    parser=argparse.ArgumentParser()
    for name in ['stage-audit','receipt','output']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--stage-audit-sha256',required=True)
    args=parser.parse_args();output=h.local(args.output)
    h.require(not output.exists(),'New output only')
    audit,aref=h.read_json(args.stage_audit)
    h.require(aref['sha256']==args.stage_audit_sha256,'Prior stage audit changed')
    window=audit['phases']['post_stage_context_through_closed_receipt']
    start=window['zero_based_sample_half_open'][0]
    sp=window['setpoint_reference_pA']
    rr,rref=h.read_json(args.receipt);ready,readyref=h.read_json(m.L/'READY.json')
    h.require(rr['recording_segment_id']=='R07' and rr['native_start_identity']==ready['native_start_identity']
              and all(h.sha((m.L/n).read_bytes())==digest for n,digest in m.LOGGER_IDENTITY_PINS.items()),'Actual recorder changed')
    stop=rr['complete_through_index']*m.BLOCK
    h.require(stop>=window['zero_based_sample_half_open'][1] and start<stop,'Receipt is older than stage audit')
    first=start//m.BLOCK+1;base=(first-1)*m.BLOCK
    data=[];files=[]
    for number in range(first,rr['complete_through_index']+1):
        name=f'{m.PREFIX}{number:05d}.dat';meta=rr['files'][name];path=h.local(m.S/'native_R07'/name);raw=path.read_bytes()
        h.require(meta['local_path']==str(path) and meta['rows']==m.BLOCK and len(raw)==meta['bytes']
                  and h.sha(raw)==meta['sha256'] and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Native block verification failed')
        data.append(h.parse_block(raw,m.BLOCK));files.append({'path':str(path),'sha256':meta['sha256'],'rows':m.BLOCK})
    a=np.concatenate(data);del data
    limits=window['Z_changes']['endpoint_limits_nm_low_high']
    def describe(lo,hi):
        r=m.stats(a,lo-base,hi-base,sp,limits)
        r['zero_based_sample_half_open']=[lo,hi];r['native_seconds_half_open']=[lo*m.DT,hi*m.DT]
        v=a[lo-base:hi-base];peak=lo+int(np.argmin(v[:,0]))
        r['minimum_I_location']={'block':peak//m.BLOCK+1,'row_zero_based':peak%m.BLOCK}
        r['setpoint_reference_pA']=sp
        r['fraction_native_current_within20pct_setpoint']=float(np.mean((-1.2*sp<=v[:,0])&(v[:,0]<=-.8*sp)))
        r['Bias_not_minus1V_samples']=int(np.count_nonzero(v[:,1]!=-1.))
        for d in r['abs_I_sample_exceedances_pA'].values():
            if d['longest_native_seconds_half_open']:d['longest_native_seconds_half_open']=[t+base*m.DT for t in d['longest_native_seconds_half_open']]
        if r['Z_changes']['pair_first_native_s'] is not None:r['Z_changes']['pair_first_native_s']+=base*m.DT
        return r
    result={'scope':'Append-only post-stage native review. The original actual command, ACK, source pins and outcome remain in the separately frozen audit.',
            'source_sha256':h.sha(Path(__file__).read_bytes()),'sources':{'stage_audit':aref,'receipt':rref,'logger_ready':readyref,'raw_blocks':files},
            'post_stage_all':describe(start,stop),'last30s_or_shorter':describe(max(start,stop-60000),stop),
            'last10s_or_shorter':describe(max(start,stop-20000),stop),
            'fixed10s_windows':[dict(partial_tail=min(i+20000,stop)-i<20000,**describe(i,min(i+20000,stop))) for i in range(start,stop,20000)],
            'limits':['This is a frozen local data review, not current control status or execution authorization.',
                      'No high-rate setpoint, XY, gain or scan-speed channel. Configurations are established by the prior actual command/readback audit.',
                      'The original historic100pA occupancy field is not the200pA target-specific comparison. Sampled extrema are not analog peak bounds.']}
    with output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(str(output),h.sha(output.read_bytes()))
    for name in ['post_stage_all','last30s_or_shorter','last10s_or_shorter']:
        r=result[name];print(name,r['native_seconds_half_open'],'I',r['samples']['Current_pA'],'Z_RMS',r['Z_linear_residual_RMS_pm'],'Z_slope',r['Z_linear_slope_pm_per_s'],'>=400',r['abs_I_ge400pA_samples'],'Biasother',r['Bias_not_minus1V_samples'])

if __name__=='__main__':main()
