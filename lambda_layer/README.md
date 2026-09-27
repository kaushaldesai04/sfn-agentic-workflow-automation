# Lambda dependency layer

This directory is the source asset for the shared Python 3.12 Lambda layer.

Build it from the repository root before synthesis:

```powershell
python scripts/build_lambda_layer.py
```

The script downloads Linux ARM64 wheels even when it runs on Windows. Generated packages under
`python/` and the `.built` marker are intentionally ignored by Git and must not be edited manually.
