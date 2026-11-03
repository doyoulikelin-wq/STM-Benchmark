"""Inspect fixed time windows surrounding every native |I| >=1 nA event in scan 212."""
import json
from pathlib import Path
from review_native_phases import BLOCK, DT, S, h, np, require
P=Path(__file__).resolve().parent
review,ref=h.read_json(P/'after_P02_recovery_scan_native_phases.json')
require(review['complete_scan_interval_bracketed_in_closed_blocks'],'Full baseline not bracketed')
data=[]
lo,hi=review['phases']['scan_core_between_observations']['zero_based_sample_half_open']
first=lo//BLOCK+1
last=(hi-1)//BLOCK+1
base=(first-1)*BLOCK
for block in review['inputs']['native_blocks']:
    if not first<=int(Path(block['path']).stem[-5:])<=last:continue
    path=h.local(block['path'])
    require(path.parent==S/'native_R06','Wrong local DAT directory')
    raw=path.read_bytes()
    require(h.sha(raw)==block['sha256'],'Changed local block')
    data.append(h.parse_block(raw,block['rows']))
a=np.concatenate(data)
lo,hi=review['phases']['scan_core_between_observations']['zero_based_sample_half_open']
i,z=a[:,0],a[:,2]; peaks=np.flatnonzero(np.abs(i[lo-base:hi-base])>=1000)+lo
events=[]
for j in map(int,peaks):
    zbase=float(np.median(z[j-base-100:j-base-20]))
    event={'native_s':j*DT,'block':j//BLOCK+1,'zero_based_row':j%BLOCK,'signed_I_pA':float(i[j-base]),'fixed_windows':[]}
    for lower,upper in [(-50,-10),(0,.5),(.5,5),(5,25),(25,100),(100,250),(250,500)]:
        left=j+round(lower/1000/DT);right=j+round(upper/1000/DT)
        require(lo<=left<right<=hi,'Outside bracketed scan core')
        ii,zz=i[left-base:right-base],z[left-base:right-base]
        event['fixed_windows'].append({'relative_half_open_ms':[lower,upper],'n':len(ii),'median_I_pA':float(np.median(ii)),
            'min_I_pA':float(ii.min()),'max_I_pA':float(ii.max()),'samples_abs_I_ge400pA':int(np.count_nonzero(np.abs(ii)>=400)),
            'median_Z_minus_pre_median_pm':float((np.median(zz)-zbase)*1000)})
    events.append(event)
result={'source':ref,'threshold_absolute_pA':1000,'events':events,'limits':'Fixed windows from all qualifying stored rows. Adjacent samples are rastering. Stored times and Z changes describe sampled electrical and piezo signals only.'}
o=P/'peak_neighborhoods_212.json'
with o.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(o,h.sha(o.read_bytes()))
for p in events:
    print(p['native_s'],p['block'],p['zero_based_row'],round(p['signed_I_pA'],1))
    for w in p['fixed_windows']:print(w['relative_half_open_ms'],round(w['median_I_pA'],1),w['samples_abs_I_ge400pA'],round(w['median_Z_minus_pre_median_pm'],1))
