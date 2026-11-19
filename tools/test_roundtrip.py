#!/usr/bin/env python3
"""Synthetic, hardware-free checks. All artifacts stay in build/test/."""
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops, ImageStat, ImageDraw

from parse_deli import InvalidStream, parse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/test"


def raster(mode, height, pages=1, invalid=None):
    ppm = OUT / f"input-{mode}.ppm"
    args = [str(ROOT / "build/make_raster"), mode, str(height), str(pages), str(ppm)]
    if invalid:
        args.append(invalid)
    return subprocess.run(args, check=True, stdout=subprocess.PIPE).stdout, ppm


def run(data, options="", copies="1", user="test-user", title="test-page"):
    return subprocess.run([str(ROOT / "build/rastertodeli"), "1", user, title, copies, options],
                          input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def must_reject(data, message):
    try:
        parse(data, verbose=False)
    except (InvalidStream, OSError, UnicodeError):
        return
    raise AssertionError(f"parser accepted {message}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    panels = []
    baseline = None
    for mode in ("rgb", "gray"):
        data, ppm = raster(mode, 537, 2)
        options = "DeliQuality=High PageSize=A4"
        result = run(data, options, "2")
        assert result.returncode == 0, result.stderr.decode()
        prn = OUT / f"{mode}.prn"
        prn.write_bytes(result.stdout)
        decoded = parse(result.stdout, OUT / f"decoded-{mode}")
        assert len(decoded) == 2
        with Image.open(ppm) as original:
            for image in decoded:
                assert original.size == image.size and original.mode == image.mode
                error = max(ImageStat.Stat(ImageChops.difference(original, image)).mean)
                assert error < 8, f"{mode}: excessive JPEG MAE {error}"
            print(f"ROUNDTRIP {mode}: 2 pages, 3 bands/page, max-channel MAE={error:.3f} < 8 PASS")
            panels.extend((original.convert("RGB"), decoded[0].convert("RGB")))
        if mode == "rgb":
            baseline = result.stdout
    montage = Image.new("RGB", (384*4, 567), "white")
    draw = ImageDraw.Draw(montage)
    for i, (label, panel) in enumerate(zip(("RGB input", "RGB decoded", "Gray input", "Gray decoded"), panels)):
        draw.text((384*i+8, 8), label, fill="black")
        montage.paste(panel, (384*i, 30))
    montage.save(OUT / "comparison.png")

    for height in (1, 7, 8, 9, 16, 63, 64, 65, 255, 256, 257):
        data, _ = raster("gray", height)
        result = run(data)
        assert result.returncode == 0, result.stderr.decode()
        assert parse(result.stdout, verbose=False)[0].height == height
    print("PASS: full/partial bands and row-token boundaries (11 heights)")

    for paper in ("A4", "Letter", "A5", "Photo4x6"):
        for media in ("Auto", "Plain", "Photo", "Matte", "Envelope", "Postcard"):
            for quality in ("Draft", "Normal", "High"):
                result = run(data, f"PageSize={paper} MediaType={media} DeliQuality={quality}")
                assert result.returncode == 0, result.stderr.decode()
                parse(result.stdout, verbose=False)
    print("PASS: 72 paper/media/quality combinations")

    # Untrusted CUPS argv fields cannot introduce ESC, quotes, or PJL commands.
    result = run(data, user='user\"\n@PJL EOJ\x1b', title='title\r\n\x1b\\\"')
    assert result.returncode == 0
    parse(result.stdout, verbose=False)
    print("PASS: PJL metadata injection sanitized")

    empty = run(b"")
    assert empty.returncode != 0 and b"ERROR:" in empty.stderr and not empty.stdout
    for invalid in ("resolution", "depth", "duplex", "colorspace", "mixed"):
        bad, _ = raster("rgb", 9, 2, invalid)
        result = run(bad)
        assert result.returncode != 0 and b"ERROR:" in result.stderr, invalid
    for bad in (data[:100], data[:-10]):
        result = run(bad)
        assert result.returncode != 0 and b"ERROR:" in result.stderr, result.stderr
    for opts in ("PageSize=Unknown", "MediaType=Unknown", "DeliQuality=Unknown"):
        result = run(data, opts)
        assert result.returncode != 0 and b"ERROR:" in result.stderr
    for copies in ("0", "65536", "garbage"):
        assert run(data, copies=copies).returncode != 0
    path = OUT / "from-file.ras"
    path.write_bytes(data)
    result = subprocess.run([str(ROOT / "build/rastertodeli"), "1", "u", "t", "1", "", str(path)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0
    parse(result.stdout, verbose=False)
    print("PASS: file/stdin input; empty, truncated, unsupported raster/options/copies rejected")

    # Mutate every byte of the binary record sequence, not just one checksum.
    # Payload corruption must also be caught before handing data to JPEG decoding.
    start = baseline.index(b"\xd1\x58\x02\x58\x02\xf8\x89")
    legal_changes = set()
    for pattern, offsets in ((b"\xc8\xc0\x02A4\xf8\x25", (4,)),):
        pos = baseline.find(pattern, start)
        while pos != -1:
            legal_changes.update(pos+n for n in offsets)
            pos = baseline.find(pattern, pos+1)
    for offset in range(start, len(baseline)):
        # A4->A5 is another legal paper name, not a malformed record.
        if offset in legal_changes:
            continue
        changed = bytearray(baseline)
        changed[offset] ^= 1
        must_reject(bytes(changed), f"binary mutation at {offset}")
    for bad in (b"", baseline[:20], baseline[:-1], baseline + b"junk"):
        must_reject(bad, "truncation/empty/trailing bytes")
    changed = bytearray(baseline)
    changed[baseline.index(b"@PJL SET RESOLUTION=600")+20] = ord("3")
    must_reject(bytes(changed), "PJL corruption")
    print("PASS: every binary byte mutation rejected (except legal A4->A5); truncation/trailing/PJL corruption rejected")
    print("ALL TESTS PASSED; visual evidence: build/test/comparison.png")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, InvalidStream, OSError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
