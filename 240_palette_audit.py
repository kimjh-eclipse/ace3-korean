# -*- coding: utf-8 -*-
"""주입 폰트 전체 팔레트 감사: idx8(우리 본체색)/idx1(외곽)이 각 폰트 팔레트에서
실제 어떤 색인지 + 원본 글리프가 본체로 쓰는 인덱스를 히스토그램으로 실측.
가설: 어떤 폰트는 팔레트가 달라 idx8이 어두움/투명 → 속 빈 테두리 글자."""
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

toc = json.loads((W / "bnd_toc.json").read_text(encoding="utf-8"))
ORIG = W.parent / "Another Century's Episode 3 - The Final (Japan).iso"
f = ORIG.open("rb")

CAPTION = [4603, 4604, 4605, 4606, 4607, 4608, 4609, 4610]
SHELL = [8780, 8781, 8782, 8783, 8784, 8787]

def load_font(eidx):
    e = toc[eidx]
    f.seek(DATA_OFF + e["off"])
    outer = f.read(e["size"])
    inner = parse_inner(outer)
    font_off, _ = inner[2500]
    if eidx == 4614:  # 경보 폰트 특례: raw 텍스처 outer+0x60, 팔레트는 그 뒤 추정
        payload_off, payload_len = 0x60, 0x40000
        tex_w, tex_h = 1024, 512
        pal_off = payload_off + payload_len
    else:
        tex_off, tex_size = inner[2000]
        payload_len = tex_size - 0x60
        tex_w, tex_h = texture_dims(payload_len)
        payload_off = tex_off + 0x20
        pal_off = payload_off + payload_len
    pal = [struct.unpack_from("<I", outer, pal_off + i * 4)[0] for i in range(16)]
    idx = build_file_index_4via32(tex_w, tex_h)
    pix = deswizzle4via32(outer[payload_off:payload_off + payload_len], tex_w, tex_h, idx)
    boxes = parse_boxes(outer, font_off, tex_w, tex_h)
    return e, pal, pix, boxes, tex_w

def body_hist(pix, tex_w, box):
    x0, y0, x1, y1 = box
    c = Counter()
    for y in range(y0, y1):
        for x in range(x0, x1):
            v = pix[y * tex_w + x]
            if v: c[v] += 1
    return c

# 원본 글리프 본체 인덱스 실측용 샘플 코드(각 폰트 charset에 있을 만한 것)
SAMPLES = [0x82A0, 0x82A2, 0x8341, 0x30, 0x41, 0x88A4, 0x8140]  # あいァ0A亜 전각공백

for eidx in CAPTION + [4614] + SHELL:
    try:
        e, pal, pix, boxes, tex_w = load_font(eidx)
    except Exception as ex:
        print(f"idx{eidx}: 파싱 실패 {ex}")
        continue
    def fmt(v):
        a = v >> 24; r = v & 0xFF; g = (v >> 8) & 0xFF; b = (v >> 16) & 0xFF
        return f"{v:08x}(a{a:02x})"
    total = Counter()
    used = 0
    for code in SAMPLES:
        b = boxes.get(code)
        if not b: continue
        h = body_hist(pix, tex_w, b)
        if h: total += h; used += 1
    top = ", ".join(f"{k}:{v}" for k, v in total.most_common(5))
    print(f"idx{eidx} id{e['id']}: pal1={fmt(pal[1])} pal8={fmt(pal[8])} "
          f"pal3={fmt(pal[3])} pal15={fmt(pal[15])} | 원본글리프 인덱스히스토({used}자): {top}")
f.close()
