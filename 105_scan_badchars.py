# -*- coding: utf-8 -*-
"""번역문에서 한글도 SJIS도 아닌(주입 불가) 문자 전수 조사"""
import sys, json, glob, os, collections
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

tl = {}
for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
    tl.update(json.load(open(p, encoding="utf-8")))

bad = collections.Counter()
examples = {}
for jp, kr in tl.items():
    i = 0
    while i < len(kr):
        ch = kr[i]
        if ch == "⟦":
            j = kr.index("⟧", i); i = j + 1; continue
        if "가" <= ch <= "힣":
            i += 1; continue
        fixed = A._SJIS_FIX.get(ch, ch)
        try:
            fixed.encode("shift_jis")
        except Exception:
            bad[ch] += 1
            examples.setdefault(ch, kr[:30])
        i += 1

print(f"주입 불가 문자 종류: {len(bad)}")
for ch, n in bad.most_common():
    print(f"  {ch!r} (U+{ord(ch):04X}) x{n}  예: {examples[ch]!r}")
