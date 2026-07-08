# -*- coding: utf-8 -*-
"""DATA.BIN BND3 TOC 파싱 + 내부 파일 매직 분류"""
import struct, json
from collections import Counter

ISO = r"C:\Emul\Switch\패치유틸.xdeltaUI\Another Century's Episode 3 - The Final (Japan).iso"
SECT = 2048
DATA_OFF = 2117 * SECT

f = open(ISO, "rb")
f.seek(DATA_OFF)
hdr = f.read(0x20)
count = struct.unpack("<I", hdr[0x10:0x14])[0]
hdr_end = struct.unpack("<I", hdr[0x14:0x18])[0]
fmt = hdr[0x0C]
print(f"format=0x{fmt:02x} count={count} hdr_end=0x{hdr_end:x}")

f.seek(DATA_OFF + 0x20)
tbl = f.read(count * 16)
entries = []
for i in range(count):
    flags, size, off, fid = struct.unpack_from("<IIII", tbl, i * 16)
    entries.append({"i": i, "flags": flags, "size": size, "off": off, "id": fid})

print("first ids:", [e["id"] for e in entries[:10]])
print("last entry:", entries[-1])
print("max end:", max(e["off"] + e["size"] for e in entries))

# 매직 분류
mag = Counter()
samples = {}
for e in entries:
    if e["size"] == 0:
        mag["<empty>"] += 1
        continue
    f.seek(DATA_OFF + e["off"])
    m = f.read(16)
    key = m[:4]
    try:
        k = key.decode("ascii")
        if not all(32 <= c < 127 for c in key):
            k = key.hex()
    except Exception:
        k = key.hex()
    mag[k] += 1
    if k not in samples:
        samples[k] = (e["i"], e["id"], e["size"], m.hex())

print("\n=== magic distribution ===")
for k, v in mag.most_common(40):
    s = samples.get(k)
    print(f"{k!r:>14} x{v:<6} sample: idx={s[0] if s else '-'} id={s[1] if s else '-'} size={s[2] if s else '-'}")

json.dump(entries, open(r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3\bnd_toc.json", "w"))
