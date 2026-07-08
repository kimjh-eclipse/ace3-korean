# -*- coding: utf-8 -*-
"""메인폰트 동적 기증 여력 측정: '이미 번역된 것만 남기면 몇 개 한자칸이 자유로워지나'.
현재/스토리 전량 번역 두 시점의 실효 슬롯을 산출."""
import sys, json, os, glob
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

usage = json.load(open(os.path.join(A.W, "kanji_usage.json")))
safe_codes = set(usage["safe_codes"])
used_kanji = set(usage["used_kanji"])

tl = {}
for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
    tl.update(json.load(open(p, encoding="utf-8")))
tl = {k: v for k, v in tl.items() if v and v != k}

db = json.load(open(os.path.join(A.W, "db.json"), encoding="utf-8"))
def is_boot(eid): return 4000000 <= eid <= 4002999 or 1200000 <= eid <= 1299999
KANJI_LO, KANJI_HI = 0x889F, 0x9872
def kanji_in(bs):
    out=set(); i=0; n=len(bs)
    while i+1<n:
        b0=bs[i]
        if 0x81<=b0<=0x9f or 0xe0<=b0<=0xef:
            c=(b0<<8)|bs[i+1]
            if KANJI_LO<=c<=KANJI_HI: out.add(c)
            i+=2
        else: i+=1
    return out

# 인게임(비셸) 미번역 문자열이 현재 쓰는 한자 = 반드시 보존
keep_now=set()
for d in db:
    if is_boot(d["id"]): continue
    for s in d["strs"]:
        if s["t"] not in tl:
            keep_now |= kanji_in(bytes.fromhex(s["hex"]))
keep_now &= used_kanji

freeable_now = used_kanji - keep_now  # 지금 추가 기증 가능한 한자칸
print(f"safe_codes(항상안전): {len(safe_codes)}")
print(f"used_kanji: {len(used_kanji)}")
print(f"  지금 미번역이 쓰는 한자(보존필수): {len(keep_now)}")
print(f"  지금 추가 기증가능(freeable): {len(freeable_now)}")
print(f"→ 현재 실효 안전슬롯 = {len(safe_codes)+len(freeable_now)}")
print(f"→ 스토리 전량번역 시 실효 안전슬롯 = {len(safe_codes)+len(used_kanji)} (미번역0 가정)")
