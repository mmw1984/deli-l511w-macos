from pathlib import Path
from io import BytesIO
import json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
obs=json.loads((ROOT/'stream-observations.json').read_text());out=[]
for name in ('color_a4_media-light.prn','band_a4_media-light.prn'):
 x=next(x for x in obs if x['file']==name);r=x['records'][0];b=(ROOT/'prn'/name).read_bytes()[r['payloadOffset']:r['payloadOffset']+r['length']]
 for label,payload in [('raw modified band',b),('SOI/EOI markers restored only',b'\xff\xd8'+b[2:-2]+b'\xff\xd9')]:
  item=dict(file=name,offset=r['payloadOffset'],length=len(b),attempt=label)
  try:
   im=Image.open(BytesIO(payload));im.load();item.update(decoded=True,size=im.size,mode=im.mode)
  except (OSError,ValueError) as e:item.update(decoded=False,error=str(e))
  out.append(item)
result=dict(attempts=out,conclusion='Not decodable directly or by SOI/EOI restoration alone. JPEG tables/frame/SOS headers are missing; no reconstructed decoder attempted. PRN bar widths/red rows not measured. DIB identity checked separately.')
assert not any(x['decoded'] for x in out),'Payload decoded: implement requested measurements'
(ROOT/'decode-check.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
