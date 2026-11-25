# -*- coding: utf-8 -*-
"""调用鲸鲸桥接的 TTS 发送逻辑（在鲸鲸 runtime python 下运行）。"""
import argparse
import ctypes
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--chat', required=True)
    ap.add_argument('--hwnd', type=int, required=True)
    ap.add_argument('--text', required=True)
    args = ap.parse_args()
    sys.path.insert(0, os.path.join(args.root, 'bridge'))
    import voice_reply
    import uiautomation as auto

    if args.chat != '文件传输助手':
        return 2

    def verified_chat():
        user32 = ctypes.windll.user32
        if user32.GetForegroundWindow() != args.hwnd:
            return ''
        window = auto.ControlFromHandle(args.hwnd)
        for control, _level in auto.WalkControl(window, includeTop=True, maxDepth=12):
            if control.ClassName != 'mmui::ChatTitleBarChatSingleView':
                continue
            for label, _child in auto.WalkControl(control, includeTop=True, maxDepth=4):
                if str(label.Name or '').strip() == args.chat:
                    return args.chat
        return ''

    def log(*items):
        print(*items, flush=True)

    def allow(pid):
        try:
            ctypes.windll.user32.AllowSetForegroundWindow(pid)
        except Exception:
            pass

    if not verified_chat():
        return 2
    outcome = {}
    ok = voice_reply.deliver(args.root, args.text, args.hwnd, verified_chat, log,
                             allow_foreground=allow, outcome=outcome)
    confirmed = bool(ok and outcome.get('Status') == 'sent_unconfirmed')
    print(json.dumps({'ok': confirmed}, ensure_ascii=False))
    return 0 if confirmed else 2


if __name__ == '__main__':
    sys.exit(main())
