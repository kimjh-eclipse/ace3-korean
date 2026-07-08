# -*- coding: utf-8 -*-
"""셸/HUD 폰트 엔트리 내 모든 0x10000 컨테이너 열거 → 전체 문자열 추출(미포착 포함).
각 폰트별 정확한 사용 한자 집계 + 미포착 문자열 목록 저장."""
import sys, struct, json, os, glob
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

f = open(A.ISO, "rb")
toc = A.load_toc()
sf = json.load(open(A.W + "\\shellfonts2.json"))
KANJI_LO, KANJI_HI = 0x889F, 0x9872

def enum_containers(b):
    """엔트리 전체에서 유효 0x10000 문자열 컨테이너 열거"""
    conts = []
    o = 0
    N = len(b)
    while o + 0x30 <= N:
        r = A.try_parse(b, o)
        if r:
            conts.append(r)
            o += max(0x10, r["csize"] & ~0xF)
        else:
            o += 16
    return conts

def kanji_in(bs):
    out = set(); i = 0; n = len(bs)
    while i + 1 < n:
        b0 = bs[i]
        if 0x81 <= b0 <= 0x9f or 0xe0 <= b0 <= 0xef:
            c = (b0 << 8) | bs[i+1]
            if KANJI_LO <= c <= KANJI_HI:
                out.add(c)
            i += 2
        else:
            i += 1
    return out

allstr = {}   # id -> set of strings
used_kanji = {}  # id -> set
for x in sf["fonts"]:
    b = A.read_entry(f, toc[x["eidx"]])
    conts = enum_containers(b)
    strs = set()
    uk = set()
    for c in conts:
        for slot, off, raw in c["strs"]:
            try:
                t = raw.decode("shift_jis")
            except Exception:
                continue
            strs.add(t)
            uk |= kanji_in(raw)
    allstr[x["id"]] = strs
    used_kanji[x["id"]] = uk
    print(f"id{x['id']}: 컨테이너 {len(conts)}  문자열 {len(strs)}  사용한자 {len(uk)}")

# 폰트 한자 코드 vs used → 기증가능
print("\n[폰트별 기증가능(미사용 한자)]")
for x in sf["fonts"]:
    b = A.read_entry(f, toc[x["eidx"]])
    o = x["fb"] + 0x2c; fk = set()
    for _ in range(x["nranges"]):
        a, z, gi = struct.unpack_from("<III", b, o); o += 12
        for c in range(a, z+1):
            if KANJI_LO <= c <= KANJI_HI: fk.add(c)
    free = fk - used_kanji[x["id"]]
    print(f"  id{x['id']}: 한자 {len(fk)}  used {len(fk & used_kanji[x['id']])}  기증가능 {len(free)}")

json.dump({str(k): sorted(v) for k, v in used_kanji.items()},
          open(A.W + "\\shell_used_by_font.json", "w"))

# tl 커버리지: 각 폰트 문자열 중 번역 존재 비율
tl = {}
for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
    tl.update(json.load(open(p, encoding="utf-8")))
tl = {k: v for k, v in tl.items() if v and v != k}
print("\n[폰트별 번역 커버리지]")
allu = set()
for x in sf["fonts"]:
    allu |= allstr[x["id"]]
    hit = sum(1 for t in allstr[x["id"]] if t in tl)
    print(f"  id{x['id']}: 문자열 {len(allstr[x['id']])}  번역됨 {hit}")
print(f"셸 전체 고유 문자열 {len(allu)}, 번역됨 {sum(1 for t in allu if t in tl)}")
json.dump(sorted(allu), open(A.W + "\\shell_all_strings.json", "w"), ensure_ascii=False, indent=0)
print("-> shell_all_strings.json (전량 번역 대상)")
