# -*- coding: utf-8 -*-
"""v5 빌드: v4 전체 로직 + ①'장'(0x88A3→0x8341) ②용어/작품명 섹션 공백·음절
③4607~4610 포즈 행 수정 이식 ④'통신' 라벨 ⑤―『』② 치환 + ※＆·잔여음절 완화 풀.
베이스 v2 → ACE3_KR_v5.iso.

배경(2026-07-12 사용자 제보: 용어 팝업 공백 ？, '함장님'의 장 ？):
- v2 빌드 문자열은 '장'을 220 시절 특수코드 0x88A3으로 emit(태그 문자열 2,464건).
  0x88A3은 대형 캡션 charset에는 있어 자막은 정상이나 4614(ADV baked)에 없어 ？.
  현행 kr_map_shell['장']=0x8341(ア)은 4614·대형6·소형2 전부 존재하고 v2 텍스처의
  그 박스에 이미 '장' 글리프가 그려져 있음(픽셀 실측) → 문자열 재매핑만으로 해결.
- 용어(WORD) 설명·작품명 섹션(대형 파일 4종 내)은 라디오 태그가 없어 v4 재작성에서
  제외됐고 공백이 날 0x20(파일당 1,851+20개) → 팝업(4614/대형 baked)에서 ？.
  0x20→R(blank) 등길이 치환 + 음절 재배치로 해결(재패킹 불필요).
- 4607~4610 포즈 섹션은 v2(235)의 START 행 수정이 누락돼 slot19가 여전히
  '게임으로 돌아가기'(8d82+82c3 행 유발 패턴) → 235 루틴 이식.
- 포즈/배너 섹션 slot '통신'(8acf 8b4f)은 신 donor가 4614에 없어 ADV 라벨이 '통？'
  → 그 문자열만 신 pool 코드로 등길이 치환(다른 포즈 문자열 불변).
입력: ACE3_KR_v2.iso → 출력: ACE3_KR_v5.iso
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
OUT_ISO = Path(os.environ.get("ACE3_V5_OUT", str(W / "ACE3_KR_v5.iso")))
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
RADIO_TAGS = (b"<op(", b"<sp(", b"<on(")
JANG_OLD, JANG_NEW = 0x88A3, 0x8341  # 220 시절 장 특수코드 → 현행 donor(글리프 실존)

# 1바이트 캐리어(v4와 동일)
CARRIER = {0x5F: (0x52, None), 0x20: (0x52, None),
           0x2E: (0x53, "."), 0x21: (0x45, "!")}
# 전각 승격(1B->2B, 태그 문자열만 — 성장하므로 용어 섹션엔 미적용)
FW_PUNCT = {0x2C: 0x8141, 0x3F: 0x8148, 0x7E: 0x8160, 0x27: 0x8166}
# 2B->2B 부호 치환(등길이): ―→ー 『』→「」 ②→２
PUNCT2 = {0x815C: 0x815B, 0x8177: 0x8175, 0x8178: 0x8176, 0x8741: 0x8251}
# 완화 풀에 글리프를 새로 그리는 기호
SYM_GLYPH = {0x81A6: "※", 0x8195: "＆"}

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


def main():
    print("복사:", OUT_ISO)
    shutil.copyfile(SRC_ISO, OUT_ISO)
    out = OUT_ISO.open("r+b")
    orig_f = ORIG_ISO.open("rb")
    db = json.loads((W / "db.json").read_text(encoding="utf-8"))

    def find_sec(idx, base):
        return next(d for d in db if d["idx"] == idx and d["base"] == base)

    # ---------- 0) 4607~4610 포즈 섹션: 235(v2) 수정 이식 ----------
    # slot19 '게임으로 돌아가기'(8d82 82c3 행 패턴) → '리줌', 번역문 날 0x20 → 0x8140
    NEW19 = bytes.fromhex("8cc09550")  # 리줌 (v2 검증 표기)
    PAUSE_LATE = [(4607, 0x7d100), (4608, 0x740a0), (4609, 0x74580), (4610, 0x7dd60)]
    PAUSE_DONE = [(4603, 0x728c0), (4604, 0x72da0), (4605, 0x4ce60), (4606, 0x4d6a0)]
    for idx, base in PAUSE_LATE:
        sec = find_sec(idx, base)
        e = toc[idx]
        csize, count, tbloff = sec["csize"], sec["count"], sec["tbloff"]
        lo = DATA_OFF + e["off"] + base
        out.seek(lo)
        cur = bytearray(out.read(max(csize, 0x4000)))
        tbl = list(struct.unpack_from(f"<{count}I", cur, tbloff))

        def gsl(off):
            i = off
            while cur[i] != 0:
                i += 1
            return bytes(cur[off:i])

        def fix_space(b):
            o = bytearray(); i = 0
            while i < len(b):
                c = b[i]
                if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
                    o += b[i:i + 2]; i += 2
                elif c == 0x20:
                    o += b"\x81\x40"; i += 1
                else:
                    o.append(c); i += 1
            return bytes(o)

        orig = {s["slot"]: bytes.fromhex(s["hex"]) for s in sec["strs"]}
        h0 = min(s["off"] for s in sec["strs"])
        oe = max(s["off"] + len(bytes.fromhex(s["hex"])) + 1 for s in sec["strs"])
        limit = max(csize, oe)
        heap = bytearray(); om = {}; nt = {}
        nfix = 0
        for s in sec["strs"]:
            slot = s["slot"]
            if slot == 19:
                data = NEW19
            else:
                data = gsl(tbl[slot])
                if data != orig[slot] and b"\x20" in data:
                    d2 = fix_space(data)
                    if d2 != data:
                        nfix += 1
                    data = d2
            if data in om:
                nt[slot] = om[data]; continue
            o = h0 + len(heap)
            assert o + len(data) + 1 <= limit, f"idx{idx} 포즈 오버플로 slot{slot}"
            om[data] = o; nt[slot] = o
            heap += data + b"\x00"
        for slot, o in nt.items():
            struct.pack_into("<I", cur, tbloff + slot * 4, o)
        cur[h0:limit] = heap + bytes(limit - h0 - len(heap))
        out.seek(lo)
        out.write(cur[:limit])
        print(f"포즈 이식 idx{idx}: slot19=리줌, 공백치환 {nfix}건, 힙 {len(heap)}/{limit - h0}B")

    # ---------- 폰트 로드(원본 baked + v2 라이브 둘 다) ----------
    fonts_o = {e: load_font(orig_f, e) for e in [ADV] + LARGE + SMALL}
    fonts_v2 = {e: load_font(out, e) for e in [ADV] + LARGE + SMALL}

    def in_both(code, eidxs):
        return all(gi_of(fonts_o[e], code) is not None and
                   gi_of(fonts_v2[e], code) is not None for e in eidxs)

    for src, (car, _g) in CARRIER.items():
        assert in_both(car, [ADV] + LARGE), f"캐리어 {car:#x} 테이블 누락"
    assert in_both(JANG_NEW, [ADV] + LARGE + SMALL), "0x8341 누락"
    if in_both(0x8143, [ADV] + LARGE):
        FW_PUNCT[0x2C] = 0x8143
    for src, fw in list(FW_PUNCT.items()):
        if not in_both(fw, [ADV] + LARGE):
            print(f"  전각 {fw:#06x} 미보유 → {src:#x} 승격 생략")
            del FW_PUNCT[src]
    for src, dst in list(PUNCT2.items()):
        if not in_both(dst, [ADV] + LARGE):
            print(f"  치환 {dst:#06x} 미보유 → {src:#06x} 생략")
            del PUNCT2[src]
    fw_ok = set()
    for c in list(range(0x41, 0x5B)) + list(range(0x61, 0x7B)):
        fw = fw_latin(c)
        if fw and in_both(fw, [ADV] + LARGE):
            fw_ok.add(c)

    # ---------- 재작성 대상 섹션 정의 ----------
    # 용어 설명(count=91)·작품명(count=25) — 대형 파일 4종에만 존재
    GLOSS = []
    for idx in LARGE:
        for sec in db:
            if sec["idx"] == idx and sec["count"] in (91, 25):
                GLOSS.append(sec)
    print(f"용어/작품명 섹션 {len(GLOSS)}개:",
          [(s["idx"], hex(s["base"]), s["count"]) for s in GLOSS])

    MISSION_EIDX = set([ADV] + LARGE + SMALL)
    GLOSS_KEY = {(s["idx"], s["base"]) for s in GLOSS}

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

    # ---------- 사용 코드 집계 + 미보유 음절 빈도(태그 / 용어 별도) ----------
    used_tagged = Counter(); used_mission = Counter()
    freq_tag = Counter(); freq_gloss = Counter()
    adv_codes = set()
    for a, z, gi in fonts_o[ADV]["rs"]:
        if 0 <= a <= z <= 0xFFFF and gi < fonts_o[ADV]["ng"]:
            adv_codes.update(range(a, z + 1))

    for sec in db:
        cur, tbl = read_sec(sec)
        if cur is None:
            continue
        in_mission = sec["idx"] in MISSION_EIDX
        is_gloss = (sec["idx"], sec["base"]) in GLOSS_KEY
        for off in tbl:
            if off == 0 or off >= len(cur):
                continue
            s = gs(cur, off)
            tagged = any(t in s for t in RADIO_TAGS)
            for _p, _sz, code in iter_units(s):
                if tagged:
                    used_tagged[code] += 1
                elif in_mission:
                    used_mission[code] += 1
                if code in donors and code not in adv_codes:
                    if tagged:
                        freq_tag[kr_inv[code]] += 1
                    elif is_gloss:
                        freq_gloss[kr_inv[code]] += 1

    # ---------- 재배치 풀: 대형(16x18+) + 완화(12x14+) ----------
    # 변환 산출물이 쓰는 코드는 풀 금지(전각 승격/치환 타깃과 글리프 충돌 방지)
    RESERVED = set(range(0x8260, 0x827A)) | set(range(0x8281, 0x829B))  # Ａ-Ｚａ-ｚ
    RESERVED |= set(FW_PUNCT.values()) | set(PUNCT2.values())
    RESERVED |= {JANG_NEW, 0x8140, 0x8251}

    def usable(c, wmin, hmin):
        if c in donors or used_tagged[c] or used_mission[c] or c in RESERVED:
            return False
        if not in_both(c, [ADV] + LARGE):
            return False
        for e in [ADV] + LARGE:
            b = box_of(fonts_o[e], c)
            if b is None or b[2] - b[0] < wmin or b[3] - b[1] < hmin:
                return False
        return True

    pool_big, pool_relax = [], []
    for c in range(0x8140, 0x9873):
        if usable(c, 16, 18):
            pool_big.append(c)
        elif usable(c, 12, 14):
            pool_relax.append(c)
    print(f"풀: 대형 {len(pool_big)} + 완화 {len(pool_relax)}")

    # 기호(※＆)는 완화 풀에서 우선 배정
    sym_map = {}
    for src, ch in SYM_GLYPH.items():
        if pool_relax:
            sym_map[src] = (pool_relax.pop(0), ch)
    # 음절: 용어 섹션 출현 우선(사용자가 정독하는 화면) → 태그 빈도순
    order = [ch for ch, _n in freq_gloss.most_common()] + \
            [ch for ch, _n in freq_tag.most_common() if ch not in freq_gloss]
    # 소형폰트 보유 donor 음절엔 소형폰트에도 있는 슬롯 우선(v4와 동일 원리)
    small_codes = set()
    for e in SMALL:
        for a, z, gi in fonts_o[e]["rs"]:
            if 0 <= a <= z <= 0xFFFF and gi < fonts_o[e]["ng"]:
                small_codes.update(range(a, z + 1))
    slots = pool_big + pool_relax   # 대형 박스 먼저 소진
    slots_sm = [c for c in slots if all(gi_of(fonts_o[e], c) is not None for e in SMALL)]
    remap = {}
    for ch in order:
        if not slots:
            break
        if kr[ch] in small_codes and slots_sm:
            c = slots_sm.pop(0)
            slots.remove(c)
        else:
            c = slots.pop(0)
            if c in slots_sm:
                slots_sm.remove(c)
        remap[kr[ch]] = (c, ch)
    cover = sum(freq_tag[ch] + freq_gloss[ch] for _d, (_c, ch) in remap.items())
    total = sum(freq_tag.values()) + sum(freq_gloss.values())
    print(f"음절 재배치 {len(remap)}슬롯: 출현 {cover}/{total} 커버")
    print("  대상:", "".join(ch for _d, (_c, ch) in remap.items()))
    miss_left = [(ch, freq_tag[ch] + freq_gloss[ch]) for ch in order if kr[ch] not in remap]
    if miss_left:
        print("  미커버:", miss_left[:15])

    # 2B 등길이 리매핑 통합 테이블(장 + 부호 치환 + 기호 + 음절)
    remap2 = {JANG_OLD: JANG_NEW}
    remap2.update(PUNCT2)
    remap2.update({src: code for src, (code, _ch) in sym_map.items()})
    remap2.update({d: code for d, (code, _ch) in remap.items()})
    # 미보유 전각 소문자 → 전각 대문자(작품명 Ｅｎｄｌｅｓｓ 등), ＇(FA56) → ’
    n_case = 0
    for i in range(26):
        lo, up = 0x8281 + i, 0x8260 + i
        if not in_both(lo, [ADV] + LARGE) and in_both(up, [ADV] + LARGE):
            remap2[lo] = up
            n_case += 1
    if in_both(0x8166, [ADV] + LARGE):
        remap2[0xFA56] = 0x8166
    print(f"전각 소문자→대문자 승격 {n_case}자, ＇→’ {'적용' if 0xFA56 in remap2 else '생략'}")

    # ---------- 문자열 변환 ----------
    BAREL_BAD = None
    if "바렐" in kr and "오" in kr:
        BAREL_BAD = (bytes((kr["바"] >> 8, kr["바"] & 0xFF, kr["렐"] >> 8, kr["렐"] & 0xFF))
                     + b"\x81\x48"
                     + bytes((kr["오"] >> 8, kr["오"] & 0xFF)))
        BAREL_FIX = (BAREL_BAD[:4] + b"\x5f" + BAREL_BAD[6:])

    def transform(s: bytes):
        """태그 문자열 변환(전각 승격 포함, 성장 가능)."""
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
                    m = remap2.get(code)
                    if m:
                        o += bytes((m >> 8, m & 0xFF))
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

    def transform_eqlen(s: bytes):
        """등길이 변환(용어/작품명 섹션·transform_nogrow 공용): 공백 캐리어 + 2B 리매핑만."""
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
                    m = remap2.get(code)
                    o += bytes((m >> 8, m & 0xFF)) if m else s[i:i + 2]
                    i += 2
                else:
                    o.append(c); i += 1
                continue
            if c in CARRIER:
                o.append(CARRIER[c][0]); i += 1; continue
            o.append(c); i += 1
        return bytes(o)

    # ---- (a) 태그 문자열(전 섹션, v4와 동일 재패킹/폴백) ----
    n_sec = n_str = n_grow_fb = 0
    for sec in db:
        if (sec["idx"], sec["base"]) in GLOSS_KEY:
            continue   # 용어 섹션은 등길이 패스에서 처리
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
        h0 = min(offs)
        oe = max(off + len(gs(cur, off)) + 1 for off in offs)
        limit = max(sec["csize"], oe)
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
                print(f"  [보류] idx{sec['idx']}/{sec['base']:#x}: 재패킹 불가, 원상 유지")
                cand = None
                break
            slot = growers[0][0]
            s, _ns = cand[slot]
            sb = s
            if BAREL_BAD and BAREL_BAD in sb:
                sb = sb.replace(BAREL_BAD, BAREL_FIX)
            cand[slot] = (s, transform_eqlen(sb))
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
    print(f"태그 문자열 재작성: {n_sec}섹션 {n_str}건, 성장 폴백 {n_grow_fb}건")

    # ---- (b) 용어/작품명 섹션(등길이 제자리, 재패킹 없음) ----
    n_gsec = n_gstr = 0
    leftover_codes = Counter()
    for sec in GLOSS:
        cur, tbl = read_sec(sec)
        assert cur is not None
        changed = False
        for off in sorted({o for o in tbl if 0 < o < len(cur)}):
            s = gs(cur, off)
            ns = transform_eqlen(s)
            assert len(ns) == len(s)
            if ns != s:
                cur[off:off + len(ns)] = ns
                changed = True
                n_gstr += 1
            for _p, sz, code in iter_units(ns):
                if sz == 2 and not in_both(code, [ADV] + LARGE):
                    leftover_codes[code] += 1
        if changed:
            e = toc[sec["idx"]]
            out.seek(DATA_OFF + e["off"] + sec["base"])
            out.write(cur[:max(sec["tbloff"] + sec["count"] * 4, sec["csize"])])
            n_gsec += 1
    print(f"용어/작품명 재작성: {n_gsec}섹션 {n_gstr}건")
    if leftover_codes:
        lo = [(f"{c:04x}", kr_inv.get(c, ""), n) for c, n in leftover_codes.most_common(12)]
        print("  잔여 미보유 2B(？ 유지):", lo)

    # ---- (c) 포즈/배너 섹션 '통신' 라벨(등길이, 해당 문자열만) ----
    sin = kr.get("신")
    n_tong = 0
    sin_new = remap2.get(sin)
    if sin_new:
        pat = bytes((kr["통"] >> 8, kr["통"] & 0xFF, sin >> 8, sin & 0xFF))
        rep = bytes((kr["통"] >> 8, kr["통"] & 0xFF, sin_new >> 8, sin_new & 0xFF))
        for idx, base in PAUSE_DONE + PAUSE_LATE:
            sec = find_sec(idx, base)
            cur, tbl = read_sec(sec)
            for off in sorted({o for o in tbl if 0 < o < len(cur)}):
                s = gs(cur, off)
                if s == pat:   # 정확히 '통신' 단독 문자열만
                    cur[off:off + 4] = rep
                    n_tong += 1
            e = toc[idx]
            out.seek(DATA_OFF + e["off"] + base)
            out.write(cur[:max(sec["tbloff"] + sec["count"] * 4, sec["csize"])])
    print(f"'통신' 라벨 치환: {n_tong}건 (신 {sin:#06x}→{sin_new:#06x})" if sin_new
          else "'통신' 치환 생략(신 풀 미배정)")

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
            grid = render_fit(ch, size, bw, bh,
                              align="center" if len(ch) == 1 and not ("가" <= ch <= "힣") else "left")
            if grid is not None:
                break
        if grid is None:
            return False
        blit(pix, tw, box, grid, body)
        return True

    jobs = [(carrier, glyph) for _src, (carrier, glyph) in CARRIER.items()]
    jobs += [(code, ch) for _src, (code, ch) in sym_map.items()]
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
        body = 8
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

    # ---------- 8781 본체 8→6 (v4와 동일) ----------
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
    tex_off, tex_size = inner[2000]
    po, pl = tex_off + 0x20, tex_size - 0x60
    idx = build_file_index_4via32(1024, 512)
    pix = bytearray(deswizzle4via32(outer[po:po + pl], 1024, 512, idx))
    code_gi = {}
    for a, z, gi in rs:
        if not (0 <= a <= z <= 0xFFFF and gi < ng):
            continue
        for k in range(z - a + 1):
            code_gi[a + k] = gi + k
    targets = set()
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
