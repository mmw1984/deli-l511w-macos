#!/usr/bin/env python3
"""Strict Enhanced XL parser for the Windows L511W and CUPS subset."""
import argparse
import io
from pathlib import Path
import re
import struct
import sys

from PIL import Image


class InvalidStream(ValueError):
    pass


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, n):
        if n < 0 or n > len(self.data) - self.pos:
            raise InvalidStream(f"truncated record at {self.pos}, need {n} bytes")
        part = self.data[self.pos:self.pos+n]
        self.pos += n
        return part

    def expect(self, value):
        start = self.pos
        if self.take(len(value)) != value:
            raise InvalidStream(f"unexpected record at {start}: expected {value.hex(' ')}")

    def byte(self):
        return self.take(1)[0]

    def integer(self, size):
        return int.from_bytes(self.take(size), "little")

    def typed(self, size, attr):
        self.expect(bytes([0xc0 + {1: 0, 2: 1, 4: 2}[size]]))
        value = self.integer(size)
        self.expect(bytes([0xf8, attr]))
        return value


def check(ok, message):
    if not ok:
        raise InvalidStream(message)


def sos_end(jpeg):
    check(jpeg[:2] == b"\xff\xd8", "missing JPEG SOI")
    pos = 2
    while pos + 4 <= len(jpeg):
        check(jpeg[pos] == 255, "invalid template JPEG")
        marker = jpeg[pos+1]
        length = int.from_bytes(jpeg[pos+2:pos+4], "big")
        check(length >= 2 and pos+length+2 <= len(jpeg), "bad template segment")
        if marker == 0xda:
            return pos + length + 2
        pos += length + 2
    raise InvalidStream("template JPEG lacks SOS")


def decode_band(payload, w, h, gray, quality):
    # Standard IJG tables; using a different API/implementation from the C filter.
    check(payload[:2] == b"\xff\x2c", "missing modified JPEG start marker")
    tokens = [0xd7, 0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6]
    check(payload[-2:] == bytes([255, tokens[((h+7)//8) % 8]]), "bad JPEG row token")
    template = io.BytesIO()
    mode = "L" if gray else "RGB"
    Image.new(mode, (w, h)).save(template, format="JPEG", quality=quality,
                                subsampling=1, optimize=False, progressive=False)
    prefix = template.getvalue()
    end = sos_end(prefix)
    sos = prefix.rfind(b"\xff\xda", 0, end)
    interval = (w + (7 if gray else 15)) // (8 if gray else 16)
    jpeg = (prefix[:sos] + b"\xff\xdd\x00\x04" + interval.to_bytes(2, "big") +
            prefix[sos:end] + payload[2:-1] + b"\xd9")
    with Image.open(io.BytesIO(jpeg)) as im:
        im.load()
        check(im.size == (w, h) and im.mode == mode, "decoded band format mismatch")
        return im.copy()


def parse_pjl(r):
    language = b") HP-PCL XL;2;1;Comment Copyright(c) 1999 Deli Group\n"
    stop = r.data.find(language)
    check(0 <= stop < 16384, "missing/oversized PJL header")
    pjl = r.take(stop)
    r.expect(language)
    check(pjl.startswith(b"\x1b%-12345X"), "missing UEL")
    lines = pjl[9:].splitlines()
    patterns = [
        b"@PJL JOB", b"@PJL SET STRINGCODESET=UTF8", rb'@PJL SET USERNAME="[^"\x00-\x1f\x7f]*"',
        b"@PJL SET LMULTIPAGEPRINT=OFF", b"@PJL COMMENT Deli L511W",
        rb'@PJL LJOBINFO USERID="[^"\x00-\x1f\x7f]*" HOSTID="[^"\x00-\x1f\x7f]*"',
        rb'@PJL SET JOBNAME="[^"\x00-\x1f\x7f]*"', b"@PJL SET ECONOMODE=OFF",
        b"@PJL SET FIMPROVE=OFF", b"@PJL SET FGHOST=OFF", b"@PJL SET FDENSITY=OFF",
        b"@PJL SET PNPQIMPROVE=OFF", rb'@PJL SET FPRINTFILEID="DELIPRINT_[0-9a-f]{16}"',
        rb"@PJL SET FDATETIME=[0-9]+\.[0-9]+", b"@PJL SET LPARM:PCL LFONTPRIORITY=NORESOLUTION",
        b"@PJL SET TIMEOUT=0", rb"@PJL SET LCOLORMODEL=(CMYK|BLACK)",
        rb"@PJL SET LINKSET=(AUTOMATIC|BLACKONLY)", b"@PJL SET LSHARPEN=OFF",
        b"@PJL SET LCTPREFERENCE=IMAGE", rb"@PJL SET PRINTQUALITY=(NORMAL|HIGH|DRAFT)",
        b"@PJL SET LPAGEMODE=NORMAL", b"@PJL SET LCOLLATION=OFF", b"@PJL SET PAGEPROTECT=OFF",
        b"@PJL SET RESOLUTION=600", b"@PJL ENTER LANGUAGE=PCLXL",
    ]
    # Count is derived from schema, not trusted stream data.
    check(len(lines) == len(patterns), "PJL schema line count mismatch")
    for line, pattern in zip(lines, patterns):
        check(re.fullmatch(pattern, line) is not None, f"unexpected PJL field {line!r}")
    gray = lines[16].endswith(b"=BLACK")
    check(lines[17].endswith(b"=BLACKONLY" if gray else b"=AUTOMATIC"), "inconsistent ink set")
    return gray


def session(r):
    start = r.pos
    r.expect(b"\xd1")
    check(r.integer(2) == r.integer(2) == 600, "bad session resolution")
    r.expect(bytes.fromhex("f8 89 c0 00 f8 86 c0 06 f8 8f 41 c0 00 f8 88 c0 01 f8 82 48 c8 c0"))
    n = r.byte()
    check(n == 20, "bad enhanced XL identifier length")
    r.expect(b"Deli Enhanced XL=1.2")
    r.expect(bytes.fromhex("f8 81 47"))
    check(r.pos-start == 51, "bad session record size")


def page_start(r, gray):
    check(r.typed(1, 0x26) == 1 and r.typed(1, 0x28) == 0, "bad simplex setup")
    media = r.typed(1, 0x27)
    check(media in (0xff, 0xdd, 0xdc, 0xf7, 0xf6), "bad media code")
    copies = r.typed(2, 0xec)
    check(copies > 0, "bad page setup copy count")
    if r.data[r.pos] == 0xd5:
        r.expect(bytes.fromhex("d5 de 6e 07 41 7f bf 2f 41 f8 2f c0 00 f8 30 43"))
        name = "LetterCustom"
    else:
        r.expect(bytes.fromhex("c8 c0"))
        name = r.take(r.byte()).decode("ascii")
        check(name in ("A4", "LETTER", "A5", "R4"), "bad paper name")
        r.expect(bytes.fromhex("f8 25"))
    border = name == "R4"
    check(r.typed(1, 0xed) == (1 if border else 2), "bad border selector")
    r.expect(bytes.fromhex("43 d5 00 00 80 3f 00 00 80 3f f8 2b 77 c0 01 f8 47 71 c0 01 f8 48 72"))
    check(r.typed(1, 3) == 2, "bad color selector")
    r.expect(b"\x6a\xd3")
    check(r.integer(2) == r.integer(2) == (0 if border else 96), "bad cursor origin")
    r.expect(bytes.fromhex("f8 2a 75"))
    quality = r.typed(1, 0xef)
    check(quality == 90, "unrecognized JPEG quality")
    check(r.typed(1, 0xee) == 1, "bad page mode")
    r.expect(b"\x40")
    return name, media, quality, copies


def begin_image(r):
    start = r.pos
    check(r.typed(1, 0x2c) == 0xcc, "bad image setup")
    r.expect(b"\x7b\xd3")
    check(r.integer(2) == 0, "bad band X")
    y = r.integer(2)
    r.expect(bytes.fromhex("f8 4c 6b"))
    check(r.typed(1, 0x64) == 0 and r.typed(1, 0x62) == 2, "bad image encoding")
    w, h = r.typed(2, 0x6c), r.typed(2, 0x6b)
    check(0 < w <= 65535 and 0 < h <= 256, "bad band dimensions")
    r.expect(b"\xd1")
    check(r.integer(2) == w and r.integer(2) == h, "inconsistent image dimensions")
    r.expect(bytes.fromhex("f8 67"))
    check(r.typed(1, 0xfa) == 8 and r.typed(1, 0xf9) == 2, "bad depth/encoding")
    check(r.typed(2, 0xf8) == 0 and r.typed(2, 0xf7) == 600, "bad image resolution")
    check(r.typed(2, 0xf6) == 6, "bad vendor attribute f6")
    r.expect(b"\xb0")
    check(r.typed(2, 0x6d) == 0 and r.typed(2, 0x63) == h, "bad read-image region")
    check(r.typed(1, 0x65) == 0xf6, "bad compressed read mode")
    checksum = r.typed(4, 0xf5)
    r.expect(b"\xb1\xfa")
    length = r.integer(4)
    check(r.pos-start == 89, "bad BeginImage size")
    check(4 <= length <= 64*1024*1024, "bad embedded payload length")
    payload = r.take(length)
    actual = (0xfa + sum(length.to_bytes(4, "little")) + sum(payload)) & 0xffffffff
    check(checksum == actual, f"checksum mismatch at Y={y}: {checksum:08x} != {actual:08x}")
    return w, h, y, payload, checksum


def end_image(r, h):
    start = r.pos
    check(r.typed(2, 0x6d) == 0 and r.typed(2, 0x63) == h, "bad end-image region")
    check(r.typed(1, 0x65) == 0xf7 and r.typed(4, 0xf5) == 0xaa, "bad end-image mode/checksum")
    r.expect(b"\xb1\xfa")
    check(r.integer(4) == 1, "bad end-image payload length")
    r.expect(b"\xaa\xb2")
    check(r.pos-start == 29, "bad EndImage size")


def parse(data, output=None, verbose=True):
    r = Reader(data)
    gray = parse_pjl(r)
    session(r)
    pages, total_bands = [], 0
    while r.data[r.pos:r.pos+2] != b"IB":
        name, media, quality, setup_copies = page_start(r, gray)
        bands, y, width, lengths = [], 0, None, []
        while r.data[r.pos:r.pos+2] == b"\xc0\xcc":
            w, h, offset, payload, checksum = begin_image(r)
            check(offset == y and (width is None or width == w), "noncontiguous raster band")
            check(not bands or bands[-1].height == 256, "non-final short band")
            check(y+h <= 65535 and w*(y+h) <= 100_000_000, "decoded page too large")
            width = w
            bands.append(decode_band(payload, w, h, gray, quality))
            end_image(r, h)
            if verbose:
                print(f"  band {len(bands)}: y={y} {w}x{h} payload={len(payload)} checksum={checksum:08x} OK JPEG decoded")
            y += h
            total_bands += 1
            lengths.append(len(payload))
        check(bool(bands), "page has no raster")
        copies = r.typed(2, 0x31)
        check(copies == setup_copies, "inconsistent page copies")
        r.expect(b"\x44")
        image = Image.new("L" if gray else "RGB", (width, y))
        y0 = 0
        for im in bands:
            image.paste(im, (0, y0))
            y0 += im.height
        pages.append(image)
        if output:
            dest = Path(f"{output}-page{len(pages)}.png")
            image.save(dest)
        if verbose:
            print(f"page {len(pages)}: {name} media={media:02x} {'gray' if gray else 'RGB'} "
                  f"{width}x{y} bands={len(bands)} copies={copies} quality={quality} OK")
    r.expect(b"IB\x1b%-12345X@PJL EOJ\n@PJL LPORTROTATE\n\x1b%-12345X")
    check(r.pos == len(data), "trailing bytes after job")
    check(bool(pages), "empty job")
    if verbose:
        print(f"VALID: {len(pages)} pages, {total_bands} bands, {len(data)} bytes; all records/checksums/JPEG bands verified")
    return pages


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stream", type=Path)
    ap.add_argument("--output", type=Path, help="PNG filename prefix (parent must exist)")
    args = ap.parse_args()
    try:
        parse(args.stream.read_bytes(), args.output)
    except (InvalidStream, OSError, UnicodeError, struct.error) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
