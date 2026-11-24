# -*- coding: utf-8 -*-
"""breeze-sing 的本地渲染：切副歌 → 分离人声 → seed-vc 换声 → 混音/母带。

由 cover.mjs 的 render 命令调用；结果写回 <data>/orders/<id>.json。
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import librosa
import numpy as np
import soundfile as sf

ROOT = os.environ.get('SING_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.environ.get('SING_SEEDVC') or os.path.join(ROOT, 'seed-vc')
PY = os.path.join(ROOT, 'engine', 'venv', 'Scripts', 'python.exe')
INFER = os.path.join(SEED, 'inference_local.py')
CONFIG = os.path.join(SEED, 'configs', 'local_sing.yml')
REF_DIR = os.path.join(ROOT, 'ref')
PROFILES = os.path.join(REF_DIR, 'profiles.json')
FFMPEG = os.environ.get('SING_FFMPEG') or os.path.join(ROOT, 'tools', 'ffmpeg', 'ffmpeg.exe')

# demucs 的权重走 HuggingFace；国内直连会超时，统一走镜像并把缓存放 D 盘
HF_ENV = {
    'HF_ENDPOINT': 'https://hf-mirror.com',
    'HF_HUB_DOWNLOAD_TIMEOUT': '180',
    'HF_HOME': os.path.join(ROOT, 'models', 'hf'),
}

SONG_RULES = [
    ('angry', ['孤勇者', '逆战', '易燃易爆炸', '咆哮', '热血', '摇滚', '燃']),
    ('sad', ['后来', '可惜不是你', '说散就散', '体面', '伤感', '慢冷', '泪']),
    ('affectionate', ['起风了', '晴天', '小幸运', '告白气球', '情歌', '温柔', '甜甜的']),
    ('excited', ['快乐', '阳光', '派对', '恋爱', '甜', '嗨', '快乐崇拜']),
    ('serious', ['夜空中最亮的星', '平凡之路', '岁月神偷', '故事', '叙述']),
]


def log(msg):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


def read_json(path, fallback=None):
    try:
        with open(path, encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return fallback


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def progress(work, stage, **extra):
    data = {'stage': stage, 'updatedAt': now_iso()}
    data.update(extra)
    write_json(os.path.join(work, 'progress.json'), data)


def run(cmd, cwd, logfile, timeout=None, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    log('RUN ' + ' '.join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd)))
    with open(logfile, 'a', encoding='utf-8', errors='replace') as f:
        p = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout, env=e)
    if p.returncode != 0:
        raise RuntimeError('command failed (%d): %s' % (p.returncode, os.path.basename(cmd[0])))
    return p.returncode


def pick_chorus(source, work, seconds=54):
    y, sr = librosa.load(source, sr=44100, mono=True)
    if len(y) <= sr * seconds:
        out = os.path.join(work, 'chorus.wav')
        sf.write(out, y, sr, subtype='PCM_16')
        return out
    hop = sr // 4
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    win = max(1, int(seconds * sr / hop))
    kernel = np.ones(win) / win
    score = np.convolve(rms, kernel, mode='valid')
    start = int(np.argmax(score)) * hop
    start = min(max(0, start), len(y) - seconds * sr)
    out = os.path.join(work, 'chorus.wav')
    sf.write(out, y[start:start + seconds * sr], sr, subtype='PCM_16')
    return out


def choose_profile(order):
    meta = read_json(PROFILES, {}) or {}
    profiles = meta.get('profiles') or {}
    aliases = meta.get('aliases') or {}
    default = meta.get('default') or 'daily'
    note = str(order.get('note') or '')
    for alias, key in aliases.items():
        if alias and alias in note and key in profiles:
            return key, os.path.join(REF_DIR, profiles[key]['file'])
    text = str(order.get('song') or '') + ' ' + str(order.get('artist') or '')
    for key, words in SONG_RULES:
        if key in profiles and any(w and w in text for w in words):
            return key, os.path.join(REF_DIR, profiles[key]['file'])
    key = default if default in profiles else next(iter(profiles), 'daily')
    return key, os.path.join(REF_DIR, profiles[key]['file'])


def find_checkpoint():
    patterns = [
        os.path.join(SEED, 'checkpoints', 'models--Plachta--Seed-VC', 'snapshots', '*', 'DiT_*f0*.pth'),
        os.path.join(SEED, 'checkpoints', 'DiT_*f0*.pth'),
    ]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))
    files = sorted(files, key=os.path.getmtime, reverse=True)
    if not files:
        raise RuntimeError('找不到 seed-vc checkpoint')
    return files[0]


def separate(chorus, work):
    sep = os.path.join(work, 'sep')
    stems = glob.glob(os.path.join(sep, 'htdemucs', '*', 'vocals.wav'))
    if stems:
        base = os.path.dirname(stems[0])
        inst = os.path.join(base, 'no_vocals.wav')
        log('复用已分离的人声：%s' % stems[0])
        return stems[0], (inst if os.path.exists(inst) else '')
    log('分离人声（demucs）')
    try:
        run([PY, '-m', 'demucs.separate', '--two-stems=vocals', '-n', 'htdemucs',
             '--device', 'cuda', '-o', sep, chorus], ROOT, os.path.join(work, 'demucs.log'), timeout=1800, env=HF_ENV)
    except Exception as exc:
        log('GPU 分离失败，尝试 CPU：%s' % exc)
        run([PY, '-m', 'demucs.separate', '--two-stems=vocals', '-n', 'htdemucs',
             '--device', 'cpu', '-o', sep, chorus], ROOT, os.path.join(work, 'demucs.log'), timeout=3600, env=HF_ENV)
    stems = glob.glob(os.path.join(sep, 'htdemucs', '*', 'vocals.wav'))
    if not stems:
        raise RuntimeError('demucs 没有产出 vocals.wav')
    base = os.path.dirname(stems[0])
    inst = os.path.join(base, 'no_vocals.wav')
    return stems[0], (inst if os.path.exists(inst) else '')


def convert(vocals, ref, work):
    log('seed-vc 换声')
    outdir = os.path.join(work, 'vc')
    os.makedirs(outdir, exist_ok=True)
    ckpt = find_checkpoint()
    env = {
        'HF_HUB_OFFLINE': '1',
        'PYTORCH_CUDA_ALLOC_CONF': 'expandable_segments:True',
        'OMP_NUM_THREADS': '2',
        'PYTHONUNBUFFERED': '1',
        'PYTHONIOENCODING': 'utf-8',
    }
    last = None
    for attempt in (1, 2):
        try:
            run([PY, '-u', INFER, '--checkpoint', ckpt, '--config', CONFIG,
                 '--source', vocals, '--target', ref, '--output', outdir,
                 '--f0-condition', 'True', '--diffusion-steps', '30', '--inference-cfg-rate', '0.7'],
                SEED, os.path.join(work, 'seedvc.log'), timeout=3600, env=env)
            last = None
            break
        except Exception as exc:
            last = exc
            log('seed-vc 第 %d 次失败：%s' % (attempt, exc))
            time.sleep(2)
    if last is not None:
        raise RuntimeError('seed-vc 连续失败：%s' % last)
    files = sorted(glob.glob(os.path.join(outdir, '*.wav')), key=os.path.getmtime, reverse=True)
    if not files:
        raise RuntimeError('seed-vc 没有产出 wav')
    return files[0]


def mix(vocal, inst, work):
    log('混音与母带')
    v, sr = sf.read(vocal, always_2d=False)
    v = v if v.ndim == 1 else v.mean(axis=1)
    if inst:
        i, sr2 = sf.read(inst, always_2d=False)
        i = i if i.ndim == 1 else i.mean(axis=1)
        n = min(len(v), len(i))
        v, i = v[:n], i[:n]
        mixed = v * 1.0 + i * (1.0 / 1.7)
    else:
        mixed = v
    raw = os.path.join(work, 'mix_raw.wav')
    sf.write(raw, mixed, sr, subtype='PCM_16')
    out = os.path.join(work, 'cover.wav')
    run([FFMPEG, '-y', '-hide_banner', '-loglevel', 'error', '-i', raw,
         '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '44100', '-ac', '1', out],
        work, os.path.join(work, 'ffmpeg.log'), timeout=600)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True)
    ap.add_argument('--source', required=True)
    ap.add_argument('--engine', default='seedvc')
    ap.add_argument('--data', required=True)
    args = ap.parse_args()

    data = args.data
    order_path = os.path.join(data, 'orders', args.id + '.json')
    work = os.path.join(data, 'work', args.id)
    os.makedirs(work, exist_ok=True)
    order = read_json(order_path)
    if not order:
        raise SystemExit('order not found: ' + order_path)
    log('order=%s song=%s' % (args.id, order.get('song')))

    progress(work, '准备中')
    chorus = pick_chorus(args.source, work)
    profile, ref = choose_profile(order)
    log('参考音 profile=%s ref=%s' % (profile, ref))
    progress(work, '分离人声')
    try:
        vocals, inst = separate(chorus, work)
    except Exception as exc:
        log('分离失败，退回纯人声：%s' % exc)
        vocals, inst = chorus, ''

    progress(work, '换声合成')
    converted = convert(vocals, ref, work)

    current = read_json(order_path, {})
    if current.get('status') == 'canceled':
        log('订单已取消，丢弃结果')
        return 0

    progress(work, '混音')
    cover = mix(converted, inst, work)
    y, sr = sf.read(cover, always_2d=False)
    duration = round(len(y) / sr, 2)
    rel = os.path.relpath(cover, data).replace('\\', '/')
    current.update({
        'status': 'ready',
        'hasAudio': True,
        'durationSec': duration,
        'audio': cover,
        'profile': profile,
        'updatedAt': now_iso(),
        'events': (current.get('events') or []) + [{
            'at': now_iso(), 'status': 'ready',
            'note': '渲染完成 %.1fs（%s）' % (duration, profile),
        }],
    })
    write_json(order_path, current)
    progress(work, '完成', durationSec=duration)
    log('DONE %s %.2fs' % (cover, duration))
    return 0


if __name__ == '__main__':
    sys.exit(main())
