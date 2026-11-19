"""Generate offset-backed v2 notes, not v1 numeric claims."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'stream-observations.json').read_text())
base=next(x for x in data if x['file']=='color_a4_media-light.prn')
b=(ROOT/'prn'/base['file']).read_bytes();r=base['records'][0]
lines=['# Observed Deli Enhanced XL - v2 corrected pixel transfer\n\n',
'Driver 1.0.1.4. Decimal zero-based offsets, except hexadecimal dump addresses. Ranges are half-open. v1 is preserved separately; v2 fixes an intermediate GDI+ DPI-dependent copy. Inputs are pixel-identical to original attachments. See INPUT_FINDINGS.md.\n\n',
'## Verified framing and limitations\n\nAll 447 records across 16 PRNs pass static NOTES.md 89-byte BeginImage / 29-byte EndImage templates, LE widths/heights/lengths, additive checksum and ff2c/row-token checks. No core framing contradiction. JPEG headers/tables, sampling and entropy component/plane order remain unverified. Direct Pillow attempts are in decode-check.json; no decoded raster measurements claimed.\n\n',
f"Baseline session={base['sessionOffset']}, page prefix={base['pagePrefixOffset']}, first band={r['offset']}. First band W={r['width']}, H={r['height']}, Y={r['y']}, DPI={r['dpi']}; N={r['length']}, checksum=0x{r['checksum']:08x}. Payload starts at {r['payloadOffset']}; EndImage at {r['endOffset']-29}; next band at {r['endOffset']}. Checksum matches 0xfa + sum(LE32(N)) + sum(payload).\n\n",
'A4 is physical 4960x7015, offsets 96x96; bands cover printable 4768x6824: 26x256 + 168 rows. Full bands end ffd7; last ends ffd4. Fixed image constants do not establish host CMYK planes.\n\n## First 512 bytes (actual xxd)\n\n```text\n']
lines.append(subprocess.check_output([r'C:\Program Files\Git\usr\bin\xxd.exe','-l','512',str(ROOT/'prn'/base['file'])],text=True))
lines.append('```\n\n## Complete first band plus 128 bytes context on each side\n\n```text\n');lines.append((ROOT/'first-band-context.hex.txt').read_text());lines.append('```\n\n## All-file evidence\n\n')
for x in data:
 raw=(ROOT/'prn'/x['file']).read_bytes()
 assert raw[x['sessionOffset']:x['sessionOffset']+51]==b[base['sessionOffset']:base['sessionOffset']+51]
 assert raw[-52:]==b[-52:]
 equal=[i for i,(p,q) in enumerate(zip(base['records'],x['records'])) if b[p['payloadOffset']:p['payloadOffset']+p['length']]==raw[q['payloadOffset']:q['payloadOffset']+q['length']]]
 lines.append(f"### {x['file']}\n\nSize {len(raw)}. Pages: `{x['pages']}`. First payload at {x['records'][0]['payloadOffset']}, length {x['records'][0]['length']}.\n\n")
 if len(x['pages'])==1 and x['pages'][0]['bands']==27: lines.append(f'Exact payload indices equal to baseline (zero-based): `{equal}`.\n\n')
 lines.append(f"Page-prefix [{x['pagePrefixOffset']},{x['firstBand']}): `{x['pagePrefixHex']}`\n\n")
 for g in x['gaps']:lines.append(f"Inter-page/trailer [{g['offset']},{g['end']}): `{g['hex']}`\n\n")
 lines.append('PJL offsets/values:\n\n```text\n')
 for line in raw[:x['sessionOffset']].splitlines():
  if line.startswith(b'@PJL'):lines.append(f'{raw.find(line):8d} {line.decode("ascii")}\n')
 lines.append('```\n\n')
lines.append('''## Gaps versus static NOTES.md

- No framing/length/checksum/endianness contradiction was observed: 447 exact band templates hold.
- PJL additionally contains LMULTIPAGEPRINT=OFF, LJOBINFO, FPRINTFILEID, FDATETIME and LPARM:PCL LFONTPRIORITY=NORESOLUTION. OFF is also present in the two-page job and does not mean single-page.
- Full page prefixes are not semantically decoded by static notes; bytes/offsets are above. Media at prefix+9: LIGHT ff, MATTE dc, HEAVY dd, ENV f7, POSTCARD f6. No PJL media selector was observed.
- Bands represent printable area, not whole sheet. No independent JPEG tables, sampling or component order verification was performed. Fixed c0 02 mode constants are not evidence of separated CMYK planes.
- Quality PJL is NORMAL/HIGH/DRAFT, all 600dpi. Exact payload equality/change indices are above; v1 observations must not be reused. Payload change does not prove a different codec or quality factor.
- Two-page output has one PJL/session start, two band sequences with reset Y, six-byte page end immediately followed by a new page prefix, then final page end + 49 42 + 44-byte PJL job trailer. Boundary offsets/bytes are above; static terminators hold.
- UI quality changes absolute DEVMODE offsets 1112/1142 (private 892/922), not a directly usable absolute +0x4e offset. A nested OEM-structure relationship remains inference.

Run python -B src/observe.py, python -B src/decode_check.py, then python -B src/write_observed_notes.py. No physical printer or reconstructed JPEG decoder was used.
''')
(ROOT/'NOTES_observed.md').write_text(''.join(lines),encoding='utf-8')
print('Wrote v2 NOTES_observed.md, bytes:',(ROOT/'NOTES_observed.md').stat().st_size)
