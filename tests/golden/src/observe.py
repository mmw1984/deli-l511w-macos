"""Validate static NOTES.md framing against captured PRNs; no JPEG decoding."""
from pathlib import Path
import struct, json, hashlib, re

ROOT = Path(__file__).resolve().parents[1]
SIG = bytes.fromhex('c0 cc f8 2c 7b')
def hx(s): return bytes.fromhex(s)
def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def u32(b, o): return struct.unpack_from('<I', b, o)[0]
def begin(w,h,y,d,n,s):
    return (SIG+hx('d3 00 00')+struct.pack('<H',y)+hx('f8 4c 6b c0 00 f8 64 c0 02 f8 62 c1')+struct.pack('<H',w)+hx('f8 6c c1')+struct.pack('<H',h)+hx('f8 6b d1')+struct.pack('<HH',w,h)+hx('f8 67 c0 08 f8 fa c0 02 f8 f9 c1 00 00 f8 f8 c1')+struct.pack('<H',d)+hx('f8 f7 c1 06 00 f8 f6 b0 c1 00 00 f8 6d c1')+struct.pack('<H',h)+hx('f8 63 c0 f6 f8 65 c2')+struct.pack('<I',s)+hx('f8 f5 b1 fa')+struct.pack('<I',n))
def end(h): return hx('c1 00 00 f8 6d c1')+struct.pack('<H',h)+hx('f8 63 c0 f7 f8 65 c2 aa 00 00 00 f8 f5 b1 fa 01 00 00 00 aa b2')
def dump(b,start,stop):
    lines=[]
    for o in range(start,min(stop,len(b)),16):
        row=b[o:min(o+16,stop)]
        groups=' '.join(row[i:i+2].hex() for i in range(0,len(row),2))
        lines.append(f'{o:08x}: {groups:<39}  '+''.join(chr(c) if 32<=c<127 else '.' for c in row))
    return '\n'.join(lines)
def parse(path):
    b=path.read_bytes(); records=[]; gaps=[]; cursor=b.find(SIG)
    assert cursor>=0
    first=cursor
    while True:
        o=cursor; w,h,y,d=u16(b,o+22),u16(b,o+27),u16(b,o+8),u16(b,o+52)
        n,s=u32(b,o+85),u32(b,o+77)
        assert b[o:o+89]==begin(w,h,y,d,n,s),(path.name,o,'begin')
        payload=b[o+89:o+89+n]; assert len(payload)==n
        assert s==0xfa+sum(struct.pack('<I',n))+sum(payload),(path.name,o,'checksum')
        e=o+89+n; assert b[e:e+29]==end(h),(path.name,e,'end')
        assert payload[:2]==hx('ff2c')
        token=[0xd7,0xd0,0xd1,0xd2,0xd3,0xd4,0xd5,0xd6,0xd7][((h+7)//8)%8]
        assert payload[-2:]==bytes([255,token]),(path.name,h,payload[-2:].hex())
        records.append(dict(offset=o,width=w,height=h,y=y,dpi=d,length=n,checksum=s,payloadOffset=o+89,endOffset=e+29,payloadTail=payload[-2:].hex()))
        cursor=e+29
        if b[cursor:cursor+5]==SIG: continue
        nxt=b.find(SIG,cursor)
        gaps.append(dict(offset=cursor,end=len(b) if nxt<0 else nxt,hex=b[cursor:len(b) if nxt<0 else nxt].hex(' ')))
        if nxt<0: break
        cursor=nxt
    session=b.find(hx('d158025802f889'))
    pages=[]; current=[]
    for r in records:
        if r['y']==0 and current: pages.append(current);current=[]
        assert r['y']==sum(i['height'] for i in current)
        current.append(r)
    pages.append(current)
    return dict(file=path.name,size=len(b),sessionOffset=session,firstBand=first,pagePrefixOffset=session+51,pagePrefixHex=b[session+51:first].hex(' '),pjl=b[:b.find(b') HP')].decode('ascii'),records=records,gaps=gaps,pages=[dict(bands=len(p),width=p[0]['width'],height=sum(r['height'] for r in p),first=p[0]['offset'],last=p[-1]['offset']) for p in pages])

def main():
    results=[parse(p) for p in sorted((ROOT/'prn').glob('*.prn'))]
    (ROOT/'stream-observations.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    b=(ROOT/'prn/color_a4_media-light.prn').read_bytes(); r=next(x for x in results if x['file']=='color_a4_media-light.prn')['records'][0]
    (ROOT/'first512.hex.txt').write_text(dump(b,0,512)+'\n')
    (ROOT/'first-band-context.hex.txt').write_text(dump(b,r['offset']-128,r['endOffset']+128)+'\n')
    base=next(x for x in results if x['file']=='color_a4_media-light.prn')
    for x in results:
        print(x['file'], 'session',x['sessionOffset'],'first',x['firstBand'],'pages',x['pages'],'gaps',[(g['offset'],g['end']) for g in x['gaps']])
        if x['file'].startswith('color_a4_') or x['file'].startswith('color_mono'):
            a=set(base['pjl'].splitlines()); bb=set(x['pjl'].splitlines())
            print(' PJL changes:',sorted(a-bb),'=>',sorted(bb-a))
            print(' prefix',x['pagePrefixOffset'],x['pagePrefixHex'])
    print('Validated',len(results),'files;',sum(len(x['records']) for x in results),'band records: exact BeginImage/EndImage templates, LE dimensions/lengths, checksums and marker tokens.')
if __name__=='__main__': main()
