# -*- coding: utf-8 -*-
"""스토리 배치 번역(batches_story/s*_kr.json) → story_idx.json으로 JP키 복원 → 검증 → tl/tl_story.json.
검증(하드): 태그 멀티셋 동일, 개행수 동일, ⟦⟧/%d 동일. (소프트) 태그 순서·전각공백수."""
import sys, json, os, re, glob
from collections import Counter
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

TOKEN = re.compile(r"<[^>]*>|#c\[[0-9A-Fa-f]{6}\]|#c|⟦[^⟧]*⟧|%[sdcuxX]")
idx_map = json.load(open(os.path.join(A.W, "story_idx.json"), encoding="utf-8"))

def tokens(s): return TOKEN.findall(s)

out, hard, soft, missing, badkey = {}, [], [], [], []
files = sorted(glob.glob(os.path.join(A.W, "batches_story", "s*_kr.json")),
               key=lambda p: int(re.search(r"s(\d+)_kr", p).group(1)))
for p in files:
    kr = json.load(open(p, encoding="utf-8"))
    for k, v in kr.items():
        jp = idx_map.get(str(k))
        if jp is None:
            badkey.append((os.path.basename(p), k)); continue
        if not v or not isinstance(v, str) or v == jp:
            missing.append(jp); continue
        tj, tk = tokens(jp), tokens(v)
        if Counter(tj) != Counter(tk):
            hard.append((jp, v, "태그멀티셋")); continue
        if jp.count("\n") != v.count("\n"):
            hard.append((jp, v, "개행수")); continue
        if tj != tk:
            soft.append((jp, v, "태그순서"))
        out[jp] = v

print(f"파일 {len(files)}개, 병합 성공 {len(out)}")
print(f"하드실패 {len(hard)}, 소프트경고 {len(soft)}, 미번역 {len(missing)}, 키오류 {len(badkey)}")
for jp, v, why in hard[:20]:
    print(f"  ✗[{why}] {jp[:46]!r}\n        -> {v[:46]!r}")
for jp, v, why in soft[:8]:
    print(f"  ~[{why}] {jp[:40]!r} -> {v[:40]!r}")

if "--write" in sys.argv and not hard:
    json.dump(out, open(os.path.join(A.W, "tl", "tl_story.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"-> tl/tl_story.json ({len(out)})")
elif hard:
    print("하드실패 존재 → 미기록(수정 후 재실행)")
