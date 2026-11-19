#!/usr/bin/env python3
"""Compare all Windows captures with independently rasterized source PNG crops.

JPEG headers are stripped on the wire: their equality is necessarily inferred
from entropy equivalence, not a comparison with unavailable original headers.
"""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess

from PIL import Image, ImageChops, ImageStat
from parse_deli import Reader, parse_pjl, session, page_start, begin_image, end_image, parse

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'tests/golden'
OUT = ROOT / 'build/golden'


def records(data):
    r = Reader(data)
    gray = parse_pjl(r)
    session(r)
    chunks, payloads = [data[:r.pos]], []
    while data[r.pos:r.pos+2] != b'IB':
        start = r.pos
        page_start(r, gray)
        chunks.append(data[start:r.pos])
        while data[r.pos:r.pos+2] == b'\xc0\xcc':
            start = r.pos
            w, h, y, payload, _ = begin_image(r)
            header = bytearray(data[start:start+89])
            # Payload checksum and byte count are image-dependent fields.
            header[76:80] = bytes(4)
            header[85:89] = bytes(4)
            chunks.append(bytes(header))
            payloads.append(payload)
            start = r.pos
            end_image(r, h)
            chunks.append(data[start:r.pos])
        start = r.pos
        r.typed(2, 0x31)
        r.expect(b'\x44')
        chunks.append(data[start:r.pos])
    chunks.append(data[r.pos:])
    normalized = b''.join(chunks)
    normalized = re.sub(rb'FPRINTFILEID="[^"]+"', b'FPRINTFILEID="MASKED"', normalized)
    normalized = re.sub(rb'FDATETIME=[0-9.]+', b'FDATETIME=MASKED', normalized)
    return normalized, payloads


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((FIX / 'manifest.json').read_text())
    for job in manifest['jobs']:
        name = job['filename'].split('\\')[-1]
        golden = (FIX / 'prn' / name).read_bytes()
        assert hashlib.sha256(golden).hexdigest().upper() == job['sha256']
        reference = parse(golden, verbose=False)
        caps = job['devcaps']
        w, h = caps['HORZRES'], caps['VERTRES']
        gray = job['settings']['color'] != 'color'
        raw = []
        for i, source in enumerate(job['sourceImages']):
            image = Image.open(FIX / source.split('\\')[-1])
            assert hashlib.sha256(image.tobytes()).hexdigest() == job['sourcePixelSha256'][i]
            if gray:
                image = image.convert('L')
            else:
                image = image.convert('RGB')
            x, y = caps['PHYSICALOFFSETX'], caps['PHYSICALOFFSETY']
            canvas = Image.new(image.mode, (max(image.width,x+w), max(image.height,y+h)),
                               255 if gray else (255,255,255))
            canvas.paste(image, (0,0))
            image = canvas.crop((x, y, x+w, y+h))
            path = OUT / f'{Path(name).stem}-{i}.raw'
            path.write_bytes(image.tobytes())
            raw.append(str(path))
        # GPD OutputOrderReversed and PPD DefaultOutputOrder: CUPS delivers last first.
        raster = subprocess.run([str(ROOT/'build/raw_raster'), str(w), str(h), str(int(gray)), *reversed(raw)],
                                check=True, stdout=subprocess.PIPE).stdout
        pjl_user = re.search(rb'USERNAME="([^"]*)"', golden)[1].decode()
        host = re.search(rb'HOSTID="([^"]*)"', golden)[1].decode()
        quality = {'NORMAL':'Normal', 'HIGH':'High', 'DRAFT':'Draft'}[job['pjlPrintQuality']]
        media = {'LIGHT':'Plain','HEAVY':'Heavy','MATTE':'Matte','ENV':'Envelope','POSTCARD':'Postcard'}[job['settings']['media']]
        options = f"PageSize={job['settings']['paper']} MediaType={media} DeliQuality={quality}"
        result = subprocess.run([str(ROOT/'build/rastertodeli'), '1', pjl_user,
                                 job['settings']['job'], '1', options], input=raster,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={**os.environ, 'HOSTNAME':host}, check=True)
        generated = result.stdout
        (OUT/name).write_bytes(generated)
        actual = parse(generated, verbose=False)
        a, ap = records(generated)
        b, bp = records(golden)
        assert a == b, f'{name}: non-image records differ at '+str(next(i for i,(x,y) in enumerate(zip(a,b)) if x!=y))
        assert len(ap) == len(bp)
        equal = sum(x == y for x,y in zip(ap,bp))
        squared, count = 0, 0
        for x,y in zip(actual,reference):
            assert x.size == y.size and x.mode == y.mode
            stat = ImageStat.Stat(ImageChops.difference(x,y))
            squared += sum(stat.sum2)
            count += x.width*x.height*len(x.getbands())
        psnr = math.inf if squared == 0 else 10*math.log10(255**2/(squared/count))
        print(f'{name}: records=IDENTICAL tables=IJG-Q90/{"1-component" if gray else "YCbCr-422"}/DRI-row (inferred) payloads={equal}/{len(ap)} identical PSNR={psnr:.2f}dB', flush=True)
        if name == 'band_a4_media-light.prn':
            reference[0].crop((0,0,1000,512)).save(OUT/'band-golden.png')
        if name == 'color_a4_media-light.prn':
            reference[0].crop((0,0,2000,1200)).save(OUT/'color-golden.png')
    print('PASS: all 16 golden streams parsed, decoded and compared; dynamic metadata masked')


if __name__ == '__main__':
    main()
