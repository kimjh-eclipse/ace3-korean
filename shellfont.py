# -*- coding: utf-8 -*-
"""셸(프론트엔드) 폰트 재작성:
- L1 한자 레인지(0x889F~0x9872)를 제거하고 그 글리프 박스를 한글에 기증
- 한글 음절은 미사용 SJIS 영역 0xEB40+ 에 연속 배치 (리드당 2레인지: 0x40-7E, 0x80-FC)
- 레인지/글리프 인덱스는 코드 순서 누적(원본 불변식 유지), 메트릭 배열 재배열
- 텍스처는 PSMT32-업로드 스위즐 해제 후 글리프 드로잉, 재스위즐
"""
import struct
from PIL import Image, ImageDraw, ImageFont
from deswz_tables import build_file_index_4via32, deswizzle4via32, swizzle4via32

W, H = 1024, 512
KANJI_LO, KANJI_HI = 0x889F, 0x9872
# 한글 배치 영역: 표준 SJIS 2수준 한자(0x989F~0xE9FC) — 게임 디코더가 확실히 수용.
# 게임/폰트가 실제 쓰는 L2 코드(전 폰트 합집합)는 피한다.
LEADS = list(range(0x99, 0xEA))
TRAILS = [t for t in range(0x40, 0xFD) if t != 0x7F]  # 188개/리드
RESERVED_L2 = {0x99E9, 0x9A6B, 0x9A99, 0x9B99, 0x9C61, 0x9D66, 0x9FAD,
               0xE0F3, 0xE177, 0xE183, 0xE3C4, 0xE56A, 0xE58E, 0xE592,
               0xE5E1, 0xE6DC, 0xE748, 0xE8A6, 0xE978}

_swz_idx = None
def swz_idx():
    global _swz_idx
    if _swz_idx is None:
        _swz_idx = build_file_index_4via32(W, H)
    return _swz_idx


def shell_codes(n):
    """앞에서부터 n개의 한글용 SJIS 코드 (0x9940부터, 예약 코드 제외)"""
    out = []
    for lead in LEADS:
        for t in TRAILS:
            c = (lead << 8) | t
            if c in RESERVED_L2:
                continue
            out.append(c)
            if len(out) == n:
                return out
    raise RuntimeError("셸 코드 영역 고갈")


def parse_font(buf, ft):
    """ft: shellfonts.json 레코드. -> (ranges, metrics list[bytes24])"""
    tbl = ft["fb"] + 0x2c
    rs = []
    o = tbl
    for _ in range(ft["nranges"]):
        rs.append(struct.unpack_from("<III", buf, o)); o += 12
    mets = [bytes(buf[ft["met"] + i * 24: ft["met"] + (i + 1) * 24]) for i in range(ft["nglyph"])]
    return rs, mets


def rebuild(buf, ft, syl_codes, glyph_render, keep_kanji=frozenset(), min_w=17):
    """buf(bytearray, 엔트리 전체)를 제자리 수정.
    syl_codes: {음절: 전역코드} — 이 폰트가 담아야 할 한글(부분집합).
    keep_kanji: 보존할 한자 SJIS 코드 집합(미번역 문자열이 쓰는 것). 나머지 한자는 기증.
    glyph_render(ch)->PIL 'L' 이미지. 반환: 사용한 {음절: 코드}."""
    rs, mets = parse_font(buf, ft)
    ng, met_off, fb = ft["nglyph"], ft["met"], ft["fb"]
    tbl_cap = (met_off - (fb + 0x2c)) // 12

    # 한자 코드→글리프 인덱스, 박스 크기
    kanji_gi = {}
    for a, z, gi in rs:
        if KANJI_LO <= a and z <= KANJI_HI:
            for k in range(z - a + 1):
                kanji_gi[a + k] = gi + k

    def box_ok(g):
        u0, v0, u1, v1 = struct.unpack_from("<4f", mets[g], 0)
        return round((u1 - u0) * W) >= min_w and round((v1 - v0) * H) >= 19

    # 기증 후보 = 보존대상 아닌 한자 중 박스 충분
    donor_codes = [c for c in sorted(kanji_gi)
                   if c not in keep_kanji and box_ok(kanji_gi[c])]
    if len(donor_codes) < len(syl_codes):
        raise RuntimeError(f"id{ft['id']} 기증 부족: {len(donor_codes)} < {len(syl_codes)}")
    donors = [kanji_gi[c] for c in donor_codes[:len(syl_codes)]]

    # 보존 한자 = keep_kanji ∩ 이 폰트 한자
    keep_codes = sorted(c for c in kanji_gi if c in keep_kanji)

    # 한글 코드 정렬
    syls_sorted = sorted(syl_codes, key=lambda s: syl_codes[s])
    codes = [syl_codes[s] for s in syls_sorted]
    mapping = dict(syl_codes)

    def runs_from_codes(code_list, val_for):
        """정렬된 코드 리스트 → [(a,z,[val,...])] 연속 런. val_for(code)->항목."""
        out = []
        for c in code_list:
            if out and c == out[-1][1] + 1:
                out[-1][1] = c
                out[-1][2].append(val_for(c))
            else:
                out.append([c, c, [val_for(c)]])
        return out

    # 이벤트: 비한자 보존 레인지 + 보존 한자 런 + 한글 런
    kept_nonkanji = [r for r in rs if r[1] < KANJI_LO or r[0] > KANJI_HI]
    events = [("keep", a, z, gi) for a, z, gi in kept_nonkanji]
    events += [("kanji", a, z, codes_) for a, z, codes_ in runs_from_codes(keep_codes, lambda c: c)]
    kr_runs = runs_from_codes(codes, lambda c: syls_sorted[codes.index(c)])
    events += [("kr", a, z, syls) for a, z, syls in kr_runs]
    events.sort(key=lambda ev: ev[1])
    for (_, _, z1, _), (_, a2, _, _) in zip(events, events[1:]):
        assert z1 < a2, f"id{ft['id']} 레인지 겹침 {z1:#x}>={a2:#x}"

    new_ranges = []   # (a, z, new_gi)
    new_mets = []     # bytes24 리스트 (새 글리프 순)
    tex_jobs = []     # (donor_box, ch)
    di = 0
    for ev in events:
        kind, a, z, payload = ev
        if kind == "keep":
            gi = payload
            new_ranges.append((a, z, len(new_mets)))
            for k in range(z - a + 1):
                new_mets.append(mets[gi + k])
        elif kind == "kanji":
            new_ranges.append((a, z, len(new_mets)))
            for c in payload:            # 보존 한자: 원본 글리프 그대로
                new_mets.append(mets[kanji_gi[c]])
        else:
            new_ranges.append((a, z, len(new_mets)))
            for syl in payload:
                donor = donors[di]; di += 1
                u0, v0, u1, v1 = struct.unpack_from("<4f", mets[donor], 0)
                new_mets.append(struct.pack("<4f4H", u0, v0, u1, v1, 0, 16, 17, 0))
                bx, by = round(u0 * W), round(v0 * H)
                bw, bh = round((u1 - u0) * W), round((v1 - v0) * H)
                tex_jobs.append(((bx, by, bw, bh), syl))

    assert len(new_ranges) <= tbl_cap, f"id{ft['id']} 레인지 초과 {len(new_ranges)}>{tbl_cap}"
    assert len(new_mets) <= ng, f"id{ft['id']} 글리프 초과 {len(new_mets)}>{ng}"

    # --- 쓰기 ---
    # 헤더 카운트: +0x10 = (nglyph<<16)|(nranges+1)
    struct.pack_into("<I", buf, fb + 0x10, (len(new_mets) << 16) | (len(new_ranges) + 1))
    o = fb + 0x2c
    for a, z, gi in new_ranges:
        struct.pack_into("<III", buf, o, a, z, gi); o += 12
    while o < met_off:               # 남는 테이블 공간 0 클리어
        buf[o] = 0; o += 1
    for i, m in enumerate(new_mets):
        buf[met_off + i * 24: met_off + (i + 1) * 24] = m
    # 남는 메트릭 슬롯은 원본 유지(참조 안 됨)

    # 텍스처: 본체=팔레트 idx8(밝은 회색·불투명), 외곽 1px=idx1(어두움), 배경=0(투명)
    INK, EDGE = 8, 1
    idx = swz_idx()
    pix = deswizzle4via32(buf[ft["tex"]: ft["tex"] + W * H // 2], W, H, idx)
    pix = bytearray(pix)
    for (bx, by, bw, bh), ch in tex_jobs:
        img = glyph_render(ch)
        gw, gh = img.size
        pm = img.load()
        on = [[(pm[xx, yy] >= 128) if (xx < gw and yy < gh) else False
               for xx in range(bw)] for yy in range(bh)]
        for yy in range(bh):
            for xx in range(bw):
                if on[yy][xx]:
                    v = INK
                else:
                    near = any(on[y2][x2]
                               for y2 in range(max(0, yy-1), min(bh, yy+2))
                               for x2 in range(max(0, xx-1), min(bw, xx+2)))
                    v = EDGE if near else 0
                pix[(by + yy) * W + (bx + xx)] = v
    buf[ft["tex"]: ft["tex"] + W * H // 2] = swizzle4via32(pix, W, H, idx)
    return mapping


def make_renderer(font_path=r"C:\Windows\Fonts\gulim.ttc", size=16, box=(19, 19)):
    ft = ImageFont.truetype(font_path, size, index=0)
    def render(ch):
        img = Image.new("L", box, 0)
        # 박스 하단 정렬(일본어 한자 베이스라인 근사): baseline y=16
        ImageDraw.Draw(img).text((1, 16), ch, font=ft, fill=255, anchor="ls")
        return img.point(lambda v: 255 if v >= 128 else 0)
    return render
