# -*- coding: utf-8 -*-
"""把本地 wav 发成微信语音：打开/核验会话 → 按住 Ctrl+Tab → 播进 CABLE Input → 松开。

由插件或旧桥接调用；退出码 0 表示观察到新语音条，2 表示录音前失败，3 表示送达不确定。
"""
import argparse
import ctypes
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import sounddevice as sd
import numpy as np
import soundfile as sf
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
kernel32.CreateMutexW.restype = ctypes.c_void_p
kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
kernel32.ReleaseMutex.argtypes = (ctypes.c_void_p,)
kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
VK_CONTROL = 0x11
VK_TAB = 0x09
KEYUP = 0x0002
WECHAT_CLASS = 'mmui::MainWindow'


def log(msg):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


def find_window():
    root = auto.GetRootControl()
    windows = []
    for c in root.GetChildren():
        try:
            if c.ClassName == WECHAT_CLASS:
                windows.append(c)
        except Exception:
            pass
    return windows[0] if len(windows) == 1 else None


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


def session_matches(win, title, chat_type):
    matches = []
    for c in walk(win):
        try:
            if c.ClassName == 'mmui::ChatSessionCell' and title_matches(c.Name, title, chat_type):
                matches.append(c)
        except Exception:
            pass
    return matches


def find_class(win, cls):
    for c in walk(win):
        try:
            if (c.ClassName or '') == cls:
                return c
        except Exception:
            pass
    return None


def title_matches(actual, wanted, chat_type):
    actual = str(actual or '').strip()
    wanted = str(wanted or '').strip()
    if not actual or not wanted:
        return False
    if actual == wanted:
        return True
    if chat_type != 'group':
        return False
    # 只忽略群标题末尾的成员人数，避免将同名前缀的会话视为目标。
    return bool(re.fullmatch(re.escape(wanted) + r'\s*(?:\([0-9]+\)|（[0-9]+）)', actual))


def title_ok(win, title, chat_type):
    bar = find_class(win, 'mmui::ChatTitleBarChatSingleView')
    if not bar:
        return False
    for c in walk(bar, 400):
        try:
            if title_matches(c.Name, title, chat_type):
                return True
        except Exception:
            pass
    return False


def wait_title(win, title, chat_type, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if title_ok(win, title, chat_type):
            return True
        time.sleep(0.2)
    return False


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


def voice_items(win, field):
    try:
        box = field.BoundingRectangle
        left, right = int(box.left), int(box.right)
    except Exception:
        return {}
    if right - left < 180:
        return {}
    items = {}
    for control in walk(win):
        try:
            if control.ClassName != 'mmui::ChatVoiceItemView':
                continue
            identity = tuple(control.GetRuntimeId())
            rect = control.BoundingRectangle
            start, end = int(rect.left), int(rect.right)
            if not identity or not left <= start < end <= right:
                continue
            name = str(control.Name or '').strip()
            # 只有完全处在聊天区右半边、靠近右侧锚点的语音气泡才有资格确认。
            outgoing = start >= (left + right) / 2 and right - end <= (right - left) * 0.25
            items[identity] = (name, outgoing)
        except Exception:
            pass
    return items


def has_new_voice(before, after, duration):
    for identity in after.keys() - before.keys():
        name, outgoing = after[identity]
        matched = re.search(r'(\d+)\s*["″”秒]', name)
        if outgoing and matched and abs(int(matched.group(1)) - duration) <= 2:
            return True
    return False


def account_ready():
    try:
        with urlopen('http://127.0.0.1:8787/api/status', timeout=3) as response:
            data = json.load(response)
        for gateway in data.get('gateways', []):
            if gateway.get('platform') == 'wechat':
                bridge = gateway.get('bridge') or {}
                return bool(bridge.get('online') and bridge.get('uia')
                            and bridge.get('accountOk') is True and bridge.get('accountGuard') is True)
    except (OSError, ValueError, TypeError):
        pass
    return False


def send(args, attempt):
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
        candidates = session_matches(win, args.chat, args.chat_type)
        if len(candidates) > 1:
            log('FAIL 有多个同名会话')
            return 2
        if not title_ok(win, args.chat, args.chat_type):
            if len(candidates) != 1:
                log('FAIL 会话列表里没有唯一匹配项')
                return 2
            candidates[0].Click()
            if not wait_title(win, args.chat, args.chat_type):
                log('FAIL 标题栏与目标不一致')
                return 2
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
    # 给微信录音留出启动/收尾缓冲，避免前后被切
    lead = np.zeros((int(sr * 0.8),) + data.shape[1:], dtype='float32')
    tail = np.zeros((int(sr * 0.6),) + data.shape[1:], dtype='float32')
    data = np.concatenate([lead, data, tail], axis=0)
    fade = min(int(sr * 0.05), max(0, len(data) // 2))
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade, dtype='float32')
        if data.ndim > 1:
            data[:fade] *= ramp[:, None]
            data[-fade:] *= ramp[::-1][:, None]
        else:
            data[:fade] *= ramp
            data[-fade:] *= ramp[::-1]
    duration = len(data) / float(sr)
    if duration > 59:
        log('FAIL 音频 %.1fs 超过微信 60 秒上限' % duration)
        return 2

    if args.result_file and not account_ready():
        log('FAIL 微信绑定账号未通过核验')
        return 2
    before = voice_items(win, field)
    if user32.GetForegroundWindow() != hwnd or (
        not args.trusted and not title_ok(win, args.chat, args.chat_type)
    ):
        log('FAIL 开始录音前目标会话或前台变化')
        return 2
    # 从发送按键开始起，异常只能记作送达不确定。
    attempt['recording'] = True
    control_held = tab_held = False
    try:
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        control_held = True
        time.sleep(0.12)
        user32.keybd_event(VK_TAB, 0, 0, 0)
        tab_held = True
        time.sleep(0.4)
        sd.play(data, sr, device=dev, blocking=False)
        next_target_check = time.monotonic()
        while sd.get_stream().active:
            now = time.monotonic()
            if user32.GetForegroundWindow() != hwnd or (
                now >= next_target_check and not args.trusted and not title_ok(win, args.chat, args.chat_type)
            ):
                sd.stop()
                log('UNCERTAIN 播放中会话或前台变化，已停止音频')
                return 3
            if now >= next_target_check:
                next_target_check = now + 0.5
            time.sleep(0.05)
        sd.wait()
        time.sleep(max(0.0, args.hold_extra))
    finally:
        try:
            sd.stop()
        except Exception:
            pass
        if tab_held:
            user32.keybd_event(VK_TAB, 0, KEYUP, 0)
            time.sleep(0.05)
        if control_held:
            user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)

    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        if user32.GetForegroundWindow() != hwnd or (
            not args.trusted and not title_ok(win, args.chat, args.chat_type)
        ):
            break
        if has_new_voice(before, voice_items(win, field), duration):
            log('OK 已发送（音频 %.1fs）' % duration)
            return 0
        time.sleep(0.25)
    log('UNCERTAIN 未观察到与本次音频匹配的新语音条')
    return 3


def write_result(path, status):
    result = Path(path)
    temporary = result.with_name(result.name + f'.{os.getpid()}.tmp')
    try:
        try:
            request = json.loads(result.read_text(encoding='utf-8')).get('request', '')
        except (OSError, ValueError):
            request = ''
        temporary.write_text(json.dumps({'status': status, 'request': request}), encoding='utf-8')
        os.replace(temporary, result)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wav', required=True)
    ap.add_argument('--chat', required=True)
    ap.add_argument('--chat-type', choices=('private', 'group'), default='group')
    ap.add_argument('--result-file')
    ap.add_argument('--trusted', action='store_true',
                    help='旧桥接 prepare() 已核验会话时使用')
    ap.add_argument('--hold-extra', type=float, default=0.5)
    args = ap.parse_args()
    if args.result_file and args.trusted:
        ap.error('本地插件发送必须核验目标会话')

    # 同一桌面只允许一个翻唱发送器持有录音热键，进程退出后由 Windows 释放。
    mutex = kernel32.CreateMutexW(None, 0, 'Local\\BreezeblueSingVoice')
    acquired = bool(mutex and kernel32.WaitForSingleObject(mutex, 0) in (0, 0x80))
    attempt = {'recording': False}
    code = 2
    try:
        if acquired and (not args.result_file or account_ready()):
            code = send(args, attempt)
        else:
            log('FAIL 语音发送器繁忙或微信绑定账号未核验')
    except Exception:
        code = 3 if attempt['recording'] else 2
        log('UNCERTAIN 录音后异常' if code == 3 else 'FAIL 录音前异常')
    finally:
        if acquired:
            kernel32.ReleaseMutex(mutex)
        if mutex:
            kernel32.CloseHandle(mutex)
        if args.result_file:
            write_result(args.result_file, {0: 'sent', 2: 'failed', 3: 'uncertain'}[code])
    return code


if __name__ == '__main__':
    sys.exit(main())
