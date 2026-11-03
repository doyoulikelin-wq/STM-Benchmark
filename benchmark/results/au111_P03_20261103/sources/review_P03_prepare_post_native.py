"""Offline closed native postroll after completed P03 current preparation."""
import json
from pathlib import Path
from review_native_phases import h,np,DT,BLOCK,S,PREFIX,require,stats
D=Path(__file__).resolve().parent
j,jref=h.read_json(D/'P03_prepare_native_phases.json')
require(jref['sha256']=='25de5798923009b8025ff333a327d9743019245560ccf01774de48c8ebca194e','Frozen complete-return audit changed')
r,rref=h.read_json(D.parent/'R06_pulse_P03/prepare_completed_native_receipt.json')
require(rref['sha256']=='6848b43e10c83023c6e61fb85baf8993e0648f5737510837413ec997c0e377a9','Frozen receipt changed')
first=j['milestones']['after']['after']['sample'];last=r['complete_through_index']*BLOCK
base=first//BLOCK*BLOCK;arrays=[];refs=[]
for idx in range(first//BLOCK+1,r['complete_through_index']+1):
    name=f'{PREFIX}{idx:05d}.dat';p=h.local(S/'native_R06'/name);meta=r['files'][name];raw=p.read_bytes()
    require(meta['rows']==BLOCK and meta['local_path']==str(p) and len(raw)==meta['bytes'] and h.sha(raw)==meta['sha256']
            and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Closed native postroll changed')
    arrays.append(h.parse_block(raw,BLOCK));refs.append({'path':str(p),'sha256':meta['sha256']})
a=np.concatenate(arrays);limits=j['whole_stage']['Z_changes']['endpoint_limits_nm_low_high']
def describe(lo,hi):
    v=stats(a,lo-base,hi-base,1000.,limits);v['zero_based_sample_half_open']=[lo,hi];v['native_seconds_half_open']=[lo*DT,hi*DT]
    v['signed_I_inside_20pct_of_1nA_fraction']=float(np.mean((-1200<=a[lo-base:hi-base,0])&(a[lo-base:hi-base,0]<=-800)))
    idx=lo+int(np.argmin(a[lo-base:hi-base,0]))
    v['minimum_I_location']={'block':idx//BLOCK+1,'row_zero_based':idx%BLOCK}
    for x in v['abs_I_sample_exceedances_pA'].values():
        if x['longest_native_seconds_half_open']:x['longest_native_seconds_half_open']=[z+base*DT for z in x['longest_native_seconds_half_open']]
    if v['Z_changes']['pair_first_native_s'] is not None:v['Z_changes']['pair_first_native_s']+=base*DT
    return v
result={'source_sha256':h.sha(Path(__file__).read_bytes()),'known_preparation_review':jref,'frozen_receipt':rref,'native_blocks':refs,
        'post_after_known_complete':describe(first,last),'nonoverlapping10s':[describe(i,min(i+20000,last)) for i in range(first,last,20000)],
        'scope':'Closed postroll following actual completed P03 preparation. Subsequent pulse has not been established by this record. DAT has no high-rate feedback state or setpoint channel.'}
out=D/'P03_prepare_postroll.json'
with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(out,h.sha(out.read_bytes()));print(json.dumps({k:result['post_after_known_complete'][k] for k in ['native_seconds_half_open','rows','signed_I_inside_20pct_of_1nA_fraction','Z_linear_residual_RMS_pm','Z_linear_slope_pm_per_s','samples','abs_I_sample_exceedances_pA']},indent=2))
