#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 OKX_Price.exe 启动后双击退出。"""

import ctypes
import ctypes.wintypes
import sys
import time


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class InputUnion(ctypes.Union):
    _fields_ = [("mi", MouseInput)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", InputUnion)]


MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def find_window(title):
    result = []

    def enum_proc(hwnd, _):
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
            if buffer.value == title:
                result.append(hwnd)
        return True

    EnumWindows = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )
    ctypes.windll.user32.EnumWindows(EnumWindows(enum_proc), None)
    return result[0] if result else None


def enum_child_windows(hwnd):
    result = []

    def enum_proc(hwnd, _):
        result.append(hwnd)
        return True

    EnumChildWindows = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )
    ctypes.windll.user32.EnumChildWindows(
        hwnd, EnumChildWindows(enum_proc), None
    )
    return result


def get_window_text(hwnd):
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def process_exists(pid):
    handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)  # SYNCHRONIZE
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


def get_window_rect(hwnd):
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect


def send_input_click():
    def send(flags):
        inp = INPUT()
        inp.type = 0  # INPUT_MOUSE
        inp.ii.mi = MouseInput(0, 0, 0, flags, 0, 0)
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    send(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.05)
    send(MOUSEEVENTF_LEFTUP)


def move_cursor_to(x, y):
    screen_width = ctypes.windll.user32.GetSystemMetrics(0)
    screen_height = ctypes.windll.user32.GetSystemMetrics(1)
    abs_x = int(x * 65535 / (screen_width - 1))
    abs_y = int(y * 65535 / (screen_height - 1))

    inp = INPUT()
    inp.type = 0
    inp.ii.mi = MouseInput(abs_x, abs_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, 0)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def send_double_click_on_window(hwnd):
    rect = get_window_rect(hwnd)
    # 窗口左上角有名称标签文本，避开透明黑色背景
    x = rect.left + 42
    y = rect.top + 14

    ctypes.windll.user32.SetForegroundWindow(hwnd)
    ctypes.windll.user32.BringWindowToTop(hwnd)
    time.sleep(0.2)
    move_cursor_to(x, y)
    time.sleep(0.1)
    send_input_click()
    time.sleep(0.1)
    send_input_click()


def find_clickable_child(hwnd):
    """找一个包含文本的子控件（标签），用于模拟双击。"""
    for child in enum_child_windows(hwnd):
        text = get_window_text(child)
        if text:
            return child
    return hwnd


def main():
    if len(sys.argv) != 2:
        print("用法: python verify_double_click.py <pid>")
        return 1

    pid = int(sys.argv[1])
    print(f"等待进程 {pid} 创建窗口...")
    hwnd = None
    for _ in range(30):
        hwnd = find_window("OKX Price")
        if hwnd:
            break
        if not process_exists(pid):
            print("进程在创建窗口前已退出。")
            return 1
        time.sleep(0.5)

    if not hwnd:
        print("未找到窗口 'OKX Price'")
        return 1

    print(f"找到窗口 HWND={hwnd}")
    target = find_clickable_child(hwnd)
    print(f"双击目标 HWND={target}, text={get_window_text(target)!r}")
    time.sleep(1)
    print("模拟双击...")
    send_double_click_on_window(target)

    for _ in range(20):
        if not process_exists(pid):
            print("进程已退出，双击退出验证通过。")
            return 0
        time.sleep(0.5)

    print("进程仍未退出，验证失败。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
