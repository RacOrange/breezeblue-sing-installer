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
from urllib.request import urlopen

import uiautomation as auto
import numpy as np
import soundcard as sc
import soundfile as sf

TEXT = ('今天过得怎么样，我在家里等你回来。外面风有点大，记得多穿一点，别着凉了。'
        '今天想跟你说一件很开心的事，你回来的时候我们慢慢聊。我最近在学做一道新菜，'
        '等你回来尝尝看。要是你累了，就先休息一会儿，不着急。对了，等你回来的时候，我们一起把阳台上的花浇一下，再商量周末去哪里走走。')
CHAT = '文件传输助手'


def find_hwnd():
    handles = [int(control.NativeWindowHandle) for control in auto.GetRootControl().GetChildren()
               if (control.ClassName or '') == 'mmui::MainWindow']
    return handles[0] if len(handles) == 1 else 0


def account_ready():
    try:
        with urlopen('http://127.0.0.1:8787/api/status', timeout=3) as response:
            state = json.load(response)
        bridge = next((item['bridge'] for item in state['gateways'] if item['platform'] == 'wechat'), {})
        return bool(bridge.get('online') and bridge.get('uia')
                    and bridge.get('accountGuard') is True and bridge.get('accountOk') is True)
    except (OSError, ValueError, KeyError, TypeError):
        return False


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
    deadline = time.monotonic() + timeout
    result = directory / (request_id + '.result')
    while time.monotonic() < deadline:
        if result.is_file():
            try:
                return json.loads(result.read_text(encoding='utf-8-sig')).get('Status') == 'sent_unconfirmed'
            except (OSError, ValueError):
                return False
        time.sleep(0.5)
    (directory / (request_id + '.cancel')).touch()
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
    if not account_ready():
        raise SystemExit('鲸鲸桥接或绑定账号未通过核验')
    hwnd = find_hwnd()
    if not hwnd:
        raise SystemExit('找不到微信主窗口，请确认微信 4.2 已登录并显示')
    mic = cable_mic()
    runtime_python = os.path.join(args.whale_girl, 'runtime', 'python', 'python.exe')
    if not os.path.isfile(runtime_python):
        raise SystemExit('找不到鲸鲸运行时 Python')
    print('先验证文件传输助手的测试语音…', flush=True)
    if not open_filehelper(args.whale_girl):
        raise SystemExit('语音测试未完成：确认鲸鲸内核/桥接在运行、语音发送已启用')

    if not account_ready() or find_hwnd() != hwnd:
        raise SystemExit('微信窗口或绑定账号已变化，停止录音')
    frames = []
    stop_event = threading.Event()
    recorder = threading.Thread(target=record_until, args=(stop_event, mic, frames), daemon=True)
    recorder.start()
    time.sleep(1.0)

    deliver = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deliver_tts.py')
    command = [runtime_python, deliver, '--root', args.whale_girl, '--chat', CHAT,
               '--hwnd', str(hwnd), '--text', TEXT]
    print('开始合成并录音…', flush=True)
    try:
        result = subprocess.run(command, capture_output=True, timeout=180)
        if result.returncode != 0:
            raise SystemExit('鲸鲸的参考音语音未完成核验，原参考音保留')
        time.sleep(1.0)
    finally:
        stop_event.set()
        recorder.join(timeout=10)

    if not frames:
        raise SystemExit('没有录到音频')
    data = np.concatenate(frames, axis=0)
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
    if len(clip) < 5 * 48000:
        raise SystemExit('录到的人声太短，原参考音保留')
    # 单独的文件名保留旧参考音，只有新清单成功提交时才切换。
    filename = 'voice_installed_' + uuid.uuid4().hex + '.wav'
    daily = os.path.join(profiles_dir, filename)
    sf.write(daily, clip, 48000, subtype='PCM_16')
    profiles = {
        'version': 1,
        'mode': 'installed-voice',
        'default': 'daily',
        'profiles': {emotion: {'file': 'profiles/' + filename, 'label': label}
                     for emotion, label in [('daily', '日常'), ('happy', '开心'), ('gentle', '温柔'),
                                             ('serious', '认真'), ('sad', '难过'), ('angry', '生气')]},
        'aliases': {'日常': 'daily', '开心': 'happy', '温柔': 'gentle',
                    '认真': 'serious', '难过': 'sad', '生气': 'angry'},
    }
    manifest = pathlib.Path(out_dir) / 'profiles.json'
    temporary = manifest.with_name(manifest.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(manifest)
    print(json.dumps({'ok': True, 'seconds': round(len(clip) / 48000, 1),
                      'dir': out_dir}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
