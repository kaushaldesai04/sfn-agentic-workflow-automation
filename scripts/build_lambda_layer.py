from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    layer_root = project_root / "lambda_layer"
    target = layer_root / "python"
    marker = layer_root / ".built"

    if target.exists():
        shutil.rmtree(target)
    marker.unlink(missing_ok=True)
    target.mkdir(parents=True)

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--requirement",
        str(layer_root / "requirements.txt"),
        "--target",
        str(target),
        "--platform",
        "manylinux2014_aarch64",
        "--implementation",
        "cp",
        "--python-version",
        "3.12",
        "--only-binary=:all:",
        "--upgrade",
    ]
    subprocess.run(command, check=True)  # nosec B603 - fixed executable and arguments
    requirements_hash = hashlib.sha256(
        (layer_root / "requirements.txt").read_bytes()
    ).hexdigest()
    marker.write_text(f"{requirements_hash}\n", encoding="utf-8")
    print(f"Lambda layer built at {layer_root}")


if __name__ == "__main__":
    main()
