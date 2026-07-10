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


HIRA_LO, HIRA_HI = 0x829F, 0x82F1


def capacity(buf, ft, keep=frozenset(), min_w=17):
    """이 폰트가 수용 가능한 최대 한글 수(= 박스 충분한 기증가능 한자+히라가나)."""
    rs, mets = parse_font(buf, ft)
    def box_ok(g):
        u0, v0, u1, v1 = struct.unpack_from("<4f", mets[g], 0)
        return round((u1 - u0) * W) >= min_w and round((v1 - v0) * H) >= 19
    n = 0
    for a, z, gi in rs:
        for k in range(z - a + 1):
            c = a + k
            if (KANJI_LO <= c <= KANJI_HI or HIRA_LO <= c <= HIRA_HI) \
               and c not in keep and box_ok(gi + k):
                n += 1
    return n


def inplace_inject(buf, ft, char_codes, glyph_render, add_ranges=None):
    """구조 무변경 제자리 주입(2026-07-08 3차): 글리프 인덱스/메트릭은 일절 바꾸지
    않고, char_codes{문자: 기존 한자코드}의 각 코드가 가리키는 글리프 박스에 문자
    글리프만 덮어그린다. HUD(무전 자막) 렌더러가 원본 레이아웃 기준의 baked
    코드→글리프 매핑을 쓰기 때문에 재배열 방식(rebuild)은 그쪽에서 깨진다.
    add_ranges: {부호자기코드: (문자, 기증한자코드)} — 폰트에 글리프가 없는 부호
    (반각 .! 등)를 1바이트 인코딩 그대로 쓰기 위해, 기증 글리프 칸에 부호를 그리고
    그 칸을 가리키는 싱글톤 레인지를 '추가'한다(기존 레인지/gi 불변, 정렬 유지).
    반환: (주입 문자 수, 추가 레인지 수)."""
    add_ranges = add_ranges or {}
    rs, mets = parse_font(buf, ft)
    code_gi = {}
    for a, z, gi in rs:
        for k in range(z - a + 1):
            code_gi[a + k] = gi + k
    INK, EDGE = 8, 1
    idx = swz_idx()
    pix = bytearray(deswizzle4via32(buf[ft["tex"]: ft["tex"] + W * H // 2], W, H, idx))

    def draw(ch, gi):
        u0, v0, u1, v1 = struct.unpack_from("<4f", mets[gi], 0)
        bx, by = round(u0 * W), round(v0 * H)
        bw, bh = round((u1 - u0) * W), round((v1 - v0) * H)
        if bw < 8 or bh < 8:
            return False
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
        return True

    done = 0
    for ch, code in char_codes.items():
        gi = code_gi.get(code)
        if gi is not None and draw(ch, gi):
            done += 1

    # 부호 싱글톤 치환: 레인지 테이블에 여유 슬롯이 없으므로(정확히 nranges개),
    # '한글이 배정되지 않은 기증코드'가 단독으로 차지한 싱글톤 엔트리(a==z)를 찾아
    # 그 엔트리의 코드만 부호 자기코드로 바꾼다(gi 그대로, 테이블 크기 불변).
    added = 0
    if add_ranges:
        used_codes = set(char_codes.values())
        singles = [i for i, (a, z, gi) in enumerate(rs)
                   if a == z and (KANJI_LO <= a <= KANJI_HI or HIRA_LO <= a <= HIRA_HI)
                   and a not in used_codes]
        new_rs = [list(r) for r in rs]
        si = 0
        for own_code, (ch, _donor) in sorted(add_ranges.items()):
            if own_code in code_gi:
                continue  # 이미 폰트에 있음
            if si >= len(singles):
                break
            ent = singles[si]; si += 1
            gi = new_rs[ent][2]
            if not draw(ch, gi):
                continue
            new_rs[ent][0] = new_rs[ent][1] = own_code
            added += 1
        if added:
            new_rs.sort(key=lambda r: r[0])
            fb = ft["fb"]
            o = fb + 0x2c
            for a, z, gi in new_rs:
                struct.pack_into("<III", buf, o, a, z, gi); o += 12

    buf[ft["tex"]: ft["tex"] + W * H // 2] = swizzle4via32(pix, W, H, idx)
    return done, added


def rebuild(buf, ft, syl_codes, glyph_render, keep_kanji=frozenset(), min_w=17,
            extra=None):
    """buf(bytearray, 엔트리 전체)를 제자리 수정.
    syl_codes: {음절: 전역코드} — 이 폰트가 담아야 할 한글(부분집합).
    extra: {코드: 문자} — 한글 외 주입할 글리프(반각 문장부호 .!~ 등, 원본 폰트에
    글리프가 없는 문자). 코드는 그 문자의 SJIS 코드.
    keep_kanji: 보존할 SJIS 코드 집합(미번역 문자열이 쓰는 한자/가나). 나머지
    한자+히라가나는 기증(2026-07-08: 대사·브리핑·HUD 전부 셸폰트 렌더 확정으로
    전 음절 수용 위해 히라가나도 기증. 가타카나는 화자명 표기용으로 보존).
    glyph_render(ch)->PIL 'L' 이미지. 반환: 사용한 {음절: 코드}."""
    extra = extra or {}
    rs, mets = parse_font(buf, ft)
    ng, met_off, fb = ft["nglyph"], ft["met"], ft["fb"]
    tbl_cap = (met_off - (fb + 0x2c)) // 12

    # 전 코드→글리프 인덱스
    code_gi = {}
    for a, z, gi in rs:
        for k in range(z - a + 1):
            code_gi[a + k] = gi + k

    def box_ok(g):
        u0, v0, u1, v1 = struct.unpack_from("<4f", mets[g], 0)
        return round((u1 - u0) * W) >= min_w and round((v1 - v0) * H) >= 19

    def donatable(c):
        return (KANJI_LO <= c <= KANJI_HI or HIRA_LO <= c <= HIRA_HI) \
               and c not in keep_kanji and box_ok(code_gi[c])

    # 주입 코드 통합: 한글 + 부호. 부호 코드가 기존 레인지에 있으면(=폰트에 이미
    # 있는 코드) 주입 대상에서 제외(겹침 방지). 없으면 신규 코드로 주입.
    inject = {syl_codes[s]: s for s in syl_codes}
    for c, ch in extra.items():
        if c not in code_gi:
            inject[c] = ch
    inject_codes = sorted(inject)

    donor_codes = [c for c in sorted(code_gi) if donatable(c)]
    if len(donor_codes) < len(inject_codes):
        raise RuntimeError(f"id{ft['id']} 기증 부족: {len(donor_codes)} < {len(inject_codes)}")
    donors = [code_gi[c] for c in donor_codes[:len(inject_codes)]]
    donated = set(donor_codes)  # 기증 대상 전체(초과분 포함)는 레인지에서 제거

    # 보존 코드 = 기증 안 하는 모든 원본 코드
    keep_codes = sorted(c for c in code_gi if c not in donated)
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

    events = [("orig", a, z, codes_) for a, z, codes_ in runs_from_codes(keep_codes, lambda c: c)]
    events += [("inj", a, z, chs) for a, z, chs in runs_from_codes(inject_codes, lambda c: inject[c])]
    events.sort(key=lambda ev: ev[1])
    for (_, _, z1, _), (_, a2, _, _) in zip(events, events[1:]):
        assert z1 < a2, f"id{ft['id']} 레인지 겹침 {z1:#x}>={a2:#x}"

    new_ranges = []   # (a, z, new_gi)
    new_mets = []     # bytes24 리스트 (새 글리프 순)
    tex_jobs = []     # (donor_box, ch)
    di = 0
    for ev in events:
        kind, a, z, payload = ev
        if kind == "orig":
            new_ranges.append((a, z, len(new_mets)))
            for c in payload:            # 보존: 원본 글리프 그대로
                new_mets.append(mets[code_gi[c]])
        else:
            new_ranges.append((a, z, len(new_mets)))
            for ch in payload:
                donor = donors[di]; di += 1
                u0, v0, u1, v1 = struct.unpack_from("<4f", mets[donor], 0)
                new_mets.append(struct.pack("<4f4H", u0, v0, u1, v1, 0, 16, 17, 0))
                bx, by = round(u0 * W), round(v0 * H)
                bw, bh = round((u1 - u0) * W), round((v1 - v0) * H)
                tex_jobs.append(((bx, by, bw, bh), ch))

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
