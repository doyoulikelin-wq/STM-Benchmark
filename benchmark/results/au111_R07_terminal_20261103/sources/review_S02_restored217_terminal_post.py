"""Offline post217 through independently stopped R07 terminal, including its partial final block. Earlier audits remain unchanged."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
D=Path(__file__).resolve().parent;B=D/'review_native_phases.py'
assert hashlib.sha256(B.read_bytes()).hexdigest()=='778bce93fe03199a3b68b3dbc923119b481d73dab9442b1d4b804c94d5dc17e8'
s=importlib.util.spec_from_file_location('R07_post217_base',B);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
h,np=m.h,m.np

def main():
    p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    output=h.local(args.output);h.require(not output.exists(),'New output only')
    old,oref=h.read_json(D/'S02_restored217_native_review.json');h.require(oref['sha256']=='5036e1d18649bac186e1061d78884528f5aeb879ec8d2baf516d91c3e12acb53','Previous completed audit changed')
    rr,rref=h.read_json(args.receipt);ready,readyref=h.read_json(m.L/'READY.json')
    h.require(rr['recording_segment_id']=='R07' and rr['native_start_identity']==ready['native_start_identity'] and all(h.sha((m.L/n).read_bytes())==d for n,d in m.LOGGER_IDENTITY_PINS.items()),'Actual recorder changed')
    h.require(rref['sha256']=='f626b3cc741852d14c1b598e8928b50deeecf33704b2a387a31c3f82c4707e51' and rr['all_blocks_including_last_archived'] and rr['terminal_rows']==24260 and rr['complete_through_index']==636, 'Exact complete terminal receipt required')
    terminal_review,tref=h.read_json(m.C/'R07_terminal_native_review/review.json')
    h.require(tref['sha256']=='263fd80c619f0bbac726f7887a3dc4fb85091870c5c02b5f624c5b8d3b711caf' and terminal_review['receipt']['sha256']==rref['sha256'], 'Terminal review changed')
    prior,pref=h.read_json(D/'S02_post217_through612_native_receipt.json')
    h.require(pref['sha256']=='efc0bda535a98aec60db251b10886116eb47f411a325930734b168e1a887a684', 'Prior612 receipt changed')
    for name,metadata in prior['files'].items():
        h.require(all(metadata[k]==rr['files'][name][k] for k in ['sha256','rows','bytes','local_path']), 'Prior612 native prefix changed')
    start=old['brackets']['end']['after']['sample'];stop=rr['total_rows_per_channel']
    h.require(stop==(rr['complete_through_index']-1)*m.BLOCK+rr['terminal_rows'], 'Terminal row total mismatch')
    first=start//m.BLOCK+1;base=(first-1)*m.BLOCK;h.require(stop>start,'No postscan coverage')
    arrays=[];files=[]
    for block in range(first,rr['complete_through_index']+1):
        name=f'{m.PREFIX}{block:05d}.dat';meta=rr['files'][name];path=h.local(m.S/'native_R07'/name);raw=path.read_bytes()
        h.require(meta['local_path']==str(path) and meta['rows']==(rr['terminal_rows'] if block==rr['complete_through_index'] else m.BLOCK) and len(raw)==meta['bytes'] and h.sha(raw)==meta['sha256'] and meta['two_source_reads_same_sha'] and meta['local_reread_matches'],'Native block verification failed')
        arrays.append(h.parse_block(raw,meta['rows']));files.append({'path':str(path),'sha256':meta['sha256'],'rows':meta['rows']})
    a=np.concatenate(arrays);del arrays
    limits=old['full']['Z_changes']['endpoint_limits_nm_low_high']
    def describe(lo,hi):
        r=m.stats(a,lo-base,hi-base,100.,limits);r['zero_based_sample_half_open']=[lo,hi];r['native_seconds_half_open']=[lo*m.DT,hi*m.DT]
        if hi>lo:
            v=a[lo-base:hi-base];peak=lo+int(np.argmin(v[:,0]));r['minimum_I_location']={'block':peak//m.BLOCK+1,'row_zero_based':peak%m.BLOCK}
            r['Bias_not_minus1V_samples']=int(np.count_nonzero(v[:,1]!=-1.))
            for d in r['abs_I_sample_exceedances_pA'].values():
                if d['longest_native_seconds_half_open']:d['longest_native_seconds_half_open']=[t+base*m.DT for t in d['longest_native_seconds_half_open']]
            if r['Z_changes']['pair_first_native_s'] is not None:r['Z_changes']['pair_first_native_s']+=base*m.DT
        return r
    result={'scope':'All post217 native data through independently verified terminal636 including24260 final rows. Full217 and prior577/612 audits remain unchanged.',
            'source_sha256':h.sha(Path(__file__).read_bytes()),'sources':{'base_reviewer':{'path':str(B),'sha256':h.sha(B.read_bytes())},'prior_full_audit':oref,'prior612_receipt':pref,'terminal_archive_review':tref,'receipt':rref,'logger_ready':readyref,'raw_blocks':files},
            'post217_all':describe(start,stop),'last30s':describe(max(start,stop-60000),stop),'last10s':describe(max(start,stop-20000),stop),
            'fixed10s_windows':[dict(partial_tail=min(i+20000,stop)-i<20000,**describe(i,min(i+20000,stop))) for i in range(start,stop,20000)],
            'limits':['These are local archived native signals ending with stopped terminal636. No later device state or authorization is inferred.',
                      'No high-rate XY, gain or setpoint channel. Bias/current/Z behavior alone cannot prove absence of every possible manual action.',
                      'Timing is relative to this R07 DataLog sample stream. No calibrated analog peak, chemistry or image-quality inference.']}
    encoded=json.dumps(result,indent=2,allow_nan=False)+'\n'
    with output.open('x') as f:f.write(encoded)
    print(str(output),h.sha(output.read_bytes()))
    for k in ['post217_all','last30s','last10s']:
        r=result[k];print(k,r['native_seconds_half_open'],'I',r['samples']['Current_pA'],'Z_RMS',r['Z_linear_residual_RMS_pm'],'Z_slope',r['Z_linear_slope_pm_per_s'],'Zchange',r['Z_changes']['median_last_minus_first_upto100ms_pm'],'>=400',r['abs_I_ge400pA_samples'],'Biasother',r['Bias_not_minus1V_samples'])

if __name__=='__main__':main()
