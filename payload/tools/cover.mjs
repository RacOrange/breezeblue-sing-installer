#!/usr/bin/env node
/**
 * breeze-sing 的本地 CLI（自建版）。
 *
 * 插件通过 `node cover.mjs <command> ... --json` 调用；所有状态落在 <data>/orders 下，
 * 渲染交给 Python（D:\whale-cover\render\render_cover.py）。
 *
 * 数据目录：WHALE_COVER_DATA_DIR 或 D:\whale-cover\data
 */
'use strict';

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = process.env.SING_ROOT || path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const DATA = process.env.WHALE_COVER_DATA_DIR || path.join(ROOT, 'data');
const PY = path.join(ROOT, 'engine', 'venv', 'Scripts', 'python.exe');
const RENDER = path.join(ROOT, 'render', 'render_cover.py');
const ENGINE_JSON = path.join(DATA, 'engine.json');

function ensureDirs() {
  for (const d of ['orders', 'prep-status', 'work', 'songs', 'refs', 'logs']) {
    fs.mkdirSync(path.join(DATA, d), { recursive: true });
  }
}
function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '')); } catch { return fallback; }
}
function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = file + '.' + crypto.randomUUID() + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), 'utf8');
  fs.renameSync(tmp, file);
}
function now() { return new Date().toISOString(); }
function orderFile(id) { return path.join(DATA, 'orders', id + '.json'); }
function readOrder(id) { return readJson(orderFile(id), null); }
function saveOrder(order) {
  order.updatedAt = now();
  writeJson(orderFile(order.id), order);
  return order;
}
function newId() { return crypto.randomBytes(4).toString('hex'); }
function arg(name, fallback = '') {
  const i = process.argv.indexOf('--' + name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
function flag(name) { return process.argv.includes('--' + name); }
function out(value, code = 0) {
  process.stdout.write(JSON.stringify(value) + '\n');
  process.exit(code);
}
function fail(error, code = 1) { out({ ok: false, error: String(error || 'unknown') }, code); }

function statusSet() {
  const raw = arg('status', '');
  return raw ? new Set(raw.split(',').map(s => s.trim()).filter(Boolean)) : null;
}
function activePosition(groupId) {
  const dir = path.join(DATA, 'orders');
  let names = [];
  try { names = fs.readdirSync(dir); } catch { return 1; }
  let n = 0;
  for (const name of names) {
    if (!name.endsWith('.json')) continue;
    const o = readJson(path.join(dir, name), null);
    if (!o || o.group?.id !== groupId) continue;
    if (['pending', 'making'].includes(o.status)) n += 1;
  }
  return n + 1;
}

function cmdOrder() {
  const song = arg('song').trim();
  if (!song) return fail('missing --song');
  const groupId = arg('group-id');
  const order = {
    id: newId(),
    song,
    artist: arg('artist').trim(),
    note: arg('note').trim(),
    requester: arg('requester').trim(),
    wxid: arg('wxid').trim(),
    via: arg('via', 'group'),
    chatType: arg('chat-type', 'group'),
    engine: arg('engine', 'seedvc'),
    group: groupId ? { id: groupId, name: arg('group-name').trim() } : null,
    source: '',
    status: 'pending',
    hasAudio: false,
    durationSec: 0,
    createdAt: now(),
    updatedAt: now(),
    events: [{ at: now(), status: 'pending', note: '下单' }],
  };
  const position = groupId ? activePosition(groupId) : 1;
  saveOrder(order);
  out({ ok: true, order, position });
}

function cmdList() {
  const wanted = statusSet();
  const limit = Math.max(1, Math.min(500, Number(arg('limit', '100')) || 100));
  const dir = path.join(DATA, 'orders');
  let names = [];
  try { names = fs.readdirSync(dir); } catch { /* empty */ }
  const orders = names.filter(n => n.endsWith('.json')).flatMap(n => {
    const o = readJson(path.join(dir, n), null);
    if (!o) return [];
    if (wanted && !wanted.has(o.status)) return [];
    return [o];
  }).sort((a, b) => String(a.createdAt).localeCompare(String(b.createdAt))).slice(0, limit);
  out({ ok: true, orders });
}

function cmdCancel() {
  const id = process.argv[3] || arg('id');
  const order = readOrder(id);
  if (!order) return fail('order not found');
  order.status = 'canceled';
  order.events = order.events || [];
  order.events.push({ at: now(), status: 'canceled', note: arg('reason', '取消') });
  saveOrder(order);
  out({ ok: true, order });
}

function cmdRender() {
  const id = process.argv[3] || arg('id');
  const order = readOrder(id);
  if (!order) return fail('order not found');
  const source = arg('source') || order.source;
  if (!source || !fs.existsSync(source)) return fail('source not found: ' + source);
  const engine = arg('engine', order.engine || 'seedvc');
  order.status = 'making';
  order.source = source;
  order.engine = engine;
  order.events = order.events || [];
  order.events.push({ at: now(), status: 'making', note: '开始渲染（' + engine + '）' });
  saveOrder(order);

  fs.mkdirSync(path.join(DATA, 'work', id), { recursive: true });
  const result = spawnSync(PY, [RENDER, '--id', id, '--source', source, '--engine', engine, '--data', DATA], {
    cwd: ROOT, windowsHide: true, encoding: 'utf8', timeout: 20 * 60 * 1000,
    maxBuffer: 16 * 1024 * 1024,
  });
  const fresh = readOrder(id);
  if (result.error) {
    return fail('render failed: ' + result.error.message, 2);
  }
  if (fresh) {
    if (fresh.status === 'canceled') return out({ ok: true, order: fresh, canceled: true });
    if (fresh.status === 'ready') return out({ ok: true, order: fresh });
  }
  const detail = (result.stderr || result.stdout || '').trim().split('\n').slice(-6).join(' | ');
  return fail('render failed: ' + (detail || 'exit ' + result.status), 2);
}

function cmdEngine() {
  const sub = process.argv[3] || '';
  if (sub === 'ref') {
    const wav = process.argv[4] || arg('wav');
    if (!wav || !fs.existsSync(wav)) return fail('ref wav not found');
    fs.mkdirSync(path.join(DATA, 'refs'), { recursive: true });
    const dest = path.join(DATA, 'refs', 'dynamic.wav');
    fs.copyFileSync(wav, dest);
    writeJson(ENGINE_JSON, { dynamicRef: dest, updatedAt: now() });
    return out({ ok: true, ref: dest });
  }
  if (sub === 'status') {
    const check = spawnSync(PY, ['-c', "import torch,demucs,soundfile;print(torch.__version__, torch.cuda.is_available())"], {
      cwd: ROOT, windowsHide: true, encoding: 'utf8', timeout: 60000,
    });
    const ok = check.status === 0;
    return out({ ok, python: ok ? check.stdout.trim() : (check.stderr || '').slice(-200) });
  }
  return fail('unknown engine command');
}

async function cmdVoice() {
  const sub = process.argv[3] || '';
  if (sub !== 'ensure') return fail('unknown voice command');
  const script = path.join(ROOT, 'voice', 'send_cover.py');
  const py = path.join(ROOT, 'voice', 'venv', 'Scripts', 'python.exe');
  if (!fs.existsSync(script) || !fs.existsSync(py)) return fail('voice sender missing');
  try {
    const res = await fetch('http://127.0.0.1:8787/api/status', { signal: AbortSignal.timeout(3000) });
    const body = await res.json();
    const gateway = (body.gateways || []).find(g => g.platform === 'wechat');
    const bridge = gateway && gateway.bridge || {};
    if (!bridge.online || !bridge.uia || bridge.accountOk !== true || bridge.accountGuard !== true) {
      return out({ ok: false, error: '微信桥接或绑定账号未通过核验' });
    }
    return out({ ok: true });
  } catch (error) {
    return out({ ok: false, error: '鲸鲸内核不可达：' + error.message });
  }
}

async function main() {
  ensureDirs();
  const cmd = process.argv[2];
  if (cmd === 'order') return cmdOrder();
  if (cmd === 'list') return cmdList();
  if (cmd === 'cancel') return cmdCancel();
  if (cmd === 'render') return cmdRender();
  if (cmd === 'engine') return cmdEngine();
  if (cmd === 'voice') return cmdVoice();
  return fail('unknown command: ' + cmd);
}

main().catch(error => fail(error && error.message || error));
