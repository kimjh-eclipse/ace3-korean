# -*- coding: utf-8 -*-
"""완화로 새로 포착된 셸(부트폰트) 미번역 고유 문자열 규모 측정 및 추출."""
import sys, json, os, struct
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

# build.py와 동일한 db 로드 + 셸 병합 재현
db = json.load(open(os.path.join(A.W, "strings_db.json"), encoding="utf-8")) \
    if os.path.exists(os.path.join(A.W, "strings_db.json")) else None

# tl 로드
import glob
tl = {}
for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
    tl.update(json.load(open(p, encoding="utf-8")))
print("번역 로드:", len(tl))

f = open(A.ISO, "rb")
toc = A.load_toc()

def is_bootfont(eid):
    return 4000000 <= eid <= 4002999 or 1200000 <= eid <= 1299999

shellfonts_meta = json.load(open(os.path.join(A.W, "shellfonts2.json")))["fonts"]
shell_eidx = sorted({x["eidx"] for x in shellfonts_meta})

def enum_records(eidx):
    e = toc[eidx]; buf = A.read_entry(f, e); recs = []
    o = 0; N = len(buf)
    while o + 0x30 <= N:
        r = A.try_parse(buf, o)
        if r:
            for slot, off, raw in r["strs"]:
                try:
                    t = raw.decode("shift_jis")
                except Exception:
                    t = A.decode_tagged(raw)
                recs.append((e["id"], t))
            o += max(0x10, r["csize"] & ~0xF)
        else:
            o += 16
    return recs

untl = {}   # jp -> count
for eidx in shell_eidx:
    for eid, t in enum_records(eidx):
        if not is_bootfont(eid):
            continue
        if t in tl:
            continue
        if not t.strip():
            continue
        # 한글 주입이 필요없는(SJIS 순수 기호/숫자만) 것은 번역 불필요 후보
        untl[t] = untl.get(t, 0) + 1

uniq = sorted(untl)
print("셸 미번역 고유 문자열:", len(uniq))
# 길이 분포
short = [t for t in uniq if len(t) <= 20]
mid = [t for t in uniq if 20 < len(t) <= 80]
lng = [t for t in uniq if len(t) > 80]
print(f"  짧음(<=20): {len(short)}  중간(21-80): {len(mid)}  장문(>80): {len(lng)}")
print("\n짧은 문자열 표본 60:")
for t in short[:60]:
    print(f"  {t!r}")

json.dump(uniq, open(os.path.join(A.W, "tl", "_new_untranslated.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n저장: tl/_new_untranslated.json")
