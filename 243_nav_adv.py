# -*- coding: utf-8 -*-
"""새 캠페인 프롤로그의 ADV 대화 UI(전투 후 대화와 동일 폰트 4614) 캡처.
타이틀 START → 로드 확인 '아니오' → 메인메뉴(기본 컨티뉴) → 위로 → 캠페인 → 새로 시작.
사용: python 243_nav_adv.py <iso> <프리픽스>"""
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
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    user32.SetCursorPos(cx, cy)
    time.sleep(0.2)
    user32.mouse_event(2, 0, 0, 0, 0)
    time.sleep(0.08)
    user32.mouse_event(4, 0, 0, 0, 0)
    time.sleep(0.5)

def force_focus(hwnd):
    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return
    cur = kernel32.GetCurrentThreadId()
    ft = user32.GetWindowThreadProcessId(fg, None)
    tt = user32.GetWindowThreadProcessId(hwnd, None)
    user32.AttachThreadInput(cur, ft, True)
    user32.AttachThreadInput(cur, tt, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.AttachThreadInput(cur, ft, False)
    user32.AttachThreadInput(cur, tt, False)
    time.sleep(0.4)

_press = emu.press
def press_focused(k, hold=0.15):
    force_focus(HWND)
    _press(k, hold)
emu.press = press_focused

iso, pref = sys.argv[1], sys.argv[2]
subprocess.run(["taskkill", "/f", "/im", "pcsx2-qt.exe"], capture_output=True)
time.sleep(2)
emu.launch(iso)
time.sleep(30)
hwnd = emu.find_hwnd()
print("hwnd", hwnd)
if not hwnd:
    sys.exit(1)
HWND = hwnd
click_focus(hwnd)

emu.press("v"); time.sleep(7)     # 무비 스킵 -> 타이틀
emu.press("v"); time.sleep(6)     # START -> 로드 확인
emu.press("z"); time.sleep(4)     # 아니오 -> 메인메뉴(컨티뉴 선택 상태)
emu.press("up"); time.sleep(1.5)  # 캠페인으로
emu.shot(hwnd, f"{pref}_menu.png")
emu.press("x"); time.sleep(4)
emu.shot(hwnd, f"{pref}_c1.png")
emu.press("x"); time.sleep(6)     # 새로 시작 확인(있다면)
emu.shot(hwnd, f"{pref}_c2.png")
emu.press("x"); time.sleep(8)
emu.shot(hwnd, f"{pref}_c3.png")
emu.press("v"); time.sleep(8)     # 오프닝 무비 스킵
emu.shot(hwnd, f"{pref}_c4.png")
for i in range(12):
    time.sleep(5)
    emu.shot(hwnd, f"{pref}_adv{i}.png")
    emu.press("x"); time.sleep(1)
print("done")
