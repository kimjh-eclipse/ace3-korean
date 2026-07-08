# -*- coding: utf-8 -*-
"""ISO 전체에서 폰트 블록(magic 0x10000 + size + type 0x13) 스캔 → 엔트리 매핑"""
import sys, struct, re, json, bisect
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

f = open(A.ISO, "rb")
toc = A.load_toc()
spans = sorted((A.DATA_OFF + e["off"], A.DATA_OFF + e["off"] + e["size"], e["i"], e["id"]) for e in toc)
starts = [s[0] for s in spans]

def locate(abs_off):
    k = bisect.bisect_right(starts, abs_off) - 1
    if k >= 0 and spans[k][0] <= abs_off < spans[k][1]:
        s = spans[k]
        return s[2], s[3], abs_off - s[0]
    return None, None, None

PAT = re.compile(rb"\x00\x00\x01\x00..\x00\x00\x13\x00\x00\x00", re.S)
CH = 1 << 24
hits = []
f.seek(0)
pos = 0
prev = b""
while True:
    chunk = f.read(CH)
    if not chunk:
        break
    data = prev + chunk
    base = pos - len(prev)
    for m in PAT.finditer(data):
        off = base + m.start()
        if off % 16 == 0:
            hits.append(off)
    prev = data[-16:]
    pos += len(chunk)

print(f"폰트 블록 후보 {len(hits)}건")
out = []
for off in hits:
    eidx, eid, rel = locate(off)
    size = None
    f.seek(off + 4)
    size = struct.unpack("<I", f.read(4))[0]
    f.seek(off + 0x10)
    cnt = struct.unpack("<I", f.read(4))[0]
    ng, nr = cnt >> 16, (cnt & 0xFFFF) - 1
    out.append(dict(abs=off, eidx=eidx, id=eid, rel=rel, size=size, nglyph=ng, nranges=nr))
    print(f"  abs={off:#x} idx={eidx} id={eid} rel={hex(rel) if rel is not None else '?'} size={size:#x} gly={ng} rng={nr}")
json.dump(out, open(A.W + "\\allfonts.json", "w"), indent=1)
