# -*- coding: utf-8 -*-
"""전체 번역 자산(tl/*.json)을 카테고리별 + 통합 CSV로 내보내기.
엑셀 호환을 위해 UTF-8-SIG(BOM) 사용."""
import sys, json, os, csv, glob
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

OUT_DIR = os.path.join(A.W, "docs")
os.makedirs(OUT_DIR, exist_ok=True)

CATS = [
    ("tl_seed.json",        "seed_다이얼로그_시스템"),
    ("tl_ui_terms.json",    "UI_전투용어"),
    ("tl_ui_system.json",   "UI_시스템_단문"),
    ("tl_shell_full.json",  "셸_부팅프론트엔드"),
    ("tl_story.json",       "스토리_인게임대사"),
]

def load(name):
    p = os.path.join(A.W, "tl", name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}

all_rows = []
for fname, cat in CATS:
    d = load(fname)
    out_path = os.path.join(OUT_DIR, f"{cat}.csv")
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["번호", "분류", "원문(일본어)", "번역(한국어)", "원문길이", "번역길이"])
        for i, (jp, kr) in enumerate(d.items(), 1):
            w.writerow([i, cat, jp, kr, len(jp), len(kr)])
            all_rows.append([cat, jp, kr, len(jp), len(kr)])
    print(f"{out_path} : {len(d)}행")

combined = os.path.join(OUT_DIR, "전체_번역_통합.csv")
with open(combined, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["번호", "분류", "원문(일본어)", "번역(한국어)", "원문길이", "번역길이"])
    for i, row in enumerate(all_rows, 1):
        w.writerow([i, *row])
print(f"{combined} : {len(all_rows)}행 (통합, 중복 포함)")

# 통계 요약
print("\n=== 카테고리별 통계 ===")
for fname, cat in CATS:
    d = load(fname)
    if not d:
        continue
    jp_chars = sum(len(k) for k in d)
    kr_chars = sum(len(v) for v in d.values())
    print(f"  {cat:20s} 항목 {len(d):6d}  일본어 {jp_chars:8,}자  한국어 {kr_chars:8,}자")
