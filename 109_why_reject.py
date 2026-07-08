# -*- coding: utf-8 -*-
"""try_parse가 0x120ba0(操作/確認 헤더 컨테이너)를 거부하는 이유 진단"""
import sys, struct
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

f = open(A.ISO, "rb")
toc = A.load_toc()
b = A.read_entry(f, toc[8780])

for base in (0x120ba0, 0x11fd00, 0x1216a0):
    magic, csize = struct.unpack_from("<II", b, base)
    count, tbloff = struct.unpack_from("<II", b, base + 0x10)
    print(f"\nbase={base:#x}: magic={magic:#x} csize={csize:#x} count={count} tbloff={tbloff:#x}")
    if magic != 0x10000:
        print("  reject: magic"); continue
    if not (0 < count < 100000) or tbloff != 0x28:
        print("  reject: count/tbloff"); continue
    tbl_end = tbloff + count * 4
    offs = struct.unpack_from(f"<{count}I", b, base + tbloff)
    nz = [o for o in offs if o]
    print(f"  tbl_end={tbl_end:#x} nz={len(nz)} min={min(nz) if nz else 0:#x} max={max(nz) if nz else 0:#x} csize+16={csize+16:#x}")
    if nz and min(nz) < tbl_end:
        print(f"  reject: min({min(nz):#x}) < tbl_end({tbl_end:#x})")
    if nz and max(nz) >= csize + 16:
        print(f"  reject: max({max(nz):#x}) >= csize+16({csize+16:#x})")
    # 정렬 검사
    prev = 0; bad = False
    for o in nz:
        if o < prev: bad = True; break
        prev = o
    if bad:
        print("  reject: 오프셋 비정렬(내림차순 존재)")
    # 디코드 성공률
    ok = 0; tot = 0
    for o in nz:
        end = b.find(b"\x00", base + o, base + csize + 16)
        if end < 0:
            print("  reject: null 없음"); break
        raw = b[base+o:end]; tot += 1
        try:
            raw.decode("shift_jis"); ok += 1
        except Exception:
            pass
    if tot:
        print(f"  디코드 {ok}/{tot} ({ok/tot:.2f}) — 임계 0.85")
