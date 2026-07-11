# -*- coding: utf-8 -*-
"""v2 빌드: ACE3_KR_caption_full.iso 기반 통합 수정판(ACE3_KR_v2.iso).
1) 포즈 섹션 4종(1200000~03): 번역문 공백 0x20→0x8140, slot19(ゲームに戻る)='리줌'
   - '게임으로 돌아가기'는 8d82+82c3 연쇄가 포즈 오픈 행 유발(재현 격리 완료)
2) FNM 유닛 테이블(107개): 공격/무기명 + 유닛명 제자리 한글화(원 길이 이내, 포인터 불변)
"""
import sys, json, struct, shutil, os, glob
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

W = A.W
SRC = os.path.join(W, "ACE3_KR_caption_full.iso")
DST = os.path.join(W, "ACE3_KR_v2.iso")

krmap = json.load(open(os.path.join(W, "kr_map_shell.json"), encoding="utf-8"))
SPECIAL = {"　": b"\x81\x40", "〜": b"\x81\x60", "・": b"\x81\x45", "·": b"\x81\x45",
           "（": b"\x81\x69", "）": b"\x81\x6a", "(": b"\x81\x69", ")": b"\x81\x6a",
           "−": b"\x81\x7c", "-": b"\x81\x7c", "＆": b"\x81\x95", "？": b"\x81\x48",
           "：": b"\x81\x46", "！": b"\x81\x49", "、": b"\x81\x41", "。": b"\x81\x42"}

def enc_kr(txt):
    """한글/ASCII/특수 → 셸 인코딩. 실패 시 None."""
    out = bytearray()
    for ch in txt:
        if "가" <= ch <= "힣":
            c = krmap.get(ch)
            if c is None:
                return None
            out += bytes((c >> 8, c & 0xFF))
        elif ch in SPECIAL:
            out += SPECIAL[ch]
        elif ord(ch) < 0x80 and ch not in "()-":
            out.append(ord(ch))
        else:
            try:
                out += ch.encode("shift_jis")
            except Exception:
                return None
    return bytes(out)

def main():
    print("복사:", DST)
    shutil.copyfile(SRC, DST)
    f = open(DST, "r+b")
    toc = A.load_toc()
    db = json.load(open(os.path.join(W, "db.json"), encoding="utf-8"))

    # ---------- 1) 포즈 섹션 4종 ----------
    PAUSE = [(4603, 0x728c0), (4604, 0x72da0), (4605, 0x4ce60), (4606, 0x4d6a0)]
    new19 = enc_kr("리줌")
    assert new19
    for idx, base in PAUSE:
        sec = next(d for d in db if d["idx"] == idx and d["base"] == base)
        e = toc[idx]
        csize, count, tbloff = sec["csize"], sec["count"], sec["tbloff"]
        lo = A.DATA_OFF + e["off"] + base
        f.seek(lo)
        cur = bytearray(f.read(max(csize, 0x4000)))
        tbl = list(struct.unpack_from(f"<{count}I", cur, tbloff))
        def gs(off):
            i = off
            while cur[i] != 0: i += 1
            return bytes(cur[off:i])
        def fix_space(b):
            o = bytearray(); i = 0
            while i < len(b):
                c = b[i]
                if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
                    o += b[i:i+2]; i += 2
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
                data = new19
            else:
                data = gs(tbl[slot])
                if data != orig[slot] and b"\x20" in data:
                    d2 = fix_space(data)
                    if d2 != data: nfix += 1
                    data = d2
            if data in om:
                nt[slot] = om[data]; continue
            o = h0 + len(heap)
            assert o + len(data) + 1 <= limit, f"idx{idx} 오버플로 slot{slot}"
            om[data] = o; nt[slot] = o
            heap += data + b"\x00"
        for slot, o in nt.items():
            struct.pack_into("<I", cur, tbloff + slot * 4, o)
        cur[h0:limit] = heap + bytes(limit - h0 - len(heap))
        f.seek(lo); f.write(cur[:limit])
        print(f"포즈 idx{idx}: slot19=리줌, 공백치환 {nfix}건, 힙 {len(heap)}/{limit-h0}B")

    # ---------- 2) FNM 테이블 ----------
    tl = {}
    for p in sorted(glob.glob(os.path.join(W, "tl", "*.json"))):
        tl.update(json.load(open(p, encoding="utf-8")))
    tw = json.load(open(os.path.join(W, "tl_weapons.json"), encoding="utf-8"))
    lut = dict(tl); lut.update(tw)

    def txt_ok(seg):
        if not (3 <= len(seg) <= 60):
            return False
        try:
            t = seg.decode("shift_jis")
        except Exception:
            return False
        for ch in t:
            o = ord(ch)
            if (0x30A0 <= o <= 0x30FF or 0x3040 <= o <= 0x309F or 0x4E00 <= o <= 0x9FFF
                or 0xFF00 <= o <= 0xFF5E or ch in "・･ー〜 　（）？！―−、。"
                or 0x20 <= o <= 0x7E):
                continue
            return False
        return True

    n_pat = n_fitfail = n_notl = n_encfail = 0
    fitfails = set(); notls = set()
    src_ro = open(A.ISO, "rb")   # 세그먼트 열거는 원본 기준(이미 패치된 문자열 재열거 방지)
    for eidx, e in enumerate(toc):
        if e["size"] < 0x100 or e["size"] > 0x2000000:
            continue
        src_ro.seek(A.DATA_OFF + e["off"])
        data = src_ro.read(e["size"])
        p = 0
        while True:
            m = data.find(b"\x00FNM\x00", p)
            if m < 0: break
            en = data.find(b"END", m)
            if en < 0 or en - m > 0x100:
                p = m + 4; continue
            targets = []   # (abs_in_entry, seg_bytes)
            pos = m + 5
            for seg in data[m+5:en].split(b"\x00"):
                if len(seg) >= 3 and txt_ok(seg):
                    targets.append((pos, seg))
                pos += len(seg) + 1
            q = m
            while True:
                r = q
                nulls = 0
                while r > 0 and data[r-1] == 0 and nulls < 16:
                    r -= 1; nulls += 1
                r2 = r - 1
                while r2 >= 0 and data[r2] != 0:
                    r2 -= 1
                seg = data[r2+1:r]
                if seg and txt_ok(seg):
                    targets.append((r2 + 1, seg))
                    q = r2
                else:
                    break
            for off, seg in targets:
                jp = seg.decode("shift_jis")
                kr = lut.get(jp)
                if not kr or kr == jp:
                    if jp != "−−−":
                        n_notl += 1; notls.add(jp)
                    continue
                enc = enc_kr(kr)
                if enc is None:
                    n_encfail += 1
                    print("  인코딩 실패:", repr(kr))
                    continue
                if len(enc) > len(seg):
                    n_fitfail += 1; fitfails.add(f"{jp}->{kr}")
                    continue
                abs_off = A.DATA_OFF + e["off"] + off
                f.seek(abs_off)
                f.write(enc + b"\x00" * (len(seg) - len(enc)))
                n_pat += 1
            p = en
    print(f"FNM 패치 {n_pat}건, 길이초과 {n_fitfail}종, 번역없음 {n_notl}건, 인코딩실패 {n_encfail}")
    for x in sorted(fitfails):
        print("  길이초과:", x)
    if notls:
        print("  번역없음 목록:", sorted(notls)[:30])
    f.flush(); os.fsync(f.fileno()); f.close()
    print("완료:", DST)

if __name__ == "__main__":
    main()
