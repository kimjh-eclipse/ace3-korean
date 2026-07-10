# -*- coding: utf-8 -*-
"""라디오 자막 최종 후보 v3: 폰트 테이블 '무변경'. 공백=0x5F, 장=0x88A3 치환.

실기 GS덤프/크래시로 확정된 사실:
- range 테이블에 엔트리를 append하면 엔진이 절대 찾지 못한다(?로 fallback).
- 테이블을 정렬 재배열하면 타이틀 로드에서 게임이 죽는다(순서 의존성 존재).
- 텍스처 편집과 기존 코드 조회는 완벽히 동작한다(GS덤프로 검증).
따라서 구조 변경 없이:
- 공백: 대형 캡션폰트에 이미 있는 미사용 코드 0x5F('_')의 글리프를 blank하고
  인코더가 공백을 0x5F 1바이트로 emit.
- 장: charset에 없는 0x978B 대신, 이미 있는 미사용 한자코드 0x88A3으로 emit하고
  그 박스에 장을 그린다(라디오 섹션 내 문자열에만 적용).
"""
from __future__ import annotations

import json
import os
import shutil
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from deswz_tables import build_file_index_4via32, deswizzle4via32, swizzle4via32


W = Path(__file__).resolve().parent
DATA_OFF = 2117 * 2048
SRC_ISO = W / "ACE3_KR_gsfontfix.iso"
OUT_ISO = Path(os.environ.get("ACE3_RADIO_SPACE5F_OUT", str(W / "ACE3_KR_gsfontfix_space5f.iso")))
FONT_PATH = Path(r"C:\Windows\Fonts\gulim.ttc")
LARGE_EIDX = (4603, 4604, 4607, 4608, 4609, 4610)
SMALL_EIDX = (4605, 4606)

FAKE_SPACE = 0x5F          # '_' : 대형폰트 charset에 존재, 라디오 emit 0회
JANG_SRC = "장"            # kr_map 대신 아래 코드로 emit
JANG_CODE = 0x88A3         # 대형폰트 charset에 존재, 라디오 emit 0회 → 장 글리프 주입

ASCII_PUNCT = {
    0x21: "!",
    0x23: "#",
    0x25: "%",
    0x27: "'",
    0x2C: ",",
    0x2D: "-",
    0x2E: ".",
    0x3A: ":",
    0x3B: ";",
    0x3F: "?",
    0x5B: "[",
    0x5D: "]",
    0x7E: "~",
}

SAFE_REPLACE = {
    "·": "・",
    "—": "―",
}


def parse_inner(buf: bytes | bytearray) -> dict[int, tuple[int, int]]:
    if buf[:4] != b"BND\x00":
        raise ValueError("not an inner BND")
    total = struct.unpack_from("<I", buf, 4)[0]
    count = struct.unpack_from("<I", buf, 8)[0]
    out: dict[int, tuple[int, int]] = {}
    prev = -1
    for i in range(count):
        fid, off = struct.unpack_from("<II", buf, 0x18 + i * 8)
        if off <= prev or off >= total:
            break
        nxt = total
        if i + 1 < count:
            _fid2, noff = struct.unpack_from("<II", buf, 0x18 + (i + 1) * 8)
            if off < noff <= total:
                nxt = noff
        out[fid] = (off, nxt - off)
        prev = off
    return out


def texture_dims(payload_len: int) -> tuple[int, int]:
    if payload_len == 1024 * 512 // 2:
        return 1024, 512
    if payload_len == 512 * 512 // 2:
        return 512, 512
    raise ValueError(f"unsupported payload length: 0x{payload_len:X}")


def font_header(outer: bytes | bytearray, font_off: int) -> tuple[int, int, int]:
    packed = struct.unpack_from("<I", outer, font_off + 0x10)[0]
    return packed & 0xFFFF, packed >> 16, struct.unpack_from("<I", outer, font_off + 0x18)[0]


def find_range(outer: bytes | bytearray, font_off: int, code: int) -> tuple[int, int, int, int] | None:
    """code를 커버하는 첫 range의 (range_index, a, z, gi)."""
    nranges, nglyph, _mo = font_header(outer, font_off)
    for i in range(nranges):
        a, z, gi = struct.unpack_from("<III", outer, font_off + 0x20 + i * 12)
        if not (0 <= a <= z <= 0xFFFF):
            continue
        if gi >= nglyph or gi + (z - a) >= nglyph:
            continue
        if a <= code <= z:
            return i, a, z, gi
    return None


def glyph_for_code(outer: bytes | bytearray, font_off: int, code: int) -> int | None:
    r = find_range(outer, font_off, code)
    return None if r is None else r[3] + (code - r[1])


def append_ranges(outer: bytearray, font_off: int, font_size: int,
                  new_ranges: list[tuple[int, int]]) -> None:
    """(code, glyph) 목록을 range 테이블 끝에 append. metric 테이블을 뒤로 민다."""
    need = 12 * len(new_ranges)
    nranges, nglyph, metric_off = font_header(outer, font_off)
    metric_len = nglyph * 24
    slack = font_size - (metric_off + metric_len)
    if slack < need:
        raise ValueError(f"font slack {slack} < needed {need}")
    src = font_off + metric_off
    outer[src + need:src + need + metric_len] = bytes(outer[src:src + metric_len])
    for k, (code, gi) in enumerate(new_ranges):
        struct.pack_into("<III", outer, src + k * 12, code, code, gi)
    struct.pack_into("<I", outer, font_off + 0x10, (nglyph << 16) | (nranges + len(new_ranges)))
    struct.pack_into("<I", outer, font_off + 0x18, metric_off + need)


def parse_boxes(outer: bytes | bytearray, font_off: int, tex_w: int, tex_h: int) -> dict[int, tuple[int, int, int, int]]:
    nranges, nglyph, metric_off = font_header(outer, font_off)
    boxes: dict[int, tuple[int, int, int, int]] = {}
    for i in range(nranges):
        a, z, gi = struct.unpack_from("<III", outer, font_off + 0x20 + i * 12)
        if not (0 <= a <= z <= 0xFFFF):
            continue
        if gi >= nglyph or gi + (z - a) >= nglyph:
            continue
        for k in range(z - a + 1):
            code = a + k
            glyph = gi + k
            u0, v0, u1, v1 = struct.unpack_from("<4f", outer, font_off + metric_off + glyph * 24)
            x0 = max(0, min(tex_w, round(u0 * tex_w)))
            y0 = max(0, min(tex_h, round(v0 * tex_h)))
            x1 = max(0, min(tex_w, round(u1 * tex_w)))
            y1 = max(0, min(tex_h, round(v1 * tex_h)))
            if x1 > x0 and y1 > y0:
                boxes.setdefault(code, (x0, y0, x1, y1))
    return boxes


def clear_box(pix: bytearray, tex_w: int, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    for yy in range(y1 - y0):
        base = (y0 + yy) * tex_w + x0
        pix[base:base + (x1 - x0)] = b"\x00" * (x1 - x0)


def draw_char(pix: bytearray, tex_w: int, box: tuple[int, int, int, int], ch: str,
              font: ImageFont.FreeTypeFont, punct: bool) -> bool:
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    if bw < 2 or bh < 6:
        return False
    clear_box(pix, tex_w, box)

    glyph = Image.new("L", (bw, bh), 0)
    draw = ImageDraw.Draw(glyph)
    if punct:
        x = max(0, bw // 3 - 1) if ch in ".,:;" else max(0, (bw - 10) // 2)
    else:
        x = 0
    draw.text((x, bh - 2), ch, font=font, fill=255, anchor="ls")
    src = glyph.load()
    on = [[src[xx, yy] >= 96 for xx in range(bw)] for yy in range(bh)]
    for yy in range(bh):
        for xx in range(bw):
            if on[yy][xx]:
                v = 15
            else:
                near = any(
                    on[y2][x2]
                    for y2 in range(max(0, yy - 1), min(bh, yy + 2))
                    for x2 in range(max(0, xx - 1), min(bw, xx + 2))
                )
                v = 4 if near else 0
            pix[(y0 + yy) * tex_w + x0 + xx] = v
    return True


def patch_caption_fonts(out) -> None:
    toc = json.loads((W / "bnd_toc.json").read_text(encoding="utf-8"))
    punct_font = ImageFont.truetype(str(FONT_PATH), 16, index=0)

    for eidx in LARGE_EIDX + SMALL_EIDX:
        e = toc[eidx]
        out.seek(DATA_OFF + e["off"])
        outer = bytearray(out.read(e["size"]))
        inner = parse_inner(outer)
        tex_off, tex_size = inner[2000]
        font_off, font_size = inner[2500]
        large = eidx in LARGE_EIDX
        notes: list[str] = []

        payload_len = tex_size - 0x60
        tex_w, tex_h = texture_dims(payload_len)
        payload_off = tex_off + 0x20
        boxes = parse_boxes(outer, font_off, tex_w, tex_h)
        idx = build_file_index_4via32(tex_w, tex_h)
        pix = bytearray(deswizzle4via32(outer[payload_off:payload_off + payload_len], tex_w, tex_h, idx))

        # 가짜 공백: 0x5F 글리프 박스 blank (대형에만 존재)
        b = boxes.get(FAKE_SPACE)
        if b:
            clear_box(pix, tex_w, b)
            notes.append(f"space blank 0x5F@{b}")
        else:
            notes.append("no 0x5F (small font)")

        # 반각 문장부호 주입 (기존 검증 방식)
        done = 0
        for code, ch in ASCII_PUNCT.items():
            bb = boxes.get(code)
            if bb and draw_char(pix, tex_w, bb, ch, punct_font, punct=True):
                done += 1
        notes.append(f"punct {done}")

        # 장 드로잉: 0x88A3 박스 (대형에만 존재)
        b = boxes.get(JANG_CODE)
        if b:
            bh = b[3] - b[1]
            size = 16 if bh >= 18 else 14
            jang_font = ImageFont.truetype(str(FONT_PATH), size, index=0)
            if draw_char(pix, tex_w, b, "장", jang_font, punct=False):
                notes.append(f"jang@{b}")
        elif large:
            raise ValueError(f"idx{eidx}: no box for 0x88A3")

        outer[payload_off:payload_off + payload_len] = swizzle4via32(pix, tex_w, tex_h, idx)
        out.seek(DATA_OFF + e["off"])
        out.write(outer)
        print(f"font idx {eidx}: " + "; ".join(notes))


def is_radio_string(text: str) -> bool:
    return "<op()>" in text or "<sp(20)>" in text or "<on()>" in text


def normalize_visible(ch: str, keep_space: bool) -> str:
    if ch in (" ", "　", " "):
        return chr(FAKE_SPACE) if keep_space else ""
    return SAFE_REPLACE.get(ch, ch)


def encode_tagged(text: str, kr_map: dict[str, int], *, keep_space: bool,
                  space_code: int = FAKE_SPACE) -> tuple[bytes, int]:
    """space_code: 무전 대사=0x5F(1B, 캡션폰트 blank), 태그 없는 배너/알림류=
    0x8140(2B 전각공백 — 0x5F가 charset에 없는 경보폰트 id1200011에서도 공백)."""
    out = bytearray()
    fallback = 0
    i = 0
    while i < len(text):
        if text[i] == "<":
            j = text.find(">", i + 1)
            if j >= 0:
                out += text[i:j + 1].encode("ascii")
                i = j + 1
                continue
        if text[i] == "⟦":
            j = text.find("⟧", i + 1)
            if j >= 0:
                out += bytes.fromhex(text[i + 1:j])
                i = j + 1
                continue
        ch = normalize_visible(text[i], keep_space)
        if not ch:
            i += 1
            continue
        if ch == chr(FAKE_SPACE):
            if space_code < 0x100:
                out.append(space_code)
            else:
                out += bytes((space_code >> 8, space_code & 0xFF))
            i += 1
            continue
        if ch == JANG_SRC:
            out += bytes((JANG_CODE >> 8, JANG_CODE & 0xFF))
            i += 1
            continue
        if "가" <= ch <= "힣":
            code = kr_map.get(ch)
            if code is None:
                out += b"?"
                fallback += 1
            else:
                out += bytes((code >> 8, code & 0xFF))
        else:
            try:
                out += ch.encode("cp932")
            except UnicodeEncodeError:
                out += b"?"
                fallback += 1
        i += 1
    return bytes(out), fallback


def load_tl() -> dict[str, str]:
    tl: dict[str, str] = {}
    for path in sorted((W / "tl").glob("*.json")):
        tl.update(json.loads(path.read_text(encoding="utf-8")))
    return {k: v for k, v in tl.items() if v and v != k}


def build_section(d: dict, tl: dict[str, str], kr_map: dict[str, int], *, keep_space: bool):
    strs = d["strs"]
    h0 = min(s["off"] for s in strs)
    orig_end = max(s["off"] + len(bytes.fromhex(s["hex"])) + 1 for s in strs)
    limit = max(d["csize"], orig_end)
    heap = bytearray()
    offmap: dict[bytes, int] = {}
    new_offs: dict[int, int] = {}
    radio = 0
    fallback = 0
    for s in strs:
        src = s["t"]
        if src in tl:
            sc = FAKE_SPACE if is_radio_string(src) else 0x8140
            data, fb = encode_tagged(tl[src], kr_map, keep_space=keep_space, space_code=sc)
            fallback += fb
            if is_radio_string(src):
                radio += 1
        else:
            data = bytes.fromhex(s["hex"])
        if data in offmap:
            new_offs[s["slot"]] = offmap[data]
            continue
        off = h0 + len(heap)
        if off + len(data) + 1 > limit:
            return None
        offmap[data] = off
        new_offs[s["slot"]] = off
        heap += data + b"\x00"
    return h0, heap + bytes(limit - h0 - len(heap)), new_offs, radio, fallback


def patch_radio_text(out) -> None:
    toc = json.loads((W / "bnd_toc.json").read_text(encoding="utf-8"))
    db = json.loads((W / "db.json").read_text(encoding="utf-8"))
    tl = load_tl()
    kr_map = {k: int(v) for k, v in json.loads((W / "kr_map_shell.json").read_text(encoding="utf-8")).items()}

    patched = 0
    compacted = 0
    radio_strings = 0
    fallback_chars = 0
    overflow: list[tuple[int, int]] = []
    for d in db:
        strs = d.get("strs", [])
        if not any(is_radio_string(s["t"]) and s["t"] in tl for s in strs):
            continue
        built = build_section(d, tl, kr_map, keep_space=True)
        if built is None:
            built = build_section(d, tl, kr_map, keep_space=False)
            compacted += 1
        if built is None:
            overflow.append((d["idx"], d["id"]))
            continue
        h0, heap, new_offs, section_radio, section_fallback = built
        e = toc[d["idx"]]
        out.seek(DATA_OFF + e["off"] + d["base"] + d["tbloff"])
        tbl = bytearray(out.read(d["count"] * 4))
        for slot, off in new_offs.items():
            struct.pack_into("<I", tbl, slot * 4, off)
        out.seek(DATA_OFF + e["off"] + d["base"] + d["tbloff"])
        out.write(tbl)
        out.seek(DATA_OFF + e["off"] + d["base"] + h0)
        out.write(heap)
        patched += 1
        radio_strings += section_radio
        fallback_chars += section_fallback
    print(f"patched text sections: {patched}")
    print(f"space-compacted sections: {compacted}")
    print(f"radio strings: {radio_strings}")
    print(f"fallback chars: {fallback_chars}")
    print(f"overflow sections: {len(overflow)}")
    if overflow:
        print("overflow sample:", overflow[:20])


def main() -> None:
    if not SRC_ISO.exists():
        raise SystemExit(f"missing source ISO: {SRC_ISO}")
    if SRC_ISO.resolve() != OUT_ISO.resolve():
        shutil.copyfile(SRC_ISO, OUT_ISO)
    with OUT_ISO.open("r+b") as out:
        patch_caption_fonts(out)
        patch_radio_text(out)
    print(f"done: {OUT_ISO}")


if __name__ == "__main__":
    main()
