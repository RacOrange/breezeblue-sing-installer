# -*- coding: utf-8 -*-
"""breeze-sing 的本地渲染：切副歌 → 分离人声 → seed-vc 换声 → 混音/母带。

由 cover.mjs 的 render 命令调用；结果写回 <data>/orders/<id>.json。
"""
import argparse
import glob
import json
import os
import subprocess
import threading
import sys
import time
from datetime import datetime, timezone

import librosa
import numpy as np
import soundfile as sf

ROOT = os.environ.get('SING_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, 'seed-vc')
PY = os.path.join(ROOT, 'engine', 'venv', 'Scripts', 'python.exe')
INFER = os.path.join(SEED, 'inference_local.py')
CONFIG = os.path.join(SEED, 'configs', 'local_sing.yml')
REF_DIR = os.path.join(ROOT, 'ref')
PROFILES = os.path.join(REF_DIR, 'profiles.json')
FFMPEG = os.environ.get('BREEZE_FFMPEG_EXE') or os.path.join(ROOT, 'tools', 'ffmpeg', 'ffmpeg.exe')
RENDER_DEVICE = os.environ.get('WHALE_RENDER_DEVICE', 'auto').strip().lower()

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
    stopped = threading.Event()
    heartbeat = os.path.join(os.path.dirname(logfile), 'heartbeat.json')

    def refresh():
        while not stopped.wait(20):
            write_json(heartbeat, {'updatedAt': now_iso()})

    write_json(heartbeat, {'updatedAt': now_iso()})
    worker = threading.Thread(target=refresh, daemon=True)
    worker.start()
    try:
        with open(logfile, 'ab') as f:
            start = f.tell()
            p = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout, env=e)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('RENDER_TIMEOUT: 子进程超过执行时限') from exc
    finally:
        stopped.set()
        worker.join()
    if p.returncode != 0:
        with open(logfile, 'rb') as f:
            f.seek(max(start, os.path.getsize(logfile) - 16000))
            recent = f.read().decode('utf-8', errors='replace').lower()
        if 'cuda_arch_unsupported' in recent or 'no kernel image' in recent or 'invalid device function' in recent:
            raise RuntimeError('CUDA_ARCH_UNSUPPORTED: 当前 PyTorch 无法在这张显卡上执行')
        if any(code in recent for code in ('cuda_unavailable:', 'cuda_execution_failed:', 'cuda_dependencies_invalid:')):
            raise RuntimeError('CUDA_UNAVAILABLE: 请检查 NVIDIA 驱动和安装器依赖步骤')
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
    if meta.get('mode') == 'windows-tts':
        raise RuntimeError('参考音仍是 Windows 默认音色，请先完成安装器方案 B 或导入参考音')
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
    pat = os.path.join(SEED, 'checkpoints', 'models--Plachta--Seed-VC', 'snapshots', '*', 'DiT_*f0*.pth')
    files = sorted(glob.glob(pat), key=os.path.getmtime, reverse=True)
    if not files:
        raise RuntimeError('找不到 seed-vc checkpoint')
    return files[0]


def separate(chorus, work):
    sep = os.path.join(work, 'sep')
    name = os.path.splitext(os.path.basename(chorus))[0]
    stems = glob.glob(os.path.join(sep, 'htdemucs', glob.escape(name), 'vocals.wav'))
    if stems:
        base = os.path.dirname(stems[0])
        inst = os.path.join(base, 'no_vocals.wav')
        log('复用已分离的人声：%s' % stems[0])
        return stems[0], (inst if os.path.exists(inst) else '')
    log('分离人声（demucs）')
    try:
        run([PY, '-m', 'demucs.separate', '--two-stems=vocals', '-n', 'htdemucs',
             '--device', 'cuda' if RENDER_DEVICE == 'cuda' else 'cpu', '-o', sep, chorus],
            ROOT, os.path.join(work, 'demucs.log'), timeout=1800 if RENDER_DEVICE == 'cuda' else 7200, env=HF_ENV)
    except Exception as exc:
        log('GPU 分离失败，尝试 CPU：%s' % exc)
        run([PY, '-m', 'demucs.separate', '--two-stems=vocals', '-n', 'htdemucs',
             '--device', 'cpu', '-o', sep, chorus], ROOT, os.path.join(work, 'demucs.log'), timeout=3600, env=HF_ENV)
    stems = glob.glob(os.path.join(sep, 'htdemucs', glob.escape(name), 'vocals.wav'))
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
        'SEED_VC_DEVICE': RENDER_DEVICE if RENDER_DEVICE in ('dml', 'cuda', 'cpu') else 'auto',
        'SEED_VC_DIAG_LOG': os.path.join(data, 'logs', 'a-card-diagnostics.log'),
    }
    last = None
    for attempt in (1, 2):
        try:
            fp16 = 'True' if RENDER_DEVICE == 'cuda' else 'False'
            run([PY, '-u', INFER, '--checkpoint', ckpt, '--config', CONFIG,
                 '--source', vocals, '--target', ref, '--output', outdir,
                 '--f0-condition', 'True', '--diffusion-steps', '30', '--inference-cfg-rate', '0.7',
                 '--fp16', fp16],
                SEED, os.path.join(work, 'seedvc.log'), timeout=7200 if RENDER_DEVICE != 'cuda' else 3600, env=env)
            last = None
            break
        except Exception as exc:
            if str(exc).startswith(('CUDA_ARCH_UNSUPPORTED:', 'CUDA_UNAVAILABLE:', 'RENDER_TIMEOUT:')):
                raise
            last = exc
            log('seed-vc 第 %d 次失败：%s' % (attempt, exc))
            if attempt == 1:
                time.sleep(2)
    if last is not None:
        raise RuntimeError('seed-vc 连续失败：%s' % last)
    files = sorted(glob.glob(os.path.join(outdir, '*.wav')), key=os.path.getmtime, reverse=True)
    if not files:
        raise RuntimeError('seed-vc 没有产出 wav')
    return files[0]


def limit_peak(audio, ceiling_db=-1.0):
    ceiling = 10.0 ** (float(ceiling_db) / 20.0)
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > ceiling:
        audio = audio * (ceiling / peak)
    return audio


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
    return master_audio(mixed, sr, work)


def master_audio(mixed, sr, work):
    raw = os.path.join(work, 'mix_raw.wav')
    sf.write(raw, mixed, sr, subtype='PCM_16')
    out = os.path.join(work, 'cover.wav')
    run([FFMPEG, '-y', '-hide_banner', '-loglevel', 'error', '-i', raw,
         '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '44100', '-ac', '1', out],
        work, os.path.join(work, 'ffmpeg.log'), timeout=600)
    audio, rate = sf.read(out, dtype='float32', always_2d=True)
    audio = limit_peak(audio)
    sf.write(out, audio, rate, subtype='PCM_16')
    return out


def mono_audio(file, rate):
    audio, sample_rate = sf.read(file, dtype='float32', always_2d=True)
    mono = audio.mean(axis=1)
    if sample_rate != rate:
        mono = librosa.resample(mono, orig_sr=sample_rate, target_sr=rate)
    return mono


def fit_timeline(audio, frames, rate, max_delta=0.5):
    # 少量补齐模型窗尾。明显短于原曲时中止，避免把缺段的文件当整首。
    if abs(len(audio) - frames) > int(rate * max_delta):
        raise RuntimeError('渲染时长与原曲差异过大，停止生成整首语音')
    if len(audio) < frames:
        return np.pad(audio, (0, frames - len(audio)))
    return audio[:frames]


def phrase_boundaries(vocal, rate, max_seconds=56):
    # 在每个可行范围内偏向人声低谷。分点用于语音发送，完整成品保留所有采样。
    from math import ceil

    frames = len(vocal)
    limit = max_seconds * rate
    total = max(1, ceil(frames / limit))
    hop = max(1, rate // 20)
    margin = max(1, rate // 5)
    levels = np.square(vocal[:frames // hop * hop]).reshape(-1, hop).mean(axis=1)
    typical = max(float(np.quantile(levels, 0.70)), 1e-8) if len(levels) else 1e-8
    points = [0]
    for left in range(total - 1, 0, -1):
        start = points[-1]
        ideal = start + (frames - start) // (left + 1)
        lo = max(start + min(25 * rate, ideal - start), frames - left * limit, ideal - 10 * rate)
        hi = min(start + limit, frames - left * 15 * rate, ideal + 9 * rate)
        candidates = range((lo + hop - 1) // hop * hop, hi + 1, hop)
        def score(cut):
            a = max(0, (cut - margin) // hop)
            b = min(len(levels), (cut + margin) // hop + 1)
            energy = float(levels[a:b].mean()) if b > a else typical
            return min(energy / typical, 5) + 0.28 * abs(cut - ideal) / (10 * rate)
        fallback = max(frames - left * limit, min(start + limit, ideal))
        points.append(min(candidates, key=score, default=fallback))
    return points + [frames]


def render_full(source, ref, work):
    # Demucs 和 Seed-VC 都处理完整语句。Seed-VC 自身为长音频分窗并交叉淡化。
    rate = 44100
    samples, _ = librosa.load(source, sr=rate, mono=False)
    frames = samples.shape[-1]
    if not frames:
        raise RuntimeError('原曲没有可用音频')
    original = os.path.join(work, 'full-source.wav')
    sf.write(original, samples.T, rate, subtype='PCM_16')
    progress(work, '整首人声分离')
    vocals, inst = separate(original, work)
    if not inst:
        raise RuntimeError('没得到整首伴奏，保留原订单等待重试')
    boundary_track = fit_timeline(mono_audio(vocals, rate), frames, rate)
    accompaniment = fit_timeline(mono_audio(inst, rate), frames, rate)
    progress(work, '整首音色转换')
    converted = convert(vocals, ref, work)
    voice = fit_timeline(mono_audio(converted, rate), frames, rate)
    progress(work, '整首混音及语音分段')
    # 整首压限和全曲音量一致，只在曲首和曲尾保留短淡入淡出。
    mixed = voice + accompaniment / 1.7
    peak = float(np.max(np.abs(mixed)))
    if peak > 0.95:
        mixed *= 0.95 / peak
    fade = min(int(rate * 0.30), frames // 2)
    if fade:
        ramp = np.linspace(0.0, 1.0, fade, dtype='float32')
        mixed[:fade] *= ramp
        mixed[-fade:] *= ramp[::-1]
    cover = master_audio(mixed, rate, work)
    mastered = limit_peak(fit_timeline(mono_audio(cover, rate), frames, rate))
    sf.write(cover, mastered, rate, subtype='PCM_16')
    bounds = phrase_boundaries(boundary_track, rate)
    parts = []
    for index, (first, last) in enumerate(zip(bounds, bounds[1:]), 1):
        file = os.path.join(work, 'voice-part-%02d.wav' % index)
        sf.write(file, mastered[first:last], rate, subtype='PCM_16')
        parts.append({'audio': file, 'startFrame': first, 'endFrame': last,
                      'sampleRate': rate, 'durationSec': (last - first) / rate})
    return cover, round(frames / rate, 2), parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True)
    ap.add_argument('--source', required=True)
    ap.add_argument('--engine', default='seedvc')
    ap.add_argument('--data', required=True)
    ap.add_argument('--full', action='store_true')
    args = ap.parse_args()

    data = args.data
    order_path = os.path.join(data, 'orders', args.id + '.json')
    work = os.path.join(data, 'work', args.id)
    os.makedirs(work, exist_ok=True)
    order = read_json(order_path)
    if not order:
        raise SystemExit('order not found: ' + order_path)
    log('order=%s song=%s' % (args.id, order.get('song')))

    profile, ref = choose_profile(order)
    if not ref or not os.path.isfile(ref):
        raise RuntimeError('未找到参考音，请先完成安装器的方案 B 或导入参考音')
    log('参考音 profile=%s' % profile)
    global RENDER_DEVICE
    cuda_probe = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cuda_smoke.py')
    if RENDER_DEVICE not in ('cpu', 'cuda', 'dml', 'auto'):
        RENDER_DEVICE = 'auto'

    def cuda_available():
        try:
            probe = subprocess.run([PY, '-c', 'import torch; print(torch.cuda.is_available())'],
                                   capture_output=True, text=True, timeout=60)
            return probe.returncode == 0 and 'True' in probe.stdout
        except Exception:
            return False

    def dml_available():
        try:
            probe = subprocess.run([PY, '-c', 'import torch_directml; print(torch_directml.device_count())'],
                                   capture_output=True, text=True, timeout=60)
            return probe.returncode == 0 and int((probe.stdout or '0').strip().splitlines()[-1] or 0) > 0
        except Exception:
            return False

    if RENDER_DEVICE == 'auto':
        if cuda_available():
            RENDER_DEVICE = 'cuda'
        elif dml_available():
            RENDER_DEVICE = 'dml'
        else:
            raise RuntimeError('A_GPU_BACKEND_UNAVAILABLE: 未检测到可用 CUDA 或 torch-directml；A 卡请先运行 a-card/setup.ps1')
    if RENDER_DEVICE == 'cuda':
        progress(work, '检查 CUDA')
        run([PY, cuda_probe], ROOT, os.path.join(work, 'cuda.log'), timeout=90)
    elif RENDER_DEVICE == 'dml':
        progress(work, '检查 DirectML')
        if not dml_available():
            raise RuntimeError('DML_UNAVAILABLE: torch-directml 没有检测到 DirectX 12 设备')
        log('A 卡 DirectML 后端已启用；demucs 分离仍使用 CPU')
    elif RENDER_DEVICE == 'cpu':
        if os.environ.get('WHALE_RENDER_DEVICE', '').strip().lower() != 'cpu':
            raise RuntimeError('A_GPU_BACKEND_UNAVAILABLE: 未检测到可用 CUDA/DirectML；A 卡不能静默降级 CPU')
        progress(work, 'CPU 兼容模式')
        log('显式选择 CPU 兼容模式')
    parts = []
    if args.full:
        cover, duration, parts = render_full(args.source, ref, work)
    else:
        progress(work, '准备中')
        chorus = pick_chorus(args.source, work)
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
        # 首尾淡入淡出，避免切歌点爆音/听感断裂
        fade_n = min(int(sr * 0.30), max(0, len(y) // 2))
        if fade_n > 0:
            ramp = np.linspace(0.0, 1.0, fade_n, dtype='float32')
            if y.ndim > 1:
                y[:fade_n] *= ramp[:, None]
                y[-fade_n:] *= ramp[::-1][:, None]
            else:
                y[:fade_n] *= ramp
                y[-fade_n:] *= ramp[::-1]
        y = limit_peak(y)
        sf.write(cover, y, sr)
        duration = round(len(y) / sr, 2)
    current = read_json(order_path, {})
    if current.get('status') == 'canceled':
        log('订单已取消，丢弃结果')
        return 0
    current.update({
        'status': 'ready',
        'hasAudio': True,
        'durationSec': duration,
        'audio': cover,
        'audioParts': parts,
        'fullTrack': args.full,
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
    try:
        sys.exit(main())
    except Exception:
        # A 卡测试版：把异常写进统一诊断日志，便于网友直接回传。
        import traceback
        try:
            argv = sys.argv[1:]
            data_dir = ''
            if '--data' in argv:
                index = argv.index('--data')
                if index + 1 < len(argv):
                    data_dir = argv[index + 1]
            log_dir = os.path.join(data_dir or '.', 'logs')
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, 'a-card-diagnostics.log'), 'a', encoding='utf-8') as handle:
                handle.write('[%s] fatal_traceback=\n%s\n' % (datetime.now().isoformat(), traceback.format_exc()))
        except Exception:
            pass
        raise
