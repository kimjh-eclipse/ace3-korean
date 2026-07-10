# -*- coding: utf-8 -*-
"""셸 폰트 6종(id400205x) 한글을 바탕 bbox-fit으로 재드로잉 — 캡션과 스타일 통일.

- 대상: idx 8780/8781/8782/8783/8784/8787 (build.py가 굴림 한글을 이미 주입한 상태)
- 순수 텍스처 편집만. 테이블/구조 무변경(엔진 제약 준수). clean 복원도 하지 않음
  (build.py가 donor box를 재배치했으므로 현재 테이블 기준 box에 덮어그리기).
- 부호/가나/한자는 그대로 둠(한글 donor box만 재드로잉).
- 8781에만 존재하는 0x5F('_') 글리프는 blank — 라디오 인코딩의 가짜 공백이
  혹시 이 폰트로 렌더될 경우 밑줄 대신 공백이 되도록.
입력: ACE3_KR_caption_batang.iso → 출력: ACE3_KR_caption_full.iso
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import struct
from pathlib import Path

from deswz_tables import build_file_index_4via32, deswizzle4via32, swizzle4via32

W = Path(__file__).resolve().parent
DATA_OFF = 2117 * 2048
SRC_ISO = W / "ACE3_KR_caption_batang.iso"
OUT_ISO = Path(os.environ.get("ACE3_SHELL_BATANG_OUT", str(W / "ACE3_KR_caption_full.iso")))
EIDX = (8780, 8781, 8782, 8783, 8784, 8787)
FAKE_SPACE = 0x5F

_spec = importlib.util.spec_from_file_location("m222", W / "222_patch_caption_batang.py")
m222 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m222)
parse_inner = m222.parse_inner
parse_boxes = m222.parse_boxes
clear_box = m222.clear_box
draw_fit = m222.draw_fit


def patch_alert_font(out, toc, kr) -> None:
    """경보/알림 HUD 폰트 idx4614(id1200011): 텍스처가 outer+0x60 raw, 폰트블록만
    inner 2500인 변형 구조. 커버 음절(988)을 바탕 비트맵으로 재드로잉."""
    eidx = 4614
    e = toc[eidx]
    out.seek(DATA_OFF + e["off"])
    outer = bytearray(out.read(e["size"]))
    inner = parse_inner(outer)
    font_off, _ = inner[2500]
    payload_off, payload_len = 0x60, 0x40000
    boxes = parse_boxes(outer, font_off, 1024, 512)
    idx = build_file_index_4via32(1024, 512)
    pix = bytearray(deswizzle4via32(outer[payload_off:payload_off + payload_len], 1024, 512, idx))
    hang = 0
    for ch, code in kr.items():
        b = boxes.get(code)
        if b and draw_fit(pix, 1024, b, ch):
            hang += 1
    outer[payload_off:payload_off + payload_len] = swizzle4via32(pix, 1024, 512, idx)
    out.seek(DATA_OFF + e["off"])
    out.write(outer)
    print(f"idx {eidx} id 1200011(경보): hangul {hang}")


def main() -> None:
    toc = json.loads((W / "bnd_toc.json").read_text(encoding="utf-8"))
    kr = {k: int(v) for k, v in json.loads((W / "kr_map_shell.json").read_text(encoding="utf-8")).items()}
    if SRC_ISO.resolve() != OUT_ISO.resolve():
        shutil.copyfile(SRC_ISO, OUT_ISO)
    with OUT_ISO.open("r+b") as out:
        patch_alert_font(out, toc, kr)
        for eidx in EIDX:
            e = toc[eidx]
            out.seek(DATA_OFF + e["off"])
            outer = bytearray(out.read(e["size"]))
            inner = parse_inner(outer)
            tex_off, tex_size = inner[2000]
            font_off, _fsz = inner[2500]
            payload_len = tex_size - 0x60
            if payload_len != 1024 * 512 // 2:
                raise ValueError(f"idx{eidx}: unexpected payload {payload_len:#x}")
            payload_off = tex_off + 0x20
            boxes = parse_boxes(outer, font_off, 1024, 512)
            idx = build_file_index_4via32(1024, 512)
            pix = bytearray(deswizzle4via32(outer[payload_off:payload_off + payload_len], 1024, 512, idx))

            hang = 0
            for ch, code in kr.items():
                b = boxes.get(code)
                if b and draw_fit(pix, 1024, b, ch):
                    hang += 1

            sp = False
            b = boxes.get(FAKE_SPACE)
            if b:
                clear_box(pix, 1024, b)
                sp = True

            outer[payload_off:payload_off + payload_len] = swizzle4via32(pix, 1024, 512, idx)
            out.seek(DATA_OFF + e["off"])
            out.write(outer)
            print(f"idx {eidx} id {e['id']}: hangul {hang}; space5f_blank={sp}")
    print(f"done: {OUT_ISO}")


if __name__ == "__main__":
    main()
