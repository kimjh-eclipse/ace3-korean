# -*- coding: utf-8 -*-
"""셸/HUD 폰트 컨테이너가 실제 쓰는 한자(0x889F~0x9872) 전수 조사.
- db 포착 문자열 + 원시 바이트 SJIS 스캔(미포착 문자열까지) 합집합.
- 번역되는 문자열은 한자가 한글로 대체되므로 '보존 필요 없음'이지만,
  안전을 위해 '번역 안 되는(원문 유지) 문자열'이 쓰는 한자를 used로 집계.
"""
import sys, struct, json, os, glob, re
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

f = open(A.ISO, "rb")
toc = A.load_toc()
sf = json.load(open(A.W + "\\shellfonts2.json"))
font_eidx = {x["eidx"] for x in sf["fonts"]}
font_ids = {x["id"] for x in sf["fonts"]}

tl = {}
for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
    tl.update(json.load(open(p, encoding="utf-8")))
tl = {k: v for k, v in tl.items() if v and v != k}

KANJI_LO, KANJI_HI = 0x889F, 0x9872

def kanji_in(text_bytes):
    out = set()
    i = 0
    n = len(text_bytes)
    while i + 1 < n:
        c = (text_bytes[i] << 8) | text_bytes[i + 1]
        b0 = text_bytes[i]
        if 0x81 <= b0 <= 0x9f or 0xe0 <= b0 <= 0xef:
            if KANJI_LO <= c <= KANJI_HI:
                out.add(c)
            i += 2
        else:
            i += 1
    return out

# 원시 바이트 스캔: 각 폰트 엔트리 전체에서 SJIS 한자 코드 집계 (미포착 포함)
raw_used = set()
for x in sf["fonts"]:
    b = A.read_entry(f, toc[x["eidx"]])
    raw_used |= kanji_in(b)
print(f"원시 스캔 used 한자: {len(raw_used)}")

# db 포착: 번역 안 되는 문자열의 한자만 (번역되면 한글로 치환)
db = json.load(open(os.path.join(A.W, "db.json"), encoding="utf-8"))
untrans_used = set()
trans_used = set()
for d in db:
    if d["id"] not in font_ids:
        continue
    for s in d["strs"]:
        ks = kanji_in(bytes.fromhex(s["hex"]))
        if s["t"] in tl:
            trans_used |= ks
        else:
            untrans_used |= ks

print(f"db 미번역 문자열 used 한자: {len(untrans_used)}")
print(f"db 번역 문자열 한자(치환됨): {len(trans_used)}")

# 최종 used = 원시 전체(미포착 안전) — 가장 보수적
used = raw_used
# 폰트 내 존재하는 한자 코드 전체(각 폰트 레인지 기준)
def font_kanji_codes(x):
    b = A.read_entry(f, toc[x["eidx"]])
    tbl = x["fb"] + 0x2c
    o = tbl; codes = set()
    for _ in range(x["nranges"]):
        a, z, gi = struct.unpack_from("<III", b, o); o += 12
        for c in range(a, z + 1):
            if KANJI_LO <= c <= KANJI_HI:
                codes.add(c)
    return codes

# 각 폰트별 기증 가능(미사용) 한자 수
print("\n[폰트별 한자/미사용(기증가능)]")
min_free = 10**9
for x in sf["fonts"]:
    fk = font_kanji_codes(x)
    free = fk - used
    min_free = min(min_free, len(free))
    print(f"  id{x['id']}: 한자 {len(fk)}  used {len(fk & used)}  기증가능 {len(free)}")
print(f"\n모든 폰트 공통 최소 기증가능 = {min_free}")
print(f"현재 필요한 셸 음절 ≈ 253")

json.dump(sorted(used), open(A.W + "\\shell_used_kanji.json", "w"))
print("-> shell_used_kanji.json")
