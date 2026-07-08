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

OUT_ISO = os.path.join(A.W, "ACE3_KR.iso")
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

    b35, b36, ranges, nglyph = A.load_font(f, toc)
    b35 = bytearray(b35); b36 = bytearray(b36)
    code2gi = {}
    for a, z, idx in ranges:
        for k in range(z - a + 1):
            code2gi[a + k] = idx + k

    # 필요한 음절 집합
    need = set()
    for jp, kr in tl.items():
        for ch in kr:
            if "가" <= ch <= "힣":
                need.add(ch)
    print("필요한 한글 음절:", len(need))

    # 기존 맵 로드(고정)
    map_path = os.path.join(A.W, "kr_map.json")
    kr_map = {}
    if os.path.exists(map_path):
        kr_map = {k: int(v) for k, v in json.load(open(map_path, encoding="utf-8")).items()}
    used_codes = set(kr_map.values())
    free_pool = [c for c in safe_codes if c not in used_codes]
    used_kanji = set(usage["used_kanji"])

    # ★ 동적 기증(메인폰트): 인게임(비셸) 미번역 문자열이 실제 쓰는 한자만 보존,
    #   전부 번역된 한자칸은 한글 기증으로 회수 → 스토리 대량 번역 시 슬롯 확보.
    #   safe_codes는 그대로 두고 회수분을 뒤에 이어붙이는 단조 확장(기존 배정 불변).
    def _kanji_codes(bs):
        out = set(); i = 0; n = len(bs)
        while i + 1 < n:
            b0 = bs[i]
            if 0x81 <= b0 <= 0x9f or 0xe0 <= b0 <= 0xef:
                c = (b0 << 8) | bs[i + 1]
                if 0x889F <= c <= 0x9872:
                    out.add(c)
                i += 2
            else:
                i += 1
        return out
    keep_main = set()
    for d in db:
        if is_bootfont_entry(d["id"]):
            continue
        for s in d["strs"]:
            if s["t"] not in tl:
                keep_main |= _kanji_codes(bytes.fromhex(s["hex"]))
    freeable = [c for c in sorted(used_kanji - keep_main)
                if c not in used_codes and c in code2gi]
    free_pool += freeable
    # 최후수단: 아직 미번역이 쓰는 한자(침범 시 그 일본어 손상)
    fallback_pool = [c for c in sorted(used_kanji & keep_main)
                     if c not in used_codes and c in code2gi]
    print(f"메인폰트 안전칸 {len(safe_codes)} + 동적회수 {len(freeable)} = free_pool {len(free_pool)}")
    fi = [0, 0]  # free idx, fallback idx
    overflow_syllables = []

    def assign(ch):
        if ch in kr_map:
            return kr_map[ch]
        # 안전칸 먼저
        while fi[0] < len(free_pool) and free_pool[fi[0]] in kr_map.values():
            fi[0] += 1
        if fi[0] < len(free_pool):
            code = free_pool[fi[0]]; fi[0] += 1
            kr_map[ch] = code
            return code
        # fallback
        while fi[1] < len(fallback_pool) and fallback_pool[fi[1]] in kr_map.values():
            fi[1] += 1
        if fi[1] < len(fallback_pool):
            code = fallback_pool[fi[1]]; fi[1] += 1
            kr_map[ch] = code
            overflow_syllables.append(ch)
            return code
        raise RuntimeError("코드 풀 완전 고갈")

    for ch in sorted(need):
        assign(ch)

    # 셸 전용 음절 맵(0xEB40+ 연속 코드). 순서 고정: 기존 코드순 + 신규 정렬순
    shell_map_path = os.path.join(A.W, "kr_map_shell.json")
    kr_map_shell_old = {}
    if os.path.exists(shell_map_path):
        kr_map_shell_old = {k: int(v) for k, v in
                            json.load(open(shell_map_path, encoding="utf-8")).items()}
    KANJI_LO, KANJI_HI = 0x889F, 0x9872
    def kanji_in(bs):
        out = set(); i = 0; n = len(bs)
        while i + 1 < n:
            b0 = bs[i]
            if 0x81 <= b0 <= 0x9f or 0xe0 <= b0 <= 0xef:
                c = (b0 << 8) | bs[i+1]
                if KANJI_LO <= c <= KANJI_HI:
                    out.add(c)
                i += 2
            else:
                i += 1
        return out

    # 폰트 엔트리별: 필요한 한글 음절 + 미번역(포착) 문자열이 쓰는 보존 한자.
    # 주의: 이 폰트들은 글리프가 포화 상태라 '모든 미포착 한자 보존'은 불가(예산 초과→폴백).
    #       포착된 미번역 문자열의 한자만 보존해 예산 내에서 ?? 최소화.
    font_need = {}   # eidx -> set(음절)
    font_keep = {}   # eidx -> set(보존 한자코드)
    shell_need = set()
    for d in db:
        if not is_bootfont_entry(d["id"]):
            continue
        fe = d["idx"]
        fn = font_need.setdefault(fe, set())
        fk = font_keep.setdefault(fe, set())
        for s in d["strs"]:
            if s["t"] in tl:
                for ch in tl[s["t"]]:
                    if "가" <= ch <= "힣":
                        fn.add(ch); shell_need.add(ch)
            else:
                fk |= kanji_in(bytes.fromhex(s["hex"]))

    shell_syls = sorted(kr_map_shell_old, key=lambda s: kr_map_shell_old[s])
    shell_syls += sorted(shell_need - set(shell_syls))
    shell_codes_all = shellfont.shell_codes(len(shell_syls))
    kr_map_shell = dict(zip(shell_syls, shell_codes_all))
    assert all(kr_map_shell[s] == c for s, c in kr_map_shell_old.items()), "셸 맵 순서 변동"
    print("셸 음절(전역):", len(shell_syls))

    enc_cache = {}
    def encode(t):
        if t not in enc_cache:
            enc_cache[t] = A.encode_tagged(t, kr_map, None)
        return enc_cache[t]

    enc_cache_sh = {}
    def encode_shell(t):
        if t not in enc_cache_sh:
            enc_cache_sh[t] = A.encode_tagged(t, kr_map_shell, None)
        return enc_cache_sh[t]

    print("ISO 복사...")
    shutil.copyfile(A.ISO, OUT_ISO)
    out = open(OUT_ISO, "r+b")

    overflow_secs = []
    patched = 0
    strings_done = 0
    skipped_boot = 0
    for d in db:
        strs = d["strs"]
        if not any(s["t"] in tl for s in strs):
            continue
        shell = is_bootfont_entry(d["id"])
        enc = encode_shell if shell else encode
        e = toc[d["idx"]]
        base, csize, count, tbloff = d["base"], d["csize"], d["count"], d["tbloff"]
        h0 = min(s["off"] for s in strs)
        orig_end = max(s["off"] + len(bytes.fromhex(s["hex"])) + 1 for s in strs)
        limit = max(csize, orig_end)
        heap = bytearray(); offmap = {}; new_offs = {}; ok = True
        for s in strs:
            t = s["t"]
            data = enc(tl[t]) if t in tl else bytes.fromhex(s["hex"])
            if data in offmap:
                new_offs[s["slot"]] = offmap[data]; continue
            o = h0 + len(heap)
            if o + len(data) + 1 > limit:
                ok = False; break
            offmap[data] = o; new_offs[s["slot"]] = o
            heap += data + b"\x00"
        if not ok:
            overflow_secs.append((d["idx"], d["base"])); continue
        f.seek(A.DATA_OFF + e["off"] + base + tbloff)
        cur_tbl = bytearray(f.read(count * 4))
        for slot, o in new_offs.items():
            struct.pack_into("<I", cur_tbl, slot * 4, o)
        iso_base = A.DATA_OFF + e["off"] + base
        out.seek(iso_base + tbloff); out.write(cur_tbl)
        out.seek(iso_base + h0); out.write(heap + bytes(limit - h0 - len(heap)))
        patched += 1
        strings_done += sum(1 for s in strs if s["t"] in tl)

    print(f"패치 섹션: {patched}, 문자열: {strings_done}, 오버플로 섹션: {len(overflow_secs)}")
    if overflow_secs:
        print("  오버플로:", overflow_secs[:10])

    # 폰트 글리프 주입
    ft = ImageFont.truetype(FONT_PATH, 11, index=0)
    for ch, code in kr_map.items():
        gi = code2gi[code]
        u0, v0, u1, v1, w16 = A.get_metric(b35, gi)
        x0, y0 = round(u0 * A.TEX_W), round(v0 * A.TEX_H)
        tile = Image.new("L", (11, 12), 0)
        ImageDraw.Draw(tile).text((0, 11), ch, font=ft, fill=255, anchor="ls")
        px = tile.load()
        for yy in range(12):
            for xx in range(11):
                A.tex_putpixel(b36, x0 + xx, y0 + yy, 15 if px[xx, yy] >= 128 else 0)
        A.set_metric(b35, gi, x0, y0, x0 + 11, y0 + 12, 0, 11, 12)

    for idx, blob in ((A.FONT_MAP_IDX, b35), (A.FONT_TEX_IDX, b36)):
        e = toc[idx]
        assert len(blob) == e["size"]
        out.seek(A.DATA_OFF + e["off"]); out.write(blob)

    # 셸 폰트 재작성 (폰트별 부분집합 음절 + 사용 한자 보존)
    render = shellfont.make_renderer(FONT_PATH)
    for ft in shellfonts_meta:
        e = toc[ft["eidx"]]
        buf = bytearray(A.read_entry(f, e))
        syl_codes = {s: kr_map_shell[s] for s in font_need.get(ft["eidx"], set())}
        keep = font_keep.get(ft["eidx"], set())
        try:
            shellfont.rebuild(buf, ft, syl_codes, render, keep_kanji=keep)
        except RuntimeError as ex:
            # 기증 부족 시 보존 한자 일부 포기(빈도 낮은 것부터) 없이 그냥 전량드롭 폴백
            print(f"  ⚠ id{ft['id']} 보존축소 폴백: {ex}")
            shellfont.rebuild(buf, ft, syl_codes, render, keep_kanji=set())
        lo = ft["tex"]
        hi = ft["met"] + ft["nglyph"] * 24
        out.seek(A.DATA_OFF + e["off"] + lo)
        out.write(buf[lo:hi])
        print(f"  셸 폰트 id{ft['id']} 재작성: 한글 {len(syl_codes)} 보존한자 {len(keep & set(range(0x889f,0x9873)))}")
    out.close()

    json.dump(kr_map_shell, open(shell_map_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    json.dump(kr_map, open(map_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"음절 총 {len(kr_map)}개 (안전칸 사용 {fi[0]}, fallback {len(overflow_syllables)})")
    if overflow_syllables:
        print("  ⚠ 사용칸 침범 음절:", "".join(overflow_syllables[:40]))
    print("완료:", OUT_ISO)

if __name__ == "__main__":
    main()
