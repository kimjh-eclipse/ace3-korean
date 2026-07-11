# -*- coding: utf-8 -*-
"""부팅→세이브로드→출격→전투→START(포즈) 자동 재현.
사용: python 231_nav_pause.py <iso> <프리픽스>
r0 수동 탐색으로 확정한 시퀀스. 각 요소 화면을 캡처해 뒤에서 검증."""
import sys, time, ctypes, subprocess
ctypes.windll.user32.SetProcessDPIAware()
sys.path.insert(0, r"C:\Emul\Switch\패치유틸.xdeltaUI\work_ace3")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import emu
from ctypes import wintypes
user32 = ctypes.windll.user32

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

kernel32 = ctypes.windll.kernel32

def force_focus(hwnd):
    """포그라운드를 뺏겼으면 AttachThreadInput으로 되찾는다."""
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

seq = [
    ("v", 7),   # 무비 스킵 -> 타이틀
    ("v", 6),   # START -> 세이브 로드 확인
    ("x", 5),   # 예
    ("x", 3),   # 로드 완료 확인
    ("x", 6),
    ("x", 4),   # 비행조작 프롬프트
    ("z", 4),   # 아니오 -> 인터미션 도움말
    ("x", 3),   # 도움말 닫기
    ("x", 4),   # 출격
    ("x", 6),   # 출격 확정 -> 브리핑
]
for k, w in seq:
    emu.press(k); time.sleep(w)
emu.shot(hwnd, f"{pref}_brief.png")
for i in range(6):
    emu.press("x"); time.sleep(2.5)
emu.press("v"); time.sleep(3)     # 브리핑 종료
emu.press("x"); time.sleep(4)
emu.press("x"); time.sleep(4)     # 승패조건 화면
emu.press("v"); time.sleep(3)     # 종료
emu.press("x"); time.sleep(4)     # 확인 -> 미션 로딩
time.sleep(15)
emu.shot(hwnd, f"{pref}_intro.png")
for i in range(4):
    emu.press("x"); time.sleep(2.5)
emu.press("v"); time.sleep(5)     # 인트로 컷신 종료
emu.press("x"); time.sleep(6)     # 콕핏 데모 종료 예
emu.shot(hwnd, f"{pref}_battle.png")
time.sleep(2)
emu.press("v"); time.sleep(2.5)   # START -> 포즈
emu.shot(hwnd, f"{pref}_pause_a.png")
time.sleep(4)
emu.shot(hwnd, f"{pref}_pause_b.png")
emu.press("down"); time.sleep(1)
emu.press("v"); time.sleep(2)
emu.shot(hwnd, f"{pref}_pause_c.png")
print("done")
