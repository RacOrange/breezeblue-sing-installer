# -*- coding: utf-8 -*-
"""生成 6 个情绪参考音。

优先顺序：
1. --breeze-key / BREEZE_API_KEY：Breeze 官方 API（音色与鲸鲸一致）
2. --import-dir：导入已有的 voice_*.wav
首次安装的方案 B 在安装器的 capture_ref.py 路径执行。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import requests

try:
    import soundfile as sf
except ImportError:
    sf = None

EMOTIONS = [
    ('daily', '日常', '自然、平稳，像平时说话。语速正常，吐字清楚，句尾不上扬。', 0),
    ('happy', '开心', '轻快一点，带一点笑意，语速稍快但吐字清楚。', 2),
    ('gentle', '温柔', '温柔、放轻，语速稍慢，句尾柔和。', -2),
    ('serious', '认真', '认真、清楚，语气平稳，不拖音。', 0),
    ('sad', '难过', '低落一些，语速偏慢，声音放软。', -3),
    ('angry', '生气', '带一点不满和力度，但不要喊。', 1),
]
TEXTS = [
    '今天过得怎么样，我在家里等你回来。外面风有点大，记得多穿一点，别着凉了。今天想跟你说一件很开心的事，你回来的时候我们慢慢聊。我最近在学做一道新菜，等你回来尝尝看。要是你累了，就先休息一会儿，不着急。',
    '你回来啦，今天想跟你说一件很开心的事。',
    '外面风有点大，记得多穿一点，别着凉了。',
    '我想认真跟你说，这件事我们慢慢商量。',
    '今天有点累，想安静地待一会儿。',
    '这件事让我有点生气，但我不想跟你吵架。',
]


def read_json(path, fallback=None):
    try:
        with open(path, encoding='utf-8-sig') as handle:
            return json.load(handle)
    except OSError:
        return fallback


def breeze_voice(whale_girl):
    settings = read_json(os.path.join(whale_girl, 'data', 'voice-send.json'), {}) or {}
    profiles = settings.get('Profiles') or {}
    for name in ('breezeblue', 'minimax'):
        value = profiles.get(name)
        if isinstance(value, dict) and value.get('Voice'):
            return value
    for value in profiles.values():
        if isinstance(value, dict) and value.get('Voice'):
            return value
    return {}


def breeze_synth(address, key, model, voice, text, instruction, out_file):
    url = address.rstrip('/') + '/text-to-speech/' + voice
    response = requests.post(url, params={'output_format': 'wav'},
                             headers={'xi-api-key': key, 'Content-Type': 'application/json'},
                             json={'text': text, 'model_id': model, 'instructions': instruction},
                             timeout=120)
    if response.status_code != 200:
        raise RuntimeError('Breeze HTTP %s: %s' % (response.status_code, response.text[:160]))
    with open(out_file, 'wb') as handle:
        handle.write(response.content)
    return out_file


def to_wav(src, dst, ffmpeg):
    if sf:
        try:
            data, sr = sf.read(src)
            sf.write(dst, data, sr, subtype='PCM_16')
            return dst
        except Exception:
            pass
    if ffmpeg and os.path.isfile(ffmpeg):
        subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-i', src, '-ar', '44100', '-ac', '1', dst],
                       check=True)
        return dst
    raise RuntimeError('无法转换音频：' + src)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime-root', required=True)
    ap.add_argument('--whale-girl', default='')
    ap.add_argument('--ffmpeg', default='')
    ap.add_argument('--breeze-key', default=os.environ.get('BREEZE_API_KEY', ''))
    ap.add_argument('--import-dir', default='')
    args = ap.parse_args()

    ref_dir = os.path.join(args.runtime_root, 'ref')
    profiles_dir = os.path.join(ref_dir, 'profiles')
    os.makedirs(profiles_dir, exist_ok=True)
    ffmpeg = args.ffmpeg or os.path.join(args.runtime_root, 'tools', 'ffmpeg', 'ffmpeg.exe')
    results = []

    if args.import_dir:
        for emotion, label, _instruction, _rate in EMOTIONS:
            src = os.path.join(args.import_dir, 'voice_%s.wav' % emotion)
            if not os.path.exists(src):
                raise SystemExit('缺少导入文件：' + src)
            shutil.copyfile(src, os.path.join(profiles_dir, 'voice_%s.wav' % emotion))
            results.append({'emotion': emotion, 'label': label, 'file': 'profiles/voice_%s.wav' % emotion})
        mode = 'import'
    elif args.breeze_key:
        voice = breeze_voice(args.whale_girl) if args.whale_girl else {}
        address = 'https://api.breeze.blue/v1'
        model = voice.get('Model') or 'breeze-tts-2'
        voice_id = voice.get('Voice') or ''
        if not voice_id:
            raise SystemExit('缺少 Breeze Voice ID（鲸鲸 voice-send.json）')
        for index, (emotion, label, instruction, _rate) in enumerate(EMOTIONS):
            raw = os.path.join(ref_dir, '_raw_%s.bin' % emotion)
            wav = os.path.join(profiles_dir, 'voice_%s.wav' % emotion)
            breeze_synth(address, args.breeze_key, model, voice_id, TEXTS[index], instruction, raw)
            to_wav(raw, wav, ffmpeg)
            os.remove(raw)
            results.append({'emotion': emotion, 'label': label, 'file': 'profiles/voice_%s.wav' % emotion})
        mode = 'breeze'
    else:
        raise SystemExit('请用安装器进入方案 B，或显式提供 Breeze Key / 导入参考音')

    profiles = {
        'version': 1,
        'mode': mode,
        'default': 'daily',
        'profiles': {item['emotion']: {'file': item['file'], 'label': item['label']} for item in results},
        'aliases': {item['label']: item['emotion'] for item in results},
    }
    with open(os.path.join(ref_dir, 'profiles.json'), 'w', encoding='utf-8') as handle:
        json.dump(profiles, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'ok': True, 'mode': mode, 'count': len(results), 'dir': ref_dir}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
