# -*- coding: utf-8 -*-
"""v6 빌드: 인터미션(<operator( 태그) 대화 미보유 음절 + ADV 잔존 음절 3자 보충.
베이스 v5 → ACE3_KR_v6.iso. 모든 변경이 등길이 제자리(재패킹 없음).

배경(2026-07-14 사용자 제보: 인터미션 LIVE 대화 '조/않/경' ？, 통신 대화 '뗄/혜' ？):
- v4/v5 문자열 변환 필터는 <op(/<sp(/<on( 만 매칭 → "<operator(" 태그의 인터미션
  시나리오 문자열 2,808건(156개 엔트리)이 통째로 미변환. 이 장면 렌더 폰트는
  셸계 8783/8784인데 kr donor 42코드가 charset에 없어 르/않/와/조/너/타/버/경/놈
  등 1,072회가 ？. (공백 0x20은 이 폰트가 정상 렌더 → 공백은 건드리지 않는다)
- 8780/8782/8787(셸)과 8783/8784는 kr 글리프 박스·픽셀 분포가 완전 동일(실측)
  → 8780에서 글리프 비트맵을 그대로 복사하면 스타일 불일치가 없다.
- ADV(4614)+대형6 공통 풀을 확장 범위(0xE0xx)에서 3개 추가 발견(E0F3/E56A/E8A6,
  전부 16x18+) → 사용자 제보 음절 뗄·혜 + 잔존 최빈 깁 배정.
입력: ACE3_KR_v5.iso → 출력: ACE3_KR_v6.iso
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
SRC_ISO = W / "ACE3_KR_v5.iso"
OUT_ISO = Path(os.environ.get("ACE3_V6_OUT", str(W / "ACE3_KR_v6.iso")))
ORIG_ISO = W.parent / "Another Century's Episode 3 - The Final (Japan).iso"

from deswz_tables import build_file_index_4via32, deswizzle4via32, swizzle4via32

_spec = importlib.util.spec_from_file_location("m220", W / "220_patch_radio_space5f.py")
m220 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m220)
parse_inner, texture_dims, font_header = m220.parse_inner, m220.texture_dims, m220.font_header

_spec2 = importlib.util.spec_from_file_location("m222", W / "222_patch_caption_batang.py")
m222 = importlib.util.module_from_spec(_spec2); _spec2.loader.exec_module(m222)
render_fit = m222.render_fit
UNIFORM_SIZE = m222.UNIFORM_SIZE

LARGE = [4603, 4604, 4607, 4608, 4609, 4610]
SMALL = [4605, 4606]
ADV = 4614
SHELL_SRC = [8780, 8782, 8787]   # kr 글리프 비트맵 공급원
SHELL_DST = [8783, 8784]         # 인터미션 렌더 폰트(42코드 결손)
RADIO_TAGS = (b"<op(", b"<sp(", b"<on(")
OP = b"<operator("
# ADV 추가 풀(an_advpool2 실측: donors/태그·미션 문자열/RESERVED 제외, orig·v5
# 양쪽 7폰트 매핑 존재, 16x18+ 박스) → 사용자 제보 음절 우선 배정
ADV_EXTRA = {"뗄": 0xE0F3, "혜": 0xE56A, "깁": 0xE8A6}

toc = json.loads((W / "bnd_toc.json").read_text(encoding="utf-8"))
kr = {k: int(v) for k, v in json.loads((W / "kr_map_shell.json").read_text(encoding="utf-8")).items()}
donors = set(kr.values())
kr_inv = {v: k for k, v in kr.items()}
db = json.loads((W / "db.json").read_text(encoding="utf-8"))


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


def pixels(F):
    if "pix" not in F:
        idxmap = build_file_index_4via32(F["tw"], F["th"])
        F["pix"] = bytearray(deswizzle4via32(bytes(F["outer"][F["po"]:F["po"] + F["pl"]]),
                                             F["tw"], F["th"], idxmap))
        F["idxmap"] = idxmap
    return F["pix"]


def iter_units(b):
    i = 0
    n = len(b)
    while i < n:
        c = b[i]
        if c == 0x3C:
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


def eqlen_map(s: bytes, mapping: dict) -> bytes:
    """태그(<...>) 보존, 2B 코드만 mapping으로 치환하는 등길이 변환."""
    o = bytearray(s)
    for p, sz, code in iter_units(s):
        if sz == 2:
            m = mapping.get(code)
            if m:
                o[p] = m >> 8
                o[p + 1] = m & 0xFF
    return bytes(o)


def main():
    assert SRC_ISO.exists() and ORIG_ISO.exists()
    print(f"베이스 복사: {SRC_ISO.name} → {OUT_ISO.name}")
    shutil.copyfile(SRC_ISO, OUT_ISO)
    out = open(OUT_ISO, "r+b")
    orig_f = open(ORIG_ISO, "rb")

    def read_sec(sec):
        e = toc[sec["idx"]]
        out.seek(DATA_OFF + e["off"] + sec["base"])
        cur = bytearray(out.read(max(sec["csize"], 0x4000)))
        if sec["tbloff"] + sec["count"] * 4 > len(cur):
            return None, None
        return cur, list(struct.unpack_from(f"<{sec['count']}I", cur, sec["tbloff"]))

    def gs(cur, off):
        j = off
        while j < len(cur) and cur[j] != 0:
            j += 1
        return bytes(cur[off:j])

    # ---------- 폰트 로드 ----------
    Fsrc = {e: load_font(out, e) for e in SHELL_SRC}
    Fdst = {e: load_font(out, e) for e in SHELL_DST}
    Fmo = {e: load_font(orig_f, e) for e in [ADV] + LARGE + SMALL}
    Fmv = {e: load_font(out, e) for e in [ADV] + LARGE + SMALL}

    # ---------- 전역 사용 코드 + operator 미보유 census ----------
    used_global = Counter()
    op_codes = Counter()
    for sec in db:
        cur, tbl = read_sec(sec)
        if cur is None:
            continue
        for off in tbl:
            if off == 0 or off >= len(cur):
                continue
            s = gs(cur, off)
            is_op = OP in s
            for _p, sz, code in iter_units(s):
                if sz == 2:
                    used_global[code] += 1
                    if is_op:
                        op_codes[code] += 1

    missing_op = {c: n for c, n in op_codes.items()
                  if any(gi_of(Fdst[e], c) is None for e in SHELL_DST)}
    print(f"operator 미보유 코드 {len(missing_op)}종 / "
          f"{sum(missing_op.values())}회")

    # ---------- 셸 풀(8783/8784 공통 매핑·전역 미사용·대형 박스) ----------
    def usable_shell(c, wmin=16, hmin=18):
        if c in donors or used_global[c] or c in missing_op:
            return False
        if c in ADV_EXTRA.values():
            return False
        for F in Fdst.values():
            b = box_of(F, c)
            if b is None or b[2] - b[0] < wmin or b[3] - b[1] < hmin:
                return False
        return True

    shell_pool = [c for c in list(range(0x8140, 0x9F00)) + list(range(0xE040, 0xEB00))
                  if usable_shell(c)]
    print(f"셸 풀: {len(shell_pool)}개")

    # ---------- 미보유 42코드 → 풀 배정(소스 글리프 = 8780계 비트맵) ----------
    def ink_bbox(F, code):
        b = box_of(F, code)
        if b is None:
            return None, None
        pix = pixels(F)
        x0, y0, x1, y1 = b
        ix0, iy0, ix1, iy1 = x1, y1, x0, y0
        n = 0
        for y in range(y0, y1):
            base = y * F["tw"]
            for x in range(x0, x1):
                if pix[base + x] != 0:
                    n += 1
                    ix0 = min(ix0, x); iy0 = min(iy0, y)
                    ix1 = max(ix1, x + 1); iy1 = max(iy1, y + 1)
        if n == 0:
            return b, None
        return b, (ix0, iy0, ix1, iy1)

    op_map = {}      # 미보유코드 -> 풀코드
    blit_jobs = []   # (풀코드, (srcF, sbox, ibox)) — 비트맵 복사
    draw_jobs = []   # (풀코드, ch) — 셸 소스에도 없는 음절: render_fit 직접 드로잉
    skipped = []
    pool_iter = list(shell_pool)
    for code, n in sorted(missing_op.items(), key=lambda kv: -kv[1]):
        ch = kr_inv.get(code)
        if ch is None:
            skipped.append((code, ch, n))
            continue
        src = None
        for e in SHELL_SRC:
            sbox, ibox = ink_bbox(Fsrc[e], kr[ch])
            if ibox is not None:
                src = (Fsrc[e], sbox, ibox)
                break
        if src is not None:
            _F, sbox, ibox = src
            iw, ih = ibox[2] - ibox[0], ibox[3] - ibox[1]
            slot = None
            for c in pool_iter:
                if all((lambda b: b[2] - b[0] >= iw and b[3] - b[1] >= ih)(box_of(F, c))
                       for F in Fdst.values()):
                    slot = c
                    break
            if slot is None:
                skipped.append((code, ch, n))
                continue
            pool_iter.remove(slot)
            op_map[code] = slot
            blit_jobs.append((slot, src))
        else:
            # 셸 3종 어디에도 글리프 없음 → 풀 박스에 render_fit로 직접 드로잉
            if not pool_iter:
                skipped.append((code, ch, n))
                continue
            slot = pool_iter.pop(0)
            op_map[code] = slot
            draw_jobs.append((slot, ch))
    print(f"셸 재배치 {len(op_map)}슬롯(복사 {len(blit_jobs)}+드로잉 {len(draw_jobs)})"
          f" / 건너뜀 {len(skipped)}:",
          [(f"{c:04x}", ch, n) for c, ch, n in skipped] or "")

    # ---------- 8783/8784 텍스처에 비트맵 복사 + render_fit 드로잉 ----------
    def render_into(pix, tw, box, ch):
        x0, y0, x1, y1 = box
        bw, bh = x1 - x0, y1 - y0
        grid = None
        for size in range(UNIFORM_SIZE, 7, -1):
            grid = render_fit(ch, size, bw, bh, align="left")
            if grid is not None:
                break
        if grid is None:
            return False
        for yy in range(bh):
            row = grid[yy]
            base = (y0 + yy) * tw + x0
            for xx in range(bw):
                pix[base + xx] = row[xx]
        return True

    for e in SHELL_DST:
        F = Fdst[e]
        pix = pixels(F)
        done = 0
        for slot, ch in draw_jobs:
            b = box_of(F, slot)
            if render_into(pix, F["tw"], b, ch):
                done += 1
        for slot, (Fs, sbox, ibox) in blit_jobs:
            db_ = box_of(F, slot)
            dx0, dy0, dx1, dy1 = db_
            # 클리어
            for y in range(dy0, dy1):
                base = y * F["tw"]
                for x in range(dx0, dx1):
                    pix[base + x] = 0
            # 잉크 상대 위치 유지(+박스 초과 시 안쪽으로 클램프)
            ox = min(ibox[0] - sbox[0], (dx1 - dx0) - (ibox[2] - ibox[0]))
            oy = min(ibox[1] - sbox[1], (dy1 - dy0) - (ibox[3] - ibox[1]))
            ox, oy = max(ox, 0), max(oy, 0)
            spix = pixels(Fs)
            for y in range(ibox[1], ibox[3]):
                sb = y * Fs["tw"]
                dbase = (dy0 + oy + (y - ibox[1])) * F["tw"] + dx0 + ox
                for x in range(ibox[0], ibox[2]):
                    v = spix[sb + x]
                    if v:
                        pix[dbase + (x - ibox[0])] = v
            done += 1
        F["outer"][F["po"]:F["po"] + F["pl"]] = swizzle4via32(bytes(pix), F["tw"], F["th"], F["idxmap"])
        out.seek(DATA_OFF + F["e"]["off"])
        out.write(F["outer"])
        print(f"폰트 idx{e}: 글리프 복사 {done}")

    # ---------- operator 문자열 등길이 재매핑 ----------
    n_sec = n_str = 0
    for sec in db:
        cur, tbl = read_sec(sec)
        if cur is None:
            continue
        changed = False
        for off in sorted({o for o in tbl if 0 < o < len(cur)}):
            s = gs(cur, off)
            if OP not in s:
                continue
            ns = eqlen_map(s, op_map)
            if ns != s:
                assert len(ns) == len(s)
                cur[off:off + len(ns)] = ns
                changed = True
                n_str += 1
        if changed:
            e = toc[sec["idx"]]
            out.seek(DATA_OFF + e["off"] + sec["base"])
            out.write(cur[:max(sec["tbloff"] + sec["count"] * 4, sec["csize"])])
            n_sec += 1
    print(f"operator 문자열 재작성: {n_sec}섹션 {n_str}건")

    # ---------- ADV 잔존 3음절: 태그·용어 문자열 등길이 재매핑 ----------
    remap3 = {}
    for ch, dst in ADV_EXTRA.items():
        okc = kr.get(ch)
        ok = okc is not None and all(
            gi_of(Fmo[e], dst) is not None and gi_of(Fmv[e], dst) is not None
            for e in [ADV] + LARGE)
        if ok and used_global[dst] == 0 and dst not in op_map.values():
            remap3[okc] = dst
        else:
            print(f"  ADV 추가 {ch} 생략(코드 {dst:#06x} 부적합)")
    GLOSS_KEY = set()
    for idx in LARGE:
        for sec in db:
            if sec["idx"] == idx and sec["count"] in (91, 25):
                GLOSS_KEY.add((sec["idx"], sec["base"]))
    n_sec3 = n_str3 = 0
    if remap3:
        for sec in db:
            cur, tbl = read_sec(sec)
            if cur is None:
                continue
            is_gloss = (sec["idx"], sec["base"]) in GLOSS_KEY
            changed = False
            for off in sorted({o for o in tbl if 0 < o < len(cur)}):
                s = gs(cur, off)
                if not (is_gloss or any(t in s for t in RADIO_TAGS)):
                    continue
                ns = eqlen_map(s, remap3)
                if ns != s:
                    assert len(ns) == len(s)
                    cur[off:off + len(ns)] = ns
                    changed = True
                    n_str3 += 1
            if changed:
                e = toc[sec["idx"]]
                out.seek(DATA_OFF + e["off"] + sec["base"])
                out.write(cur[:max(sec["tbloff"] + sec["count"] * 4, sec["csize"])])
                n_sec3 += 1
    print(f"ADV 추가음절 재작성: {n_sec3}섹션 {n_str3}건 "
          f"({''.join(kr_inv[c] for c in remap3)})")

    # ---------- ADV/대형/소형 텍스처에 3음절 드로잉 ----------
    def blit_grid(pix, tw, box, grid, body):
        x0, y0, x1, y1 = box
        for yy in range(y1 - y0):
            row = grid[yy]
            base = (y0 + yy) * tw + x0
            for xx in range(x1 - x0):
                v = row[xx]
                pix[base + xx] = body if v == 8 else v

    inv3 = {dst: ch for ch, dst in ADV_EXTRA.items() if kr.get(ch) in remap3}
    for eidx in [ADV] + LARGE + SMALL:
        Fo = Fmo[eidx]
        # ④의 문자열 제자리 쓰기(같은 엔트리 내 섹션)를 덮지 않도록 재로드
        F = load_font(out, eidx)
        pix = pixels(F)
        done = 0
        boxes = []
        for dst, ch in inv3.items():
            b = box_of(Fo, dst)
            if b is None:
                continue
            bw, bh = b[2] - b[0], b[3] - b[1]
            grid = None
            for size in range(UNIFORM_SIZE, 7, -1):
                grid = render_fit(ch, size, bw, bh, align="left")
                if grid is not None:
                    break
            if grid is None:
                continue
            blit_grid(pix, F["tw"], b, grid, 8)
            boxes.append(b)
            done += 1
        if eidx == ADV:
            n8 = 0
            for x0, y0, x1, y1 in boxes:
                for y in range(y0, y1):
                    base = y * F["tw"]
                    for x in range(x0, x1):
                        if pix[base + x] == 8:
                            pix[base + x] = 5
                            n8 += 1
            print(f"폰트 idx{eidx}: 추가음절 {done}, 박스 내 8→5 {n8}px")
        else:
            print(f"폰트 idx{eidx}: 추가음절 {done}")
        if done:
            F["outer"][F["po"]:F["po"] + F["pl"]] = swizzle4via32(bytes(pix), F["tw"], F["th"], F["idxmap"])
            out.seek(DATA_OFF + F["e"]["off"])
            out.write(F["outer"])

    # ---------- 검증 ----------
    Fck = {e: load_font(out, e) for e in SHELL_DST + [ADV]}
    left_op = Counter()
    left_tag = Counter()
    for sec in db:
        cur, tbl = read_sec(sec)
        if cur is None:
            continue
        for off in {o for o in tbl if 0 < o < len(cur)}:
            s = gs(cur, off)
            is_op = OP in s
            is_tag = any(t in s for t in RADIO_TAGS)
            for _p, sz, code in iter_units(s):
                if sz != 2:
                    continue
                if is_op and any(gi_of(Fck[e], code) is None for e in SHELL_DST):
                    left_op[code] += 1
                if is_tag and gi_of(Fck[ADV], code) is None:
                    left_tag[code] += 1
    print(f"검증: operator 잔존 미보유 {sum(left_op.values())}회 {len(left_op)}종",
          [(f"{c:04x}", kr_inv.get(c, "·"), n) for c, n in left_op.most_common(6)])
    print(f"검증: 태그(4614) 잔존 미보유 {sum(left_tag.values())}회 {len(left_tag)}종")
    out.close()
    print(f"완료: {OUT_ISO}")


if __name__ == "__main__":
    main()
