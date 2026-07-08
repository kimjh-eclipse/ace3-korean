# -*- coding: utf-8 -*-
"""셸 전체 미번역 문자열 → 인덱스 배치 JSON (에이전트 번역용). 키 손상 방지 위해 번호↔JP."""
import sys, json, os, glob
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

f = open(A.ISO, "rb")
toc = A.load_toc()
sf = json.load(open(A.W + "\\shellfonts2.json"))["fonts"]

tl = {}
for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
    tl.update(json.load(open(p, encoding="utf-8")))
tl = {k: v for k, v in tl.items() if v and v != k}

def enum(eidx):
    buf = A.read_entry(f, toc[eidx])
    out = []
    o = 0
    while o + 0x30 <= len(buf):
        r = A.try_parse(buf, o)
        if r:
            for slot, off, raw in r["strs"]:
                try:
                    out.append(raw.decode("shift_jis"))
                except Exception:
                    pass
            o += max(0x10, r["csize"] & ~0xF)
        else:
            o += 16
    return out

uniq = []
seen = set()
for x in sf:
    for t in enum(x["eidx"]):
        if t in seen or t in tl:
            continue
        # 순수 기호/공백/숫자만인 것은 번역 불필요(그대로) — 스킵
        if not any('぀' <= c <= '鿿' or '぀' <= c <= 'ヿ' or '＀' <= c <= '￯' or ('가' <= c <= '힣') for c in t):
            continue
        seen.add(t)
        uniq.append(t)

print(f"셸 미번역 고유 문자열: {len(uniq)}")
idx_map = {i: t for i, t in enumerate(uniq)}
json.dump(idx_map, open(A.W + "\\shell_idx.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)

# 배치 분할
N = 10
per = (len(uniq) + N - 1) // N
os.makedirs(A.W + "\\batches", exist_ok=True)
for bi in range(N):
    part = {i: uniq[i] for i in range(bi * per, min((bi + 1) * per, len(uniq)))}
    if not part:
        continue
    json.dump(part, open(A.W + f"\\batches\\b{bi}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"  b{bi}.json: {len(part)}개 (idx {bi*per}~{min((bi+1)*per, len(uniq))-1})")
