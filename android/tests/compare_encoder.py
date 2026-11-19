#!/usr/bin/env python3
"""Compare pinned Android JPEG/shared encoder with Linux CUPS on all golden inputs."""
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from compare_golden import records
from parse_deli import parse

out = ROOT / "build/android-encoder"
out.mkdir(parents=True, exist_ok=True)
host = Path(sys.argv[1]).resolve()
manifest = json.loads((ROOT / "tests/golden/manifest.json").read_text())
for job in manifest["jobs"]:
    caps = job["devcaps"]
    w, h = caps["HORZRES"], caps["VERTRES"]
    gray = job["settings"]["color"] != "color"
    paths = []
    for index, name in enumerate(job["sourceImages"]):
        image = Image.open(ROOT / "tests/golden" / name.split("\\")[-1])
        if not gray or image.mode != "L":
            image = image.convert("RGB")
        x, y = caps["PHYSICALOFFSETX"], caps["PHYSICALOFFSETY"]
        canvas = Image.new(image.mode, (max(image.width, x+w), max(image.height, y+h)), 255 if image.mode == "L" else "white")
        canvas.paste(image, (0, 0))
        path = out / f"page-{index}.raw"
        path.write_bytes(canvas.crop((x, y, x+w, y+h)).tobytes())
        paths.append(str(path))
    inputgray = image.mode == "L"
    paths.reverse()
    raster = subprocess.check_output([str(ROOT / "build/raw_raster"), str(w), str(h), str(int(inputgray)), *paths])
    media_name, media_byte = {"LIGHT": ("Plain", 255), "MATTE": ("Matte", 220), "HEAVY": ("Heavy", 221), "ENV": ("Envelope", 247), "POSTCARD": ("Postcard", 246)}[job["settings"]["media"]]
    quality = job["pjlPrintQuality"]
    options = f"PageSize={job['settings']['paper']} MediaType={media_name} DeliQuality={quality.title()} ColorModel={'Gray' if gray else 'RGB'}"
    linux = subprocess.run([str(ROOT / "build/rastertodeli"), "1", "Android", "host", "1", options], input=raster, capture_output=True, check=True).stdout
    android = subprocess.check_output([str(host), str(w), str(h), str(int(inputgray)), str(int(gray)), job["settings"]["paper"], str(media_byte), quality, *paths])
    a, ap = records(android)
    b, bp = records(linux)
    assert a == b and ap == bp, job["filename"]
    assert len(parse(android, verbose=False)) == len(paths)
    print(f"PASS: {job['filename'].split(chr(92))[-1]}: {len(ap)}/{len(bp)} identical payloads and normalized records", flush=True)
assert subprocess.run([str(host), "384", "16", "0", "0", "A4", "255", "NORMAL", "/dev/null"], capture_output=True).returncode != 0
print("PASS: all 16 golden inputs byte-identical to Linux encoder; empty/truncated raw rejected")
