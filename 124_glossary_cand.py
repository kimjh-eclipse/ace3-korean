# -*- coding: utf-8 -*-
"""스토리 전량에서 고유명사 후보 추출: 가타카나 연속run + 자주 나오는 한자어.
빈도순 상위를 용어집 시드로."""
import sys, json, os, re
from collections import Counter
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

idx_map = json.load(open(os.path.join(A.W, "story_idx.json"), encoding="utf-8"))
TOKEN = re.compile(r"<[^>]*>|#c\[[0-9A-Fa-f]{6}\]|#c|⟦[^⟧]*⟧|%[sdcuxX]")
KATA = re.compile(r"[ァ-ヶー・]{2,}")          # 가타카나 연속(고유명사 후보)
KANJI = re.compile(r"[一-龠]{2,4}")            # 한자어

kata = Counter(); kanji = Counter()
for t in idx_map.values():
    plain = TOKEN.sub("", t)
    for m in KATA.findall(plain):
        kata[m] += 1
    for m in KANJI.findall(plain):
        kanji[m] += 1

print("=== 가타카나 고유명사 후보 top 80 (빈도) ===")
for w, c in kata.most_common(80):
    print(f"  {c:4} {w}")
print("\n=== 한자어 top 50 ===")
for w, c in kanji.most_common(50):
    print(f"  {c:4} {w}")

json.dump({"kata": kata.most_common(200), "kanji": kanji.most_common(120)},
          open(os.path.join(A.W, "glossary_cand.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n저장: glossary_cand.json")
