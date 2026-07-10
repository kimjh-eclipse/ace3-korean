# -*- coding: utf-8 -*-
"""ACE3 한국어화 공용 라이브러리"""
import struct, json, os

ISO = r"C:\Emul\Switch\패치유틸.xdeltaUI\Another Century's Episode 3 - The Final (Japan).iso"
SECT = 2048
DATA_LBA = 2117
DATA_OFF = DATA_LBA * SECT
ELF_LBA = 439
ELF_SIZE = 2744880
W = r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3"

def load_toc():
    return json.load(open(os.path.join(W, "bnd_toc.json")))

def read_entry(f, e):
    f.seek(DATA_OFF + e["off"])
    return f.read(e["size"])

# ---------- 문자열 컨테이너 ----------
def _sjis_structural_ok(raw):
    """코덱 매핑 없이 SJIS 바이트 구조만 검증(버튼아이콘 등 미정의 2바이트 허용).
    랜덤 바이너리는 유효하지 않은 lead/trail로 거의 항상 탈락."""
    i = 0
    L = len(raw)
    while i < L:
        c = raw[i]
        if c < 0x80 or 0xA1 <= c <= 0xDF:
            i += 1
            continue
        if not (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC):
            return False
        if i + 1 >= L:
            return False
        t = raw[i + 1]
        if not (0x40 <= t <= 0x7E or 0x80 <= t <= 0xFC):
            return False
        i += 2
    return True

def try_parse(buf, base):
    """0x00010000 문자열 테이블. 성공: dict, 실패: None"""
    if base + 0x30 > len(buf):
        return None
    magic, csize = struct.unpack_from("<II", buf, base)
    if magic != 0x10000 or csize < 0x30 or base + csize > len(buf) + 16:
        return None
    count, tbloff = struct.unpack_from("<II", buf, base + 0x10)
    # tbloff는 보통 0x28이지만, 헤더가 더 큰 변종(0x34 등)도 존재한다(2026-07-08 발견:
    # 오프닝/미션목표 컨테이너 다수가 이 변종이라 tbloff==0x28 고정 검사에 전량 누락됐었음).
    # 2026-07-08 2차: 화자명 테이블(count 637, tbloff 0x250)이 0x200 상한에 걸려 상향(0x1000).
    if not (0 < count < 100000) or not (0x10 <= tbloff <= 0x1000) or tbloff % 4:
        return None
    tbl_end = tbloff + count * 4
    if base + tbl_end > len(buf):
        return None
    offs = struct.unpack_from(f"<{count}I", buf, base + tbloff)
    nz = [o for o in offs if o]
    if not nz:
        return None
    if min(nz) < tbl_end or max(nz) >= csize + 16:
        return None
    prev = 0
    for o in nz:
        if o < prev:
            return None
        prev = o
    strs = []
    ok = 0
    for slot, o in enumerate(offs):
        if not o:
            continue
        end = buf.find(b"\x00", base + o, base + csize + 16)
        if end < 0:
            return None
        raw = buf[base + o:end]
        if _sjis_structural_ok(raw):
            ok += 1
        strs.append((slot, o, raw))
    if strs and ok < len(strs) * 0.85:
        return None
    return {"base": base, "csize": csize, "count": count,
            "tbloff": tbloff, "offs": offs, "strs": strs}

def scan_entry_sections(buf):
    secs = []
    pos = 0
    while pos + 0x30 <= len(buf):
        r = try_parse(buf, pos)
        if r:
            secs.append(r)
            pos = pos + ((r["csize"] + 15) // 16 * 16)
        else:
            pos += 16
    return secs

# ---------- 태그 디코드/인코드 (바이트 보존) ----------
def decode_tagged(raw):
    """SJIS + 비표준 2바이트를 ⟦XXXX⟧ 플레이스홀더로"""
    out = []
    i = 0
    L = len(raw)
    while i < L:
        c = raw[i]
        if c < 0x80:
            out.append(chr(c))
            i += 1
        elif 0xA1 <= c <= 0xDF:  # 반각 가나
            out.append(raw[i:i+1].decode("shift_jis"))
            i += 1
        else:
            pair = raw[i:i+2]
            if len(pair) < 2:
                out.append(f"⟦{c:02X}⟧")
                i += 1
                continue
            try:
                out.append(pair.decode("shift_jis"))
            except Exception:
                out.append(f"⟦{pair[0]:02X}{pair[1]:02X}⟧")
            i += 2
    return "".join(out)

# Shift-JIS로 못 가는 문자 → 대체(전각/카나 중점 등으로 정규화)
_SJIS_FIX = {
    "·": "・",  # · 라틴 중점 → ・ 카나 중점
    "•": "・",  # • 불릿 → ・
    "‧": "・",
    "～": "〜",  # ～ 전각틸드 변형
    "‑": "‐",  # 비분리 하이픈 → 하이픈
    "–": "―", "—": "―",  # en/em dash → 전각 대시
    "×": "ｘ" if False else "×",  # × 그대로(SJIS 있음)
    "…": "…",  # … (SJIS 있음)
    "－": "−", "～": "〜",  # FF0D/FF5E 전각 → SJIS 등가
    # 2026-07-08: 셸폰트에 글리프 없는 반각 부호 → 전각 등가(폰트 보유) 치환.
    # 고빈도 . ! 은 크기 보존 위해 치환하지 않고 폰트에 싱글톤 레인지로 주입한다.
    "~": "〜", ":": "：", "'": "’", "#": "＃",
    "『": "「", "』": "」",
    "A": "Ａ", "B": "Ｂ", "C": "Ｃ", "D": "Ｄ", "E": "Ｅ", "F": "Ｆ",
    "G": "Ｇ", "H": "Ｈ", "I": "Ｉ", "J": "Ｊ", "K": "Ｋ", "L": "Ｌ",
    "M": "Ｍ", "N": "Ｎ", "O": "Ｏ", "P": "Ｐ", "Q": "Ｑ", "R": "Ｒ",
    "S": "Ｓ", "T": "Ｔ", "U": "Ｕ", "V": "Ｖ", "W": "Ｗ", "X": "Ｘ",
    "Y": "Ｙ", "Z": "Ｚ",
}
def _sjis_safe_char(ch):
    ch = _SJIS_FIX.get(ch, ch)
    try:
        ch.encode("shift_jis")
        return ch
    except Exception:
        # 최후: 물음표 대신 유사 대체 없으면 공백
        return "?"

def encode_tagged(text, kr_map=None, kr_assign=None):
    """텍스트 → SJIS 바이트. 한글은 kr_map(음절→코드)로, ⟦XXXX⟧는 원시 바이트로.
    kr_assign: callable(ch)->code, 새 음절 등장 시 코드 할당"""
    out = bytearray()
    i = 0
    L = len(text)
    while i < L:
        ch = text[i]
        if ch == "⟦":
            j = text.index("⟧", i)
            hx = text[i+1:j]
            out += bytes.fromhex(hx)
            i = j + 1
            continue
        if kr_map is not None and ch in kr_map:
            code = kr_map[ch]
            out += bytes([code >> 8, code & 0xFF])
            i += 1
            continue
        if "가" <= ch <= "힣":
            code = None
            if kr_map is not None:
                code = kr_map.get(ch)
            if code is None and kr_assign is not None:
                code = kr_assign(ch)
            if code is None:
                raise ValueError(f"no code for {ch!r}")
            out += bytes([code >> 8, code & 0xFF])
            i += 1
            continue
        out += _sjis_safe_char(ch).encode("shift_jis")
        i += 1
    return bytes(out)

# ---------- 폰트 ----------
FONT_MAP_IDX = 4   # id35
FONT_TEX_IDX = 5   # id36
TEX_PIX_OFF = 0x20
MET_OFF = 0x218
TEX_W, TEX_H = 1024, 512

def load_font(f, toc):
    b35 = bytearray(read_entry(f, toc[FONT_MAP_IDX]))
    b36 = bytearray(read_entry(f, toc[FONT_TEX_IDX]))
    nrange, nglyph = struct.unpack_from("<HH", b35, 0x10)
    ranges = []
    for i in range(nrange):
        a, z, idx = struct.unpack_from("<III", b35, 0x20 + i*12)
        ranges.append((a, z, idx))
    return b35, b36, ranges, nglyph

def kanji_codes(ranges):
    """한자 레인지(0x889F~)의 (code, glyph_idx) 나열"""
    out = []
    for a, z, idx in ranges:
        if a >= 0x889F:
            for k in range(z - a + 1):
                out.append((a + k, idx + k))
    return out

def get_metric(b35, gi):
    u0, v0, u1, v1 = struct.unpack_from("<4f", b35, MET_OFF + gi*24)
    w16 = struct.unpack_from("<4H", b35, MET_OFF + gi*24 + 16)
    return u0, v0, u1, v1, w16

def set_metric(b35, gi, x0, y0, x1, y1, ofs, w, adv):
    struct.pack_into("<4f", b35, MET_OFF + gi*24,
                     x0 / TEX_W, y0 / TEX_H, x1 / TEX_W, y1 / TEX_H)
    struct.pack_into("<4H", b35, MET_OFF + gi*24 + 16, ofs, w, adv, 0)

def tex_putpixel(b36, x, y, v):
    i = TEX_PIX_OFF + y * (TEX_W // 2) + x // 2
    b = b36[i]
    if x % 2 == 0:
        b36[i] = (b & 0xF0) | (v & 15)
    else:
        b36[i] = (b & 0x0F) | ((v & 15) << 4)

def tex_getpixel(b36, x, y):
    i = TEX_PIX_OFF + y * (TEX_W // 2) + x // 2
    b = b36[i]
    return (b & 15) if x % 2 == 0 else (b >> 4)
