# -*- coding: utf-8 -*-
"""id1200xxx 폰트 구조 검증([tex][pal][fb]) + 해당 엔트리 문자열 표본 + L2 사용코드 합집합"""
import sys, struct, json, os
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

f = open(A.ISO, "rb")
toc = A.load_toc()
allf = json.load(open(A.W + "\\allfonts.json"))
cand = [x for x in allf if x["nranges"] and x["nranges"] > 100]

def parse_ranges(b, tbl, n):
    rs = []
    o = tbl
    for _ in range(n):
        rs.append(struct.unpack_from("<III", b, o)); o += 12
    return rs

def grid_err(b, met, ng, scale, which):
    err = 0.0; n = 0
    for i in range(0, ng, max(1, ng // 150)):
        u0, v0, u1, v1 = struct.unpack_from("<4f", b, met + i * 24)
        for v in ((u0, u1) if which == "u" else (v0, v1)):
            err += abs(v * scale - round(v * scale)); n += 1
    return err / n

results = []
reserved = set()
for x in cand:
    e = toc[x["eidx"]]
    b = A.read_entry(f, e)
    fb, nr, ng = x["rel"], x["nranges"], x["nglyph"]
    tbl = fb + 0x2c
    met = fb + struct.unpack_from("<I", b, fb + 0x18)[0]
    pal, tex = fb - 0x40, fb - 0x40 - 0x40000
    ue, ve = grid_err(b, met, ng, 1024, "u"), grid_err(b, met, ng, 512, "v")
    pal0 = [struct.unpack_from("<I", b, pal + 4 * i)[0] for i in range(16)]
    ok = tex >= 0 and ue < 0.01 and ve < 0.01
    rs = parse_ranges(b, tbl, nr)
    for a, z, gi in rs:
        for c in range(a, z + 1):
            if 0x9873 <= c <= 0xF9FF:
                reserved.add(c)
    results.append(dict(eidx=x["eidx"], id=x["id"], fb=fb, size=x["size"], nranges=nr,
                        nglyph=ng, met=met, pal=pal, tex=tex,
                        uerr=round(ue, 4), verr=round(ve, 4), ok1024x512=bool(ok)))
    print(f"id{x['id']}: fb={fb:#x} met={met:#x} tex={tex:#x} uerr={ue:.4f} verr={ve:.4f} "
          f"{'OK' if ok else '??'} pal[0..3]={['%08x' % v for v in pal0[:4]]}")

print("\nL2 예약 합집합(0x9873-0xF9FF):", sorted(hex(c) for c in reserved))
json.dump(dict(fonts=results, reserved_l2=sorted(reserved)),
          open(A.W + "\\shellfonts2.json", "w"), indent=1)

# 1200xxx 엔트리 문자열 표본
db = json.load(open(os.path.join(A.W, "db.json"), encoding="utf-8"))
import collections
cnt = collections.Counter()
samples = collections.defaultdict(list)
for d in db:
    if 1200000 <= d["id"] <= 1299999:
        for s in d["strs"]:
            cnt[d["id"]] += 1
            if len(samples[d["id"]]) < 6:
                samples[d["id"]].append(s["t"][:36])
print("\n[id 1200xxx 문자열]")
for eid in sorted(cnt):
    print(f"  id{eid}: {cnt[eid]}개  예: {samples[eid][:4]}")
