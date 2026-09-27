from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a request to a deployed workflow API")
    parser.add_argument("--endpoint", required=True, help="Full POST /requests endpoint URL")
    parser.add_argument("--request-file", type=Path, required=True)
    args = parser.parse_args()

    request: dict[str, Any] = json.loads(args.request_file.read_text(encoding="utf-8"))
    import urllib.request

    encoded = json.dumps(request).encode("utf-8")
    http_request = urllib.request.Request(
        args.endpoint,
        data=encoded,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(http_request, timeout=30) as response:  # noqa: S310
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
