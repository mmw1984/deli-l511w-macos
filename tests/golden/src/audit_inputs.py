from pathlib import Path
import hashlib,json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
EXPECTED={'band':'856d6a0a897036d41aa8cd3642652506a7912ea2645fa2db6deeab900713ede4','color':'72e14afd7402682e75c66578b0ae3f19d83a73fec6477d8a2a990b95736c56bf','gray':'bcfec8f1e86c151a133a6ff927cacfd4afd01ee60e0c1571a094ba2395629d99'}
OLD=[Path(r'C:\Users\Administrator\attachments')/folder/name for folder,name in [('efe779af-c5fa-49d3-a1bb-d3d3baf4088b','a4_color_600.png'),('39b00802-ba68-47b6-8e56-b41b3bd83821','a4_gray_600.png'),('b9d976c8-2990-47c7-a499-9732e466b6e9','a4_band_600.png')]]
def info(p):
 with Image.open(p) as im:
  raw=im.tobytes(); mode=im.mode
  return dict(filename=str(p),width=im.width,height=im.height,mode=mode,dpi=im.info.get('dpi'),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pixel_sha256=hashlib.sha256(raw).hexdigest(),mode_and_pixel_sha256=hashlib.sha256(mode.encode('ascii')+b'\0'+raw).hexdigest(),rgb_bgr_sha256=hashlib.sha256(im.convert('RGB').tobytes('raw','BGR')).hexdigest())
old=[info(p) for p in OLD];new=[]
for key in ('color','gray','band'):
 x=info(ROOT/'inputs'/f'a4_{key}_600.png');assert (x['width'],x['height'])==(4960,7016)
 x['expected_file_sha256']=EXPECTED[key];x['matches_user_expected_file_sha256']=x['sha256']==EXPECTED[key];new.append(x)
result=dict(original_attachments=old,inputs=new,pixel_hash_definition='pixel_sha256=SHA256(Image.tobytes()); mode is recorded separately. mode_and_pixel_sha256=SHA256(ASCII mode + NUL + Image.tobytes()).')
(ROOT/'input-audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
