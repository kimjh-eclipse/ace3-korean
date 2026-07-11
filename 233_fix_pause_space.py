# -*- coding: utf-8 -*-
"""포즈 섹션(idx4603 base 0x728c0) 공백 수정: 번역 문자열의 0x20 → 0x8140(전각).
0x20은 미션 셸폰트에 글리프가 없어 ？로 나오고, 하이라이트(선택) 항목 렌더 경로에서
게임이 행에 빠진다(전투 중 START 멈춤 — slot19 '게임으로 돌아가기' 재현·격리 완료).
사용: python 233_fix_pause_space.py <입력iso> <출력iso> [idx] [base16진]"""
import sys, json, struct, shutil
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

def fix_section(src_iso_bytes_reader, out, toc, sec):
    e = toc[sec["idx"]]
    base, csize, count, tbloff = sec["base"], sec["csize"], sec["count"], sec["tbloff"]
    lo = A.DATA_OFF + e["off"] + base
    src_iso_bytes_reader.seek(lo)
    cur = bytearray(src_iso_bytes_reader.read(max(csize, 0x4000)))
    tbl = list(struct.unpack_from(f"<{count}I", cur, tbloff))

    def get_str(data, off):
        i = off
        while data[i] != 0:
            i += 1
        return bytes(data[off:i])

    def sjis_replace_space(b):
        """SJIS 스트림을 리드바이트 인식하며 순회, 1바이트 0x20만 8140으로."""
        out_b = bytearray(); i = 0
        while i < len(b):
            c = b[i]
            if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
                out_b += b[i:i+2]; i += 2
            elif c == 0x20:
                out_b += b"\x81\x40"; i += 1
            else:
                out_b.append(c); i += 1
        return bytes(out_b)

    orig_by_slot = {s["slot"]: bytes.fromhex(s["hex"]) for s in sec["strs"]}
    h0 = min(s["off"] for s in sec["strs"])
    orig_end = max(s["off"] + len(bytes.fromhex(s["hex"])) + 1 for s in sec["strs"])
    limit = max(csize, orig_end)

    heap = bytearray(); offmap = {}; new_tbl = {}
    n_fix = 0
    for s in sec["strs"]:
        slot = s["slot"]
        data = get_str(cur, tbl[slot])
        if data != orig_by_slot[slot] and b"\x20" in data:  # 번역문만 수정
            fixed = sjis_replace_space(data)
            if fixed != data:
                n_fix += 1
            data = fixed
        if data in offmap:
            new_tbl[slot] = offmap[data]; continue
        o = h0 + len(heap)
        if o + len(data) + 1 > limit:
            raise RuntimeError(f"오버플로 idx{sec['idx']} base{base:#x} slot{slot}")
        offmap[data] = o; new_tbl[slot] = o
        heap += data + b"\x00"

    for slot, o in new_tbl.items():
        struct.pack_into("<I", cur, tbloff + slot * 4, o)
    cur[h0:limit] = heap + bytes(limit - h0 - len(heap))
    out.seek(lo); out.write(cur[:limit])
    return n_fix, len(heap), limit - h0

def main():
    src_iso, out_iso = sys.argv[1], sys.argv[2]
    idx = int(sys.argv[3]) if len(sys.argv) > 3 else 4603
    base = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x728c0
    toc = A.load_toc()
    db = json.load(open(A.W + r"\db.json", encoding="utf-8"))
    sec = next(d for d in db if d["idx"] == idx and d["base"] == base)
    if src_iso != out_iso:
        shutil.copyfile(src_iso, out_iso)
    src = open(out_iso, "rb")
    out = open(out_iso, "r+b")
    n, hs, cap = fix_section(src, out, toc, sec)
    out.close()
    print(f"idx{idx} base{base:#x}: {n}개 문자열 공백치환, 힙 {hs}/{cap}B")

if __name__ == "__main__":
    main()
