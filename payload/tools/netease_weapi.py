# -*- coding: utf-8 -*-
"""网易云 weapi 最小实现：搜索 + 会员播放地址（配合 cookies.txt）。"""
import base64
import json
import random
import string

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

NONCE = '0CoJUm6Qyw8W8jud'
IV = '0102030405060708'
PUBKEY = '010001'
MODULUS = ('00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e'
           '417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce'
           '10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/122.0 Safari/537.36',
    'Referer': 'https://music.163.com/',
}


def _aes(text, key):
    cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, IV.encode('utf-8'))
    return base64.b64encode(cipher.encrypt(pad(text.encode('utf-8'), 16)))


def _rsa(text):
    value = pow(int(text[::-1].encode('utf-8').hex(), 16), int(PUBKEY, 16), int(MODULUS, 16))
    return format(value, 'x').zfill(256)


def _encrypt(payload):
    raw = json.dumps(payload, separators=(',', ':'))
    key = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    params = _aes(_aes(raw, NONCE).decode('ascii'), key).decode('ascii')
    return params, _rsa(key)


def post(session, path, payload, timeout=20):
    csrf = session.cookies.get('__csrf', '')
    params, enc_sec = _encrypt(payload)
    response = session.post(
        'https://music.163.com/weapi/' + path,
        params={'csrf_token': csrf},
        data={'params': params, 'encSecKey': enc_sec},
        headers=HEADERS, timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def cloud_search(session, song, artist, limit=30):
    data = post(session, 'cloudsearch/get/web', {
        's': (song + ' ' + artist).strip(), 'type': 1, 'limit': limit, 'offset': 0,
    })
    return ((data.get('result') or {}).get('songs') or [])


def player_url(session, song_id, level='exhigh'):
    data = post(session, 'song/enhance/player/url/v1', {
        'ids': json.dumps([song_id]), 'level': level, 'encodeType': 'flac',
    })
    items = data.get('data') or []
    if isinstance(items, dict):
        items = [items]
    for item in items:
        if isinstance(item, dict) and item.get('url'):
            return item['url']
    return ''

def song_detail(session, song_id):
    data = post(session, 'song/detail', {'ids': json.dumps([song_id]), 'c': '[]'})
    songs = data.get('songs') or []
    if not songs:
        return None
    item = songs[0]
    names = [(a.get('name') if isinstance(a, dict) else str(a)) or '' for a in (item.get('ar') or item.get('artists') or [])]
    return {'id': item.get('id'), 'name': str(item.get('name') or ''), 'artists': names}