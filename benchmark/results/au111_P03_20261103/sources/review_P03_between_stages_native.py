"""Offline whole inter-stage native intervals, including gaps between prior reviews."""
import json
from pathlib import Path
from review_native_phases import h,np,DT,BLOCK,S,PREFIX,require,stats
D=Path(__file__).resolve().parent
PINS={'after_P02_recovery_scan_native_phases.json':'e40f89026e36e0e388e54c74338ffa90c86f13dde99a491b58fcbbfeffaa6766',
      'P03_prepare_native_phases.json':'25de5798923009b8025ff333a327d9743019245560ccf01774de48c8ebca194e',
      'P03_native_pre_pulse_post.json':'e1b1f6e9df22a76bb7c5d9b65a7cf1631fc243c749c6dadb3924ef85968d3418',
      'P03_return_native_phases.json':'337dfc9313e2387c4bc339c2b4e84558b795894d994bb9245ecc8d97d5037121'}
j={};refs={}
for name,digest in PINS.items():
    j[name],refs[name]=h.read_json(D/name);require(refs[name]['sha256']==digest,'Pinned interval source changed')
receipt,rref=h.read_json(D.parent/'R06_pulse_P03/return_completed_native_receipt.json')
require(rref['sha256']=='61062baff35f4bcdfae7cd899431d03410607d2c378a031090428a55ff0c1d70','Frozen native receipt changed')
scan=j['after_P02_recovery_scan_native_phases.json'];prep=j['P03_prepare_native_phases.json'];pulse=j['P03_native_pre_pulse_post.json'];ret=j['P03_return_native_phases.json']
intervals=[('full_post212_until_P03_prepare',scan['phases']['post_event_context_unclassified']['zero_based_sample_half_open'][0],prep['whole_stage']['zero_based_sample_half_open'][0],100.),
 ('post_P03_prepare_until_pulse_pre30',prep['whole_stage']['zero_based_sample_half_open'][1],pulse['phases']['pre30s_start_edge']['zero_based_sample_half_open'][0],1000.),
 ('post_P03_pulse_until_return',pulse['phases']['post30s_end_edge']['zero_based_sample_half_open'][1],ret['whole_stage']['zero_based_sample_half_open'][0],1000.),
 ('post_P03_return_through_closed542',ret['whole_stage']['zero_based_sample_half_open'][1],receipt['complete_through_index']*BLOCK,100.)]
first=intervals[0][1];last=intervals[-1][2];base=first//BLOCK*BLOCK;arrays=[];blocks=[]
for index in range(first//BLOCK+1,(last-1)//BLOCK+2):
    name=f'{PREFIX}{index:05d}.dat';p=h.local(S/'native_R06'/name);meta=receipt['files'][name];raw=p.read_bytes()
    require(meta['local_path']==str(p) and meta['rows']==BLOCK and len(raw)==meta['bytes'] and h.sha(raw)==meta['sha256']
            and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Native closed block verification failed')
    arrays.append(h.parse_block(raw,BLOCK));blocks.append({'path':str(p),'sha256':meta['sha256'],'rows':BLOCK})
a=np.concatenate(arrays);limits=prep['whole_stage']['Z_changes']['endpoint_limits_nm_low_high']
def describe(lo,hi,target):
    require(base<=lo<hi<=base+len(a),'Invalid interval')
    x=a[lo-base:hi-base];v=stats(a,lo-base,hi-base,target,limits)
    v['zero_based_sample_half_open']=[lo,hi];v['native_seconds_half_open']=[lo*DT,hi*DT];v['setpoint_reference_pA']=target
    idx=lo+int(np.argmin(x[:,0]));v['minimum_I_location']={'block':idx//BLOCK+1,'row_zero_based':idx%BLOCK}
    for item in v['abs_I_sample_exceedances_pA'].values():
        if item['longest_native_seconds_half_open']:item['longest_native_seconds_half_open']=[t+base*DT for t in item['longest_native_seconds_half_open']]
    if v['Z_changes']['pair_first_native_s'] is not None:v['Z_changes']['pair_first_native_s']+=base*DT
    v['signed_I_within20pct_reference_fraction']=float(np.mean((-1.2*target<=x[:,0])&(x[:,0]<=-.8*target)))
    v['signed_I_within25pct_reference_fraction']=float(np.mean((-1.25*target<=x[:,0])&(x[:,0]<=-.75*target)))
    v['Bias_not_minus1V_sample_count']=int(np.count_nonzero(x[:,1]!=-1.))
    difference=np.diff(x[:,2]);top=np.argsort(np.abs(difference))[-5:][::-1]
    v['largest_adjacent_Z_changes']=[{'absolute_first_sample':lo+int(i),'native_s':(lo+int(i))*DT,'change_pm':float(difference[i]*1000),'I_before_pA':float(x[i,0]),'I_after_pA':float(x[i+1,0])} for i in top]
    return v
results={}
for label,lo,hi,target in intervals:
    results[label]={'whole':describe(lo,hi,target),'nonoverlapping_10s_windows':[{**describe(k,min(k+20000,hi),target),'partial_tail':k+20000>hi} for k in range(lo,hi,20000)]}
out={'source_sha256':h.sha(Path(__file__).read_bytes()),'sources':refs,'frozen_receipt':rref,'native_blocks':blocks,'intervals':results,
 'coverage':'All required closed25000-row six-channel blocks locally SHA-verified, finite0.5ms sample sequence checked. Intervals exclude the separately audited preparation, pulse and return actions.',
 'timing':'Interval boundaries use the actual native counter brackets in the pinned completed action and scan reviews. No wallclock-only interpolation.',
 'limits':'Current400pA descriptors are historical100pA descriptors and do not indicate overload at1nA. DAT lacks high-rate setpoint, feedback and XY channels. Complete stored rows do not prove absence of faster unrecorded transients or establish an independent physical acquisition-gap test. Z extrema and drift do not measure the physical tunnelling gap.'}
p=D/'P03_between_stages_native_review.json'
with p.open('x') as f:json.dump(out,f,indent=2,allow_nan=False);f.write('\n')
print(p,h.sha(p.read_bytes()))
for label,v in results.items():
    w=v['whole'];print(label,w['native_seconds_half_open'],'I',w['samples']['Current_pA']['min'],w['samples']['Current_pA']['max'],'band20',w['signed_I_within20pct_reference_fraction'],'Zrms',w['Z_linear_residual_RMS_pm'],'Zslope',w['Z_linear_slope_pm_per_s'],'biaschanges',w['Bias_not_minus1V_sample_count'],'>=4nA',w['abs_I_sample_exceedances_pA']['4000']['sample_count'],'maxadjZ',w['largest_adjacent_Z_changes'][0])
