#!/usr/bin/env python3
"""Compute build metadata for the standalone aider artifact."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

API_BASE = "https://api.github.com"
RELEASE_TAG_TEMPLATE = "standalone-v{aider_version}-build{build_number}"


@dataclass
class ReleaseInfo:
    build_number: int


RE_RELEASE_TAG = re.compile(r"^standalone-v(?P<version>[^-]+)-build(?P<build>\d+)$")


def fetch_releases(repo: str, token: str) -> Iterable[Dict[str, object]]:
    url = f"{API_BASE}/repos/{repo}/releases?per_page=100"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:  # type: ignore[no-untyped-call]
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Unexpected response when querying releases for {repo}")
    return data


def next_build_number(releases: Iterable[Dict[str, object]], aider_version: str) -> int:
    max_build = 0
    for release in releases:
        tag_name = release.get("tag_name") if isinstance(release, dict) else None
        if not isinstance(tag_name, str):
            continue
        match = RE_RELEASE_TAG.match(tag_name)
        if not match:
            continue
        if match.group("version") != aider_version:
            continue
        build_number = int(match.group("build"))
        max_build = max(max_build, build_number)
    return max_build + 1


def build_metadata(aider_version: str, build_number: int) -> Dict[str, object]:
    tag_name = RELEASE_TAG_TEMPLATE.format(aider_version=aider_version, build_number=build_number)
    artifact_name = f"aider-{aider_version}-build{build_number}"
    return {
        "aider_version": aider_version,
        "build_number": build_number,
        "tag_name": tag_name,
        "artifact_name": artifact_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aider-version", required=True)
    parser.add_argument("--github-output", help="GitHub Actions output file")
    parser.add_argument("--output", help="Path to write JSON metadata", required=True)
    parser.add_argument(
        "--override-build-number",
        type=int,
        help="Explicit build number to use instead of auto-increment",
    )
    args = parser.parse_args(argv)

    build_number = args.override_build_number
    if build_number is None:
        repo = os.environ.get("GITHUB_REPOSITORY")
        token = os.environ.get("GITHUB_TOKEN")
        if not repo or not token:
            raise SystemExit(
                "GITHUB_REPOSITORY and GITHUB_TOKEN must be set to compute build numbers automatically"
            )
        try:
            releases = list(fetch_releases(repo, token))
        except urllib.error.URLError as exc:  # pragma: no cover - network failure
            raise SystemExit(f"Failed to query GitHub releases: {exc}")
        build_number = next_build_number(releases, args.aider_version)

    metadata = build_metadata(args.aider_version, build_number)

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")

    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write(f"build_number={metadata['build_number']}\n")
            handle.write(f"tag_name={metadata['tag_name']}\n")
            handle.write(f"artifact_name={metadata['artifact_name']}\n")

    print(json.dumps(metadata))
    return 0


if __name__ == "__main__":
    sys.exit(main())
