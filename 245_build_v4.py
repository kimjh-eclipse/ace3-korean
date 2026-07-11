# -*- coding: utf-8 -*-
"""v4 빌드: ADV(4614, 전투 후 대화)용 baked-safe 공백/부호/음절 수정. 베이스 v2.

배경(2026-07-12 확정):
- ADV 렌더러는 4614의 파일 range 테이블 재코딩을 읽지 않음(원본 레이아웃 baked).
  v3의 테이블 재코딩(0x5F 공백+29음절)은 무효 → 폐기(베이스 v2라 테이블은 자동 원복).
- 대신 '문자열 바이트'를 원본 charset에 이미 있는 코드로 고쳐 쓴다(테이블 무변경):
  ① 공백 0x5F → 'R'(0x52, 4614∩대형6 공통, 실사용 1회) 글리프 blank
  ② '!' 0x21 → 'E'(0x45), '.' 0x2E → 'S'(0x53) 글리프에 !/. 드로잉
  ③ ','→、(0x8141) '?'→？(0x8148) '~'→〜(0x8160) '''→’(0x8166) 전각 승격(+1B, 힙 재패킹)
  ④ 라틴 대소문자 → 전각(Ａ0x8260+/ａ0x8281+) — 대피 겸 ADV 미보유 라틴 해결
  ⑤ 4614 미보유 음절 → 미사용 2바이트 코드 27개에 재배치(2B→2B), 글리프 드로잉
- 대상: 라디오 태그(<op(/<sp(/<on()가 '문자열 자체'에 있는 것만(섹션 단위 아님).
- 텍스처: 4614 전역 8→5(본체 투명 수정, v3 검증됨) + 신규 글리프, 8781 박스 8→6.
입력: ACE3_KR_v2.iso → 출력: ACE3_KR_v4.iso
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = Path(__file__).resolve().parent
DATA_OFF = 2117 * 2048
SRC_ISO = W / "ACE3_KR_v2.iso"
OUT_ISO = Path(os.environ.get("ACE3_V4_OUT", str(W / "ACE3_KR_v4.iso")))
ORIG_ISO = W.parent / "Another Century's Episode 3 - The Final (Japan).iso"

from deswz_tables import build_file_index_4via32, deswizzle4via32, swizzle4via32

_spec = importlib.util.spec_from_file_location("m220", W / "220_patch_radio_space5f.py")
m220 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m220)
parse_inner, texture_dims, font_header = m220.parse_inner, m220.texture_dims, m220.font_header

_spec2 = importlib.util.spec_from_file_location("m222", W / "222_patch_caption_batang.py")
m222 = importlib.util.module_from_spec(_spec2); _spec2.loader.exec_module(m222)
render_fit = m222.render_fit          # 8=본체/1=외곽/0 그리드
UNIFORM_SIZE = m222.UNIFORM_SIZE

LARGE = [4603, 4604, 4607, 4608, 4609, 4610]
SMALL = [4605, 4606]
ADV = 4614
RADIO_TAGS = (b"<op(", b"<sp(", b"<on(")

# 1바이트 캐리어(4614∩대형6 공통 실측). 0x20(날 공백)도 blank R로.
CARRIER = {0x5F: (0x52, None),   # 공백 -> R box blank
           0x20: (0x52, None),
           0x2E: (0x53, "."),    # 마침표 -> S
           0x21: (0x45, "!")}    # 느낌표 -> E
# 전각 승격(1B->2B). 쉼표는 폰트 보유에 따라 ，(8143) 우선, 없으면 、(8141).
FW_PUNCT = {0x2C: 0x8141, 0x3F: 0x8148, 0x7E: 0x8160, 0x27: 0x8166}
# 라틴 -> 전각
def fw_latin(c):
    if 0x41 <= c <= 0x5A:
        return 0x8260 + (c - 0x41)
    if 0x61 <= c <= 0x7A:
        return 0x8281 + (c - 0x61)
    return None

toc = json.loads((W / "bnd_toc.json").read_text(encoding="utf-8"))
kr = {k: int(v) for k, v in json.loads((W / "kr_map_shell.json").read_text(encoding="utf-8")).items()}
donors = set(kr.values())
kr_inv = {v: k for k, v in kr.items()}


def load_font(iso_f, eidx):
    e = toc[eidx]
    iso_f.seek(DATA_OFF + e["off"])
    outer = bytearray(iso_f.read(e["size"]))
    inner = parse_inner(outer)
    fo, _ = inner[2500]
    nr, ng, mo = font_header(outer, fo)
    rs = [struct.unpack_from("<III", outer, fo + 0x20 + i * 12) for i in range(nr)]
    if 2000 in inner:
        tex_off, tex_size = inner[2000]
        po, pl = tex_off + 0x20, tex_size - 0x60
        tw, th = texture_dims(pl)
    else:
        po, pl, tw, th = 0x60, 0x40000, 1024, 512
    return {"eidx": eidx, "e": e, "outer": outer, "fo": fo, "rs": rs, "ng": ng,
            "mo": mo, "po": po, "pl": pl, "tw": tw, "th": th}


def gi_of(F, code):
    for a, z, gi in F["rs"]:
        if 0 <= a <= z <= 0xFFFF and gi < F["ng"] and a <= code <= z:
            return gi + (code - a)
    return None


def box_of(F, code):
    gi = gi_of(F, code)
    if gi is None:
        return None
    u0, v0, u1, v1 = struct.unpack_from("<4f", F["outer"], F["fo"] + F["mo"] + gi * 24)
    x0, y0 = round(u0 * F["tw"]), round(v0 * F["th"])
    return x0, y0, x0 + round((u1 - u0) * F["tw"]), y0 + round((v1 - v0) * F["th"])


def iter_units(b):
    """SJIS 구조 워커. <...> 태그는 (pos,end) 스킵. yield (pos, size, code)."""
    i = 0
    n = len(b)
    while i < n:
        c = b[i]
        if c == 0x3C:  # '<'
            j = b.find(b">", i)
            if 0 < j < i + 64:
                i = j + 1
                continue
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
            if i + 1 < n:
                yield i, 2, (c << 8) | b[i + 1]
                i += 2
            else:
                yield i, 1, c
                i += 1
        else:
            yield i, 1, c
            i += 1


def main():
    print("복사:", OUT_ISO)
    shutil.copyfile(SRC_ISO, OUT_ISO)
    out = OUT_ISO.open("r+b")
    orig_f = ORIG_ISO.open("rb")

    # ---------- 폰트 로드: 원본(baked 기준) + v2(라이브 테이블 기준) 둘 다 ----------
    fonts_o = {e: load_font(orig_f, e) for e in [ADV] + LARGE + SMALL}
    fonts_v2 = {e: load_font(out, e) for e in [ADV] + LARGE + SMALL}

    def in_both(code, eidxs):
        """원본(baked 렌더러)과 v2 라이브 테이블 모두에서 조회 가능해야 안전."""
        return all(gi_of(fonts_o[e], code) is not None and
                   gi_of(fonts_v2[e], code) is not None for e in eidxs)

    for src, (car, _g) in CARRIER.items():
        assert in_both(car, [ADV] + LARGE), f"캐리어 {car:#x} 테이블 누락"
    # 쉼표 전각: ，(8143)가 4614+대형6에 있으면 그걸로
    if in_both(0x8143, [ADV] + LARGE):
        FW_PUNCT[0x2C] = 0x8143
    for src, fw in list(FW_PUNCT.items()):
        if not in_both(fw, [ADV] + LARGE):
            print(f"  전각 {fw:#06x} 미보유 → {src:#x} 승격 생략")
            del FW_PUNCT[src]
    fw_ok = set()
    for c in list(range(0x41, 0x5B)) + list(range(0x61, 0x7B)):
        fw = fw_latin(c)
        if fw and in_both(fw, [ADV] + LARGE):
            fw_ok.add(c)

    # ---------- 사용 코드 집계(태그문자열/미션기타) & 미보유 음절 빈도 ----------
    db = json.loads((W / "db.json").read_text(encoding="utf-8"))
    used_tagged = Counter(); used_mission = Counter()
    tag_freq_missing = Counter()
    adv_codes = set()
    for a, z, gi in fonts_o[ADV]["rs"]:
        if 0 <= a <= z <= 0xFFFF and gi < fonts_o[ADV]["ng"]:
            adv_codes.update(range(a, z + 1))
    MISSION_EIDX = set([ADV] + LARGE + SMALL)

    def read_sec(sec):
        e = toc[sec["idx"]]
        out.seek(DATA_OFF + e["off"] + sec["base"])
        cur = bytearray(out.read(max(sec["csize"], 0x4000)))
        count, tbloff = sec["count"], sec["tbloff"]
        if tbloff + count * 4 > len(cur):
            return None, None
        tbl = list(struct.unpack_from(f"<{count}I", cur, tbloff))
        return cur, tbl

    def gs(cur, off):
        j = off
        while j < len(cur) and cur[j] != 0:
            j += 1
        return bytes(cur[off:j])

    for sec in db:
        cur, tbl = read_sec(sec)
        if cur is None:
            continue
        in_mission = sec["idx"] in MISSION_EIDX
        for off in tbl:
            if off == 0 or off >= len(cur):
                continue
            s = gs(cur, off)
            tagged = any(t in s for t in RADIO_TAGS)
            tgt = used_tagged if tagged else used_mission if in_mission else None
            for _p, _sz, code in iter_units(s):
                if tgt is not None:
                    tgt[code] += 1
                if tagged and code in donors and code not in adv_codes:
                    tag_freq_missing[kr_inv[code]] += 1

    # ---------- 음절 재배치 풀: 미사용 2바이트, 4614∩대형6 전부, 박스 16x18+ ----------
    pool = []
    for c in range(0x8140, 0x9873):
        if c in donors or used_tagged[c] or used_mission[c]:
            continue
        if not in_both(c, [ADV] + LARGE):
            continue
        ok = True
        for e in [ADV] + LARGE:
            b = box_of(fonts_o[e], c)
            if b is None or b[2] - b[0] < 16 or b[3] - b[1] < 18:
                ok = False; break
        if not ok:
            continue
        in_small = all(box_of(fonts_o[e], c) is not None and
                       box_of(fonts_o[e], c)[2] - box_of(fonts_o[e], c)[0] >= 14
                       for e in SMALL)
        pool.append((c, in_small))
    order = [ch for ch, _n in tag_freq_missing.most_common()]
    n_slots = len(pool)
    chosen = order[:n_slots]
    # 소형 보유 donor 음절에 소형가능 풀 우선 배정
    small_codes = set()
    for e in SMALL:
        for a, z, gi in fonts_o[e]["rs"]:
            if 0 <= a <= z <= 0xFFFF and gi < fonts_o[e]["ng"]:
                small_codes.update(range(a, z + 1))
    pool_small = [c for c, s in pool if s]
    pool_other = [c for c, s in pool if not s]
    remap = {}
    rest = []
    for ch in chosen:
        if kr[ch] in small_codes and pool_small:
            remap[kr[ch]] = (pool_small.pop(0), ch)
        else:
            rest.append(ch)
    leftover = pool_small + pool_other
    for ch in rest:
        if leftover:
            remap[kr[ch]] = (leftover.pop(0), ch)
    cover = sum(tag_freq_missing[ch] for _d, (_c, ch) in remap.items())
    total = sum(tag_freq_missing.values())
    print(f"음절 재배치 {len(remap)}슬롯: 출현 {cover}/{total} 커버")
    print("  대상:", "".join(ch for _d, (_c, ch) in remap.items()))

    # ---------- 문자열 변환 ----------
    BAREL_BAD = None
    if "바렐" in kr and "오" in kr:
        BAREL_BAD = (bytes((kr["바"] >> 8, kr["바"] & 0xFF, kr["렐"] >> 8, kr["렐"] & 0xFF))
                     + b"\x81\x48"
                     + bytes((kr["오"] >> 8, kr["오"] & 0xFF)))
        BAREL_FIX = (BAREL_BAD[:4] + b"\x5f" + BAREL_BAD[6:])  # 0x5F는 뒤 워크에서 캐리어로 변환됨

    def transform(s: bytes):
        """태그 문자열 변환. (새 바이트, 성장량)"""
        if BAREL_BAD and BAREL_BAD in s:
            s = s.replace(BAREL_BAD, BAREL_FIX)
        o = bytearray()
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c == 0x3C:
                j = s.find(b">", i)
                if 0 < j < i + 64:
                    o += s[i:j + 1]; i = j + 1; continue
            if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
                if i + 1 < n:
                    code = (c << 8) | s[i + 1]
                    m = remap.get(code)
                    if m:
                        o += bytes((m[0] >> 8, m[0] & 0xFF))
                    else:
                        o += s[i:i + 2]
                    i += 2
                else:
                    o.append(c); i += 1
                continue
            if c in CARRIER:
                o.append(CARRIER[c][0]); i += 1; continue
            if c in FW_PUNCT:
                fw = FW_PUNCT[c]
                o += bytes((fw >> 8, fw & 0xFF)); i += 1; continue
            if c in fw_ok:
                fw = fw_latin(c)
                o += bytes((fw >> 8, fw & 0xFF)); i += 1; continue
            o.append(c); i += 1
        return bytes(o)

    n_sec = n_str = n_grow_fb = 0
    for sec in db:
        cur, tbl = read_sec(sec)
        if cur is None:
            continue
        count, tbloff = sec["count"], sec["tbloff"]
        offs = [o for o in tbl if 0 < o < len(cur)]
        if not offs:
            continue
        strs = {}
        any_tagged = False
        for slot, off in enumerate(tbl):
            if off == 0 or off >= len(cur):
                continue
            s = gs(cur, off)
            tagged = any(t in s for t in RADIO_TAGS)
            ns = transform(s) if tagged else s
            if ns != s:
                any_tagged = True
            strs[slot] = (s, ns)
        if not any_tagged:
            continue
        # 힙 재패킹(중복 공유). 원본 힙 범위 내.
        h0 = min(offs)
        oe = max(off + len(gs(cur, off)) + 1 for off in offs)
        limit = max(sec["csize"], oe)
        # 성장 폴백: 안 들어가면 성장(길이증가) 문자열부터 원상 유지
        cand = dict(strs)
        while True:
            heap = bytearray(); om = {}; nt = {}
            for slot, (s, ns) in cand.items():
                d = ns
                if d in om:
                    nt[slot] = om[d]; continue
                om[d] = h0 + len(heap); nt[slot] = om[d]
                heap += d + b"\x00"
            if h0 + len(heap) <= limit:
                break
            growers = sorted(((slot, len(ns) - len(s)) for slot, (s, ns) in cand.items()
                              if len(ns) > len(s)), key=lambda x: -x[1])
            if not growers:
                # 등길이 변환만 남았는데도 안 들어감(원본 힙의 접미사 공유 소실)
                # → 섹션 통째 원상 유지
                print(f"  [보류] idx{sec['idx']}/{sec['base']:#x}: 재패킹 불가, 원상 유지")
                cand = None
                break
            slot = growers[0][0]
            s, _ns = cand[slot]
            # 성장분(전각 승격)만 포기: 캐리어/음절(등길이)은 유지하는 재변환
            def transform_nogrow(sb):
                o2 = bytearray(); i2 = 0; n2 = len(sb)
                while i2 < n2:
                    c2 = sb[i2]
                    if c2 == 0x3C:
                        j2 = sb.find(b">", i2)
                        if 0 < j2 < i2 + 64:
                            o2 += sb[i2:j2 + 1]; i2 = j2 + 1; continue
                    if 0x81 <= c2 <= 0x9F or 0xE0 <= c2 <= 0xFC:
                        if i2 + 1 < n2:
                            code2 = (c2 << 8) | sb[i2 + 1]
                            m2 = remap.get(code2)
                            o2 += bytes((m2[0] >> 8, m2[0] & 0xFF)) if m2 else sb[i2:i2 + 2]
                            i2 += 2
                        else:
                            o2.append(c2); i2 += 1
                        continue
                    if c2 in CARRIER:
                        o2.append(CARRIER[c2][0]); i2 += 1; continue
                    o2.append(c2); i2 += 1
                return bytes(o2)
            cand[slot] = (s, transform_nogrow(s))
            n_grow_fb += 1
        if cand is None:
            continue
        for slot, o in nt.items():
            struct.pack_into("<I", cur, tbloff + slot * 4, o)
        cur[h0:limit] = heap + bytes(limit - h0 - len(heap))
        e = toc[sec["idx"]]
        out.seek(DATA_OFF + e["off"] + sec["base"])
        out.write(cur[:max(tbloff + count * 4, limit)])
        n_sec += 1
        n_str += sum(1 for s, ns in cand.values() if ns != s)
    print(f"문자열 재작성: {n_sec}섹션 {n_str}건, 성장 폴백 {n_grow_fb}건")

    # ---------- 글리프 드로잉 ----------
    def blit(pix, tw, box, grid, body):
        x0, y0, x1, y1 = box
        for yy in range(y1 - y0):
            row = grid[yy]
            base = (y0 + yy) * tw + x0
            for xx in range(x1 - x0):
                v = row[xx]
                pix[base + xx] = body if v == 8 else v

    def draw_or_blank(pix, tw, box, ch, body):
        x0, y0, x1, y1 = box
        if ch is None:
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    pix[yy * tw + xx] = 0
            return True
        bw, bh = x1 - x0, y1 - y0
        grid = None
        for size in range(UNIFORM_SIZE, 7, -1):
            grid = render_fit(ch, size, bw, bh, align="center" if len(ch) == 1 and not ("가" <= ch <= "힣") else "left")
            if grid is not None:
                break
        if grid is None:
            return False
        blit(pix, tw, box, grid, body)
        return True

    jobs = [(carrier, glyph) for _src, (carrier, glyph) in CARRIER.items()]
    jobs += [(code, ch) for _d, (code, ch) in remap.items()]

    for eidx in [ADV] + LARGE + SMALL:
        Fo = fonts_o[eidx]
        e = toc[eidx]
        out.seek(DATA_OFF + e["off"])
        outer = bytearray(out.read(e["size"]))
        inner = parse_inner(outer)
        if 2000 in inner:
            tex_off, tex_size = inner[2000]
            po, pl = tex_off + 0x20, tex_size - 0x60
            tw, th = texture_dims(pl)
        else:
            po, pl, tw, th = 0x60, 0x40000, 1024, 512
        idx = build_file_index_4via32(tw, th)
        pix = bytearray(deswizzle4via32(outer[po:po + pl], tw, th, idx))
        body = 8  # 대형/소형 캡션 본체
        done = 0
        for code, ch in jobs:
            b = box_of(Fo, code)
            if b is None:
                continue
            if draw_or_blank(pix, tw, b, ch, body):
                done += 1
        if eidx == ADV:
            n8 = 0
            for i in range(len(pix)):
                if pix[i] == 8:
                    pix[i] = 5
                    n8 += 1
            print(f"폰트 idx{eidx}: 글리프 {done}, 전역 8→5 {n8}px")
        else:
            print(f"폰트 idx{eidx}: 글리프 {done}")
        outer[po:po + pl] = swizzle4via32(pix, tw, th, idx)
        out.seek(DATA_OFF + e["off"])
        out.write(outer)

    # ---------- 8781 본체 8→6 (v3와 동일) ----------
    F81o = load_font(orig_f, 8781)
    codes81o = set()
    for a, z, gi in F81o["rs"]:
        if 0 <= a <= z <= 0xFFFF and gi < F81o["ng"]:
            codes81o.update(range(a, z + 1))
    e = toc[8781]
    out.seek(DATA_OFF + e["off"])
    outer = bytearray(out.read(e["size"]))
    inner = parse_inner(outer)
    fo, _ = inner[2500]
    nr, ng, mo = font_header(outer, fo)
    rs = [struct.unpack_from("<III", outer, fo + 0x20 + i * 12) for i in range(nr)]
    F81 = {"eidx": 8781, "outer": outer, "fo": fo, "rs": rs, "ng": ng, "mo": mo,
           "tw": 1024, "th": 512}
    tex_off, tex_size = inner[2000]
    po, pl = tex_off + 0x20, tex_size - 0x60
    idx = build_file_index_4via32(1024, 512)
    pix = bytearray(deswizzle4via32(outer[po:po + pl], 1024, 512, idx))
    targets = set()
    code_gi = {}
    for a, z, gi in rs:
        if not (0 <= a <= z <= 0xFFFF and gi < ng):
            continue
        for k in range(z - a + 1):
            code_gi[a + k] = gi + k
    for code, gi in code_gi.items():
        if code in donors or code not in codes81o:
            targets.add(gi)
    n8 = 0
    for gi in targets:
        u0, v0, u1, v1 = struct.unpack_from("<4f", outer, fo + mo + gi * 24)
        x0, y0 = round(u0 * 1024), round(v0 * 512)
        x1, y1 = x0 + round((u1 - u0) * 1024), y0 + round((v1 - v0) * 512)
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        for yy in range(y0, y1):
            base = yy * 1024
            for xx in range(x0, x1):
                if pix[base + xx] == 8:
                    pix[base + xx] = 6
                    n8 += 1
    print(f"idx8781: 본체 8→6 {n8}px")
    outer[po:po + pl] = swizzle4via32(pix, 1024, 512, idx)
    out.seek(DATA_OFF + e["off"])
    out.write(outer)

    out.flush(); os.fsync(out.fileno()); out.close()
    orig_f.close()
    print("완료:", OUT_ISO)


if __name__ == "__main__":
    main()
