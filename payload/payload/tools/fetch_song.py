# -*- coding: utf-8 -*-
"""从网易云搜索并下载一首歌；支持 cookies.txt（VIP 账号）。

用法: python fetch_song.py --query "晴天 周杰伦" --out D:\\...\\song.mp3
输出单行 JSON：{"ok":true,"path":...,"title":...,"artist":...,"id":...}
"""
import argparse
import json
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netease_weapi  # noqa: E402

ROOT = os.environ.get('SING_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.environ.get('BREEZE_COOKIES') or os.path.join(ROOT, 'cookies.txt')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/122.0 Safari/537.36',
    'Referer': 'https://music.163.com/',
}
SEARCH = 'https://music.163.com/api/search/get'
OUTER = 'https://music.163.com/song/media/outer/url?id=%s.mp3'
BAD = ('伴奏', '纯音乐', 'dj', 'DJ', 'remix', 'Remix', '铃声', '片段')


def load_cookies(path):
    jar = {}
    try:
        with open(path, encoding='utf-8', errors='ignore') as handle:
            for line in handle:
                if not line.strip() or line.startswith('#'):
                    continue
                parts = line.rstrip('\n').split('\t')
                if len(parts) >= 7 and ('163.com' in parts[0] or 'music.163' in parts[0]):
                    jar[parts[5]] = parts[6]
    except OSError:
        return {}
    return jar


def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    cookies = load_cookies(COOKIE_FILE)
    if cookies:
        s.cookies.update(cookies)
    return s, bool(cookies)


def split_query(query):
    text = str(query or '').strip()
    parts = [p for p in re.split(r'\s+', text) if p]
    if len(parts) >= 2:
        return ' '.join(parts[:-1]), parts[-1]
    return text, ''


def parse_direct(query):
    text = str(query or '').strip()
    match = re.search(r'[?&]id=(\d+)', text) or re.search(r'/song/(\d+)', text)
    if match:
        return match.group(1)
    match = re.match(r'^id[:\s]*(\d+)$', text, re.I)
    if match:
        return match.group(1)
    match = re.match(r'^(\d{5,})$', text)
    if match:
        return match.group(1)
    return ''


def normalize(item):
    artists = item.get('ar') or item.get('artists') or []
    names = [(a.get('name') if isinstance(a, dict) else str(a)) or '' for a in artists]
    duration = item.get('dt') or item.get('duration') or 0
    return {
        'id': item.get('id'),
        'name': str(item.get('name') or ''),
        'artists': names,
        'duration': int(duration) / 1000.0,
        'fee': int(item.get('fee') or 0),
    }


def score(item, song, artist):
    name = item['name']
    artists = ' '.join(item['artists'])
    value = 0
    if song and song in name:
        value += 10
    if artist and artist in artists:
        value += 8
    if 60 <= item['duration'] <= 420:
        value += 3
    if any(bad in name for bad in BAD):
        value -= 20
    return value


def search(s, song, artist, has_cookie):
    items = []
    if has_cookie:
        try:
            items = [normalize(x) for x in netease_weapi.cloud_search(s, song, artist)]
        except Exception:
            items = []
    if not items:
        params = {'s': (song + ' ' + artist).strip(), 'type': 1, 'limit': 30, 'offset': 0}
        response = s.get(SEARCH, params=params, timeout=15)
        response.raise_for_status()
        items = [normalize(x) for x in ((response.json().get('result') or {}).get('songs') or [])]
    scored = [(score(item, song, artist), item) for item in items]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for value, item in scored if value > 0] or [item for _, item in scored]


def save_stream(s, url, out):
    with s.get(url, headers=HEADERS, timeout=30, stream=True, allow_redirects=True) as response:
        response.raise_for_status()
        content_type = str(response.headers.get('Content-Type') or '')
        if 'text/html' in content_type:
            return None
        os.makedirs(os.path.dirname(out), exist_ok=True)
        size = 0
        with open(out, 'wb') as handle:
            for chunk in response.iter_content(64 * 1024):
                if chunk:
                    handle.write(chunk)
                    size += len(chunk)
        if size < 300 * 1024:
            try:
                os.remove(out)
            except OSError:
                pass
            return None
    return out


def download(s, item, out, has_cookie):
    song_id = item.get('id')
    if not song_id:
        return None
    if has_cookie:
        try:
            url = netease_weapi.player_url(s, song_id, 'exhigh')
            if url:
                path = save_stream(s, url, out)
                if path:
                    return path
        except Exception:
            pass
    try:
        return save_stream(s, OUTER % song_id, out)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    song, artist = split_query(args.query)
    s, has_cookie = session()
    direct = parse_direct(args.query)
    if direct:
        detail = None
        try:
            detail = netease_weapi.song_detail(s, int(direct))
        except Exception:
            detail = None
        item = {
            'id': int(direct),
            'name': (detail or {}).get('name') or ('id ' + direct),
            'artists': (detail or {}).get('artists') or [],
            'duration': 0.0,
            'fee': 1,
        }
        try:
            path = download(s, item, args.out, has_cookie)
        except Exception:
            path = None
        if path:
            print(json.dumps({
                'ok': True, 'path': path, 'id': direct, 'title': item['name'],
                'artist': '/'.join(item['artists']), 'vip': True,
                'cookies': has_cookie, 'direct': True,
            }, ensure_ascii=False))
            return 0
        print(json.dumps({'ok': False, 'error': 'direct id download failed',
                          'id': direct, 'cookies': has_cookie}, ensure_ascii=False))
        return 0
    try:
        candidates = search(s, song, artist, has_cookie)
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': 'search: ' + str(exc)}, ensure_ascii=False))
        return 0
    for item in candidates[:6]:
        try:
            path = download(s, item, args.out, has_cookie)
        except Exception:
            continue
        if path:
            print(json.dumps({
                'ok': True, 'path': path, 'id': item['id'],
                'title': item['name'], 'artist': '/'.join(item['artists']),
                'vip': item['fee'] != 0, 'cookies': has_cookie,
            }, ensure_ascii=False))
            return 0
    print(json.dumps({'ok': False, 'error': 'no downloadable song', 'cookies': has_cookie}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
