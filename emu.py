# -*- coding: utf-8 -*-
"""공용: PCSX2 실행/캡처/키입력 (사용자 지정 에뮬 경로)"""
import ctypes, time, os, subprocess
ctypes.windll.user32.SetProcessDPIAware()
from ctypes import wintypes
from PIL import Image

EXE = r"C:\Users\OXP2\Desktop\슈퍼로봇대전 2차, 3파 알파 hd버전\pcsx2-v1.7.4005-windows-64bit-AVX2-Qt\pcsx2-qt.exe"
W = r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3"
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
VK = {"v": 0x56, "x": 0x58, "z": 0x5A, "s": 0x53, "a": 0x41,
      "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
      "enter": 0x0D, "back": 0x08, "esc": 0x1B, "f1": 0x70}

def launch(iso):
    return subprocess.Popen([EXE, "-nofullscreen", "-fastboot", "--", os.path.join(W, iso)])

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
kernel32 = ctypes.windll.kernel32

def _pid_exe(pid):
    """pid의 실행파일 경로. 접근 실패 시 None (다른 사용자 프로세스 등)."""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return None
    finally:
        kernel32.CloseHandle(h)

def find_hwnd(pid=None):
    """PCSX2 게임 창 탐색. 창 제목만으로는 브라우저 탭 등과 오탐될 수 있어
    소유 프로세스가 pcsx2-qt.exe인지 반드시 함께 확인한다(2026-07-08 오탐 사고).
    pid를 알면(launch()의 Popen.pid) 그 프로세스 소유 창만 매칭해 더 정확히 특정."""
    res = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        b = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, b, n + 1)
        if "Another Century" not in b.value:
            return True
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if pid is not None and wpid.value != pid:
            return True
        exe = _pid_exe(wpid.value)
        if not exe or "pcsx2" not in exe.lower():
            return True
        res.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return res[0] if res else None

def focus(hwnd):
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.8)

def press(key, hold=0.15):
    vk = VK[key]
    user32.keybd_event(vk, 0, 0, 0); time.sleep(hold)
    user32.keybd_event(vk, 0, 2, 0); time.sleep(0.35)

def shot(hwnd, name):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)
    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                    ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32), ("x", ctypes.c_int32),
                    ("y", ctypes.c_int32), ("a", ctypes.c_uint32), ("b", ctypes.c_uint32)]
    bi = BMIH(ctypes.sizeof(BMIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBX", (w, h), buf, "raw", "BGRX")
    img.convert("RGB").save(os.path.join(W, name))
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
    print("shot", name)
