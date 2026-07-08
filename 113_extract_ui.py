# -*- coding: utf-8 -*-
"""새로 포착된 셸 미번역 중 '번역 대상'(가나/한자 포함)만, 폰트 여유 안전한 것 위주로 추출.
장문(>80, 용어사전 계열 가능성)은 제외하여 4002050/57 예산 초과 회피."""
import sys, json, os, glob
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

tl = {}
for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
    tl.update(json.load(open(p, encoding="utf-8")))
tl = {k: v for k, v in tl.items() if v and v != k}

f = open(A.ISO, "rb"); toc = A.load_toc()
shellfonts_meta = json.load(open(os.path.join(A.W, "shellfonts2.json")))["fonts"]

def is_bootfont(eid): return 4000000 <= eid <= 4002999 or 1200000 <= eid <= 1299999

def has_jp(t):
    """가나/한자 포함 여부(⟦⟧ 태그 내부 제외)"""
    i = 0; L = len(t)
    while i < L:
        ch = t[i]
        if ch == "⟦":
            j = t.find("⟧", i); i = (j+1) if j >= 0 else i+1; continue
        o = ord(ch)
        if 0x3040 <= o <= 0x30ff or 0x4e00 <= o <= 0x9fff:  # 히라/가타/한자
            return True
        i += 1
    return False

def enum_records(eidx):
    e = toc[eidx]; buf = A.read_entry(f, e); out = []
    o = 0; N = len(buf)
    while o + 0x30 <= N:
        r = A.try_parse(buf, o)
        if r:
            for slot, off, raw in r["strs"]:
                try: t = raw.decode("shift_jis")
                except Exception: t = A.decode_tagged(raw)
                out.append((e["id"], t))
            o += max(0x10, r["csize"] & ~0xF)
        else: o += 16
    return out

cand = {}
for eidx in sorted({x["eidx"] for x in shellfonts_meta}):
    for eid, t in enum_records(eidx):
        if not is_bootfont(eid): continue
        if t in tl: continue
        if not has_jp(t): continue      # 순수기호/숫자/아이콘은 번역 불필요
        if len(t) > 80: continue          # 장문 제외(용어사전 계열 → 별도 단계)
        cand[t] = cand.get(t, 0) + 1

uniq = sorted(cand, key=lambda s: (len(s), s))
print(f"번역 대상(단문 UI/시스템): {len(uniq)}")
for t in uniq:
    print(f"  {t!r}")
json.dump(uniq, open(os.path.join(A.W, "ui_to_translate.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n저장: ui_to_translate.json")
