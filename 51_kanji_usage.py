# -*- coding: utf-8 -*-
"""게임 코퍼스가 실제 사용하는 한자 집합 vs 폰트 한자 슬롯 → 안전한 빈 칸 산정"""
import json, sys, struct
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

db = json.load(open(A.W + r"\db.json", encoding="utf-8"))
f = open(A.ISO, "rb")
toc = A.load_toc()
b35, b36, ranges, nglyph = A.load_font(f, toc)

# 폰트가 가진 모든 코드포인트 (SJIS) 집합
font_codes = set()
code2gi = {}
for a, z, idx in ranges:
    for k in range(z - a + 1):
        font_codes.add(a + k)
        code2gi[a + k] = idx + k

# 한자 슬롯(0x889F 이상)
kanji_codes = {c for c in font_codes if c >= 0x889F}
print("폰트 한자 슬롯:", len(kanji_codes))

# 코퍼스에서 실제 쓰인 2바이트 SJIS 코드 집계
used = set()
used_kanji = set()
for d in db:
    for s in d["strs"]:
        raw = bytes.fromhex(s["hex"])
        i = 0
        while i < len(raw) - 1:
            c = raw[i]
            if c < 0x80:
                i += 1; continue
            if 0xA1 <= c <= 0xDF:
                i += 1; continue
            code = (raw[i] << 8) | raw[i+1]
            used.add(code)
            if code >= 0x889F:
                used_kanji.add(code)
            i += 2

print("코퍼스 사용 2바이트 코드:", len(used))
print("코퍼스 사용 한자:", len(used_kanji))

free_kanji = kanji_codes - used_kanji
print("사용되지 않는(안전) 한자 슬롯:", len(free_kanji))

# 박스폭 >=10인 안전 슬롯만
safe = []
EXCLUDE = {711, 1326, 1592, 2471}
for c in sorted(free_kanji):
    gi = code2gi[c]
    if gi in EXCLUDE:
        continue
    u0, v0, u1, v1, w16 = A.get_metric(b35, gi)
    bw = round((u1 - u0) * A.TEX_W)
    if bw >= 10:
        safe.append(c)
print("박스폭>=10 안전 슬롯:", len(safe))

json.dump({"safe_codes": safe, "used_kanji": sorted(used_kanji)},
          open(A.W + r"\kanji_usage.json", "w"), )
print("saved kanji_usage.json")
