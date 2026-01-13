# Aider Standalone

Standalone, self-contained builds of [aider](https://github.com/Aider-AI/aider) for RHEL 9.

## What is this?

This repository provides pre-built executables of aider that bundle Python and all dependencies into a single file. No Python installation required on the target system.

## Download

Get the latest release from the [Releases page](../../releases).

## Usage

```bash
chmod +x aider-standalone-build*
./aider-standalone-build* --help
```

The executable works on systems where `/tmp` is mounted with `noexec` by using a local `.aider-standalone-tmp` directory.

## Verifying Downloads

Each release includes a `manifest.json` with the SHA-256 checksum. Compare it against your download:

```bash
sha256sum aider-standalone-build*
```
