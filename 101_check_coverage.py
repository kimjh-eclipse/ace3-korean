# -*- coding: utf-8 -*-
"""헤더 '確認' 등 미포착 의심 문자열이 db.json에 있는지 정확히 확인"""
import sys, json, os
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

db = json.load(open(os.path.join(A.W, "db.json"), encoding="utf-8"))
targets = ["確認", "メモリーカード（ＰＳ２）確認", "空き容量確認", "０１　未確認生命体調査"]
for tgt in targets:
    found = []
    for d in db:
        for s in d["strs"]:
            if s["t"] == tgt:
                found.append((d["id"], d["base"]))
    print(f"{tgt!r}: db에 {'있음' if found else '없음'} {found[:3]}")

# db의 4002050 컨테이너 수
c50 = [d for d in db if d["id"] == 4002050]
print(f"\ndb의 id4002050 섹션 수: {len(c50)}")
bases = sorted(d["base"] for d in c50)
print("bases:", [hex(x) for x in bases])
