# -*- coding: utf-8 -*-
"""폰트별 기증 예산 여유 + 새 번역대상 문자열이 어느 폰트에 몰리는지 측정."""
import sys, json, os, struct, glob
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A
import shellfont

tl = {}
for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
    tl.update(json.load(open(p, encoding="utf-8")))
tl = {k: v for k, v in tl.items() if v and v != k}

f = open(A.ISO, "rb")
toc = A.load_toc()
shellfonts_meta = json.load(open(os.path.join(A.W, "shellfonts2.json")))["fonts"]

def is_bootfont(eid):
    return 4000000 <= eid <= 4002999 or 1200000 <= eid <= 1299999

# db + 병합 재현 (build.py enum_records와 동일)
db = json.load(open(os.path.join(A.W, "db.json"), encoding="utf-8"))
have = {(d["idx"], d["base"]) for d in db}
def enum_records(eidx):
    e = toc[eidx]; buf = A.read_entry(f, e); recs = []
    o = 0; N = len(buf)
    while o + 0x30 <= N:
        r = A.try_parse(buf, o)
        if r:
            strs = []
            for slot, off, raw in r["strs"]:
                try: t = raw.decode("shift_jis")
                except Exception: continue
                strs.append({"t": t, "hex": raw.hex(), "off": off, "slot": slot})
            recs.append({"idx": eidx, "id": e["id"], "base": r["base"],
                         "csize": r["csize"], "count": r["count"],
                         "tbloff": r["tbloff"], "strs": strs})
            o += max(0x10, r["csize"] & ~0xF)
        else:
            o += 16
    return recs
for eidx in sorted({x["eidx"] for x in shellfonts_meta}):
    for r in enum_records(eidx):
        if (r["idx"], r["base"]) not in have:
            db.append(r); have.add((r["idx"], r["base"]))

KANJI_LO, KANJI_HI = 0x889F, 0x9872
def kanji_in(bs):
    out = set(); i = 0; n = len(bs)
    while i + 1 < n:
        b0 = bs[i]
        if 0x81 <= b0 <= 0x9f or 0xe0 <= b0 <= 0xef:
            c = (b0 << 8) | bs[i+1]
            if KANJI_LO <= c <= KANJI_HI: out.add(c)
            i += 2
        else: i += 1
    return out

# 현재(번역 반영 후) + 가상(새 문자열까지 번역했을 때) 음절 수요 계산
font_need_cur = {}   # 현재 tl 기준
font_need_hyp = {}   # 새 문자열도 번역됐다고 가정(=문자열의 한글화 필요분을 근사: 일단 미번역이면 그 문자열이 새 음절을 요구한다고 못 봄)
font_keep = {}
font_untl = {}       # eidx -> 미번역 문자열 수
for d in db:
    if not is_bootfont(d["id"]): continue
    fe = d["idx"]
    fn = font_need_cur.setdefault(fe, set())
    fk = font_keep.setdefault(fe, set())
    for s in d["strs"]:
        if s["t"] in tl:
            for ch in tl[s["t"]]:
                if "가" <= ch <= "힣": fn.add(ch)
        else:
            fk |= kanji_in(bytes.fromhex(s["hex"]))
            font_untl[fe] = font_untl.get(fe, 0) + 1

# 폰트별 box_ok 한자 수 → 기증 가능 수, 여유
print(f"{'id':>9} {'eidx':>5} {'hangul':>6} {'keep':>5} {'boxok한자':>8} {'기증가능':>7} {'여유':>5} {'미번역':>6}")
for ft in shellfonts_meta:
    e = toc[ft["eidx"]]
    buf = bytearray(A.read_entry(f, e))
    rs, mets = shellfont.parse_font(buf, ft)
    kanji_gi = {}
    for a, z, gi in rs:
        if KANJI_LO <= a and z <= KANJI_HI:
            for k in range(z - a + 1): kanji_gi[a+k] = gi+k
    def box_ok(g):
        u0,v0,u1,v1 = struct.unpack_from("<4f", mets[g], 0)
        return round((u1-u0)*shellfont.W) >= 17 and round((v1-v0)*shellfont.H) >= 19
    boxok = [c for c in kanji_gi if box_ok(kanji_gi[c])]
    keep = font_keep.get(ft["eidx"], set())
    hangul = len(font_need_cur.get(ft["eidx"], set()))
    donors = [c for c in boxok if c not in keep]
    head = len(donors) - hangul
    print(f"{ft['id']:>9} {ft['eidx']:>5} {hangul:>6} {len(keep&set(kanji_gi)):>5} "
          f"{len(boxok):>8} {len(donors):>7} {head:>5} {font_untl.get(ft['eidx'],0):>6}")
