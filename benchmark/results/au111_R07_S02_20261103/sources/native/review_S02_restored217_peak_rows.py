"""Offline row-level timing context for S02_restored217 native excursions. No pixel synchronization."""
from pathlib import Path
import hashlib,importlib.util,json,math
D=Path(__file__).resolve().parent
B=D/'review_native_phases.py'
assert hashlib.sha256(B.read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
spec=importlib.util.spec_from_file_location('R07_peak_base',B);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
h,np=m.h,m.np
audit,ar=h.read_json(D/'S02_restored217_native_review.json')
h.require(ar['sha256']=='5036e1d18649bac186e1061d78884528f5aeb879ec8d2baf516d91c3e12acb53','Audit changed')
receipt,rr=h.read_json(D/'S02_restored217_completed_through577_native_receipt.json')
mf,mr=h.read_json(m.S/'after_R07_S02_restored_full/manifest.json')
after,afr=h.read_json(m.S/'after_R07_S02_restored_full/after_frames.json')
v=after['values'];line=sum(v['Scan.SpeedGet'][2:4]);frame=v['Scan.FrameGet'];rows=v['Scan.BufferGet'][3]
h.require(mf['scan_direction']==0 and rows==240 and frame[4]==0 and line==1.8240000009536743,'Actual down-raster timing differs')
lo,hi=audit['phases']['scan_core_between_observations']['zero_based_sample_half_open']
first,last=lo//m.BLOCK+1,(hi-1)//m.BLOCK+1;base=(first-1)*m.BLOCK
arrays=[];files=[]
for num in range(first,last+1):
    name=f'{m.PREFIX}{num:05d}.dat';meta=receipt['files'][name];p=h.local(m.S/'native_R07'/name);raw=p.read_bytes()
    h.require(h.sha(raw)==meta['sha256'] and len(raw)==meta['bytes'] and meta['rows']==25000,'Raw data changed')
    arrays.append(h.parse_block(raw,25000));files.append({'path':str(p),'sha256':meta['sha256']})
a=np.concatenate(arrays);del arrays
core=a[lo-base:hi-base];start=audit['brackets']['start'];start_bounds=[start['before']['native_s'],start['after']['native_s']]

def location(index):
    index=int(index)
    t=index*m.DT
    row_range=[math.floor((t-start_bounds[1])/line),math.floor((t-start_bounds[0])/line)]
    center=(sum(row_range)/2+.5)/rows
    return {'native_s':t,'block':index//m.BLOCK+1,'row_zero_based_in_DAT':index%m.BLOCK,
            'nominal_scan_row_zero_based_range_from_start_bracket':row_range,
            'nominal_frame_Y_nm_using_row_centers':(frame[1]+frame[3]*(.5-center))*1e9,
            'scope':'Approximate row timing only. Allow at least one-row uncertainty for positioning and raster timing. No X, scan-direction half-line or physical-object attribution.'}

groups={}
for threshold in [400,1000]:
    mask=np.abs(core[:,0])>=threshold;edges=np.diff(np.r_[False,mask,False].astype(int));beg,end=np.flatnonzero(edges==1),np.flatnonzero(edges==-1)
    result=[]
    for st,en in zip(beg,end,strict=True):
        peak=st+int(np.argmin(core[st:en,0]));j=lo+peak
        result.append({'samples':int(en-st),'duration_ms':float((en-st)*m.DT*1000),
                       'native_seconds_half_open':[(lo+int(st))*m.DT,(lo+int(en))*m.DT],
                       'minimum_I_pA':float(core[peak,0]),'Z_at_peak_nm':float(core[peak,2]),'location':location(j)})
    groups[str(threshold)]={'groups':len(result),'samples':int(mask.sum()),
                            'longest':max(result,key=lambda x:x['samples']) if result else None,
                            'minimum_current_group':min(result,key=lambda x:x['minimum_I_pA']) if result else None,
                            'all_groups':result if threshold==1000 else None}
result={'source_sha256':h.sha(Path(__file__).read_bytes()),'sources':{'native_audit':ar,'receipt':rr,'manifest':mr,'after_frames':afr,'raw_blocks':files},
        'actual_line_period_s':line,'start_native_s_outer':start_bounds,'groups':groups,
        'restored_configuration_wait_before_scan':audit['phases']['S02_restore_speed_receipt_end_to_validation_Start'],
        'post_scan_recovery_through577':audit['phases']['post_event_context_unclassified'],
        'interpretation':['Approximate row timing is calculated from actual Start bounds and read-back line period. Image correspondence is needed before relating an electrical group to a physical feature.',
                          'No sample in this restored-condition scan core reaches the historical negative digitizer edge. The preceding changed-setting exposure216 has a different current reference, speed and gain.',
                          'Native current stability does not imply zero Z working-point drift. Raster Z is not fixed-point noise. This report does not decide image usability or induced bad state.'],
        'limits':['No high-rate XY or hardware line trigger is recorded. Row indices and Y are conditional timing estimates, not exact spatial measurements.',
                  'Current peaks are sampled values within measurement bandwidth. No high-rate sample reaches the historical negative digitizer value in this scan.',
                  'This electrical audit does not decide task usability, chemical composition, induced bad state or repair success.']}
p=D/'S02_restored217_peak_rows_and_recovery.json'
encoded=json.dumps(result,indent=2,allow_nan=False)+'\n'
with p.open('x') as f:f.write(encoded)
print(str(p),h.sha(p.read_bytes()))
print(json.dumps({k:{x:y for x,y in z.items() if x!='all_groups'} for k,z in groups.items()}))
