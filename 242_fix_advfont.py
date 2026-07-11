# -*- coding: utf-8 -*-
"""v3 빌드: ADV(전투 후 대화) 폰트 idx4614 + 셸 idx8781 팔레트 인덱스 수정.

배경(2026-07-12 실측):
- idx4614(id1200011)는 팔레트가 다른 폰트와 다름: 본체=idx5(0xb4b4b4), idx6~15=알파0.
  기존 주입(본체 idx8)은 이 폰트에서 '속이 투명한 테두리 글자'가 됨(전투 후 대화 화면).
  원본 4614 텍스처는 픽셀값 0~5만 사용 → 전역 8→5 치환이 안전·완전(우리 드로잉만 영향).
- idx8781(id4002051)은 본체=idx6(0xb3b3b3), idx8=0x414141(어두움) → 우리가 그린 박스만
  8→6 치환(원본 글리프가 8을 음영으로 써서 전역 치환 불가).
- 4614 미보유 구제: 미사용 싱글톤 23 + 전구간 미사용 다중 레인지 7 = 30슬롯을
  재코딩(빌드 검증된 build.py 부호 싱글톤 치환과 동일 기법).
  0x5F(가짜 공백)=blank 1슬롯 + 미보유 200음절 중 대사 빈도 상위 29(출현의 95%).
입력: ACE3_KR_v2.iso → 출력: ACE3_KR_v3.iso
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import struct
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = Path(__file__).resolve().parent
DATA_OFF = 2117 * 2048
SRC_ISO = W / "ACE3_KR_v2.iso"
OUT_ISO = Path(os.environ.get("ACE3_V3_OUT", str(W / "ACE3_KR_v3.iso")))

from deswz_tables import build_file_index_4via32, deswizzle4via32, swizzle4via32

_spec = importlib.util.spec_from_file_location("m220", W / "220_patch_radio_space5f.py")
m220 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m220)
parse_inner, texture_dims, font_header = m220.parse_inner, m220.texture_dims, m220.font_header

_spec2 = importlib.util.spec_from_file_location("m222", W / "222_patch_caption_batang.py")
m222 = importlib.util.module_from_spec(_spec2); _spec2.loader.exec_module(m222)
render_fit = m222.render_fit  # 값 8=본체/1=외곽/0=배경 그리드 반환
UNIFORM_SIZE = m222.UNIFORM_SIZE

KANJI = lambda a: 0x889F <= a <= 0x9872
HIRA = lambda a: 0x829F <= a <= 0x82F1
FAKE_SPACE = 0x5F
RESCUE_N = 29  # 공백 1 + 음절 29 = 30슬롯

toc = json.loads((W / "bnd_toc.json").read_text(encoding="utf-8"))
kr = {k: int(v) for k, v in json.loads((W / "kr_map_shell.json").read_text(encoding="utf-8")).items()}
donors = set(kr.values())


def load_font(out, eidx):
    e = toc[eidx]
    out.seek(DATA_OFF + e["off"])
    outer = bytearray(out.read(e["size"]))
    inner = parse_inner(outer)
    font_off, _ = inner[2500]
    if 2000 in inner:
        tex_off, tex_size = inner[2000]
        payload_len = tex_size - 0x60
        tw, th = texture_dims(payload_len)
        payload_off = tex_off + 0x20
    else:  # 4614 변형: raw 텍스처 outer+0x60
        payload_off, payload_len = 0x60, 0x40000
        tw, th = 1024, 512
    return e, outer, font_off, payload_off, payload_len, tw, th


def read_ranges(outer, font_off):
    nranges, nglyph, metric_off = font_header(outer, font_off)
    rs = []
    for i in range(nranges):
        a, z, gi = struct.unpack_from("<III", outer, font_off + 0x20 + i * 12)
        rs.append([a, z, gi])
    return rs, nglyph, metric_off


def box_of(outer, font_off, metric_off, gi, tw, th):
    u0, v0, u1, v1 = struct.unpack_from("<4f", outer, font_off + metric_off + gi * 24)
    x0, y0 = round(u0 * tw), round(v0 * th)
    return x0, y0, x0 + round((u1 - u0) * tw), y0 + round((v1 - v0) * th)


def blit(pix, tw, box, grid):
    x0, y0, x1, y1 = box
    for yy in range(y1 - y0):
        row = grid[yy]
        base = (y0 + yy) * tw + x0
        for xx in range(x1 - x0):
            pix[base + xx] = row[xx]


def missing_by_freq():
    """4614 미보유 음절을 대사 코퍼스(tl/*.json 번역문) 빈도 내림차순으로."""
    import glob
    with (W / "ACE3_KR_v2.iso").open("rb") as f:
        e = toc[4614]
        f.seek(DATA_OFF + e["off"])
        outer = f.read(e["size"])
    inner = parse_inner(outer)
    fo, _ = inner[2500]
    rs, ng, _mo = read_ranges(outer, fo)
    codes = set()
    for a, z, gi in rs:
        if 0 <= a <= z <= 0xFFFF and gi < ng:
            codes.update(range(a, z + 1))
    missing = {ch for ch, c in kr.items() if c not in codes}
    cnt = Counter()
    for p in sorted(glob.glob(str(W / "tl" / "*.json"))):
        for v in json.load(open(p, encoding="utf-8")).values():
            for ch in v:
                if ch in missing:
                    cnt[ch] += 1
    return [ch for ch, _n in cnt.most_common()], missing


def fix_4614(out):
    e, outer, fo, po, pl, tw, th = load_font(out, 4614)
    rs, nglyph, mo = read_ranges(outer, fo)
    idx = build_file_index_4via32(tw, th)
    pix = bytearray(deswizzle4via32(outer[po:po + pl], tw, th, idx))

    # --- 재코딩 슬롯 수집: 미사용 싱글톤 + 전구간 미사용 다중 레인지(축소) ---
    slots = []  # (entry_index, gi, box)
    for i, (a, z, gi) in enumerate(rs):
        if not (0 <= a <= z <= 0xFFFF and gi < nglyph):
            continue
        span = range(a, z + 1)
        if all((KANJI(c) or HIRA(c)) and c not in donors for c in span):
            b = box_of(outer, fo, mo, gi, tw, th)
            slots.append((i, gi, b))
    # 큰 박스 우선(고빈도 음절에 좋은 칸)
    slots.sort(key=lambda s: (s[2][2] - s[2][0]) * (s[2][3] - s[2][1]), reverse=True)
    print(f"idx4614: 재코딩 가용 슬롯 {len(slots)}")

    order, missing = missing_by_freq()
    print(f"  미보유 {len(missing)}음절, 구제 대상 상위: {''.join(order[:RESCUE_N])}")

    # 공백은 가장 작은 슬롯(blank라 크기 무관)
    sp_i, sp_gi, sp_box = slots.pop()
    x0, y0, x1, y1 = sp_box
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            pix[yy * tw + xx] = 0
    rs[sp_i][0] = rs[sp_i][1] = FAKE_SPACE
    print(f"  0x5F 공백 → entry{sp_i} box{sp_box} blank")

    rescued = []
    si = 0
    for ch in order:
        if len(rescued) >= RESCUE_N or si >= len(slots):
            break
        ent, gi, b = slots[si]
        bw, bh = b[2] - b[0], b[3] - b[1]
        grid = None
        for size in range(UNIFORM_SIZE, 9, -1):
            grid = render_fit(ch, size, bw, bh)
            if grid is not None:
                break
        if grid is None:
            print(f"  [skip] '{ch}' box {bw}x{bh} 드로잉 실패")
            si += 1
            continue
        blit(pix, tw, b, grid)
        rs[ent][0] = rs[ent][1] = kr[ch]
        rescued.append(ch)
        si += 1
    print(f"  음절 구제 {len(rescued)}: {''.join(rescued)}")

    # --- 전역 본체 인덱스 교정: 8(이 폰트에선 투명) → 5(원본 본체 0xb4b4b4) ---
    n8 = 0
    for i in range(len(pix)):
        if pix[i] == 8:
            pix[i] = 5
            n8 += 1
    print(f"  본체 픽셀 8→5 치환 {n8}")

    # 레인지 테이블 재기록(build.py와 동일하게 코드 오름차순 정렬)
    rs.sort(key=lambda r: r[0])
    o = fo + 0x20
    for a, z, gi in rs:
        struct.pack_into("<III", outer, o, a, z, gi); o += 12

    outer[po:po + pl] = swizzle4via32(pix, tw, th, idx)
    out.seek(DATA_OFF + e["off"])
    out.write(outer)
    return rescued


def fix_8781(out):
    """우리가 그린 박스(한글 donor + 재코딩 부호)만 8→6. 원본 글리프는 8을 음영으로
    쓰므로 전역 치환 금지."""
    e, outer, fo, po, pl, tw, th = load_font(out, 8781)
    rs, nglyph, mo = read_ranges(outer, fo)
    code_gi = {}
    for a, z, gi in rs:
        if not (0 <= a <= z <= 0xFFFF and gi < nglyph):
            continue
        for k in range(z - a + 1):
            code_gi[a + k] = gi + k

    # 원본 charset(재코딩 전) — 신규 코드 판별용
    with (W.parent / "Another Century's Episode 3 - The Final (Japan).iso").open("rb") as f:
        f.seek(DATA_OFF + e["off"])
        outer_o = f.read(e["size"])
    inner_o = parse_inner(outer_o)
    fo_o, _ = inner_o[2500]
    rs_o, ng_o, _ = read_ranges(outer_o, fo_o)
    codes_o = set()
    for a, z, gi in rs_o:
        if 0 <= a <= z <= 0xFFFF and gi < ng_o:
            codes_o.update(range(a, z + 1))

    targets = set()
    for code, gi in code_gi.items():
        if code in donors or code not in codes_o:  # 한글 donor 또는 우리가 추가한 부호
            targets.add(gi)

    idx = build_file_index_4via32(tw, th)
    pix = bytearray(deswizzle4via32(outer[po:po + pl], tw, th, idx))
    n8 = 0
    nbox = 0
    for gi in targets:
        x0, y0, x1, y1 = box_of(outer, fo, mo, gi, tw, th)
        if x1 - x0 < 8 or y1 - y0 < 8:  # inplace_inject가 스킵한 작은 박스=원본 유지
            continue
        nbox += 1
        for yy in range(y0, y1):
            base = yy * tw
            for xx in range(x0, x1):
                if pix[base + xx] == 8:
                    pix[base + xx] = 6
                    n8 += 1
    print(f"idx8781: 대상 박스 {nbox}, 본체 픽셀 8→6 치환 {n8}")

    outer[po:po + pl] = swizzle4via32(pix, tw, th, idx)
    out.seek(DATA_OFF + e["off"])
    out.write(outer)


def main():
    print("복사:", OUT_ISO)
    shutil.copyfile(SRC_ISO, OUT_ISO)
    with OUT_ISO.open("r+b") as out:
        rescued = fix_4614(out)
        fix_8781(out)
        out.flush(); os.fsync(out.fileno())
    print("완료:", OUT_ISO)
    return rescued


if __name__ == "__main__":
    main()
