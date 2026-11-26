import json
import platform
import sys
import traceback

result = {
    'python': sys.version.split()[0],
    'platform': platform.platform(),
    'torch': None,
    'torch_directml': None,
    'device_count': 0,
    'device': None,
    'matmul_ok': False,
    'error': '',
}
try:
    import torch
    result['torch'] = torch.__version__
    result['cuda_available'] = bool(torch.cuda.is_available())
    try:
        import torch_directml
        result['torch_directml'] = getattr(torch_directml, '__version__', 'unknown')
        result['device_count'] = int(torch_directml.device_count() or 0)
        if result['device_count'] > 0:
            device = torch_directml.device()
            result['device'] = str(device)
            a = torch.ones((64, 64), dtype=torch.float32).to(device)
            b = torch.ones((64, 64), dtype=torch.float32).to(device)
            c = (a @ b).cpu()
            result['matmul_ok'] = bool(float(c[0, 0]) == 64.0)
    except Exception:
        result['error'] = traceback.format_exc()
except Exception:
    result['error'] = traceback.format_exc()
print(json.dumps(result, ensure_ascii=False))
