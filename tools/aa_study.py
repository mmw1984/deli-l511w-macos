#!/usr/bin/env python3
"""Linux rendering approximation; measures decoded Deli JPEG, not printer optics."""
import ctypes
import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat
from parse_deli import parse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/aa-study'
FONT = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
W, H = 1024, 768


def scene(scale, aliased=False):
    image = Image.new('RGB', (W * scale, H * scale), 'white')
    draw = ImageDraw.Draw(image)
    if aliased:
        draw.fontmode = '1'
    for y, size, color, text in (
        (24.4, 60, 'black', 'Printer Aa 0123 /\\'),
        (115.2, 32, 'black', 'Small text: Illl 1 / fine edges'),
        (185.6, 80, 'black', '600 dpi — Smooth'),
        (300.4, 60, '#e01020', 'Red text Aa 0123 /\\'),
        (405.1, 48, '#1020df', 'Blue text Aa 0123 /\\'),
    ):
        draw.text((24.2 * scale, y * scale), text, font=ImageFont.truetype(str(FONT), size * scale), fill=color)
    for i, width in enumerate((0.35, 0.7, 1.0, 1.5, 2.0)):
        y = 540.3 + i * 32.2
        draw.line((30.2 * scale, y * scale, 950.7 * scale, (y + 29.4) * scale),
                  fill='black', width=max(1, round(width * scale)))
    return image


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(['make', 'build/raw_raster', 'build/rastertodeli'], cwd=ROOT, check=True)
    subprocess.run(['cc', '-std=c11', '-O2', '-shared', '-fPIC', str(ROOT / 'src/resample.c'),
                    '-lm', '-o', str(OUT / 'resample.so')], check=True)
    downsample = ctypes.CDLL(str(OUT / 'resample.so')).deli_downsample
    downsample.argtypes = [ctypes.c_char_p] + [ctypes.c_uint] * 6 + [ctypes.c_void_p]
    reference = scene(8).resize((W, H), Image.Resampling.BOX)
    reference.save(OUT / 'reference.png')
    gray = reference.convert('L')
    edge = ImageChops.subtract(gray.filter(ImageFilter.MaxFilter(3)), gray.filter(ImageFilter.MinFilter(3))).point(lambda x: 255 if x > 12 else 0)
    white = gray.filter(ImageFilter.MinFilter(7)).point(lambda x: 255 if x == 255 else 0)
    variants = [('aliased', scene(1, aliased=True))]
    for scale in (2, 4):
        source = scene(scale).convert('RGBA').tobytes()
        for kernel, name in enumerate(('box', 'lanczos3', 'mitchell')):
            dest = ctypes.create_string_buffer(W * H * 4)
            assert downsample(source, W, H * scale, scale, 0, H, kernel, dest)
            image = Image.frombytes('RGBA', (W, H), dest.raw).convert('RGB')
            variants.append((f'{scale}x-{name}', image))
            if name == 'box':
                luminance = image.convert('L')
                edges = ImageChops.subtract(luminance.filter(ImageFilter.MaxFilter(3)), luminance.filter(ImageFilter.MinFilter(3))).point(lambda x: 255 if x > 12 else 0)
                darkened = image.point(lambda x: round(255 * (x / 255) ** 1.1))
                variants.append((f'{scale}x-{name}-gamma', Image.composite(darkened, image, edges)))
            if scale == 4 and name != 'box':
                variants.append((f'{scale}x-{name}-unsharp', image.filter(ImageFilter.UnsharpMask(radius=0.5, percent=30, threshold=2))))
    results = []
    panels = [('8x area reference', reference)]
    for name, image in variants:
        image.save(OUT / f'{name}-input.png')
        raw = OUT / 'input.raw'
        raw.write_bytes(image.tobytes())
        raster = subprocess.check_output([str(ROOT / 'build/raw_raster'), str(W), str(H), '0', str(raw)])
        encoded = subprocess.run([str(ROOT / 'build/rastertodeli'), '1', 'study', name, '1', 'ColorModel=RGB'], input=raster, capture_output=True, check=True).stdout
        (OUT / f'{name}.prn').write_bytes(encoded)
        decoded, = parse(encoded, verbose=False)
        decoded.save(OUT / f'{name}-decoded.png')
        diff = ImageChops.difference(reference, decoded)
        def psnr(mask=None):
            mse = sum(x*x for x in ImageStat.Stat(diff, mask).rms) / 3
            return 10 * math.log10(255*255/mse)
        row = dict(name=name, psnr=psnr(), edge_psnr=psnr(edge),
                   white_mae=ImageStat.Stat(ImageChops.invert(decoded.convert('L')), white).mean[0])
        results.append(row)
        print(f"{name:22} PSNR={row['psnr']:.3f} dB edge-PSNR={row['edge_psnr']:.3f} dB white-MAE={row['white_mae']:.4f}", flush=True)
        panels.append((f"{name} / edge {row['edge_psnr']:.2f} dB", decoded))
    (OUT / 'metrics.json').write_text(json.dumps(results, indent=2) + '\n')
    montage = Image.new('RGB', (1320, 4 * 380), '#dddddd')
    label_font = ImageFont.truetype(str(FONT), 19)
    for i, (label, image) in enumerate(panels):
        x, y = (i % 3) * 440, (i // 3) * 380
        ImageDraw.Draw(montage).text((x + 8, y + 8), label, font=label_font, fill='black')
        for j, box in enumerate(((20, 20, 220, 75), (20, 300, 220, 355), (100, 590, 300, 645))):
            montage.paste(image.crop(box).resize((400, 110), Image.Resampling.NEAREST), (x + 8, y + 38 + j * 112))
    montage.save(OUT / 'compare.png')
    print('Evidence: build/aa-study/compare.png; metrics.json; *-decoded.png')


if __name__ == '__main__':
    main()
