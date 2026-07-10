# -*- coding: utf-8 -*-
"""캡션폰트 v3: 바탕체(명조, 원본 영숫자/한자와 동일 계열) + bbox-fit 드로잉.

221 대비 변경:
- 폰트: 굴림 → 바탕(batang.ttc). 원본 캡션폰트의 영문/숫자/한자가 세리프(명조)계라
  한글만 고딕이면 이질적이라는 피드백 반영.
- 드로잉: 큰 캔버스에 그린 뒤 잉크 bbox를 실측해 박스 안(모든 변 1px 여백, halo 포함)에
  배치. 221의 baseline 고정 방식이 받침 하단을 1-2px 잘라먹던 문제를 구조적으로 제거.
  박스에 안 들어가면 폰트 크기를 줄여 재시도.
출력: ACE3_KR_caption_batang.iso (베이스 ACE3_KR.iso)
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from deswz_tables import build_file_index_4via32, deswizzle4via32, swizzle4via32

W = Path(__file__).resolve().parent
DATA_OFF = 2117 * 2048
SRC_ISO = W / "ACE3_KR.iso"
CLEAN_ISO = W.parent / "Another Century's Episode 3 - The Final (Japan).iso"
OUT_ISO = Path(os.environ.get("ACE3_CAPTION_BATANG_OUT", str(W / "ACE3_KR_caption_batang.iso")))
FONT_PATH = str(Path(r"C:\Windows\Fonts\batang.ttc"))
INK_THRESH = 80  # 바탕 가는 획 보존
UNIFORM_SIZE = 14  # 전 음절 균일 크기 — 원본 영숫자(본체 12px)와 높이 일치
BOTTOM_ROW = 15    # 원본 숫자 잉크 바닥행(19px 박스) — 베이스라인 공유
LARGE_EIDX = (4603, 4604, 4607, 4608, 4609, 4610)
SMALL_EIDX = (4605, 4606)

FAKE_SPACE = 0x5F
JANG_CODE = 0x88A3

_spec = importlib.util.spec_from_file_location("m220", W / "220_patch_radio_space5f.py")
m220 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m220)
parse_inner = m220.parse_inner
texture_dims = m220.texture_dims
parse_boxes = m220.parse_boxes
clear_box = m220.clear_box
ASCII_PUNCT = m220.ASCII_PUNCT

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(FONT_PATH, size, index=0)
    return _font_cache[size]


def render_fit(ch: str, size: int, bw: int, bh: int, *, align: str = "left"):
    """모노(내장 비트맵) 렌더 → (bw x bh) 값배열.
    batang.ttc는 작은 크기에 수제 비트맵 글리프를 내장 — mode="1"로 받으면
    픽셀 균일·획 손실 없음. (AA+임계값 방식은 ㅇ 왼쪽 곡선 등 가는 획이 끊김 — 실기 확인.)
    잉크는 1px 여백 안(1..bw-2/1..bh-2), halo 동일 창 클립, 바닥은 BOTTOM_ROW 정렬."""
    mask = _font(size).getmask(ch, mode="1")
    mw, mh = mask.size
    pts = [(xx, yy) for yy in range(mh) for xx in range(mw) if mask.getpixel((xx, yy))]
    if not pts:
        return None
    x0 = min(p[0] for p in pts); x1 = max(p[0] for p in pts) + 1
    y0 = min(p[1] for p in pts); y1 = max(p[1] for p in pts) + 1
    iw, ih = x1 - x0, y1 - y0
    if iw > bw - 2 or ih > bh - 2:  # 잉크가 1px 여백 안에 못 들어감
        return None
    cropim = Image.new("L", (iw, ih), 0)
    for xx, yy in pts:
        cropim.putpixel((xx - x0, yy - y0), 255)
    crop = cropim.load()
    ink = [[False] * bw for _ in range(bh)]
    if align == "center":
        ox = max(1, (bw - iw) // 2)
    else:
        ox = 1
    oy = min(BOTTOM_ROW, bh - 2) - ih + 1  # 잉크 바닥 = 원본 숫자 바닥행(베이스라인 공유)
    if oy < 1:
        oy = 1
    for yy in range(ih):
        for xx in range(iw):
            if crop[xx, yy]:
                ink[oy + yy][ox + xx] = True
    # 팔레트 실측(캡션폰트): idx10-15 = 알파0(투명!), 원본 본체=idx8(0xb4), 외곽=idx1(0x20).
    # 15로 칠하면 인게임에서 투명(테두리만 보임) — 반드시 8/1 사용.
    out = [[0] * bw for _ in range(bh)]
    for yy in range(bh):
        for xx in range(bw):
            if ink[yy][xx]:
                out[yy][xx] = 8
            else:
                # halo(어두운 idx1)는 박스 가장자리까지 허용 — 잉크가 여백 경계(col1 등)에
                # 닿는 글리프(예: ㅇ의 왼쪽 호)도 사방 외곽선을 가져야 밝은 배경에서
                # 가장자리가 안 사라진다. idx1은 50% 알파 암색이라 이웃 번짐은 무시 가능.
                near = any(ink[y2][x2]
                           for y2 in range(max(0, yy - 1), min(bh, yy + 2))
                           for x2 in range(max(0, xx - 1), min(bw, xx + 2)))
                out[yy][xx] = 1 if near else 0
    return out


def draw_fit(pix: bytearray, tex_w: int, box: tuple[int, int, int, int], ch: str,
             *, punct: bool = False) -> bool:
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    if bw < 4 or bh < 8:
        return False
    r = None
    for size in range(UNIFORM_SIZE, 9, -1):
        r = render_fit(ch, size, bw, bh, align="center" if punct else "left")
        if r is not None:
            break
    if r is None:
        return False
    clear_box(pix, tex_w, box)
    for yy in range(bh):
        row = r[yy]
        base = (y0 + yy) * tex_w + x0
        for xx in range(bw):
            pix[base + xx] = row[xx]
    return True


def restore_clean_texture(clean_f, toc, eidx: int, outer: bytearray, inner: dict) -> None:
    e = toc[eidx]
    clean_f.seek(DATA_OFF + e["off"])
    clean_outer = clean_f.read(e["size"])
    clean_inner = parse_inner(clean_outer)
    dst_off, dst_size = inner[2000]
    src_off, src_size = clean_inner[2000]
    if dst_size != src_size:
        raise ValueError(f"inner2000 size mismatch at eidx {eidx}")
    outer[dst_off:dst_off + dst_size] = clean_outer[src_off:src_off + src_size]


def patch_caption_fonts(out) -> None:
    toc = json.loads((W / "bnd_toc.json").read_text(encoding="utf-8"))
    shell_map = {k: int(v) for k, v in json.loads((W / "kr_map_shell.json").read_text(encoding="utf-8")).items()}
    shell_inv = {v: k for k, v in shell_map.items()}

    clean_f = CLEAN_ISO.open("rb")
    try:
        for eidx in LARGE_EIDX + SMALL_EIDX:
            e = toc[eidx]
            out.seek(DATA_OFF + e["off"])
            outer = bytearray(out.read(e["size"]))
            inner = parse_inner(outer)
            tex_off, tex_size = inner[2000]
            font_off, _fsz = inner[2500]
            large = eidx in LARGE_EIDX

            restore_clean_texture(clean_f, toc, eidx, outer, inner)

            payload_len = tex_size - 0x60
            tex_w, tex_h = texture_dims(payload_len)
            payload_off = tex_off + 0x20
            boxes = parse_boxes(outer, font_off, tex_w, tex_h)
            idx = build_file_index_4via32(tex_w, tex_h)
            pix = bytearray(deswizzle4via32(outer[payload_off:payload_off + payload_len], tex_w, tex_h, idx))

            hang = 0
            for code, ch in shell_inv.items():
                b = boxes.get(code)
                if b and draw_fit(pix, tex_w, b, ch):
                    hang += 1

            b = boxes.get(FAKE_SPACE)
            sp = False
            if b:
                clear_box(pix, tex_w, b)
                sp = True

            done = 0
            for code, ch in ASCII_PUNCT.items():
                bb = boxes.get(code)
                if bb and draw_fit(pix, tex_w, bb, ch, punct=True):
                    done += 1

            jang = False
            b = boxes.get(JANG_CODE)
            if b:
                jang = draw_fit(pix, tex_w, b, "장")
            elif large:
                raise ValueError(f"idx{eidx}: no 0x88A3 box")

            outer[payload_off:payload_off + payload_len] = swizzle4via32(pix, tex_w, tex_h, idx)
            out.seek(DATA_OFF + e["off"])
            out.write(outer)
            print(f"font idx {eidx}: hangul {hang}; space5f={sp}; punct {done}; jang={jang}")
    finally:
        clean_f.close()


def main() -> None:
    if not SRC_ISO.exists():
        raise SystemExit(f"missing source ISO: {SRC_ISO}")
    if not CLEAN_ISO.exists():
        raise SystemExit(f"missing clean ISO: {CLEAN_ISO}")
    if SRC_ISO.resolve() != OUT_ISO.resolve():
        shutil.copyfile(SRC_ISO, OUT_ISO)
    with OUT_ISO.open("r+b") as out:
        patch_caption_fonts(out)
        m220.patch_radio_text(out)
    print(f"done: {OUT_ISO}")


if __name__ == "__main__":
    main()
