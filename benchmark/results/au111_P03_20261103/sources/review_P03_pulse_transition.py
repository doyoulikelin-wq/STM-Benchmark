"""Offline high-rate timing description of actual P03 pulse and feedback response."""
import json
from pathlib import Path
from review_native_phases import h,np,DT,BLOCK,require
D=Path(__file__).resolve().parent
j,ref=h.read_json(D/'P03_native_pre_pulse_post.json')
require(ref['sha256']=='e1b1f6e9df22a76bb7c5d9b65a7cf1631fc243c749c6dadb3924ef85968d3418','Frozen review changed')
a=[]
for block in j['native_blocks']:
    p=h.local(block['path']);raw=p.read_bytes();require(h.sha(raw)==block['sha256'],'Raw native changed');a.append(h.parse_block(raw,block['rows']))
a=np.concatenate(a);base=(int(Path(j['native_blocks'][0]['path']).stem[-5:])-1)*BLOCK
lo,hi=j['phases']['claim_to_ACK_outer_including_timing_uncertainty']['zero_based_sample_half_open'];z0=j['phases']['pre30s_inner']['samples']['Z_nm']['median']
def point(idx):
    v=a[idx-base];return {'absolute_sample':idx,'native_s':idx*DT,'block':idx//BLOCK+1,'row_zero_based':idx%BLOCK,'I_pA':float(v[0]),'Bias_V':float(v[1]),'Z_relative_pre_nm':float(v[2]-z0)}
x=a[lo-base:hi-base];pstart,pend=j['bias_below_minus4V_within_Start_outer'][0]['zero_based_sample_half_open']
first_base=pend+int(np.flatnonzero(a[pend-base:hi-base,1]==-1.)[0]);zpeak=lo+int(np.argmax(x[:,2]))
thresholds={}
for label,mask in [('at_historical_negative_edge',x[:,0]==-9999.4768),('abs_I_at_least4nA',abs(x[:,0])>=4000)]:
    edges=np.diff(np.r_[False,mask,False].astype(int));groups=[]
    for left,right in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
        groups.append({'absolute_samples_half_open':[lo+int(left),lo+int(right)],'native_seconds_half_open':[(lo+int(left))*DT,(lo+int(right))*DT],'duration_ms':int(right-left)*.5})
    thresholds[label]=groups
windows=[]
for lower,upper in [(0,5),(5,30),(30,60),(60,100),(100,250)]:
    left=first_base+round(lower/1000/DT);right=first_base+round(upper/1000/DT);v=a[left-base:right-base]
    windows.append({'relative_to_resting_bias_return_ms':[lower,upper],'n':len(v),'I_min_pA':float(v[:,0].min()),'I_max_pA':float(v[:,0].max()),'I_median_pA':float(np.median(v[:,0])),'Z_min_relative_pre_nm':float(v[:,2].min()-z0),'Z_max_relative_pre_nm':float(v[:,2].max()-z0),'Z_median_relative_pre_nm':float(np.median(v[:,2])-z0)})
out={'review':ref,'source_sha256':h.sha(Path(__file__).read_bytes()),'last_pulse_threshold_sample':point(pend-1),'first_resting_Bias_minus1V':point(first_base),'native_Z_transient_peak':point(zpeak),'threshold_runs':thresholds,'post_bias_return_windows':windows,'readiness_observation_count':len(j['feedback_readiness']['observations']),'Hold_wait_branch_observed':False,'limits':'Current reaches the saved software range edge. The true analog peak and full charge are censored. High-rate DAT has no direct feedback-state channel. Timing of current and Z recovery cannot uniquely distinguish electronics overload recovery, controller response and junction response. Transient Z peak differs from later steady workpoint. The added Hold wait branch was not exercised in this actual pulse.'}
p=D/'P03_pulse_transition_timeline.json'
with p.open('x') as f:json.dump(out,f,indent=2,allow_nan=False);f.write('\n')
print(p,h.sha(p.read_bytes()));print(json.dumps({k:out[k] for k in ['first_resting_Bias_minus1V','native_Z_transient_peak','threshold_runs','post_bias_return_windows']},indent=2))
