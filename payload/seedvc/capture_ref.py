# -*- coding: utf-8 -*-
"""用鲸鲸现有 Breeze TTS 生成参考音：发给文件传输助手，同时录 CABLE Output。

用法（用 voice venv 的 python 运行）：
  python capture_ref.py --runtime-root D:\\whale-cover --whale-girl "E:\\Program Files\\WhaleGirl"
"""
import argparse
import ctypes
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import uuid

import uiautomation as auto
import numpy as np
import soundcard as sc
import soundfile as sf

TEXT = ('今天过得怎么样，我在家里等你回来。外面风有点大，记得多穿一点，别着凉了。'
        '今天想跟你说一件很开心的事，你回来的时候我们慢慢聊。我最近在学做一道新菜，'
        '等你回来尝尝看。要是你累了，就先休息一会儿，不着急。对了，等你回来的时候，我们一起把阳台上的花浇一下，再商量周末去哪里走走。')
CHAT = '文件传输助手'


def find_hwnd():
    root = auto.GetRootControl()
    for control in root.GetChildren():
        try:
            if (control.ClassName or '') == 'mmui::MainWindow':
                return int(control.NativeWindowHandle)
        except Exception:
            pass
    return 0


def cable_mic():
    mics = [m for m in sc.all_microphones(include_loopback=False) if 'CABLE Output' in m.name]
    if not mics:
        raise RuntimeError('找不到 CABLE Output 设备，请先安装 VB-CABLE')
    return mics[0]


def open_filehelper(whale_girl, timeout=20):
    directory = pathlib.Path(whale_girl) / 'data' / 'voice-send-tests'
    directory.mkdir(parents=True, exist_ok=True)
    request_id = uuid.uuid4().hex
    request = directory / (request_id + '.json')
    request.write_text(json.dumps({'CreatedAt': int(time.time() * 1000)}), encoding='utf-8')
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (directory / (request_id + '.result')).exists():
            return True
        time.sleep(0.5)
    return False


def record_until(stop_event, mic, frames):
    with mic.recorder(samplerate=48000, channels=2, blocksize=4800) as recorder:
        while not stop_event.is_set():
            frames.append(recorder.record(numframes=4800))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime-root', required=True)
    ap.add_argument('--whale-girl', required=True)
    ap.add_argument('--seconds', type=int, default=30)
    args = ap.parse_args()

    out_dir = os.path.join(args.runtime_root, 'ref')
    profiles_dir = os.path.join(out_dir, 'profiles')
    os.makedirs(profiles_dir, exist_ok=True)
    hwnd = find_hwnd()
    if not hwnd:
        raise SystemExit('找不到微信主窗口，请确认微信 4.2 已登录并显示')
    print('hwnd', hwnd, flush=True)
    print('先发送一次短语音，把会话切到文件传输助手…', flush=True)
    if not open_filehelper(args.whale_girl):
        raise SystemExit('语音测试未完成：确认鲸鲸内核/桥接在运行、语音发送已启用')

    mic = cable_mic()
    frames = []
    stop_event = threading.Event()
    recorder = threading.Thread(target=record_until, args=(stop_event, mic, frames), daemon=True)
    recorder.start()
    time.sleep(1.0)

    deliver = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deliver_tts.py')
    runtime_python = os.path.join(args.whale_girl, 'runtime', 'python', 'python.exe')
    if not os.path.exists(runtime_python):
        stop_event.set()
        raise SystemExit('找不到鲸鲸运行时 python：' + runtime_python)
    command = [runtime_python, deliver, '--root', args.whale_girl, '--chat', CHAT,
               '--hwnd', str(hwnd), '--text', TEXT]
    print('开始合成并录音…', flush=True)
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    print(result.stdout.strip()[-500:], flush=True)
    if result.returncode != 0:
        print(result.stderr.strip()[-500:], flush=True)
    time.sleep(1.0)
    stop_event.set()
    recorder.join(timeout=10)

    if not frames:
        raise SystemExit('没有录到音频')
    data = np.concatenate(frames, axis=0)
    raw = os.path.join(out_dir, '_captured_tts.wav')
    sf.write(raw, data, 48000)
    mono = data.mean(axis=1)
    peak = np.abs(mono)
    active = np.where(peak > 0.005)[0]
    if not len(active):
        raise SystemExit('录音是静音：检查默认播放设备是否为 CABLE Input')
    start = max(0, int(active[0]) - 4800)
    end = min(len(mono), int(active[-1]) + 4800)
    clip = data[start:end]
    limit = args.seconds * 48000
    if len(clip) > limit:
        clip = clip[:limit]
    daily = os.path.join(profiles_dir, 'voice_daily.wav')
    sf.write(daily, clip, 48000, subtype='PCM_16')
    profiles = {
        'version': 1,
        'mode': 'installed-voice',
        'default': 'daily',
        'profiles': {emotion: {'file': 'profiles/voice_daily.wav', 'label': label}
                     for emotion, label in [('daily', '日常'), ('happy', '开心'), ('gentle', '温柔'),
                                             ('serious', '认真'), ('sad', '难过'), ('angry', '生气')]},
        'aliases': {'日常': 'daily', '开心': 'happy', '温柔': 'gentle',
                    '认真': 'serious', '难过': 'sad', '生气': 'angry'},
    }
    with open(os.path.join(out_dir, 'profiles.json'), 'w', encoding='utf-8') as handle:
        json.dump(profiles, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'ok': True, 'seconds': round(len(clip) / 48000, 1),
                      'dir': out_dir}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
