# -*- coding: utf-8 -*-
"""포즈 행 원인 판별: 최종본+공백수정 상태에서 slot19에 지정 텍스트를 넣은 ISO 생성.
사용: python 234_slot19_probe.py <출력iso> <slot19텍스트>"""
import sys, json, struct, shutil, os
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

out_iso, text19 = sys.argv[1], sys.argv[2]
krmap = json.load(open(A.W + r"\kr_map_shell.json", encoding="utf-8"))
def enc(txt):
    out = bytearray()
    for ch in txt:
        c = krmap[ch]; out += bytes((c >> 8, c & 0xFF))
    return bytes(out)

toc = A.load_toc()
db = json.load(open(A.W + r"\db.json", encoding="utf-8"))
sec = next(d for d in db if d["idx"] == 4603 and d["base"] == 0x728c0)
e = toc[4603]
base, csize, count, tbloff = sec["base"], sec["csize"], sec["count"], sec["tbloff"]
lo = A.DATA_OFF + e["off"] + base

shutil.copyfile(A.W + r"\ACE3_KR_caption_full.iso", out_iso)
f = open(out_iso, "r+b")
f.seek(lo)
cur = bytearray(f.read(max(csize, 0x4000)))
tbl = list(struct.unpack_from(f"<{count}I", cur, tbloff))
def gs(off):
    i = off
    while cur[i] != 0: i += 1
    return bytes(cur[off:i])
def fix_space(b):
    o = bytearray(); i = 0
    while i < len(b):
        c = b[i]
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
            o += b[i:i+2]; i += 2
        elif c == 0x20:
            o += b"\x81\x40"; i += 1
        else:
            o.append(c); i += 1
    return bytes(o)

orig = {s["slot"]: bytes.fromhex(s["hex"]) for s in sec["strs"]}
h0 = min(s["off"] for s in sec["strs"])
oe = max(s["off"] + len(bytes.fromhex(s["hex"])) + 1 for s in sec["strs"])
limit = max(csize, oe)
new19 = enc(text19)
print("slot19:", repr(text19), "=", new19.hex(" "))
heap = bytearray(); om = {}; nt = {}
for s in sec["strs"]:
    slot = s["slot"]
    if slot == 19:
        data = new19
    else:
        data = gs(tbl[slot])
        if data != orig[slot] and b"\x20" in data:
            data = fix_space(data)
    if data in om:
        nt[slot] = om[data]; continue
    o = h0 + len(heap)
    assert o + len(data) + 1 <= limit
    om[data] = o; nt[slot] = o
    heap += data + b"\x00"
for slot, o in nt.items():
    struct.pack_into("<I", cur, tbloff + slot * 4, o)
cur[h0:limit] = heap + bytes(limit - h0 - len(heap))
f.seek(lo); f.write(cur[:limit])
f.flush(); os.fsync(f.fileno()); f.close()
print(out_iso, "완료")
