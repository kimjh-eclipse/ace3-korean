# -*- coding: utf-8 -*-
"""idx4614 정밀 분석: 팔레트 위치 검증, 원본 글리프 ASCII 아트(본체 인덱스 판별),
charset(range 테이블) 요약 — 0x5F/0x8145/ASCII 보유 여부, 한글 donor 커버.
idx8781도 원본 글리프 본체 인덱스 확인."""
from __future__ import annotations
import importlib.util, json, struct, sys
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = Path(__file__).resolve().parent
DATA_OFF = 2117 * 2048
from deswz_tables import build_file_index_4via32, deswizzle4via32

_spec = importlib.util.spec_from_file_location("m220", W / "220_patch_radio_space5f.py")
m220 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m220)
parse_inner, texture_dims, parse_boxes = m220.parse_inner, m220.texture_dims, m220.parse_boxes
font_header = m220.font_header

toc = json.loads((W / "bnd_toc.json").read_text(encoding="utf-8"))
ORIG = W.parent / "Another Century's Episode 3 - The Final (Japan).iso"
V2 = W / "ACE3_KR_v2.iso"

def load(iso, eidx):
    e = toc[eidx]
    f = iso.open("rb"); f.seek(DATA_OFF + e["off"])
    outer = f.read(e["size"]); f.close()
    inner = parse_inner(outer)
    font_off, _ = inner[2500]
    if 2000 in inner:
        tex_off, tex_size = inner[2000]
        payload_len = tex_size - 0x60
        tex_w, tex_h = texture_dims(payload_len)
        payload_off = tex_off + 0x20
    else:
        payload_off, payload_len = 0x60, 0x40000
        tex_w, tex_h = 1024, 512
    idx = build_file_index_4via32(tex_w, tex_h)
    pix = deswizzle4via32(outer[payload_off:payload_off + payload_len], tex_w, tex_h, idx)
    return e, outer, font_off, payload_off, payload_len, tex_w, tex_h, pix

CH = "0123456789abcdef"
def art(pix, tex_w, box):
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        print("   " + "".join(CH[pix[y * tex_w + x]] for x in range(x0, x1)).replace("0", "."))

# ---- 4614 ----
e, outer, font_off, payload_off, payload_len, tw, th, pix = load(ORIG, 4614)
print(f"idx4614 outer size {e['size']:#x}, font_off {font_off:#x}, payload {payload_off:#x}+{payload_len:#x}")
# 팔레트 후보: payload 직후 0x40
po = payload_off + payload_len
print("payload 직후 0x60 hex:")
print(outer[po:po+0x60].hex(" "))
nranges, nglyph, mo = font_header(outer, font_off)
print(f"nranges={nranges} nglyph={nglyph}")
ranges = []
for i in range(nranges):
    a, z, gi = struct.unpack_from("<III", outer, font_off + 0x20 + i * 12)
    if 0 <= a <= z <= 0xFFFF and gi < nglyph:
        ranges.append((a, z, gi))
def has(code):
    return any(a <= code <= z for a, z, _ in ranges)
print("charset 검사: 0x20", has(0x20), "| 0x5F", has(0x5F), "| 0x8140", has(0x8140),
      "| 0x8145(・)", has(0x8145), "| 0x8148(？)", has(0x8148))
ascii_have = [c for c in range(0x21, 0x7F) if has(c)]
print("ASCII 보유:", " ".join(f"{c:02x}" for c in ascii_have) or "(없음)")
print("range 수 유효:", len(ranges), "| 코드 총수:", sum(z - a + 1 for a, z, _ in ranges))

boxes = parse_boxes(outer, font_off, tw, th)
for code, label in ((0x8341, "ア(0x8341)"), (0x82A0, "あ(0x82A0)")):
    b = boxes.get(code)
    if b:
        print(f"원본 {label} box={b}:")
        art(pix, tw, b)
        break

# 한글 커버리지: kr_map_shell donor 코드 중 4614 charset에 없는 것
kr = {k: int(v) for k, v in json.loads((W / "kr_map_shell.json").read_text(encoding="utf-8")).items()}
missing = sorted(ch for ch, code in kr.items() if not has(code))
print(f"kr_map_shell {len(kr)}음절 중 4614 미보유 {len(missing)}: {''.join(missing[:80])}{'…' if len(missing)>80 else ''}")
for probe in "입루리편":
    print(f"  '{probe}' donor {kr.get(probe, 0):#06x} 보유: {has(kr[probe]) if probe in kr else 'N/A'}")

# v2(패치본)에서 우리가 주입한 글리프 확인
e2, outer2, fo2, po2, pl2, tw2, th2, pix2 = load(V2, 4614)
b = parse_boxes(outer2, fo2, tw2, th2).get(kr["가"])
if b:
    print(f"v2 주입 '가' donor {kr['가']:#06x} box={b}:")
    art(pix2, tw2, b)

# ---- 8781 원본 본체 인덱스 ----
e, outer, font_off, payload_off, payload_len, tw, th, pix = load(ORIG, 8781)
boxes = parse_boxes(outer, font_off, tw, th)
po = payload_off + payload_len
print(f"\nidx8781 payload 직후 0x40 hex:\n{outer[po:po+0x40].hex(' ')}")
for code in (0x8341, 0x82A0, 0x30):
    b = boxes.get(code)
    if b:
        print(f"idx8781 원본 {code:#x} box={b}:")
        art(pix, tw, b)
        break
