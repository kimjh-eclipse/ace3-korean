# -*- coding: utf-8 -*-
"""ACE3 한국어 패치 빌더 (안전 할당판)
- 한글 음절은 '게임이 안 쓰는 한자 칸'에 우선 배정 → 미번역 일본어 무손상.
- 안전칸 소진 시에만 사용칸 사용(경고). 음절-코드 매핑은 kr_map.json에 고정 보존.
"""
import json, os, sys, struct, glob, shutil
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A
import shellfont
from PIL import Image, ImageDraw, ImageFont

OUT_ISO = os.environ.get("ACE3_OUT_ISO", os.path.join(A.W, "ACE3_KR.iso"))
FONT_PATH = r"C:\Windows\Fonts\gulim.ttc"

def main():
    tl = {}
    for p in sorted(glob.glob(os.path.join(A.W, "tl", "*.json"))):
        d = json.load(open(p, encoding="utf-8"))
        tl.update(d)
    # 빈 문자열/동일 값 제거
    tl = {k: v for k, v in tl.items() if v and v != k}
    print("번역 항목:", len(tl))

    db = json.load(open(os.path.join(A.W, "db.json"), encoding="utf-8"))
    usage = json.load(open(os.path.join(A.W, "kanji_usage.json")))
    safe_codes = usage["safe_codes"]

    # 자체 폰트(1024x512 PSMT32-업로드 스위즐) 내장 컨테이너 계열:
    #  - 부팅/시스템 셸 id 4000000~4002999
    #  - 미션 HUD/메뉴 id 1200000~1299999
    # 이들 문자열은 L2 코드영역(0x9940+) 셸 맵으로 인코딩한다.
    def is_bootfont_entry(eid):
        return 4000000 <= eid <= 4002999 or 1200000 <= eid <= 1299999

    f = open(A.ISO, "rb")
    toc = A.load_toc()

    # 셸 엔트리는 원래 추출기가 일부 컨테이너를 놓쳤다(예: id4002050 0x120ba0의 헤더 '確認').
    # 전수 열거로 누락 컨테이너를 db에 병합한다.
    shellfonts_meta = json.load(open(os.path.join(A.W, "shellfonts2.json")))["fonts"]
    shell_eidx = {x["eidx"] for x in shellfonts_meta}
    have = {(d["idx"], d["base"]) for d in db}

    def enum_records(eidx):
        e = toc[eidx]
        buf = A.read_entry(f, e)
        recs = []
        o = 0
        N = len(buf)
        while o + 0x30 <= N:
            r = A.try_parse(buf, o)
            if r:
                strs = []
                for slot, off, raw in r["strs"]:
                    try:
                        t = raw.decode("shift_jis")
                    except Exception:
                        continue
                    strs.append({"t": t, "hex": raw.hex(), "off": off, "slot": slot})
                recs.append({"idx": eidx, "id": e["id"], "base": r["base"],
                             "csize": r["csize"], "count": r["count"],
                             "tbloff": r["tbloff"], "strs": strs})
                o += max(0x10, r["csize"] & ~0xF)
            else:
                o += 16
        return recs

    added = 0
    for eidx in sorted(shell_eidx):
        for r in enum_records(eidx):
            if (r["idx"], r["base"]) not in have:
                db.append(r); have.add((r["idx"], r["base"])); added += 1
    print(f"셸 컨테이너 병합: +{added}개")

    # ★ 2026-07-08 확정(동적디버깅): 인게임 텍스트(브리핑/미션 대사/HUD/자막)는 전부
    #   셸 계열 폰트로 렌더된다. 메인폰트(idx4/5)는 대사 렌더에 쓰이지 않으며,
    #   메인 kr_map 코드로 인코딩한 텍스트는 셸폰트 레인지에 없어 ?로 나온다
    #   (RAM 라이브테스트: 같은 문자열을 셸 코드로 치환하자 즉시 한글 렌더).
    #   → 모든 텍스트를 kr_map_shell로 인코딩하고, 셸폰트에 전 음절을 수용시킨다.
    #   메인폰트는 원본 그대로 둔다(미지의 메인폰트 렌더 화면이 있어도 일본어 원문 유지).

    # 전체 필요 음절 + 코퍼스 빈도(폰트 용량 부족 시 저빈도부터 탈락)
    from collections import Counter
    syl_freq = Counter()
    for jp, kr in tl.items():
        for ch in kr:
            if "가" <= ch <= "힣":
                syl_freq[ch] += 1
    need = set(syl_freq)
    print("필요한 한글 음절:", len(need))

    # ★ 2026-07-08 3차(제자리 방식): HUD(무전) 렌더러는 원본 폰트 레이아웃 기준의
    #   baked 코드→글리프 매핑을 써서, 레인지/글리프를 재배열하는 rebuild 방식은
    #   그 경로에서 깨진다(가타카나까지 뭉개짐). → 폰트 구조는 일절 안 바꾸고,
    #   '기증된 기존 한자/히라가나 코드'에 한글·부호를 배정해 그 글리프 박스의
    #   텍스처 픽셀만 교체한다. 어떤 렌더러(baked/공식/레인지)든 같은 코드에서
    #   같은 박스를 보므로 범용으로 작동. 메인폰트에도 같은 코드로 주입한다.
    shell_map_path = os.path.join(A.W, "kr_map_shell.json")
    KANJI_LO, KANJI_HI = 0x889F, 0x9872
    HIRA_LO, HIRA_HI = 0x829F, 0x82F1

    # 폰트별 기증가능 코드(한자+히라, 박스>=16x19) — 원본 폰트에서 산출
    import re as _re
    _TOKEN = _re.compile(r"<[^>]*>|#c\[[0-9A-Fa-f]{6}\]|#c|⟦[^⟧]*⟧|%[sdcuxX]")
    donor_sets = {}
    font_covered = {}
    for ftm in shellfonts_meta:
        fbuf = bytearray(A.read_entry(f, toc[ftm["eidx"]]))
        rs, mets = shellfont.parse_font(fbuf, ftm)
        dset = set(); cov = set()
        for a, z, gi in rs:
            for k in range(z - a + 1):
                c = a + k
                cov.add(c)
                if KANJI_LO <= c <= KANJI_HI or HIRA_LO <= c <= HIRA_HI:
                    g = gi + k
                    u0, v0, u1, v1 = struct.unpack_from("<4f", mets[g], 0)
                    if round((u1-u0)*1024) >= 16 and round((v1-v0)*512) >= 19:
                        dset.add(c)
        donor_sets[ftm["id"]] = dset
        font_covered[ftm["id"]] = cov

    MISSION_IDS = [i for i in donor_sets if 1200000 <= i <= 1200007]
    BOOT_IDS = [i for i in donor_sets if i >= 4002050]
    mission_set = set.intersection(*[donor_sets[i] for i in MISSION_IDS])
    all_donors = set.union(*donor_sets.values())

    # 매핑: (a) 한글 음절 → 기증 한자코드(2B→2B, 크기 불변).
    #       (b) 폰트에 글리프 없는 부호(반각 .!~ 등) → 인코딩은 자기 코드 그대로
    #           (1B 유지, 크기 불변!) + 폰트에 '자기코드→기증글리프' 레인지 추가.
    #   ※ 부호를 2B 맵코드로 바꾸면 텍스트가 커져 5만개 문자열이 폴백된다(실측).
    char_freq = Counter()
    for v in tl.values():
        for ch in _TOKEN.sub("", v):
            if ch in " \n\t　":
                continue
            if "가" <= ch <= "힣":
                char_freq[ch] += 1
            else:
                char_freq[A._sjis_safe_char(ch)] += 1
    syls = [ch for ch, _ in char_freq.most_common() if "가" <= ch <= "힣"]
    punct_missing = {}   # own_code -> ch
    for ch, n in char_freq.most_common():
        if "가" <= ch <= "힣":
            continue
        try:
            code = int.from_bytes(ch.encode("shift_jis"), "big")
        except Exception:
            continue
        if any(code not in font_covered[i] for i in donor_sets):
            punct_missing[code] = ch
    print(f"음절 {len(syls)}, 글리프 없는 부호 {len(punct_missing)}")

    # ★ 2026-07-09 무전자막 해결: 전투 무전 캡션은 미션 엔트리(1200000~1200007)의
    #   내부 nested 폰트 inner 2501(241글리프) + 아틀라스 inner 2001(256x256 선형)을
    #   쓴다. 이걸 아무도 안 패치해서 자막이 원본 한자로 나왔다(셸 2500/메인과 별개).
    #   → 무전폰트가 가진 172개 기증코드를 '빈도 상위 음절'에 우선 배정해서, 자막에
    #   자주 나오는 음절이 이 폰트에 담기게 한다(브리핑은 셸폰트가 전 코드 커버).
    def _parse_inner(buf):
        total = struct.unpack_from("<I", buf, 4)[0]; count = struct.unpack_from("<I", buf, 8)[0]
        out = []; prev = -1
        for i in range(count):
            fid, off = struct.unpack_from("<II", buf, 0x18 + i * 8)
            if off <= prev or off >= total: break
            nxt = total
            if i + 1 < count:
                _f, noff = struct.unpack_from("<II", buf, 0x18 + (i + 1) * 8)
                if off < noff <= total: nxt = noff
            out.append((fid, off, nxt - off)); prev = off
        return out

    def radio_font_boxes(outer):
        """inner 2501(폰트)+2001(아틀라스). 반환: (code->box(256기준), inner2001_off)."""
        inner = {fid: (off, sz) for fid, off, sz in _parse_inner(outer)}
        if 2501 not in inner or 2001 not in inner:
            return None, None
        fb = inner[2501][0]
        packed = struct.unpack_from("<I", outer, fb + 0x10)[0]; nr = packed & 0xFFFF
        met = struct.unpack_from("<I", outer, fb + 0x18)[0]
        boxes = {}; o = fb + 0x20
        for i in range(nr - 1):
            a, z, gi = struct.unpack_from("<III", outer, o); o += 12
            for k in range(z - a + 1):
                c = a + k; g = gi + k
                u = struct.unpack_from("<4f", outer, fb + met + g * 24)
                boxes[c] = (round(u[0]*256), round(u[1]*256), round(u[2]*256), round(u[3]*256))
        return boxes, inner[2001][0]

    def caption_boxes_2500(outer):
        """대형 캡션폰트(inner 2500 메트릭, 1024x512 아틀라스)의 code->(w,h).
        2501(소형 변형)이 아니라 실제 무전자막이 쓰는 2500 기준 크기 —
        같은 코드라도 2501에선 통과하고 2500에선 좁은 가나 칸이 있어(예 0x8344=14px),
        여기 기준으로 거르지 않으면 고빈도 음절이 좁은 칸에 배정돼 찌그러진다."""
        inner = {fid: (off, sz) for fid, off, sz in _parse_inner(outer)}
        if 2500 not in inner:
            return {}
        fb = inner[2500][0]
        packed = struct.unpack_from("<I", outer, fb + 0x10)[0]
        nr2 = packed & 0xFFFF
        ng2 = packed >> 16
        met = struct.unpack_from("<I", outer, fb + 0x18)[0]
        out = {}
        o = fb + 0x20
        for _i in range(nr2):
            a, z, gi = struct.unpack_from("<III", outer, o); o += 12
            if not (0 <= a <= z <= 0xFFFF) or gi >= ng2 or gi + (z - a) >= ng2:
                continue
            for k in range(z - a + 1):
                c = a + k
                if c in out:
                    continue
                u = struct.unpack_from("<4f", outer, fb + met + (gi + k) * 24)
                out[c] = (round((u[2] - u[0]) * 1024), round((u[3] - u[1]) * 512))
        return out

    RADIO_EIDX = [x["eidx"] for x in shellfonts_meta if 1200000 <= x["id"] <= 1200007]
    _rbuf = bytearray(A.read_entry(f, toc[RADIO_EIDX[0]])) if RADIO_EIDX else None
    _rb, _ = radio_font_boxes(_rbuf) if _rbuf is not None else (None, None)
    _cap_wh = caption_boxes_2500(_rbuf) if _rbuf is not None else {}
    radio_donor = []
    if _rb:
        # 무전폰트 charset의 한자/가나 슬롯(박스 충분). all_donors(셸 도너) 제약을 걸지
        # 않는다 — 이 코드들은 셸폰트에도 거의 다 존재하므로(검증) 브리핑도 렌더된다.
        # ★캡션(2500) 박스 폭>=16·높이>=18 필수 — 좁은 칸 배정 방지(2026-07-10).
        radio_donor = [c for c, (x0, y0, x1, y1) in sorted(_rb.items())
                       if (0x829F <= c <= 0x8396 or c >= 0x889F)
                       and (x1 - x0) >= 11 and (y1 - y0) >= 14
                       and _cap_wh.get(c, (0, 0))[0] >= 16
                       and _cap_wh.get(c, (0, 0))[1] >= 18]
    radio_set = set(radio_donor)
    all_donors = all_donors | radio_set   # 무전 코드를 도너 풀에 포함(빈도상위 음절 배정)
    print(f"무전폰트(2501) 기증코드: {len(radio_donor)}")

    # 기증 코드 우선순위: 무전폰트 보유(최우선, 빈도상위 음절이 무전에 담김) > 미션폰트 > ...
    def code_rank(c):
        return (c in radio_set,
                c in mission_set,
                sum(1 for i in BOOT_IDS if c in donor_sets[i]),
                c in donor_sets.get(1200011, set()),
                -c)
    donor_order = sorted(all_donors, key=code_rank, reverse=True)
    kr_map_shell = dict(zip(syls, donor_order))            # 한글: 빈도순 배정(무전코드 우선)
    # 부호(.! 등 잔여): 한글 미배정 기증코드의 싱글톤 레인지를 재활용해 폰트에 주입
    punct_ranges = {oc: (ch, None) for oc, ch in punct_missing.items()}
    n_in_mission = sum(1 for c in kr_map_shell.values() if c in mission_set)
    print(f"한글맵 {len(kr_map_shell)} (미션폰트 보유 {n_in_mission}), 부호(싱글톤치환) {len(punct_ranges)}")

    enc_cache_sh = {}
    def encode_shell(t):
        if t not in enc_cache_sh:
            enc_cache_sh[t] = A.encode_tagged(t, kr_map_shell, None)
        return enc_cache_sh[t]

    print("ISO 복사...")
    shutil.copyfile(A.ISO, OUT_ISO)
    out = open(OUT_ISO, "r+b")

    overflow_secs = []
    partial_secs = []   # 컨테이너 전체가 아니라 일부 문자열만 원문으로 되돌린 경우
    patched = 0
    strings_done = 0
    for d in db:
        strs = d["strs"]
        if not any(s["t"] in tl for s in strs):
            continue
        enc = encode_shell  # 전 텍스트 셸 인코딩(2026-07-08 셸폰트 렌더 확정)
        e = toc[d["idx"]]
        base, csize, count, tbloff = d["base"], d["csize"], d["count"], d["tbloff"]
        h0 = min(s["off"] for s in strs)
        orig_end = max(s["off"] + len(bytes.fromhex(s["hex"])) + 1 for s in strs)
        limit = max(csize, orig_end)

        # 번역 대상 슬롯(줄어들 수 있음): 넘치면 가장 많이 늘어난 문자열부터 하나씩
        # 원문으로 되돌리며 재시도 → 컨테이너 전체를 포기하지 않고 최대한 살린다.
        active = {s["slot"]: s["t"] for s in strs if s["t"] in tl}

        def try_pack():
            heap = bytearray(); offmap = {}; new_offs = {}
            for s in strs:
                data = enc(tl[active[s["slot"]]]) if s["slot"] in active else bytes.fromhex(s["hex"])
                if data in offmap:
                    new_offs[s["slot"]] = offmap[data]; continue
                o = h0 + len(heap)
                if o + len(data) + 1 > limit:
                    return None
                offmap[data] = o; new_offs[s["slot"]] = o
                heap += data + b"\x00"
            return heap, new_offs

        n_orig_tl = len(active)
        result = try_pack()
        while result is None and active:
            growth = {slot: len(enc(tl[t])) - len(bytes.fromhex(next(s["hex"] for s in strs if s["slot"] == slot)))
                      for slot, t in active.items()}
            worst = max(growth, key=growth.get)
            del active[worst]
            result = try_pack()
        if result is None:
            overflow_secs.append((d["idx"], d["base"])); continue
        if len(active) < n_orig_tl:
            partial_secs.append((d["idx"], d["base"], n_orig_tl - len(active)))
        heap, new_offs = result

        f.seek(A.DATA_OFF + e["off"] + base + tbloff)
        cur_tbl = bytearray(f.read(count * 4))
        for slot, o in new_offs.items():
            struct.pack_into("<I", cur_tbl, slot * 4, o)
        iso_base = A.DATA_OFF + e["off"] + base
        out.seek(iso_base + tbloff); out.write(cur_tbl)
        out.seek(iso_base + h0); out.write(heap + bytes(limit - h0 - len(heap)))
        patched += 1
        strings_done += len(active)

    print(f"패치 섹션: {patched}, 문자열: {strings_done}, 오버플로 섹션: {len(overflow_secs)}, "
          f"부분폴백 섹션: {len(partial_secs)}(문자열 {sum(x[2] for x in partial_secs)}개 원문유지)")
    if overflow_secs:
        print("  오버플로:", overflow_secs)
        json.dump(overflow_secs, open(os.path.join(A.W, "overflow_secs.json"), "w"))
    if partial_secs:
        print("  부분폴백:", partial_secs)

    # 셸 폰트: 구조 무변경 제자리 주입(글리프 인덱스/메트릭 원본 유지) + 부호 레인지 추가.
    render = shellfont.make_renderer(FONT_PATH)
    for ft in shellfonts_meta:
        e = toc[ft["eidx"]]
        buf = bytearray(A.read_entry(f, e))
        done, added = shellfont.inplace_inject(buf, ft, kr_map_shell, render,
                                               add_ranges=punct_ranges)
        lo = min(ft["tex"], ft["fb"])
        hi = ft["met"] + ft["nglyph"] * 24
        out.seek(A.DATA_OFF + e["off"] + lo)
        out.write(buf[lo:hi])
        print(f"  셸 폰트 id{ft['id']} 제자리 주입: 한글 {done}/{len(kr_map_shell)}, 부호레인지 +{added}")

    # 메인폰트에도 같은 코드로 주입(어느 렌더러가 메인폰트를 쓰더라도 동일 코드 유효).
    b35, b36, ranges, nglyph = A.load_font(f, toc)
    b35 = bytearray(b35); b36 = bytearray(b36)
    code2gi = {}
    for a, z, gidx in ranges:
        for k in range(z - a + 1):
            code2gi[a + k] = gidx + k
    # 전투 무전 자막은 메인폰트의 작은 박스(대부분 10~12x12)를 쓴다.
    # 12px 그레이스케일은 박스 안에서 획이 뭉개져서, 실제 박스에 맞춘 10px
    # 바이너리 렌더가 더 읽기 좋다(라이브 화면/타일 미리보기로 확인).
    ftt = ImageFont.truetype(FONT_PATH, 10, index=0)
    main_threshold = 64
    n_main = 0
    for ch, code in kr_map_shell.items():
        gi = code2gi.get(code)
        if gi is None:
            continue
        u0, v0, u1, v1, w16 = A.get_metric(b35, gi)
        x0, y0 = round(u0 * A.TEX_W), round(v0 * A.TEX_H)
        x1, y1 = round(u1 * A.TEX_W), round(v1 * A.TEX_H)
        bw, bh = max(1, x1 - x0), max(1, y1 - y0)
        tile = Image.new("L", (bw, bh), 0)
        ImageDraw.Draw(tile).text((0, max(0, bh - 2)), ch, font=ftt, fill=255, anchor="ls")
        px = tile.load()
        for yy in range(bh):
            for xx in range(bw):
                A.tex_putpixel(b36, x0 + xx, y0 + yy, 15 if px[xx, yy] >= main_threshold else 0)
        n_main += 1
    for idx2, blob in ((A.FONT_MAP_IDX, b35), (A.FONT_TEX_IDX, b36)):
        e2 = toc[idx2]
        assert len(blob) == e2["size"]
        out.seek(A.DATA_OFF + e2["off"]); out.write(blob)
    print(f"  메인폰트 제자리 주입: {n_main}/{len(kr_map_shell)}")

    # ★ 무전 폰트(inner 2001 아틀라스, 256x256 선형) 한글 주입 — 전투 무전 자막용.
    #   2501의 각 기증코드 박스에 그 코드에 배정된 한글을 16px 그레이스케일로 그린다.
    inv_shell = {code: ch for ch, code in kr_map_shell.items()}
    ftr = ImageFont.truetype(FONT_PATH, 16, index=0)
    for eidx in RADIO_EIDX:
        e = toc[eidx]
        out.seek(A.DATA_OFF + e["off"]); outer = bytearray(out.read(e["size"]))
        boxes, t2001 = radio_font_boxes(outer)
        if boxes is None:
            continue
        atlas_off = t2001 + 0x60
        def gp(x, y):
            b = outer[atlas_off + (y * 256 + x) // 2]
            return (b & 0xF) if x % 2 == 0 else (b >> 4)
        def sp(x, y, v):
            i = atlas_off + (y * 256 + x) // 2; b = outer[i]
            outer[i] = ((b & 0xF0) | (v & 15)) if x % 2 == 0 else ((b & 0x0F) | ((v & 15) << 4))
        rdone = 0
        for code, (x0, y0, x1, y1) in boxes.items():
            ch = inv_shell.get(code)
            if ch is None:
                continue
            bw, bh = x1 - x0, y1 - y0
            if bw < 1 or bh < 1:
                continue
            for yy in range(bh):
                for xx in range(bw):
                    sp(x0 + xx, y0 + yy, 0)
            tile = Image.new("L", (bw, bh), 0)
            ImageDraw.Draw(tile).text((0, bh - 2), ch, font=ftr, fill=255, anchor="ls")
            p = tile.load()
            for yy in range(bh):
                for xx in range(bw):
                    sp(x0 + xx, y0 + yy, round(p[xx, yy] / 255 * 15))
            rdone += 1
        out.seek(A.DATA_OFF + e["off"]); out.write(outer)
        print(f"  무전폰트 id{e['id']} 아틀라스 주입: {rdone}")
    out.close()

    # ★ 2026-07-08 3차: 매직 없는 raw NUL구분 문자열(유닛명/UI라벨/화자명) 제자리 번역.
    #   00010000 컨테이너에 안 담긴 flat 텍스트를 게임이 직접 읽는 경로가 존재한다
    #   (브리핑 이름표 등). 엔트리를 OUT_ISO(컨테이너 패치 후)에서 읽어 세그먼트가
    #   'tl에 번역 존재 + 이름형 문자만 + 셸인코딩이 원본 길이 이내'면 제자리 덮어쓴다.
    #   'tl 존재' 조건이 바이너리 오염 방지막. 오프셋 불변(포인터 테이블 안전).
    #   ⚠ 게임 행(hang) 원인 격리용 토글. RAW_PASS=False면 이 패스 생략.
    RAW_PASS = False
    def is_name_seg(seg):
        if not (2 <= len(seg) <= 48):
            return False
        try:
            t = seg.decode("shift_jis")
        except Exception:
            return False
        for ch in t:
            o = ord(ch)
            if 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF or 0xFF00 <= o <= 0xFF9F:
                continue
            if ch in "・･ 　0123456789":
                continue
            return False
        return True

    raw_patched = raw_entries = raw_skip_long = 0
    if RAW_PASS:
        out2 = open(OUT_ISO, "r+b")
        for e in toc:
            if e["size"] < 4 or e["size"] > 0x800000:  # 초대용량(무비)만 제외; 부트폰트(~5MB) 포함
                continue
            base_abs = A.DATA_OFF + e["off"]
            out2.seek(base_abs); data = bytearray(out2.read(e["size"]))
            pos = 0; changed = False
            for seg in bytes(data).split(b"\x00"):
                L = len(seg)
                if 2 <= L <= 48 and is_name_seg(seg):
                    jp = seg.decode("shift_jis")
                    kr = tl.get(jp)
                    if kr:
                        enc = encode_shell(kr)
                        if len(enc) <= L:
                            data[pos:pos + len(enc)] = enc
                            for z in range(pos + len(enc), pos + L):
                                data[z] = 0
                            changed = True; raw_patched += 1
                        else:
                            raw_skip_long += 1
                pos += L + 1
            if changed:
                out2.seek(base_abs); out2.write(data); raw_entries += 1
        out2.close()
    print(f"raw 문자열 제자리 번역: {raw_patched}건 / {raw_entries}엔트리 "
          f"(길이초과 스킵 {raw_skip_long}){' [비활성]' if not RAW_PASS else ''}")

    json.dump(kr_map_shell, open(shell_map_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print(f"셸 음절 총 {len(kr_map_shell)}개")
    print("완료:", OUT_ISO)

if __name__ == "__main__":
    main()
