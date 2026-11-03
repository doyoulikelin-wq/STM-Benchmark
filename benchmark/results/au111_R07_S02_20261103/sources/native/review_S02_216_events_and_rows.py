"""Offline sampled-current groups and approximate scan-row context for actual full216."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math

D=Path(__file__).resolve().parent;B=D/'review_native_phases.py'
assert hashlib.sha256(B.read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
spec=importlib.util.spec_from_file_location('S02_216_peak_base',B);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
h,np=m.h,m.np
audit,ar=h.read_json(D/'S02_full216_native_review.json')
assert ar['sha256']=='e241a60e5005f07a3723cea15ff04b1e86e4d066718f2e5aea530be8ee0c7bb9'
receipt,rr=h.read_json(D/'S02_full216_completed_through495_native_receipt.json')
assert rr['sha256']=='030abb6c3c496e369806f623895022a20bb1ca0ff28bcfb9e9eb690fd3200bf9'
mf,mr=h.read_json(m.S/'induction_R07_S02_full02/manifest.json')
after,afr=h.read_json(m.S/'induction_R07_S02_full02/after_frames.json')
v=after['values'];line=sum(v['Scan.SpeedGet'][2:4]);frame=v['Scan.FrameGet'];nrows=v['Scan.BufferGet'][3]
assert mf['scan_direction']==0 and nrows==240 and frame[4]==0 and line==.9120000004768372
lo,hi=audit['phases']['scan_core_between_observations']['zero_based_sample_half_open']
first,last=lo//m.BLOCK+1,(hi-1)//m.BLOCK+1;base=(first-1)*m.BLOCK
arrays=[];files=[]
for num in range(first,last+1):
    name=f'{m.PREFIX}{num:05d}.dat';meta=receipt['files'][name];p=h.local(m.S/'native_R07'/name);raw=p.read_bytes()
    assert h.sha(raw)==meta['sha256'] and len(raw)==meta['bytes'] and meta['rows']==25000
    arrays.append(h.parse_block(raw,25000));files.append({'path':str(p),'sha256':meta['sha256']})
a=np.concatenate(arrays);del arrays
core=a[lo-base:hi-base]
start=audit['brackets']['start'];bounds=[start['before']['native_s'],start['after']['native_s']]

def location(index):
    index=int(index);t=index*m.DT
    row_range=[math.floor((t-bounds[1])/line),math.floor((t-bounds[0])/line)]
    center=(sum(row_range)/2+.5)/nrows
    return {'native_s':t,'block':index//m.BLOCK+1,'DAT_row_zero_based':index%m.BLOCK,
            'nominal_scan_row_range':row_range,'nominal_Y_nm':(frame[1]+frame[3]*(.5-center))*1e9}

masks={'abs_ge400pA':np.abs(core[:,0])>=400.,'abs_ge1000pA':np.abs(core[:,0])>=1000.,
       'abs_gt5000pA':np.abs(core[:,0])>5000.,'historical_negative_edge':np.isclose(core[:,0],-9999.4768,atol=.00005,rtol=0)}
groups={}
for label,mask in masks.items():
    edges=np.diff(np.r_[False,mask,False].astype(int));beg,end=np.flatnonzero(edges==1),np.flatnonzero(edges==-1)
    rows=[]
    for st,en in zip(beg,end,strict=True):
        peak=st+int(np.argmin(core[st:en,0]));index=lo+peak
        rows.append({'samples':int(en-st),'duration_ms':float((en-st)*m.DT*1000),
                     'native_s_half_open':[(lo+int(st))*m.DT,(lo+int(en))*m.DT],
                     'sampled_minimum_I_pA':float(core[peak,0]),'Z_at_sampled_minimum_nm':float(core[peak,2]),
                     'sampled_minimum_location':location(index)})
    groups[label]={'samples':int(mask.sum()),'duration_s_total':float(mask.sum()*m.DT),'groups':len(rows),
                   'longest':max(rows,key=lambda r:r['samples']) if rows else None,
                   'first':rows[0] if rows else None,'last':rows[-1] if rows else None,
                   'all_groups':rows if label!='abs_ge400pA' else None}

nominal_rows=np.floor(((lo+np.arange(len(core)))*m.DT-sum(bounds)/2)/line).astype(int)
by_row=[]
for row in sorted(set(nominal_rows)):
    selection=nominal_rows==row
    by_row.append({'nominal_scan_row':int(row),'nominal_Y_nm':float((frame[1]+frame[3]*(.5-(row+.5)/nrows))*1e9),
                   'stored_samples':int(selection.sum()),'minimum_I_pA':float(core[selection,0].min()),
                   **{name:int((selection&mask).sum()) for name,mask in masks.items()}})
result={'scope':'Actual216 changed-setting exposure. Local recorded-current groups and conditional row timing, not an image-quality decision.',
        'source_sha256':h.sha(Path(__file__).read_bytes()),'sources':{'full_audit':ar,'receipt':rr,'manifest':mr,'after_frames':afr,'raw_blocks':files},
        'actual_double_direction_row_s':line,'start_native_outer_s':bounds,'core_native_s':[lo*m.DT,hi*m.DT],
        'groups':groups,'nominal_row_histogram':by_row,
        'start_boundary_separate':audit['phases']['Start_boundary_and_positioning'],
        'end_boundary_separate':audit['phases']['end_boundary'],
        'limits':['No high-rate XY or hardware row trigger. Nominal row and Y carry at least one-row uncertainty and do not specify X or direction half-line.',
                  'Repeated historical negative digitizer-edge values censor the negative peak. The observed minimum is not a bound on the actual analog current.',
                  'The5nA slow-current software runtime criterion does not guarantee every2kHz native sample is below5nA.',
                  'This200pA/doubled-speed/doubled-T exposure cannot be treated as a matched100pA quality image. Restoration and independent complete imaging are separate stages.']}
out=D/'S02_full216_events_and_rows.json'
with out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(out,h.sha(out.read_bytes()))
for name,entry in groups.items():print(name,json.dumps({k:v for k,v in entry.items() if k!='all_groups'}))
