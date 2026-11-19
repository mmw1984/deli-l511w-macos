"""Validate manifest references, inventory every artifact, zip and verify bytes."""
from pathlib import Path
import json, hashlib, zipfile, collections

ROOT=Path(__file__).resolve().parents[1]
ZIP=ROOT.parent/'deli_l511w_golden_prn_v2.zip'
def sha(b): return hashlib.sha256(b).hexdigest()
manifest=ROOT/'manifest.json'
m=json.loads(manifest.read_text(encoding='utf-8-sig'))
assert len(m['jobs'])==16
for j in m['jobs']:
    p=Path(j['filename']); b=p.read_bytes()
    assert len(b)>0 and len(b)==j['fileSize'] and sha(b)==j['sha256'].lower()
    for key in ('ticketFile','devmodeBlob'): assert Path(j[key]).is_file()
    for source in j['sourceImages']: assert Path(source).is_file()
    assert j['devcaps']['LOGPIXELSX']==j['devcaps']['LOGPIXELSY']==600
    assert len(bytes.fromhex(j['driverExtraHex']))==j['devmode']['dmDriverExtra']
files=sorted(p for p in ROOT.rglob('*') if p.is_file())
m['artifactInventory']=[dict(filename=p.relative_to(ROOT).as_posix(),fileSize=p.stat().st_size,sha256=sha(p.read_bytes())) for p in files if p!=manifest]
m['artifactInventoryNote']='Every archive file except manifest.json itself; self-hashing is intentionally excluded. Job paths refer to this Windows capture machine.'
manifest.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
assert json.loads(manifest.read_text())['jobs']==m['jobs']
with zipfile.ZipFile(ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files: z.write(p,p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(ZIP) as z:
    names=z.namelist()
    assert z.testzip() is None
    assert sum(n.lower().endswith('.prn') for n in names)==16
    assert sum(n.lower().endswith('.png') for n in names)==3
    assert set(names)=={p.relative_to(ROOT).as_posix() for p in files}
    for p in files: assert sha(z.read(p.relative_to(ROOT).as_posix()))==sha(p.read_bytes())
    summary=collections.Counter(n.split('/')[0] if '/' in n else '(root files)' for n in names)
    listing='\n'.join(f'{i.file_size:10d} {i.filename}' for i in z.infolist())+'\n'
    (ROOT.parent/'deli_l511w_golden_prn_v2_listing.txt').write_text(listing,encoding='utf-8')
    print('ZIP:',ZIP)
    print('Size:',ZIP.stat().st_size,'bytes')
    print('Entries:',len(names),'files; .prn count:',sum(n.lower().endswith('.prn') for n in names))
    print('.png count:',sum(n.lower().endswith('.png') for n in names))
    print('Listing summary:',dict(sorted(summary.items())))
    print('CRC test: OK; every archived file SHA256 matches source; manifest JSON and all 16 job references/hashes validated.')
    print('ZIP SHA256:',sha(ZIP.read_bytes()))
    print('Full listing:',ROOT.parent/'deli_l511w_golden_prn_v2_listing.txt')
    print('PRN listing:')
    for i in z.infolist():
        if i.filename.lower().endswith('.prn'): print(i.file_size,i.filename)
