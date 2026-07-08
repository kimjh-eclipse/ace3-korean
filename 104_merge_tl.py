# -*- coding: utf-8 -*-
"""배치 번역 결과(b*_kr.json) → shell_idx.json으로 JP키 복원 → tl/tl_shell_full.json 병합"""
import sys, json, os, glob
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

idx_map = json.load(open(A.W + "\\shell_idx.json", encoding="utf-8"))  # "i" -> JP
out = {}
missing = []
bad = []
for bi in range(10):
    p = A.W + f"\\batches\\b{bi}_kr.json"
    if not os.path.exists(p):
        print(f"  b{bi}_kr.json 없음!"); continue
    kr = json.load(open(p, encoding="utf-8"))
    for k, v in kr.items():
        jp = idx_map.get(str(k))
        if jp is None:
            bad.append((bi, k)); continue
        if not v or not isinstance(v, str):
            missing.append(jp); continue
        out[jp] = v

# 마크업/개행/포맷 보존 검증
import re
def toks(s):
    return sorted(re.findall(r"%[sd]|<book\(\d+\)>|<endbook\(\)>", s)) + [s.count("\n")]
warn = 0
for jp, kr in out.items():
    if toks(jp) != toks(kr):
        warn += 1
        if warn <= 15:
            print(f"  ⚠토큰불일치: {jp[:24]!r} -> {kr[:24]!r}")
print(f"\n병합 {len(out)}개, 토큰불일치 {warn}, 미번역 {len(missing)}, 키오류 {len(bad)}")

json.dump(out, open(A.W + "\\tl\\tl_shell_full.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("-> tl/tl_shell_full.json")
