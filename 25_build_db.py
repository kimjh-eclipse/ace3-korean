# -*- coding: utf-8 -*-
"""마스터 DB 구축: 모든 문자열(원시 바이트 포함) + 고유 텍스트 목록"""
import json, sys, os
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

f = open(A.ISO, "rb")
toc = A.load_toc()

db = []          # 섹션 단위
uniq = {}        # text -> 등장 횟수
for e in toc:
    if e["size"] < 0x60:
        continue
    buf = A.read_entry(f, e)
    secs = A.scan_entry_sections(buf)
    for s in secs:
        strs = []
        for slot, off, raw in s["strs"]:
            t = A.decode_tagged(raw)
            # 라운드트립 검증
            rt = A.encode_tagged(t)
            assert rt == raw, (e["i"], slot, raw.hex(), rt.hex())
            strs.append({"slot": slot, "off": off, "hex": raw.hex(), "t": t})
            uniq[t] = uniq.get(t, 0) + 1
        db.append({"idx": e["i"], "id": e["id"], "base": s["base"],
                   "csize": s["csize"], "count": s["count"], "tbloff": s["tbloff"],
                   "strs": strs})

print("sections:", len(db), "instances:", sum(len(d['strs']) for d in db), "unique:", len(uniq))
json.dump(db, open(os.path.join(A.W, "db.json"), "w", encoding="utf-8"), ensure_ascii=False)

def has_jp(s):
    return any('぀' <= c <= 'ヿ' or '一' <= c <= '鿿' or c in '、。「」・ー' for c in s)

jp = [t for t in uniq if has_jp(t)]
jp.sort()
json.dump(jp, open(os.path.join(A.W, "uniq_jp2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("unique JP:", len(jp))
