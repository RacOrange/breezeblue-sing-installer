import os
import sys

BASE = os.environ.get('HF_MIRROR', 'https://hf-mirror.com').rstrip('/')
ROOT = os.path.abspath(sys.argv[sys.argv.index('--root') + 1]) if '--root' in sys.argv else os.getcwd()
SEED = os.path.join(ROOT, 'seed-vc')


def get_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def download(repo, filename, dest):
    if get_size(dest) > 0:
        print('skip', filename)
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    url = BASE + '/' + repo + '/resolve/main/' + filename
    part = dest + '.part'
    start = get_size(part)
    headers = {'Range': 'bytes=%d-' % start} if start else {}
    import requests
    with requests.get(url, headers=headers, stream=True, timeout=300) as response:
        if response.status_code == 416:
            os.replace(part, dest)
            return dest
        response.raise_for_status()
        mode = 'ab' if start and response.status_code == 206 else 'wb'
        with open(part, mode) as handle:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    handle.write(chunk)
    os.replace(part, dest)
    print('ok', filename, get_size(dest))
    return dest


def main():
    files = [
        ('nvidia/bigvgan_v2_44khz_128band_512x', 'config.json', 'models/bigvgan-44k/config.json'),
        ('nvidia/bigvgan_v2_44khz_128band_512x', 'bigvgan_generator.pt', 'models/bigvgan-44k/bigvgan_generator.pt'),
        ('openai/whisper-small', 'config.json', 'models/whisper-small/config.json'),
        ('openai/whisper-small', 'model.safetensors', 'models/whisper-small/model.safetensors'),
        ('openai/whisper-small', 'preprocessor_config.json', 'models/whisper-small/preprocessor_config.json'),
        ('openai/whisper-small', 'generation_config.json', 'models/whisper-small/generation_config.json'),
        ('openai/whisper-small', 'tokenizer.json', 'models/whisper-small/tokenizer.json'),
        ('openai/whisper-small', 'tokenizer_config.json', 'models/whisper-small/tokenizer_config.json'),
        ('openai/whisper-small', 'vocab.json', 'models/whisper-small/vocab.json'),
        ('openai/whisper-small', 'merges.txt', 'models/whisper-small/merges.txt'),
        ('openai/whisper-small', 'normalizer.json', 'models/whisper-small/normalizer.json'),
        ('openai/whisper-small', 'added_tokens.json', 'models/whisper-small/added_tokens.json'),
        ('openai/whisper-small', 'special_tokens_map.json', 'models/whisper-small/special_tokens_map.json'),
        ('Plachta/Seed-VC', 'DiT_seed_v2_uvit_whisper_base_f0_44k_bigvgan_pruned_ft_ema_v2.pth',
         'checkpoints/DiT_seed_v2_uvit_whisper_base_f0_44k_bigvgan_pruned_ft_ema_v2.pth'),
        ('Plachta/Seed-VC', 'config_dit_mel_seed_uvit_whisper_base_f0_44k.yml',
         'checkpoints/config_dit_mel_seed_uvit_whisper_base_f0_44k.yml'),
        ('lj1995/VoiceConversionWebUI', 'rmvpe.pt', 'models/rmvpe.pt'),
        ('funasr/campplus', 'campplus_cn_common.bin', 'models/campplus/campplus_cn_common.bin'),
    ]
    failed = 0
    for repo, name, rel in files:
        try:
            download(repo, name, os.path.join(SEED, rel))
        except Exception as error:
            failed += 1
            print('FAIL', repo, name, error)
    print('done failed=%d' % failed)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
