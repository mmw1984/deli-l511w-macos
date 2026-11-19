#!/usr/bin/env python3
"""Native PDF geometry regression and input validation checks."""
from pathlib import Path
import subprocess
import sys

from parse_deli import parse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/test'


def document(content):
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.2 841.8] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
               f'<< /Length {len(content)} >>\nstream\n'.encode() + content + b'\nendstream',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    data = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(data)
    data.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        data.extend(f'{offset:010d} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return data


def run(data, options=''):
    return subprocess.run([str(ROOT / 'build/pdftodeli'), '1', 'test', 'pdf', '1', options],
                          input=data, capture_output=True)


def main():
    if sys.platform != 'darwin':
        print('SKIP: native CoreGraphics PDF checks require macOS')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    data = document(b'0 g 72 700 72 24 re f')
    for rendering in ('Crisp', 'Smooth', 'HighQuality'):
        result = run(data, f'PageSize=A4 DeliRendering={rendering}')
        assert result.returncode == 0, result.stderr
        image, = parse(result.stdout, verbose=False)
        assert image.size == (4768, 6824)
        mask = image.convert('L').point(lambda p: 255 if p < 128 else 0)
        bounds = mask.getbbox()
        assert bounds and all(abs(a-b) <= 2 for a, b in zip(bounds, (504, 886, 1104, 1086))), bounds
        assert image.convert('L').crop((510, 892, 1098, 1080)).getextrema()[1] < 10
        image.save(OUT / f'pdf-{rendering}.png')
    diagonal = document(b'0 G 0.7 w 72.12 700.12 m 144.65 723.73 l S')
    variants = []
    for options in ('', 'DeliRendering=Smooth', 'DeliRendering=Crisp'):
        result = run(diagonal, options)
        assert result.returncode == 0, result.stderr
        image, = parse(result.stdout, verbose=False)
        variants.append(image.tobytes())
    assert variants[0] == variants[1] and variants[0] != variants[2]
    print('PASS: absent Rendering matches Smooth and differs from Crisp on diagonal edges')
    text = document(b'0 g BT /F1 10 Tf 72 700 Td (Printer Aa 0123) Tj ET\n'
                    b'1 0 0 rg BT /F1 10 Tf 72 680 Td (Red Aa 0123) Tj ET\n'
                    b'0 G .08 w 72 650 m 144 654 l S')
    for rendering in ('Smooth', 'HighQuality'):
        result = run(text, f'DeliRendering={rendering}')
        assert result.returncode == 0, result.stderr
        image, = parse(result.stdout, verbose=False)
        assert image.convert('L').getextrema()[0] < 30
        image.save(OUT / f'pdf-text-{rendering}.png')
    blank = run(document(b''), 'DeliRendering=HighQuality')
    assert blank.returncode == 0, blank.stderr
    image, = parse(blank.stdout, verbose=False)
    assert image.getextrema() == ((255, 255),) * 3
    empty = run(data, 'page-ranges=2')
    assert empty.returncode == 0 and not empty.stdout
    for invalid in (b'', b'not a PDF', data[:20]):
        assert run(invalid).returncode != 0
    assert run(data, 'DeliRendering=invalid').returncode != 0
    print('PASS: native PDF Crisp/Smooth/HighQuality geometry, band-crossing solid fill; HQ blank/empty/error input')


if __name__ == '__main__':
    main()
