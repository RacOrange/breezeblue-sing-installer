# A-card test plan

1. Run `setup.ps1` and `diagnose.ps1`.
2. Generate a **20 second** test cover first, not a full song.
3. If 20s succeeds, try one full song.
4. On any failure, run `collect.ps1` and report the zip.

Expected success markers in `data/logs/a-card-diagnostics.log`:

```text
backend=dml device=privateuseone:0
```

and in `seedvc.log`, the process should not mention CUDA availability errors.

Known A-card-specific failures to report:

- `DML_UNAVAILABLE`: torch-directml cannot see a DirectX 12 adapter.
- `A_GPU_BACKEND_UNAVAILABLE`: neither CUDA nor DirectML is available.
- Unsupported operator / `privateuseone` stack trace: keep the full traceback.
- Out of memory: report GPU model, VRAM and whether it was a 20s or full-song render.

Do not include WeChat chat text or credentials in reports. `collect.ps1` only gathers system, GPU, Python and render logs.
