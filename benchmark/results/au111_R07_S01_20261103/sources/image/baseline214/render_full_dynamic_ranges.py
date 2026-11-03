"""Local completed image pairs only: preserve full raw range and explicitly mark clipping at frozen before-image contrast."""
from pathlib import Path
import datetime, hashlib, json, sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
S = HERE.parents[1] / 'session_02'
sys.path.insert(0, '/Users/maxlin/Desktop/Nanonis/work/ag110_plot_dependencies')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch

def src(p):
    p = Path(p)
    return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}

def main():
    D = HERE / 'baseline_vs_213'
    report = D / 'image_measurements.json'
    m = json.loads(report.read_bytes())
    assert m['pair_type'] == 'prior213_vs_recovered_R07_baseline02'
    labels = m['actual_native_labels']
    arrays = {}
    for role, stage in [('reference', 'after_R06_P03_full'), ('observed', 'baseline_segment07_full02')]:
        p = S / stage / 'analysis/analysis_planes.npz'
        assert src(p) in m['sources'][labels[role]]
        arrays[role] = np.load(p)
    keys = [(r, d) for r in ('reference', 'observed') for d in ('F', 'B')]
    data, offsets = {}, {}
    for r, d in keys:
        raw = arrays[r]['z' + d + '_nm']
        assert raw.shape == (240, 240) and np.isfinite(raw).all()
        offsets[r+d] = float(np.median(raw))
        data[r+d] = raw - offsets[r+d]
    full = [min(float(v.min()) for v in data.values()), max(float(v.max()) for v in data.values())]
    contrast_source = HERE.parent/'R06_induction_I03/after_vs_210/dynamic_range_display_record.json'
    frozen = json.loads(contrast_source.read_bytes())['frozen_baseline_only_p1_p99_nm']
    modes = [('full_raw_range', full), ('frozen_210_contrast_marked_clipping', frozen)]
    result = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'pair': src(report), 'source_script': src(__file__), 'actual_native_labels': labels,
              'method': 'Raw Z minus one whole-frame median per direction; no global plane, row subtraction, smoothing, resampling or registration. Median offsets explicitly saved.',
              'offset_medians_nm': offsets, 'full_range_nm': full, 'inherited_210_terrace_contrast_nm': frozen, 'contrast_source':src(contrast_source),
              'limitations': 'Scalar-normalized displays assess shape and dynamic range, not absolute Z displacement or chemistry. Marked clipping is a visualization choice; raw arrays are unchanged.',
              'panels': {}, 'figures': []}
    for mode, limits in modes:
        fig, ax = plt.subplots(2, 2, figsize=(12, 11), layout='constrained')
        cmap = plt.get_cmap('afmhot').copy()
        cmap.set_over('#ff00bb')
        cmap.set_under('#00bfff')
        counts = {}
        for index, (role, direction) in enumerate(keys):
            aa = ax.flat[index]
            v = data[role+direction]
            over, under = int((v > limits[1]).sum()), int((v < limits[0]).sum())
            label = labels[role] + direction
            counts[label] = {'above_display_limit_pixels': over, 'below_display_limit_pixels': under,
                             'pixels': int(v.size), 'actual_relative_min_max_nm': [float(v.min()), float(v.max())],
                             'raw_min_max_nm': [float(arrays[role]['z'+direction+'_nm'].min()), float(arrays[role]['z'+direction+'_nm'].max())]}
            im = aa.imshow(v, origin='upper', extent=[-25, 25, -25, 25], cmap=cmap,
                           vmin=limits[0], vmax=limits[1], interpolation='nearest')
            aa.set(title=f'{label}: relative min {v.min():.3f}, max {v.max():.3f} nm\nabove={over}; below={under} / 57600 pixels',
                   xlabel='Nominal X (nm)', ylabel='Nominal Y (nm)')
            for reg in m['regions']:
                r0, r1, c0, c1 = reg['rc_half_open']
                color = '#66ff66' if reg['id'] in ['C2_right_upper','D4_lower_object'] else '#66ccff'
                aa.add_patch(Rectangle((-25+c0*50/240,25-r1*50/240),(c1-c0)*50/240,(r1-r0)*50/240,fill=False,edgecolor=color,lw=.7))
                aa.text(-25+c0*50/240,25-r1*50/240,reg['id'].split('_')[0],color=color,fontsize=7)
            aa.scatter(18,-2.1,marker='+',color='#00ffff',s=55)
        title = 'Unclipped common full range' if mode == 'full_raw_range' else 'Inherited 210 terrace contrast; current comparison reference is 213; magenta = ABOVE upper limit, cyan = BELOW lower limit'
        fig.suptitle(f'{title}\nUpper: before {labels["reference"]}; lower: after {labels["observed"]}. Raw heights minus scalar median only.\nPlus marks prior I03 site. New image follows a recording gap. Inspect remote crops separately.',fontsize=11)
        fig.colorbar(im,ax=ax.ravel().tolist(),label='Raw Z minus frame median (nm)',shrink=.8,extend='neither' if mode=='full_raw_range' else 'both')
        out = D / (mode + '.png')
        assert not out.exists()
        fig.savefig(out,dpi=150)
        plt.close(fig)
        result['panels'][mode] = counts
        result['figures'].append(src(out))
    with (D/'dynamic_range_display_record.json').open('x') as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'figures':result['figures'],'limits':{'full':full,'frozen210':frozen},'counts':result['panels']},indent=2))

if __name__ == '__main__':
    main()
