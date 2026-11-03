"""Secondary shared-translation sensitivity. Matched raw images and task ROIs remain unchanged."""
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent
S=D.parents[1]/'session_02'
sys.path.insert(0,str(S.parents[1]/'ag110_plot_dependencies'))
import numpy as np

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def ref(p):return {'path':str(p),'sha256':sha(p)}

def main():
    review=D/'restored_vs_215/image_measurements.json'
    r=json.loads(review.read_bytes())
    if r['pair_type']!='actual215_vs_R07_S02_full02_restored_validation':raise ValueError('Complete S02 restored image pair required')
    planes=[]
    for role,name in [('reference','after_R07_S01_recovered_full'),('observed','after_R07_S02_restored_full')]:
        p=S/name/'analysis/analysis_planes.npz'
        if not any(x['path']==str(p) and x['sha256']==sha(p) for x in r['sources'][r['actual_native_labels'][role]]):
            raise ValueError('Frame differs from completed comparison')
        planes.append(np.load(p))
    regions={reg['id']:reg['rc_half_open'] for reg in r['regions']}
    # Same auxiliary patches reused from 207/208 before this post-induction frame review. Vertical edge supplies primarily cross-edge (X) sensitivity.
    regions.update(central_steep_edge=[139,162,133,168],left_lower_edge=[145,165,15,46])
    pitch=50/240
    offsets=range(-12,13)
    options=[(dy,dx) for dy in offsets for dx in offsets]
    all_scores={}
    for region,(a,b,c,d) in regions.items():
        by_dir={}
        for direction in 'FB':
            before,after=[ar[f'z{direction}_nm'] for ar in planes]
            x=before[a:b,c:d];x=x-x.mean()
            scores=[]
            for dy,dx in options:
                y=after[a+dy:b+dy,c+dx:d+dx];y=y-y.mean()
                norm=np.linalg.norm(x)*np.linalg.norm(y)
                scores.append(float(np.sum(x*y)/norm) if norm else -1.)
            by_dir[direction]=np.array(scores)
        all_scores[region]=by_dir
    zero=options.index((0,0))
    def point(scores,i):
        dy,dx=options[i];return {'dy_rows':dy,'dx_cols':dx,'dx_nm':dx*pitch,'dy_nominal_Y_nm':-dy*pitch,'corr':float(scores[i]),'on_search_boundary':max(abs(dy),abs(dx))==12}
    ctrls=['C1_upper_isolated','C3_diagonal_edge','S1_left_nonselected_I03_candidate']
    shared=np.mean([all_scores[k][d] for k in ctrls for d in 'FB'],axis=0)
    best=int(np.argmax(shared));separated=sorted((i for i,k in enumerate(options) if max(abs(a-b) for a,b in zip(k,options[best]))>=3),key=lambda i:shared[i],reverse=True)
    result={'scope':'Secondary descriptive sensitivity. Search over +/-12 pixels with untouched raw before crops and shifted after crops in corresponding directions. Positive dx/dy is target displacement toward later column/row. No resampling or registration applied to primary figures.',
            'shared_anchor_basis':'C1/C3 are the R07 retained primary remote regions and S1 is a prospectively added secondary remote region. C2 and D4 are locally affected by the I03 mound and cannot select the shared displacement. Two historical fixed terrace patches are reported descriptively only; edge geometry constrains primarily cross-edge motion.',
            'regions':regions,'pitch_nm':pitch,'shared_peak':point(shared,best),'shared_zero':point(shared,zero),
            'best_alternative_at_least_three_pixels_away':point(shared,separated[0]),'by_region':{},
            'not_identifiable_if':'Direction-to-direction or feature-to-feature offsets disagree; best shift on boundary; displaced shape differs or multiple near-equal offset families. Edge correlation along its own tangent is underdetermined.',
            'inputs':[ref(review),ref(Path(__file__))]}
    for key,by_dir in all_scores.items():
        result['by_region'][key]={d:{'zero':point(scores,zero),'independent_best':point(scores,int(np.argmax(scores))),
                                      'at_shared_displacement':point(scores,best)} for d,scores in by_dir.items()}
    out=D/'restored_vs_215/landmark_displacement.json'
    with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(sha(out),result['shared_zero'],result['shared_peak'])
if __name__=='__main__':main()
