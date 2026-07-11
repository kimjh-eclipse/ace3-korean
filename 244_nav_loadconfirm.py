# -*- coding: utf-8 -*-
"""부팅→타이틀 START→로드 화면→세이브 선택→로드 확인 대화 캡처.
사용: python 244_nav_loadconfirm.py <iso> <프리픽스>"""
import sys, time, ctypes, subprocess
ctypes.windll.user32.SetProcessDPIAware()
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import emu
from ctypes import wintypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def click_focus(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    user32.SetForegroundWindow(hwnd); time.sleep(0.3)
    user32.SetCursorPos(cx, cy); time.sleep(0.2)
    user32.mouse_event(2, 0, 0, 0, 0); time.sleep(0.08)
    user32.mouse_event(4, 0, 0, 0, 0); time.sleep(0.5)

def force_focus(hwnd):
    fg = user32.GetForegroundWindow()
    if fg == hwnd: return
    cur = kernel32.GetCurrentThreadId()
    ft = user32.GetWindowThreadProcessId(fg, None)
    tt = user32.GetWindowThreadProcessId(hwnd, None)
    user32.AttachThreadInput(cur, ft, True); user32.AttachThreadInput(cur, tt, True)
    user32.BringWindowToTop(hwnd); user32.SetForegroundWindow(hwnd)
    user32.AttachThreadInput(cur, ft, False); user32.AttachThreadInput(cur, tt, False)
    time.sleep(0.4)

_press = emu.press
def press_focused(k, hold=0.15):
    force_focus(HWND); _press(k, hold)
emu.press = press_focused

iso, pref = sys.argv[1], sys.argv[2]
subprocess.run(["taskkill", "/f", "/im", "pcsx2-qt.exe"], capture_output=True)
time.sleep(2)
emu.launch(iso)
time.sleep(30)
hwnd = emu.find_hwnd()
print("hwnd", hwnd)
if not hwnd: sys.exit(1)
HWND = hwnd
click_focus(hwnd)

emu.press("v"); time.sleep(7)   # 무비 스킵 -> 타이틀
emu.shot(hwnd, f"{pref}_title.png")
emu.press("v"); time.sleep(6)   # START -> 로드 화면
emu.shot(hwnd, f"{pref}_list.png")
emu.press("x"); time.sleep(3)   # 세이브 선택 -> 확인 대화
emu.shot(hwnd, f"{pref}_confirm.png")
subprocess.run(["taskkill", "/f", "/im", "pcsx2-qt.exe"], capture_output=True)
print("done")
