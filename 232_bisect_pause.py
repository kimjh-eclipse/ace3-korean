# -*- coding: utf-8 -*-
"""포즈 섹션(idx4603 base 0x728c0) 문자열 이분법용 변형 ISO 생성.
사용: python 232_bisect_pause.py <출력iso> <원복슬롯: 19-40,72 형식>
최종 ISO를 복사한 뒤, 지정 슬롯만 원본(일본어) 바이트로 되돌려 힙을 리팩."""
import sys, json, struct, shutil
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

IDX, BASE = 4603, 0x728c0

def parse_slots(spec):
    out = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-"); out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out

def main():
    out_iso, spec = sys.argv[1], sys.argv[2]
    revert = parse_slots(spec)
    toc = A.load_toc()
    db = json.load(open(A.W + r"\db.json", encoding="utf-8"))
    sec = next(d for d in db if d["idx"] == IDX and d["base"] == BASE)
    e = toc[IDX]
    base, csize, count, tbloff = sec["base"], sec["csize"], sec["count"], sec["tbloff"]

    src = open(A.W + r"\ACE3_KR_caption_full.iso", "rb")
    lo = A.DATA_OFF + e["off"] + base
    src.seek(lo)
    cur = bytearray(src.read(max(csize, 0x4000)))
    tbl = list(struct.unpack_from(f"<{count}I", cur, tbloff))

    def get_str(data, off):
        i = off
        while i < len(data) and data[i] != 0:
            i += 1
        return bytes(data[off:i])

    orig_by_slot = {s["slot"]: bytes.fromhex(s["hex"]) for s in sec["strs"]}
    h0 = min(s["off"] for s in sec["strs"])
    orig_end = max(s["off"] + len(bytes.fromhex(s["hex"])) + 1 for s in sec["strs"])
    limit = max(csize, orig_end)

    heap = bytearray(); offmap = {}
    new_tbl = dict()
    for s in sec["strs"]:
        slot = s["slot"]
        data = orig_by_slot[slot] if slot in revert else get_str(cur, tbl[slot])
        if data in offmap:
            new_tbl[slot] = offmap[data]; continue
        o = h0 + len(heap)
        assert o + len(data) + 1 <= limit, f"오버플로 slot{slot}"
        offmap[data] = o; new_tbl[slot] = o
        heap += data + b"\x00"

    shutil.copyfile(A.W + r"\ACE3_KR_caption_full.iso", out_iso)
    out = open(out_iso, "r+b")
    for slot, o in new_tbl.items():
        struct.pack_into("<I", cur, tbloff + slot * 4, o)
    cur[h0:limit] = heap + bytes(limit - h0 - len(heap))
    out.seek(lo); out.write(cur[:limit])
    out.close()
    print(f"{out_iso}: {len(revert & set(orig_by_slot))}슬롯 원복, 힙 {len(heap)}/{limit-h0}B")

if __name__ == "__main__":
    main()
