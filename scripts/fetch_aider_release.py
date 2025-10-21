#!/usr/bin/env python3
"""Resolve the aider release version to build."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict

PYPI_URL = "https://pypi.org/pypi/aider-chat/json"


def fetch_release_data() -> Dict[str, Any]:
    req = urllib.request.Request(PYPI_URL)
    with urllib.request.urlopen(req) as resp:  # type: ignore[no-untyped-call]
        return json.loads(resp.read().decode("utf-8"))


def resolve_version(requested: str | None) -> str:
    data = fetch_release_data()
    if requested:
        if requested not in data.get("releases", {}):
            available = sorted(data.get("releases", {}).keys(), reverse=True)
            raise SystemExit(
                f"Requested aider version '{requested}' was not found on PyPI. "
                f"Available versions (newest first): {', '.join(available[:20])}"
            )
        return requested
    version = data.get("info", {}).get("version")
    if not version:
        raise SystemExit("Unable to determine latest aider release from PyPI response")
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requested", help="Explicit aider version to use", default=None)
    parser.add_argument(
        "--github-output",
        help="File path provided by GitHub Actions for setting outputs",
    )
    args = parser.parse_args(argv)

    try:
        version = resolve_version(args.requested)
    except urllib.error.URLError as exc:  # pragma: no cover - network failure
        raise SystemExit(f"Failed to query PyPI for aider releases: {exc}")

    print(version)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write(f"aider_version={version}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
