"""Verify that the installed wheel can execute an actual CUDA kernel."""

import sys


def main():
    try:
        import torch
    except Exception as error:
        print(f'CUDA_DEPENDENCIES_INVALID: {type(error).__name__}', file=sys.stderr)
        return 1
    if not torch.cuda.is_available():
        print('CUDA_UNAVAILABLE: PyTorch cannot access an NVIDIA CUDA device', file=sys.stderr)
        return 1
    try:
        major, minor = torch.cuda.get_device_capability(0)
        result = torch.arange(4, device='cuda:0').add(1).sum().item()
        if result != 10:
            raise RuntimeError('incorrect CUDA result')
    except Exception as error:
        message = str(error).lower()
        if 'no kernel image' in message or 'invalid device function' in message:
            print('CUDA_ARCH_UNSUPPORTED: this PyTorch build cannot execute on the GPU', file=sys.stderr)
        else:
            print(f'CUDA_EXECUTION_FAILED: {type(error).__name__}', file=sys.stderr)
        return 1
    print(f'cuda-ok torch={torch.__version__} sm_{major}{minor}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
