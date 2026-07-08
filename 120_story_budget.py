# -*- coding: utf-8 -*-
"""스토리(인게임 메인폰트) 번역 실현성 측정.
- 메인폰트 안전칸(한글 배정 가능 칸) 총량 vs 현재 사용량
- 미번역 인게임(비셸) 고유 문자열 규모 = 스토리 대사 잔량
- 전량 번역 시 필요 한글 음절 수를 근사(대형 코퍼스 유니크 음절 추정)"""
import sys, json, os, glob
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

usage = json.load(open(os.path.join(A.W, "kanji_usage.json")))
safe_codes = usage["safe_codes"]
used_kanji = usage["used_kanji"]
kr_map = {k: int(v) for k, v in json.load(open(os.path.join(A.W, "kr_map.json"), encoding="utf-8")).items()}

print(f"메인폰트 안전칸(safe_codes): {len(safe_codes)}")
print(f"메인폰트 사용한자(fallback 후보): {len(used_kanji)}")
print(f"현재 kr_map 배정 음절: {len(kr_map)}")
print(f"→ 안전칸 잔여: {len(safe_codes) - len([c for c in kr_map.values() if c in set(safe_codes)])}")

# 번역 로드
tl = {}
for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
    tl.update(json.load(open(p, encoding="utf-8")))
tl = {k: v for k, v in tl.items() if v and v != k}

# db 기준 인게임(비셸) 미번역 문자열 열거
db = json.load(open(os.path.join(A.W, "db.json"), encoding="utf-8"))
def is_boot(eid): return 4000000 <= eid <= 4002999 or 1200000 <= eid <= 1299999

untl = {}
for d in db:
    if is_boot(d["id"]):
        continue
    for s in d["strs"]:
        t = s["t"]
        if t in tl or not t.strip():
            continue
        # 번역 대상(가나/한자 포함)만
        if any(0x3040 <= ord(c) <= 0x30ff or 0x4e00 <= ord(c) <= 0x9fff for c in t):
            untl[t] = untl.get(t, 0) + 1

uniq = sorted(untl)
tot_chars = sum(len(t) for t in uniq)
print(f"\n인게임(스토리) 미번역 고유 문자열: {len(uniq)}")
print(f"  총 문자수(일본어): {tot_chars:,}")
short = [t for t in uniq if len(t) <= 30]
mid = [t for t in uniq if 30 < len(t) <= 100]
lng = [t for t in uniq if len(t) > 100]
print(f"  길이분포: <=30 {len(short)} / 31-100 {len(mid)} / >100 {len(lng)}")
print("\n표본 20:")
for t in uniq[:20]:
    print(f"  {t[:60]!r}")

# 기존 번역문에서 이미 쓰인 유니크 음절 (실측 밀도 참고)
kr_syl = set()
for v in tl.values():
    for ch in v:
        if "가" <= ch <= "힣":
            kr_syl.add(ch)
kr_chars = sum(len(v) for v in tl.values())
print(f"\n[실측] 현재 번역 한글 총 {kr_chars:,}자에서 유니크 음절 {len(kr_syl)}")
