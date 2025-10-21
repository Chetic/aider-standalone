# Aider Standalone Builder

This repository houses the tooling to build standalone, self-contained releases of the
[aider](https://github.com/Aider-AI/aider) chat client. The resulting artifact bundles
Python, aider, and all dependencies into a single executable suited for RHEL 9
environments.

## Repository Layout

- `scripts/`
  - `fetch_aider_release.py` – resolve the aider version to build (defaults to the
    latest PyPI release).
  - `compute_version.py` – calculate the build number and metadata for GitHub releases.
  - `build_standalone.py` – assemble the PyInstaller-based executable and manifest.
- `.github/workflows/build-standalone.yml` – GitHub Actions workflow that produces the
  standalone release artifact.

## Building Locally

A RHEL 9 (or compatible) system with Python 3.11 is required. The build process creates a
virtual environment and installs all dependencies in isolation.

```bash
python scripts/fetch_aider_release.py > build/aider_version.txt
AIDER_VERSION=$(cat build/aider_version.txt)
python scripts/compute_version.py \
  --aider-version "$AIDER_VERSION" \
  --override-build-number 1 \
  --output build/version.json
python scripts/build_standalone.py \
  --aider-version "$AIDER_VERSION" \
  --build-number 1 \
  --output-dir build/artifacts \
  --metadata build/manifest.json
```

The executable will be written to `build/artifacts/aider-standalone-build1` with a
corresponding `requirements.lock` file and JSON manifest.

## GitHub Actions Workflow

The workflow can be triggered manually (optionally specifying an aider version) or on a
schedule. It performs the following steps:

1. Resolve the aider version (defaulting to the latest PyPI release).
2. Determine the next build number based on prior GitHub releases.
3. Build the standalone executable inside a RHEL 9 container.
4. Run a smoke test (`--help`) to verify the artifact starts.
5. Upload the build outputs and publish a GitHub release tagged with the computed version.

## Triggering a Build Manually

Use the **Run workflow** button in GitHub Actions and optionally provide an `aider_version`
input. If omitted, the workflow builds the latest aider release.

## Verifying the Artifact

After downloading the executable, compare its SHA-256 checksum against the value recorded
in the manifest JSON. Run the binary with `--help` on a RHEL 9 system to ensure it
operates as expected.
