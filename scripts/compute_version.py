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
DEFAULT_VARIANT = "aider-chat"

RELEASE_TAG_TEMPLATES = {
    "aider-chat": {
        "pypi": "standalone-v{aider_version}-build{build_number}",
        "main": "standalone-main-{date}-{commit_hash}-build{build_number}",
    },
    "aider-ce": {
        "pypi": "standalone-ce-v{aider_version}-build{build_number}",
        "main": "standalone-ce-main-{date}-{commit_hash}-build{build_number}",
    },
}

RE_RELEASE_TAGS = {
    "aider-chat": {
        "pypi": re.compile(r"^standalone-v(?P<version>[^-]+)-build(?P<build>\d+)$"),
        "main": re.compile(
            r"^standalone-main-(?P<date>\d{8})-(?P<commit>[a-f0-9]+)-build(?P<build>\d+)$"
        ),
    },
    "aider-ce": {
        "pypi": re.compile(r"^standalone-ce-v(?P<version>[^-]+)-build(?P<build>\d+)$"),
        "main": re.compile(
            r"^standalone-ce-main-(?P<date>\d{8})-(?P<commit>[a-f0-9]+)-build(?P<build>\d+)$"
        ),
    },
}


@dataclass
class ReleaseInfo:
    build_number: int


def fetch_releases(repo: str, token: str) -> Iterable[Dict[str, object]]:
    url = f"{API_BASE}/repos/{repo}/releases?per_page=100"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:  # type: ignore[no-untyped-call]
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Unexpected response when querying releases for {repo}")
    return data


def next_build_number(
    releases: Iterable[Dict[str, object]],
    aider_version: str,
    source_type: str = "pypi",
    date_str: str | None = None,
    commit_hash: str | None = None,
    variant: str = DEFAULT_VARIANT,
) -> int:
    max_build = 0
    pattern = RE_RELEASE_TAGS[variant][source_type]
    for release in releases:
        tag_name = release.get("tag_name") if isinstance(release, dict) else None
        if not isinstance(tag_name, str):
            continue
        match = pattern.match(tag_name)
        if not match:
            continue
        if source_type == "main":
            if match.group("date") != date_str or match.group("commit") != commit_hash:
                continue
        else:
            if match.group("version") != aider_version:
                continue
        build_number = int(match.group("build"))
        max_build = max(max_build, build_number)
    return max_build + 1


def build_metadata(
    aider_version: str,
    build_number: int,
    source_type: str = "pypi",
    date_str: str | None = None,
    commit_hash: str | None = None,
    variant: str = DEFAULT_VARIANT,
) -> Dict[str, object]:
    template = RELEASE_TAG_TEMPLATES[variant][source_type]
    if source_type == "main":
        tag_name = template.format(
            date=date_str, commit_hash=commit_hash, build_number=build_number
        )
        if variant == "aider-ce":
            artifact_name = f"aider-ce-main-{date_str}-{commit_hash}-build{build_number}"
        else:
            artifact_name = f"aider-main-{date_str}-{commit_hash}-build{build_number}"
    else:
        tag_name = template.format(
            aider_version=aider_version, build_number=build_number
        )
        if variant == "aider-ce":
            artifact_name = f"aider-ce-{aider_version}-build{build_number}"
        else:
            artifact_name = f"aider-{aider_version}-build{build_number}"
    return {
        "variant": variant,
        "aider_version": aider_version,
        "build_number": build_number,
        "tag_name": tag_name,
        "artifact_name": artifact_name,
        "source_type": source_type,
        "commit_hash": commit_hash,
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
    parser.add_argument(
        "--source-type",
        choices=["pypi", "main"],
        default="pypi",
        help="Source type: pypi (default) or main branch",
    )
    parser.add_argument(
        "--commit-hash",
        help="Git commit hash (required for main branch builds)",
    )
    parser.add_argument(
        "--date",
        help="Build date in YYYYMMDD format (required for main branch builds)",
    )
    parser.add_argument(
        "--variant",
        choices=["aider-chat", "aider-ce"],
        default="aider-chat",
        help="Which aider variant to build (default: aider-chat)",
    )
    args = parser.parse_args(argv)

    if args.source_type == "main" and (not args.commit_hash or not args.date):
        raise SystemExit("--commit-hash and --date are required for main branch builds")

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
        build_number = next_build_number(
            releases,
            args.aider_version,
            source_type=args.source_type,
            date_str=args.date,
            commit_hash=args.commit_hash,
            variant=args.variant,
        )

    metadata = build_metadata(
        args.aider_version,
        build_number,
        source_type=args.source_type,
        date_str=args.date,
        commit_hash=args.commit_hash,
        variant=args.variant,
    )

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
