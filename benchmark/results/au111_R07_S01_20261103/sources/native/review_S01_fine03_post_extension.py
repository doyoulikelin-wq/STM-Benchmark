"""Offline append-only post_fine03 native extension without changing previous audits."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
D=Path(__file__).resolve().parent;B=D/'review_native_phases.py'
assert hashlib.sha256(B.read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
s=importlib.util.spec_from_file_location('R07_post_fine03_base',B);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
h,np=m.h,m.np

def main():
    p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    output=h.local(args.output);h.require(not output.exists(),'New output only')
    old,oref=h.read_json(D/'S01_fine03_native_review.json');h.require(oref['sha256']=='369c2a711e7b3b463b55478e5b7a911acd902af99498bbd5580ad6c8a0b732e0','Previous fine03 audit changed')
    rr,rref=h.read_json(args.receipt);ready,readyref=h.read_json(m.L/'READY.json')
    h.require(rr['recording_segment_id']=='R07' and rr['native_start_identity']==ready['native_start_identity'] and all(h.sha((m.L/n).read_bytes())==d for n,d in m.LOGGER_IDENTITY_PINS.items()),'Actual recorder changed')
    start=old['fine03_after_bracket']['after']['sample'];stop=rr['complete_through_index']*m.BLOCK
    first=start//m.BLOCK+1;base=(first-1)*m.BLOCK;h.require(stop>start,'No post-fine03 coverage')
    arrays=[];files=[]
    for block in range(first,rr['complete_through_index']+1):
        name=f'{m.PREFIX}{block:05d}.dat';meta=rr['files'][name];path=h.local(m.S/'native_R07'/name);raw=path.read_bytes()
        h.require(meta['local_path']==str(path) and meta['rows']==m.BLOCK and len(raw)==meta['bytes'] and h.sha(raw)==meta['sha256'] and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Native block verification failed')
        arrays.append(h.parse_block(raw,m.BLOCK));files.append({'path':str(path),'sha256':meta['sha256'],'rows':m.BLOCK})
    a=np.concatenate(arrays);del arrays
    limits=old['fine03_final_native10s_before_after_readback_lower_bound']['Z_changes']['endpoint_limits_nm_low_high']
    def describe(lo,hi):
        r=m.stats(a,lo-base,hi-base,100.,limits);r['zero_based_sample_half_open']=[lo,hi];r['native_seconds_half_open']=[lo*m.DT,hi*m.DT]
        if hi>lo:
            v=a[lo-base:hi-base];peak=lo+int(np.argmin(v[:,0]));r['minimum_I_location']={'block':peak//m.BLOCK+1,'row_zero_based':peak%m.BLOCK}
            r['Bias_not_minus1V_samples']=int(np.count_nonzero(v[:,1]!=-1.))
            for d in r['abs_I_sample_exceedances_pA'].values():
                if d['longest_native_seconds_half_open']:d['longest_native_seconds_half_open']=[t+base*m.DT for t in d['longest_native_seconds_half_open']]
            if r['Z_changes']['pair_first_native_s'] is not None:r['Z_changes']['pair_first_native_s']+=base*m.DT
        return r
    result={'scope':'All closed post_fine03 native data through selected receipt. Previous full214 audit is unchanged.',
            'source_sha256':h.sha(Path(__file__).read_bytes()),'sources':{'base_reviewer':{'path':str(B),'sha256':h.sha(B.read_bytes())},'prior_full_audit':oref,'receipt':rref,'logger_ready':readyref,'raw_blocks':files},
            'post_fine03_all':describe(start,stop),'last30s':describe(max(start,stop-60000),stop),'last10s':describe(max(start,stop-20000),stop),
            'fixed10s_windows':[dict(partial_tail=min(i+20000,stop)-i<20000,**describe(i,min(i+20000,stop))) for i in range(start,stop,20000)],
            'limits':['These are native signals through the last closed block, not a fresh device read or authorization. Root separately verifies current status and intervening writers.',
                      'No high-rate XY, gain or setpoint channel. Bias/current/Z behavior alone cannot prove absence of every possible manual action.',
                      'Timing is relative to this R07 DataLog sample stream. No calibrated analog peak, chemistry or image-quality inference.']}
    encoded=json.dumps(result,indent=2,allow_nan=False)+'\n'
    with output.open('x') as f:f.write(encoded)
    print(str(output),h.sha(output.read_bytes()))
    for k in ['post_fine03_all','last30s','last10s']:
        r=result[k];print(k,r['native_seconds_half_open'],'I',r['samples']['Current_pA'],'Z_RMS',r['Z_linear_residual_RMS_pm'],'Z_slope',r['Z_linear_slope_pm_per_s'],'Zchange',r['Z_changes']['median_last_minus_first_upto100ms_pm'],'>=400',r['abs_I_ge400pA_samples'],'Biasother',r['Bias_not_minus1V_samples'])

if __name__=='__main__':main()
