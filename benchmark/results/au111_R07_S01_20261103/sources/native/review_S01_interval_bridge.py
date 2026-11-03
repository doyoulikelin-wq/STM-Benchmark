"""Offline continuity from the prior frozen receipt to a later actual S01 stage."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
D=Path(__file__).resolve().parent;B=D/'review_native_phases.py'
assert hashlib.sha256(B.read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
s=importlib.util.spec_from_file_location('S01_bridge_base',B);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
h,np=m.h,m.np

def main():
    p=argparse.ArgumentParser()
    for key in ['prior-receipt','receipt','stage-audit','output']:p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args();output=h.local(args.output);h.require(not output.exists(),'New output required')
    old,oref=h.read_json(args.prior_receipt);new,nref=h.read_json(args.receipt);audit,aref=h.read_json(args.stage_audit)
    h.require(old['recording_segment_id']==new['recording_segment_id']=='R07' and old['native_start_identity']==new['native_start_identity']=='2026/11/3 13:45:34','Recorder segment differs')
    h.require(all(new['files'][k]['sha256']==v['sha256'] and new['files'][k]['rows']==v['rows'] for k,v in old['files'].items()),'Prior immutable native prefix changed')
    if 'steps' in audit:
        stop=audit['milestones']['before']['before']['sample'];sp=audit['steps'][0]['previous_setpoint_pA'];stage=audit['mode']
    else:
        stop=audit['boundaries']['entry']['before']['sample'];stage=audit['stage'];sp=audit['phases']['entry_before_configuration']['setpoint_reference_pA']
    start=old['complete_through_index']*m.BLOCK
    h.require(0<start<stop<=new['complete_through_index']*m.BLOCK,'Bridge already covered, inverted or unarchived')
    first=start//m.BLOCK+1;last=(stop-1)//m.BLOCK+1;base=(first-1)*m.BLOCK
    arrays=[];files=[]
    for block in range(first,last+1):
        name=f'{m.PREFIX}{block:05d}.dat';meta=new['files'][name];path=h.local(m.S/'native_R07'/name);raw=path.read_bytes()
        h.require(str(path)==meta['local_path'] and len(raw)==meta['bytes'] and h.sha(raw)==meta['sha256'] and meta['rows']==m.BLOCK and meta['source_double_read_sha_equal'] and meta['local_reread_sha_equal'],'Native block verification failed')
        arrays.append(h.parse_block(raw,m.BLOCK));files.append({'path':str(path),'sha256':meta['sha256'],'rows':m.BLOCK})
    a=np.concatenate(arrays);del arrays
    values=json.loads((m.L/'before.json').read_text())['values'];limits=sorted(v*1e9 for v in values['ZCtrl.LimitsGet'])
    def describe(lo,hi):
        r=m.stats(a,lo-base,hi-base,sp,limits);r['zero_based_sample_half_open']=[lo,hi];r['native_seconds_half_open']=[lo*m.DT,hi*m.DT];r['setpoint_reference_pA']=sp
        if hi>lo:
            v=a[lo-base:hi-base];j=lo+int(np.argmin(v[:,0]));r['minimum_I_location']={'block':j//m.BLOCK+1,'row_zero_based':j%m.BLOCK}
            r['Bias_not_minus1V_samples']=int(np.count_nonzero(v[:,1]!=-1.));r['fraction_native_current_within20pct_setpoint']=float(np.mean((-1.2*sp<=v[:,0])&(v[:,0]<=-.8*sp)))
            for d in r['abs_I_sample_exceedances_pA'].values():
                if d['longest_native_seconds_half_open']:d['longest_native_seconds_half_open']=[t+base*m.DT for t in d['longest_native_seconds_half_open']]
            if r['Z_changes']['pair_first_native_s'] is not None:r['Z_changes']['pair_first_native_s']+=base*m.DT
        return r
    result={'scope':'Complete native interval between preceding frozen receipt endpoint and current stage entry lower bound. No new hardware or permission.',
            'source_sha256':h.sha(Path(__file__).read_bytes()),'base_source':{'path':str(B),'sha256':h.sha(B.read_bytes())},'stage':stage,
            'sources':{'prior_receipt':oref,'receipt':nref,'stage_native_audit':aref,'raw_blocks':files},
            'whole_interval':describe(start,stop),'last10s_or_shorter':describe(max(start,stop-20000),stop),
            'fixed10s_windows':[dict(partial_tail=min(i+20000,stop)-i<20000,**describe(i,min(i+20000,stop))) for i in range(start,stop,20000)],
            'limits':['Current and Z continuity alone do not exclude every unrecorded manual action. Root independently verifies exclusive operation and control state.',
                      'End boundary is inherited from asynchronous native counter and host stage reads. It is not a hardware trigger.',
                      'Software threshold descriptors do not determine image quality or calibrated analog peaks. Z trend need not be zero.']}
    encoded=json.dumps(result,indent=2,allow_nan=False)+'\n'
    with output.open('x') as f:f.write(encoded)
    print(str(output),h.sha(output.read_bytes()))
    for k in ['whole_interval','last10s_or_shorter']:
        v=result[k];print(k,v['native_seconds_half_open'],'I',v['samples']['Current_pA'],'Z_RMS',v['Z_linear_residual_RMS_pm'],'Z_slope',v['Z_linear_slope_pm_per_s'],'>=400',v['abs_I_ge400pA_samples'],'Biasother',v['Bias_not_minus1V_samples'])

if __name__=='__main__':main()
