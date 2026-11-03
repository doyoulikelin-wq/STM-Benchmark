"""Offline closed native postroll after independently completed P02 current return."""
import json
from pathlib import Path
from review_native_phases import h,np,DT,BLOCK,S,PREFIX,require,stats
D=Path(__file__).resolve().parent
j,jref=h.read_json(D/'P02_independent_return_native_phases.json')
require(jref['sha256']=='46a707bfec1f707063c67b7c185d8d2e6634995c36fb3c823ab1ee5a0ffc48c2','Frozen complete-return audit changed')
r,rref=h.read_json(D.parent/'R06_pulse_P02/independent_return_completed_native_receipt.json')
require(rref['sha256']=='3bee6ff7de362a83e5e261bcc52891339d3888db2adcb896b84ff8d9cd4c6dfc','Frozen receipt changed')
first=j['milestones']['after']['after']['sample'];last=r['complete_through_index']*BLOCK
base=first//BLOCK*BLOCK;arrays=[];refs=[]
for idx in range(first//BLOCK+1,r['complete_through_index']+1):
    name=f'{PREFIX}{idx:05d}.dat';p=h.local(S/'native_R06'/name);meta=r['files'][name];raw=p.read_bytes()
    require(meta['rows']==BLOCK and meta['local_path']==str(p) and len(raw)==meta['bytes'] and h.sha(raw)==meta['sha256']
            and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Closed native postroll changed')
    arrays.append(h.parse_block(raw,BLOCK));refs.append({'path':str(p),'sha256':meta['sha256']})
a=np.concatenate(arrays);limits=j['whole_stage']['Z_changes']['endpoint_limits_nm_low_high']
def describe(lo,hi):
    v=stats(a,lo-base,hi-base,100.,limits);v['zero_based_sample_half_open']=[lo,hi];v['native_seconds_half_open']=[lo*DT,hi*DT]
    idx=lo+int(np.argmin(a[lo-base:hi-base,0]))
    v['minimum_I_location']={'block':idx//BLOCK+1,'row_zero_based':idx%BLOCK}
    for x in v['abs_I_sample_exceedances_pA'].values():
        if x['longest_native_seconds_half_open']:x['longest_native_seconds_half_open']=[z+base*DT for z in x['longest_native_seconds_half_open']]
    if v['Z_changes']['pair_first_native_s'] is not None:v['Z_changes']['pair_first_native_s']+=base*DT
    return v
result={'source_sha256':h.sha(Path(__file__).read_bytes()),'known_return_review':jref,'frozen_receipt':rref,'native_blocks':refs,
        'post_after_known_complete':describe(first,last),'nonoverlapping10s':[describe(i,min(i+20000,last)) for i in range(first,last,20000)],
        'scope':'Closed postroll following actual completed independent recovery return. Original P02 postguard failure remains unchanged. DAT has no high-rate feedback state or setpoint channel.'}
out=D/'P02_independent_return_postroll_v2.json'
with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(out,h.sha(out.read_bytes()));print(json.dumps({k:result['post_after_known_complete'][k] for k in ['native_seconds_half_open','rows','signed_I_inside_minus120_to_minus80pA_fraction','Z_linear_residual_RMS_pm','Z_linear_slope_pm_per_s','samples','abs_I_sample_exceedances_pA']},indent=2))
