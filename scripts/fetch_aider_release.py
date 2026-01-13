#!/usr/bin/env python3
"""Resolve the aider release version to build."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict

PYPI_URLS = {
    "aider-chat": "https://pypi.org/pypi/aider-chat/json",
    # aider-ce is deprecated, use cecli-dev instead for PyPI builds
    "aider-ce": "https://pypi.org/pypi/cecli-dev/json",
}
DEFAULT_VARIANT = "aider-chat"


def fetch_release_data(variant: str = DEFAULT_VARIANT) -> Dict[str, Any]:
    url = PYPI_URLS.get(variant, PYPI_URLS[DEFAULT_VARIANT])
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:  # type: ignore[no-untyped-call]
        return json.loads(resp.read().decode("utf-8"))


def resolve_version(requested: str | None, variant: str = DEFAULT_VARIANT) -> str:
    data = fetch_release_data(variant)
    if requested:
        if requested not in data.get("releases", {}):
            available = sorted(data.get("releases", {}).keys(), reverse=True)
            raise SystemExit(
                f"Requested {variant} version '{requested}' was not found on PyPI. "
                f"Available versions (newest first): {', '.join(available[:20])}"
            )
        return requested
    version = data.get("info", {}).get("version")
    if not version:
        raise SystemExit(f"Unable to determine latest {variant} release from PyPI response")
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requested", help="Explicit aider version to use", default=None)
    parser.add_argument(
        "--variant",
        choices=["aider-chat", "aider-ce"],
        default="aider-chat",
        help="Which aider variant to query (default: aider-chat)",
    )
    parser.add_argument(
        "--github-output",
        help="File path provided by GitHub Actions for setting outputs",
    )
    args = parser.parse_args(argv)

    try:
        version = resolve_version(args.requested, args.variant)
    except urllib.error.URLError as exc:  # pragma: no cover - network failure
        raise SystemExit(f"Failed to query PyPI for {args.variant} releases: {exc}")

    print(version)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write(f"aider_version={version}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
