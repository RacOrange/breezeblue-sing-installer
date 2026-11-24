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

    def log(*items):
        print(*items, flush=True)

    def allow(pid):
        try:
            ctypes.windll.user32.AllowSetForegroundWindow(pid)
        except Exception:
            pass

    ok = voice_reply.deliver(args.root, args.text, args.hwnd, lambda: args.chat, log,
                             allow_foreground=allow)
    print(json.dumps({'ok': bool(ok)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
