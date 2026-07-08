# -*- coding: utf-8 -*-
"""try_parse 완화(구조검증) 영향 측정.
(1) 타깃 컨테이너 0x120ba0가 이제 통과하는지
(2) 전역: 구조OK지만 strict디코드 실패한 '새로 잡히는' 문자열 표본
"""
import sys, struct, collections
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import ace3lib as A

f = open(A.ISO, "rb")
toc = A.load_toc()

# (1) 타깃 엔트리 8780의 0x120ba0
b = A.read_entry(f, toc[8780])
r = A.try_parse(b, 0x120ba0)
print(f"[1] 0x120ba0 try_parse: {'PASS' if r else 'REJECT'}")
if r:
    hdrs = []
    for slot, o, raw in r["strs"][:40]:
        hdrs.append(A.decode_tagged(raw))
    print(f"    count={r['count']} 문자열 표본:")
    for h in hdrs[:20]:
        print(f"      {h!r}")

# (2) 전역 스캔: 새로 잡히는(구조OK ∧ strict실패) 문자열 통계
new_ct = 0
sec_ct = 0
str_ct = 0
examples = []
weird = []   # 구조OK지만 사람이 보기에 텍스트 같지 않은 것(휴리스틱: 한글/카나/한자/ASCII영숫자 비율 낮음)
for i, e in enumerate(toc):
    try:
        buf = A.read_entry(f, e)
    except Exception:
        continue
    for sec in A.scan_entry_sections(buf):
        sec_ct += 1
        for slot, o, raw in sec["strs"]:
            str_ct += 1
            try:
                raw.decode("shift_jis")
                strict = True
            except Exception:
                strict = False
            if not strict:
                new_ct += 1
                if len(examples) < 40:
                    examples.append(A.decode_tagged(raw))
print(f"\n[2] 전역 섹션={sec_ct} 문자열={str_ct} / strict실패(새로판정ok)={new_ct}")
print("    새로 잡힌 문자열 표본:")
for ex in examples[:40]:
    print(f"      {ex!r}")
