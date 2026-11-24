#!/usr/bin/env node
/**
 * breeze-sing 的准备工作：找本地音源 → （可选）yt-dlp 下载 → 切 54 秒副歌 → 调 render。
 *
 * 由插件以 `node breeze-prep.mjs <订单号> <歌名> <原唱>` 启动，环境变量见下。
 */
'use strict';

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const id = process.argv[2] || '';
const song = process.argv[3] || '';
const artist = process.argv[4] || '';
const data = process.env.BREEZE_DATA || 'D:\\whale-cover\\data';
const cli = process.env.BREEZE_CLI || 'D:\\whale-cover\\tools\\cover.mjs';
const python = process.env.BREEZE_PYTHON || 'D:\\whale-cover\\engine\\venv\\Scripts\\python.exe';
const cache = process.env.BREEZE_CACHE || 'D:\\whale-cover\\cache';
const seconds = Math.max(20, Math.min(59, Number(process.env.BREEZE_SECONDS) || 54));
const work = path.join(data, 'work', id);

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  try { fs.appendFileSync(process.env.BREEZE_LOG || path.join(data, 'logs', 'prep.log'), line + '\n'); } catch { /* ignore */ }
}
function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), 'utf8');
  fs.renameSync(tmp, file);
}
function prep(status, extra = {}) {
  writeJson(path.join(data, 'prep-status', `${id}.json`), { status, updatedAt: Date.now(), ...extra });
}
function progress(stage, extra = {}) {
  writeJson(path.join(work, 'progress.json'), { stage, updatedAt: Date.now(), ...extra });
}
function norm(value) {
  return String(value || '').normalize('NFKC').toLowerCase()
    .replace(/[\s\-_·.,，。()（）【】'"“”‘’]/g, '');
}
function readProxy() {
  try {
    return JSON.parse(fs.readFileSync('D:\\whale-cover\\config.json', 'utf8')).proxy || '';
  } catch { return ''; }
}
const EXTS = new Set(['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.wma']);

function findLocal() {
  const dir = path.join(data, 'songs');
  let names = [];
  try { names = fs.readdirSync(dir); } catch { return ''; }
  const want = norm(song);
  let loose = '';
  for (const name of names) {
    if (!EXTS.has(path.extname(name).toLowerCase())) continue;
    const stem = norm(path.basename(name, path.extname(name)));
    if (!stem) continue;
    if (stem === want) return path.join(dir, name);
    if (!loose && (stem.includes(want) || want.includes(stem))) loose = path.join(dir, name);
  }
  return loose;
}

function download() {
  fs.mkdirSync(cache, { recursive: true });
  const query = [song, artist].filter(Boolean).join(' ');
  const target = path.join(cache, `${id}.%(ext)s`);

  // 1) 网易云直连（国内可用；官方原版常是 VIP，会退到可下载版本）
  const fetcher = path.join(path.dirname(cli), 'fetch_song.py');
  if (fs.existsSync(fetcher)) {
    const out = path.join(cache, `${id}.mp3`);
    log(`尝试网易云搜索下载：${query}`);
    const fetched = spawnSync(python, [fetcher, '--query', query, '--out', out],
      { windowsHide: true, encoding: 'utf8', timeout: 2 * 60 * 1000,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
    const line = String(fetched.stdout || '').trim().split('\n').filter(Boolean).pop() || '';
    try {
      const parsed = JSON.parse(line);
      if (parsed.ok && parsed.path && fs.existsSync(parsed.path)) {
        log(`网易云下载成功：${parsed.title || query}`);
        return { path: parsed.path, title: parsed.title || '', artist: parsed.artist || '' };
      }
      log(`网易云失败：${parsed.error || 'no result'}`);
    } catch { log('网易云无输出'); }
  }

  log(`尝试 yt-dlp 搜索下载：${query}`);
  const proxy = process.env.BREEZE_PROXY || readProxy();
  const extra = proxy ? ['--proxy', proxy] : [];
  const result = spawnSync(python, ['-m', 'yt_dlp', '-x', '--audio-format', 'wav', '--no-playlist',
    ...extra, '-o', target, `ytsearch1:${query}`], { windowsHide: true, encoding: 'utf8', timeout: 8 * 60 * 1000 });
  if (result.status !== 0) {
    log(`yt-dlp 失败：${String(result.stderr || result.error || '').trim().split('\n').slice(-2).join(' | ')}`);
    return '';
  }
  const files = fs.readdirSync(cache).filter(n => n.startsWith(`${id}.`) && EXTS.has(path.extname(n).toLowerCase()));
  return files.length ? { path: path.join(cache, files[0]), title: '', artist: '' } : null;
}

function updateOrderMeta(meta) {
  const file = path.join(data, 'orders', id + '.json');
  try {
    const order = JSON.parse(fs.readFileSync(file, 'utf8'));
    const raw = String(order.song || '').trim();
    const looksRef = /^(?:https?:\/\/|\/\/)/i.test(raw) || /^id[:\s]*\d+$/i.test(raw) || /^\d{5,}$/.test(raw);
    if (!looksRef) return;
    order.song = meta.title;
    if (meta.artist) order.artist = meta.artist;
    order.source = meta.path;
    fs.writeFileSync(file, JSON.stringify(order, null, 2), 'utf8');
    log(`订单改名：《${meta.title}》`);
  } catch { /* ignore */ }
}

function main() {
  try {
    if (!id || !song) { log('缺少订单号或歌名'); return 1; }
    fs.mkdirSync(work, { recursive: true });
    progress('准备中');
    let source = '';
    let meta = null;
    const local = findLocal();
    if (local) { source = local; log(`本地音源：${local}`); }
    else {
      const got = download();
      if (got) { source = got.path; meta = got; }
    }
    if (!source) {
      prep('error', { error: '没找到音源：把音频放进 ' + path.join(data, 'songs') + '（文件名用歌名），或确认本机可下载' });
      return 0;
    }
    if (meta && meta.title) updateOrderMeta(meta);

    const cut = path.join(work, 'chorus.wav');
    const py = `import sys; sys.path.insert(0, r'D:\\whale-cover\\render'); import render_cover; render_cover.pick_chorus(sys.argv[1], sys.argv[2], int(sys.argv[3])); print('cut ok')`;
    const r = spawnSync(python, ['-c', py, source, work, String(seconds)], { windowsHide: true, encoding: 'utf8', timeout: 5 * 60 * 1000 });
    if (r.status !== 0 || !fs.existsSync(cut)) {
      prep('error', { error: '切副歌失败：' + String(r.stderr || r.error || '').slice(-160) });
      return 0;
    }
    log(`副歌已切：${cut}`);

    progress('换声合成');
    const render = spawnSync(process.execPath, [cli, 'render', id, '--engine', process.env.BREEZE_ENGINE || 'seedvc',
      '--source', cut, '--json'], { windowsHide: true, encoding: 'utf8', timeout: 30 * 60 * 1000, maxBuffer: 16 * 1024 * 1024,
      env: { ...process.env, WHALE_COVER_DATA_DIR: data } });
    const text = String(render.stdout || '').trim();
    let parsed = null;
    try { parsed = JSON.parse(text.split('\n').filter(Boolean).pop() || '{}'); } catch { /* ignore */ }
    if (render.status !== 0 || !parsed || parsed.ok !== true) {
      const detail = String(render.stderr || text || '').trim().split('\n').slice(-3).join(' | ');
      prep('error', { error: '渲染失败：' + (detail || 'exit ' + render.status) });
      return 0;
    }
    prep('ok', { song });
    log('准备完成');
    return 0;
  } catch (error) {
    prep('error', { error: String(error && error.message || error) });
    log('异常：' + String(error && error.message || error));
    return 0;
  }
}

process.exit(main());
