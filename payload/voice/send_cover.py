# -*- coding: utf-8 -*-
"""把本地 wav 发成微信语音：打开/核验会话 → 按住 Ctrl+Tab → 播进 CABLE Input → 松开。

由 bridge/cover_voice.py 调用；退出码 0 表示语音条已出现，2 表示失败。
"""
import argparse
import ctypes
import re
import sys
import time

import sounddevice as sd
import soundfile as sf
import uiautomation as auto

user32 = ctypes.windll.user32
VK_CONTROL = 0x11
VK_TAB = 0x09
KEYUP = 0x0002
WECHAT_CLASS = 'mmui::MainWindow'


def log(msg):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


def find_window():
    root = auto.GetRootControl()
    for c in root.GetChildren():
        try:
            if (c.ClassName or '') == WECHAT_CLASS:
                return c
        except Exception:
            pass
    return None


def walk(root, limit=9000):
    q = [root]
    n = 0
    while q and n < limit:
        c = q.pop(0)
        n += 1
        yield c
        try:
            q.extend(c.GetChildren())
        except Exception:
            pass


def find_session(win, title):
    for c in walk(win):
        try:
            if (c.ClassName or '') == 'mmui::ChatSessionCell' and (c.Name or '').startswith(title):
                return c
        except Exception:
            pass
    return None


def find_class(win, cls):
    for c in walk(win):
        try:
            if (c.ClassName or '') == cls:
                return c
        except Exception:
            pass
    return None


def title_matches(actual, wanted):
    a = str(actual or '').strip()
    w = str(wanted or '').strip()
    if not a or not w:
        return False
    if a == w:
        return True
    # 群聊标题常带「(5)」「（5）」成员数后缀，按前缀归一化比较
    if a.startswith(w) or w.startswith(a):
        return True
    return False


def title_ok(win, title):
    bar = find_class(win, 'mmui::ChatTitleBarChatSingleView')
    if not bar:
        return False
    for c in walk(bar, 400):
        try:
            if title_matches(c.Name, title):
                return True
        except Exception:
            pass
    return False


def wait_title(win, title, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if title_ok(win, title):
            return True
        time.sleep(0.4)
    return False


def rect(c):
    r = c.BoundingRectangle
    return int(r.left), int(r.top), int(r.right), int(r.bottom)


def force_foreground(hwnd):
    try:
        user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
    except Exception:
        pass
    for _ in range(4):
        if user32.GetForegroundWindow() == hwnd:
            return True
        try:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            fg = user32.GetForegroundWindow()
            tid_fg = user32.GetWindowThreadProcessId(fg, None)
            tid = user32.GetWindowThreadProcessId(hwnd, None)
            if tid_fg and tid and tid_fg != tid:
                user32.AttachThreadInput(tid_fg, tid, True)
                user32.SetForegroundWindow(hwnd)
                user32.AttachThreadInput(tid_fg, tid, False)
            else:
                user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
        except Exception:
            pass
        time.sleep(0.4)
    return user32.GetForegroundWindow() == hwnd


def cable_output_device():
    for i, d in enumerate(sd.query_devices()):
        if 'CABLE Input' in d['name'] and d['max_output_channels'] > 0:
            return i, d['name']
    return None, None


def voice_items(win):
    out = []
    for c in walk(win):
        try:
            if (c.ClassName or '') == 'mmui::ChatVoiceItemView':
                out.append(((c.Name or ''), rect(c)))
        except Exception:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wav', required=True)
    ap.add_argument('--chat', required=True)
    ap.add_argument('--trusted', action='store_true',
                    help='桥接 prepare() 已核验会话时跳过本脚本的会话核验')
    ap.add_argument('--hold-extra', type=float, default=0.5)
    args = ap.parse_args()

    auto.SetGlobalSearchTimeout(2)
    # 父进程（桥接）会在这段时间里调用 AllowSetForegroundWindow，之后才允许抢前台
    time.sleep(0.8)
    win = find_window()
    if not win:
        log('FAIL 找不到微信主窗口')
        return 2
    hwnd = int(win.NativeWindowHandle)

    win.SetActive()
    time.sleep(0.3)
    if not force_foreground(hwnd):
        log('FAIL 微信无法切到前台（请先点一下微信窗口再试）')
        return 2

    if not args.trusted:
        if not title_ok(win, args.chat):
            cell = find_session(win, args.chat)
            if not cell:
                log('FAIL 会话列表里没有 %r' % args.chat)
                return 2
            opened = False
            for _ in range(2):
                cell.Click()
                time.sleep(1.3)
                if wait_title(win, args.chat, 3.0):
                    opened = True
                    break
            if not opened:
                log('FAIL 标题栏不是 %r' % args.chat)
                return 2
    else:
        log('信任桥接的会话核验，跳过标题检查')
    field = find_class(win, 'mmui::ChatInputField')
    if not field:
        log('FAIL 找不到输入框')
        return 2
    field.Click()
    time.sleep(0.3)
    if not force_foreground(hwnd):
        log('FAIL 微信不在前台')
        return 2

    dev, dev_name = cable_output_device()
    if dev is None:
        log('FAIL 找不到 CABLE Input')
        return 2
    data, sr = sf.read(args.wav, dtype='float32')
    duration = len(data) / float(sr)
    if duration > 59:
        log('FAIL 音频 %.1fs 超过微信 60 秒上限' % duration)
        return 2

    before = voice_items(win)
    held = False
    try:
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.12)
        user32.keybd_event(VK_TAB, 0, 0, 0)
        held = True
        time.sleep(0.4)
        sd.play(data, sr, device=dev, blocking=True)
        time.sleep(max(0.0, args.hold_extra))
    finally:
        if held:
            user32.keybd_event(VK_TAB, 0, KEYUP, 0)
            time.sleep(0.05)
            user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)

    time.sleep(2.5)
    after = voice_items(win)
    if not after:
        log('FAIL 会话里没有语音条')
        return 2
    last = max(after, key=lambda item: item[1][3])
    matched = re.search(r'(\d+)', last[0] or '')
    seconds = int(matched.group(1)) if matched else 0
    if seconds and abs(seconds - duration) > 2:
        log('FAIL 最新语音 %r 与音频 %.1fs 不匹配' % (last[0], duration))
        return 2
    log('OK 已发送 %r（音频 %.1fs）' % (last[0], duration))
    return 0


if __name__ == '__main__':
    sys.exit(main())
