#!/usr/bin/env python3
"""Build a standalone aider executable using PyInstaller."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict


def run(
    cmd: list[str],
    *,
    env: Dict[str, str] | None = None,
    cwd: Path | None = None,
) -> None:
    print(f":: Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env, cwd=str(cwd) if cwd else None)


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_standalone(
    aider_version: str,
    build_number: int,
    output_dir: Path,
    aider_source_path: Path | None = None,
    variant: str = "aider-chat",
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aider-standalone-") as tmp:
        tmp_path = Path(tmp)
        venv_dir = tmp_path / "venv"
        python = Path(sys.executable)
        run([str(python), "-m", "venv", str(venv_dir)])
        venv_python = venv_dir / "bin" / "python"
        venv_pip = venv_dir / "bin" / "pip"

        run([str(venv_pip), "install", "--upgrade", "pip", "setuptools", "wheel"])
        run([str(venv_pip), "install", "pip-tools", "pyinstaller"])

        requirements_in = tmp_path / "requirements.in"
        requirements_lock = tmp_path / "requirements.lock"

        if aider_source_path:
            # Install aider from local source first
            run([str(venv_pip), "install", str(aider_source_path)])
            # Only compile tree-sitter-languages with hashes
            requirements = ["tree-sitter-languages"]
        else:
            # Use correct PyPI package based on variant
            # aider-ce PyPI package is deprecated, use cecli-dev instead
            if variant == "aider-ce":
                package_name = "cecli-dev"
            else:
                package_name = "aider-chat"
            requirements = [
                f"{package_name}=={aider_version}",
                "tree-sitter-languages",
            ]
        requirements_in.write_text("\n".join(requirements) + "\n", encoding="utf-8")

        run(
            [
                str(venv_python),
                "-m",
                "piptools",
                "compile",
                "--generate-hashes",
                "--resolver=backtracking",
                str(requirements_in),
                "-o",
                str(requirements_lock),
            ]
        )

        run([str(venv_pip), "install", "--require-hashes", "-r", str(requirements_lock)])

        binary_name = f"aider-standalone"
        dist_dir = tmp_path / "dist"

        launcher_path = tmp_path / "launch_aider.py"
        # Determine module name and entry point based on variant and source
        # - aider-ce from source (GitHub): uses 'aider' module with aider.main:main
        # - aider-ce from PyPI (cecli-dev): uses 'cecli' module with cecli.main:main
        # - aider-chat: uses 'aider' module with aider.__main__:main
        if variant == "aider-ce":
            if aider_source_path:
                # Building from source - uses aider module
                module_name = "aider"
                launcher_code = """\
from aider.main import main


if __name__ == "__main__":
    main()
"""
            else:
                # Building from PyPI (cecli-dev) - uses cecli module
                module_name = "cecli"
                launcher_code = """\
from cecli.main import main


if __name__ == "__main__":
    main()
"""
        else:
            module_name = "aider"
            launcher_code = """\
from aider.__main__ import main


if __name__ == "__main__":
    main()
"""
        launcher_path.write_text(launcher_code, encoding="utf-8")

        pyinstaller_cmd = [
            str(venv_python),
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            "--name",
            binary_name,
            "--onefile",
            "--runtime-tmpdir",
            "./.aider-standalone-tmp",
            "--collect-all",
            module_name,
            "--collect-data",
            "litellm",
            "--collect-submodules",
            "litellm",
            "--collect-data",
            "tiktoken",
            "--collect-data",
            "tiktoken_ext",
            "--collect-submodules",
            "tiktoken_ext",
            "--collect-data",
            "tiktoken_ext.openai_public",
            "--collect-submodules",
            "tiktoken_ext.openai_public",
            "--collect-data",
            "tree_sitter_languages",
            "--collect-submodules",
            "tree_sitter_languages",
            "--collect-binaries",
            "tree_sitter_languages",
            str(launcher_path),
        ]
        run(pyinstaller_cmd, cwd=tmp_path)

        artifact = dist_dir / binary_name
        if not artifact.exists():
            raise SystemExit(f"PyInstaller failed to produce expected artifact at {artifact}")

        final_artifact = output_dir / f"aider-standalone-build{build_number}"
        shutil.copy2(artifact, final_artifact)
        os.chmod(final_artifact, 0o755)

        final_lock = output_dir / "requirements.lock"
        shutil.copy2(requirements_lock, final_lock)

    checksum = sha256sum(final_artifact)
    return {
        "artifact": str(final_artifact),
        "checksum": checksum,
        "lock_file": str(final_lock),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aider-version", required=True)
    parser.add_argument("--build-number", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("build/artifacts"))
    parser.add_argument("--metadata", type=Path, required=True, help="Path to metadata JSON file")
    parser.add_argument(
        "--aider-source-path",
        type=Path,
        help="Path to local aider source (for main branch builds)",
    )
    parser.add_argument(
        "--variant",
        choices=["aider-chat", "aider-ce"],
        default="aider-chat",
        help="Which aider variant to build (default: aider-chat)",
    )
    args = parser.parse_args(argv)

    metadata = build_standalone(
        args.aider_version,
        args.build_number,
        args.output_dir,
        aider_source_path=args.aider_source_path,
        variant=args.variant,
    )

    manifest = {
        "variant": args.variant,
        "aider_version": args.aider_version,
        "build_number": args.build_number,
        "artifact_path": metadata["artifact"],
        "artifact_sha256": metadata["checksum"],
        "lock_file": metadata["lock_file"],
    }
    args.metadata.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
