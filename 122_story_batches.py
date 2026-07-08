# -*- coding: utf-8 -*-
"""스토리(인게임 비셸) 미번역 고유 문자열 → 씬순서 배치 + 태그 인벤토리 감사.
- db 순회 순서 유지(씬 문맥 보존) → 번역 품질↑
- 태그 종류 전수 집계로 보존 검증 규칙 확정"""
import sys, json, os, re, glob
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

tl = {}
for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
    tl.update(json.load(open(p, encoding="utf-8")))
tl = {k: v for k, v in tl.items() if v and v != k}

db = json.load(open(os.path.join(A.W, "db.json"), encoding="utf-8"))
def is_boot(eid): return 4000000 <= eid <= 4002999 or 1200000 <= eid <= 1299999

# 토큰 정의(보존 대상): 순서 중요 — 긴 것 먼저
TOKEN = re.compile(r"<[^>]*>|#c\[[0-9A-Fa-f]{6}\]|#c|⟦[^⟧]*⟧|%[sdcuxX]")
def has_jp(t):
    return any(0x3040 <= ord(c) <= 0x30ff or 0x4e00 <= ord(c) <= 0x9fff for c in t)

uniq, seen = [], set()
for d in db:
    if is_boot(d["id"]):
        continue
    for s in d["strs"]:
        t = s["t"]
        if t in seen or t in tl or not t.strip():
            continue
        if not has_jp(t):
            continue
        seen.add(t); uniq.append(t)

print(f"스토리 미번역 고유: {len(uniq)}")

# 태그 인벤토리
from collections import Counter
tagnames = Counter()
angle = Counter()
for t in uniq:
    for m in TOKEN.findall(t):
        if m.startswith("<"):
            nm = re.match(r"<([a-zA-Z_]+)", m)
            angle[nm.group(1) if nm else m] += 1
            tagnames["<tag>"] += 1
        else:
            tagnames[m if m in ("#c",) else re.sub(r"\[.*\]", "[..]", m) if m.startswith("#c") else ("⟦..⟧" if m.startswith("⟦") else m)] += 1
print("토큰 종류:", dict(tagnames))
print("angle 태그 이름 top:", dict(angle.most_common(30)))
mx = max(uniq, key=lambda t: len(TOKEN.findall(t)))
print(f"토큰 최다 문자열({len(TOKEN.findall(mx))}개): {mx[:80]!r}")

# 인덱스맵 + 배치
idx_map = {str(i): t for i, t in enumerate(uniq)}
json.dump(idx_map, open(os.path.join(A.W, "story_idx.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
PER = 400
os.makedirs(os.path.join(A.W, "batches_story"), exist_ok=True)
nb = (len(uniq) + PER - 1) // PER
for bi in range(nb):
    part = {str(i): uniq[i] for i in range(bi*PER, min((bi+1)*PER, len(uniq)))}
    json.dump(part, open(os.path.join(A.W, "batches_story", f"s{bi}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
print(f"배치 {nb}개(각 {PER}) → batches_story/s0..s{nb-1}.json, story_idx.json 저장")
