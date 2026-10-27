"""Audit Spine's project-local blue graph palette and render CVD proof images.

Machado, Oliveira & Fernandes (2009), full-severity matrices, applied to linear RGB.
These are simulations, not evidence about any individual's visual perception.
"""
import hashlib
import json
import math
import pathlib
import re
import subprocess
import sys

MATRICES = {
    'protanopia': ((.152286, 1.052583, -.204868), (.114503, .786281, .099216), (-.003882, -.048116, 1.051998)),
    'deuteranopia': ((.367322, .860646, -.227968), (.280085, .672501, .047413), (-.011820, .042940, .968881)),
    'tritanopia': ((1.255528, -.076749, -.178779), (-.078411, .930809, .147602), (.004733, .691367, .303900)),
}


def linear(c):
    return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4


def rgb(color):
    return [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def luminance(values):
    return sum(c * w for c, w in zip(values, (.2126, .7152, .0722)))


def sim(color, matrix=None):
    values = [linear(c) for c in rgb(color)]
    return values if matrix is None else [min(1, max(0, sum(a * b for a, b in zip(row, values)))) for row in matrix]


def contrast(a, b, matrix=None):
    low, high = sorted((luminance(sim(a, matrix)), luminance(sim(b, matrix))))
    return (high + .05) / (low + .05)


def audit(css):
    colors = dict(re.findall(r'--chart-([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})', css))
    checks = []
    roles = [('ink', 'bg', 4.5), ('secondary', 'bg', 4.5), ('blue', 'bg', 3), ('context', 'bg', 3)]
    for mode, matrix in [('normal', None), *MATRICES.items()]:
        for fg, bg, minimum in roles:
            ratio = contrast(colors[fg], colors[bg], matrix)
            checks.append(dict(mode=mode, foreground=fg, background=bg, ratio=ratio, minimum=minimum, passed=ratio >= minimum))
    # Text is backed by opaque white rather than relying on a midpoint blue fill.
    assert all(c['passed'] for c in checks)
    assert colors['bg'].lower() == '#ffffff'
    assert colors['blue'].lower() == '#0052ff'
    return {'palette': colors, 'checks': checks, 'passed': True,
            'heat_labels': 'Opaque white backing; ink for values, secondary for Not run. Fills are redundant to printed values.',
            'method': 'Machado et al. 2009 severity1 matrices on linear RGB; ImageMagick conversions use the same matrices.'}


if __name__ == '__main__':
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    css = pathlib.Path('site/chart-system.css').read_text()
    report = audit(css)
    report['css_sha256'] = hashlib.sha256(css.encode()).hexdigest()
    report['simulations'] = []
    for filename in sys.argv[2:]:
        source = pathlib.Path(filename)
        for name, matrix in MATRICES.items():
            target = out / (source.stem + '-' + name + '.png')
            subprocess.run(['magick', str(source), '-colorspace', 'RGB', '-color-matrix', ' '.join(str(v) for row in matrix for v in row), '-colorspace', 'sRGB', str(target)], check=True)
            report['simulations'].append({'type': name, 'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    (out / 'palette-cvd.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: blue/neutral text and marks meet declared contrast targets under normal and three simulated vision modes.')
