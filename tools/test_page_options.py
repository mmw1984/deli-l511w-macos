#!/usr/bin/env python3
"""Exercise shared mono selection and cached raster manual-duplex output."""
from pathlib import Path
import subprocess
from parse_deli import parse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/test"


def run(data, options, copies="1"):
    return subprocess.run([str(ROOT / 'build/rastertodeli'), '1', 'test', 'page-options',
                           copies, options], input=data, capture_output=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for n in range(1, 8):
        data = subprocess.check_output([str(ROOT / 'build/make_raster'), 'rgb', '16',
                                        str(n), str(OUT / 'duplex-input.ppm'), 'pagecode'])
        for mode in ('Odd', 'Even'):
            for order in ('Auto', 'Reverse', 'Normal'):
                result = run(data, f'DeliDuplex={mode} DeliPass2Order={order}', '2')
                assert result.returncode == 0, result.stderr
                images = parse(result.stdout, verbose=False)
                assert len(images) == (n + 1) // 2
                expected = [2 * i + (1 if mode == 'Odd' else 2) for i in range((n + 1) // 2)]
                expected = [p if p <= n else 0 for p in expected]
                if mode == 'Odd' or order != 'Normal':
                    expected.reverse()
                for image, number in zip(images, expected):
                    level = number * 25 if number else 255
                    assert all(abs(v - level) <= 1 for v in image.getpixel((10, 10)))
                assert b'\xc1\x02\x00\xf8\xec' in result.stdout
                assert b'\xc1\x02\x00\xf8\x31' in result.stdout
                if mode == 'Even' and n % 2:
                    blank = images[-1 if order == 'Normal' else 0]
                    assert all(low == high == 255 for low, high in blank.getextrema())
        mono = run(data, 'ColorModel=RGB print-color-mode=monochrome')
        reference = run(data, 'ColorModel=Gray')
        assert mono.returncode == reference.returncode == 0
        a, b = parse(mono.stdout, verbose=False), parse(reference.stdout, verbose=False)
        assert len(a) == len(b) == n
        assert all(x.mode == 'L' and x.tobytes() == y.tobytes() for x, y in zip(a, b))
    empty = run(data, 'page-ranges=99-100')
    assert empty.returncode == 0 and empty.stdout == b''
    selected = run(data, 'page-ranges=2-6 page-set=even outputorder=reverse')
    assert selected.returncode == 0, selected.stderr
    assert [im.getpixel((10, 10))[0] for im in parse(selected.stdout, verbose=False)] == [150, 100, 50]
    standard = run(data, 'media=na_letter_8.5x11in,stationery print-quality=5 reverse=true')
    assert standard.returncode == 0, standard.stderr
    assert b'LETTER' in standard.stdout and b'PRINTQUALITY=HIGH\n' in standard.stdout
    for options in ('DeliDuplex=bad', 'DeliPass2Order=bad', 'page-ranges=0',
                    'page-set=bad', 'print-color-mode=bad', 'media=bogus', 'print-quality=0'):
        assert run(data, options).returncode != 0
    print('PASS: raster 1-7 pages, both passes/all orders, odd-count blanks, copies=2')
    print('PASS: IPP monochrome matches calibrated ColorModel=Gray; empty/error selections')


if __name__ == '__main__':
    main()
