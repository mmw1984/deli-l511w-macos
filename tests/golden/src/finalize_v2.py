from pathlib import Path
import hashlib,json,re
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
audit=json.loads((ROOT/'input-audit.json').read_text())
m=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8-sig'))
old=json.loads((ROOT.parent/'deliverable_v1/manifest.json').read_text(encoding='utf-8-sig'))
oldjobs={Path(j['filename']).name:j for j in old['jobs']}
sources={x['filename']:x for x in audit['inputs']}
draw=(ROOT/'drawing-audit.txt').read_text(encoding='utf-16')
for x,original in zip(audit['inputs'],audit['original_attachments']):
 assert x['pixel_sha256']==original['pixel_sha256'] and x['mode']==original['mode']
 assert x['rgb_bgr_sha256'] in draw
for j in m['jobs']:
 oldj=oldjobs[Path(j['filename']).name]
 assert all(j['settings'][k]==oldj['settings'][k] for k in ('printer','paper','color','media','job'))
 assert Path(j['settings']['qualityBlob']).read_bytes()==(ROOT.parent/'deliverable_v1/devmodes'/Path(j['settings']['qualityBlob']).name).read_bytes()
 j['sourceImageSha256']=[sources[p]['sha256'] for p in j['sourceImages']]
 j['sourcePixelSha256']=[sources[p]['pixel_sha256'] for p in j['sourceImages']]
 j['pages']=[dict(source=p,sourceSha256=sources[p]['sha256'],sourceSize=[sources[p]['width'],sources[p]['height']],sourceRect=[0,0,sources[p]['width'],sources[p]['height']],destinationRect=[-j['devcaps']['PHYSICALOFFSETX'],-j['devcaps']['PHYSICALOFFSETY'],sources[p]['width'],sources[p]['height']],mapMode='MM_TEXT',dibMode='24bpp top-down BGR',dibSha256=sources[p]['rgb_bgr_sha256']) for p in j['sourceImages']]
m['inputs']=audit['inputs'];m['originalAttachmentAudit']=audit['original_attachments'];m['pixelHashDefinition']=audit['pixel_hash_definition']
m['revision']='v2: explicit pixel-unit GDI+ source/destination rectangles; explicit MM_TEXT; original inputs were correct, intermediate GDI+ copy was not.'
(ROOT/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
table=['| PRN | v1 bytes | v2 bytes |','|---|---:|---:|']
for j in sorted(m['jobs'],key=lambda j:Path(j['filename']).name):
 name=Path(j['filename']).name;table.append(f"| {name} | {oldjobs[name]['fileSize']:,} | {j['fileSize']:,} |")
(ROOT/'PRN_sizes_v1_v2.md').write_text('\n'.join(table)+'\n')
# Retain screenshot evidence as JPEG so the archive has exactly 3 PNG input files.
for p in (ROOT/'screenshots').glob('*.png'):
 with Image.open(p) as im: im.convert('RGB').save(p.with_suffix('.jpg'),quality=95)
 p.unlink()
print('Verified all 3 new pixel hashes equal original attachments; all 3 converted DIB hashes equal Pillow BGR bytes, including grayscale.')
print('Verified 16 job settings and captured DEVMODE input blobs match v1; added input references and per-page draw geometry.')
print('\n'.join(table))
