#!/usr/bin/env python3
"""Recover the mono tone curve and discriminate luminance models from v2 PRNs."""
import json
from pathlib import Path
import statistics

from PIL import Image
from parse_deli import parse

ROOT = Path(__file__).resolve().parents[1]


def derive():
    fixtures = ROOT / 'tests/golden'
    source = Image.open(fixtures / 'a4_gray_600.png')
    gray = parse((fixtures / 'prn/gray_mono_a4_media-light.prn').read_bytes(), verbose=False)[0]
    color = parse((fixtures / 'prn/color_mono_a4_media-light.prn').read_bytes(), verbose=False)[0]
    samples = [[] for _ in range(256)]
    for y in range(1616, 2585, 16):
        for x in range(gray.width):
            samples[source.getpixel((x+96,y))].append(gray.getpixel((x,y-96)))
    # Clipping removes ramp levels 0..3 and 251..255; flat black/white fix endpoints.
    samples[0] = list(gray.crop((3520,400,3800,1000)).tobytes())
    samples[255] = list(gray.crop((0,0,gray.width,100)).tobytes())
    lut = [round(statistics.median(s)) if s else None for s in samples]
    missing = [i for i,v in enumerate(lut) if v is None]
    for i in missing:
        lo = max(j for j in range(i) if samples[j])
        hi = min(j for j in range(i+1,256) if samples[j])
        lut[i] = round(lut[lo]+(lut[hi]-lut[lo])*(i-lo)/(hi-lo))
    assert all(a <= b for a,b in zip(lut,lut[1:])), 'nonmonotonic median curve'
    differences = [b-a for a,b in zip(lut,lut[1:])]
    rgb = [(255,0,0),(0,255,0),(0,0,255),(0,255,255),
           (255,0,255),(255,255,0),(0,0,0),(128,128,128)]
    observed = [round(statistics.median(color.crop((250+i*560,400,550+i*560,1000)).tobytes()))
                for i in range(8)]
    weights = {'BT601':(299,587,114,1000), 'decimal-GDI':(30,59,11,100),
               'BT709':(2126,7152,722,10000), 'integer-256':(77,150,29,256),
               'integer-65536':(19595,38470,7471,65536)}
    models = []
    for name,(r,g,b,scale) in weights.items():
        for order in ('before-luminance','after-luminance'):
            predicted = []
            for pixel in rgb:
                values = [lut[v] for v in pixel] if order == 'before-luminance' else pixel
                v = (r*values[0]+g*values[1]+b*values[2]+scale//2)//scale
                predicted.append(v if order == 'before-luminance' else lut[v])
            models.append(dict(model=name, lut_order=order, predicted=predicted,
                               squared_error=sum((a-b)**2 for a,b in zip(predicted,observed))))
    return dict(lut=lut, interpolated_levels=missing, monotonic=True,
                max_step=max(differences),
                max_second_difference=max(abs(b-a) for a,b in zip(differences,differences[1:])),
                observed_bars=observed, models=models)


if __name__ == '__main__':
    print(json.dumps(derive(), indent=2))
