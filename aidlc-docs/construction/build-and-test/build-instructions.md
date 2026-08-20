# Build Instructions

## Scope

This repository contains one Python application unit, `ai-worker`. It is configured with `tool.uv.package = false`, so the deployable artifact is the source tree plus `uv.lock`; no wheel or sdist is expected. The build gate consists of a frozen dependency sync, lockfile validation, Python bytecode compilation, and deployment-file presence checks.

## Prerequisites

### Local quality build
- Linux x86_64 or aarch64
- Python 3.12; validated with Python 3.12.3
- uv 0.8.12
- Network access to the package registry only when the lockfile cache is cold
- At least 2 GB free disk space for the virtual environment and caches

### EC2 runtime and generated Android app build
- Target sizing: t3.xlarge, 4 vCPU, 16 GB RAM, with `/data/jobs` on writable storage
- `kiro-cli` 2.18.1 with authenticated model access
- Model ID `claude-opus-5`
- Gradle 9.7.0 or a version compatible with the generated project
- Java and Android SDK versions compatible with the generated Android Gradle Plugin
- EC2 Instance Profile with the SQS, S3, and DynamoDB permissions listed in the NFR design
- systemd and a dedicated `prompton` service account

The validation host currently has kiro-cli 2.18.1, Gradle 9.7.0, Java 21.0.11, and an Android SDK at `/home/ubuntu/android-sdk`. The deployment template references Java 17 paths, so the EC2 image and `JAVA_HOME` must be aligned before service activation.

## Environment Variables

Required by the Worker at runtime:

| Variable | Purpose |
|---|---|
| `SQS_QUEUE_URL` | Main Job queue URL |
| `DYNAMODB_TABLE_NAME` | Job-state table name |
| `S3_BUCKET_NAME` | Input and output bucket |

Optional variables and defaults are documented in `deploy/env.example`: `AWS_REGION`, `WORK_DIR`, `VISIBILITY_TIMEOUT`, `CLEANUP_HOURS`, `LOG_LEVEL`, `KIRO_CLI_PATH`, `GRADLE_PATH`, `ANDROID_HOME`, `ANDROID_SDK_ROOT`, `JAVA_HOME`, and `GRADLE_USER_HOME`.

Do not put AWS access keys or session tokens in the environment file. Use the EC2 Instance Profile.

## Build Steps

Run all commands from the repository root.

### 1. Install the pinned uv executable

If uv is already installed, verify it with `uv --version`. Otherwise install the official standalone release into the user-local path:

```bash
set -euo pipefail
UV_VERSION=0.8.12
case "$(uname -m)" in
  x86_64) UV_TARGET=x86_64-unknown-linux-gnu ;;
  aarch64|arm64) UV_TARGET=aarch64-unknown-linux-gnu ;;
  *) echo "Unsupported architecture" >&2; exit 1 ;;
esac
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
curl --fail --location --silent --show-error \
  "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${UV_TARGET}.tar.gz" \
  --output "$TMP_DIR/uv.tar.gz"
tar -xzf "$TMP_DIR/uv.tar.gz" -C "$TMP_DIR"
install -d "$HOME/.local/bin"
install -m 0755 "$TMP_DIR/uv-${UV_TARGET}/uv" "$HOME/.local/bin/uv"
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

Expected version: `uv 0.8.12`.

### 2. Synchronize locked dependencies

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync --extra dev --frozen
uv lock --check
```

`--frozen` prevents an implicit lockfile update. A build must fail rather than silently changing dependency resolution.

### 3. Compile all application and test modules

```bash
uv run python -m compileall -q \
  main.py ai build config dynamo models s3 sqs utils worker tests
```

Successful compilation exits with status 0 and no output.

### 4. Verify mandatory deployment files

```bash
test -f pyproject.toml
test -f uv.lock
test -f deploy/env.example
test -f deploy/prompton-worker.service
test -f main.py
```

### 5. Run quality gates

```bash
uv run pytest
uv run ruff check .
uv run mypy main.py config models sqs s3 dynamo ai build utils worker
```

All commands must exit with status 0 before deployment.

## Build Outputs

| Output | Location | Notes |
|---|---|---|
| Frozen Python environment | `.venv/` | Recreated with `uv sync --frozen`; do not deploy by copying between hosts |
| Worker application | Repository source tree | Deploy source plus `pyproject.toml` and `uv.lock` |
| systemd unit template | `deploy/prompton-worker.service` | Install as `/etc/systemd/system/prompton-worker.service` |
| Environment template | `deploy/env.example` | Copy to `/etc/prompton-worker/env`, then set deployment values |
| Runtime Android source | `${WORK_DIR}/{jobId}/project/` | Generated per Job by kiro-cli |
| Runtime APK | `${WORK_DIR}/{jobId}/output/app-debug.apk` | Generated per Job by Gradle Wrapper |

## EC2 Deployment Build Check

After copying the source to `/opt/prompton-ai-worker`:

```bash
cd /opt/prompton-ai-worker
sudo -u prompton env HOME=/home/prompton \
  /home/prompton/.local/bin/uv sync --extra dev --frozen
sudo install -m 0644 deploy/prompton-worker.service \
  /etc/systemd/system/prompton-worker.service
sudo systemctl daemon-reload
sudo systemctl cat prompton-worker.service
```

Before starting the service, ensure every path named by `ReadWritePaths` exists and is writable by `prompton`. If `GRADLE_USER_HOME=/data/gradle` is used, add `/data/gradle` to `ReadWritePaths` and create it with the correct ownership.

## Troubleshooting

### `uv: command not found`
- Add `$HOME/.local/bin` to `PATH` or invoke `$HOME/.local/bin/uv` directly.
- Verify the executable architecture and mode with `file ~/.local/bin/uv` and `ls -l ~/.local/bin/uv`.

### Frozen sync or lock check fails
- Confirm `pyproject.toml` and `uv.lock` come from the same revision.
- Do not remove `--frozen` in CI. Regenerate the lockfile only as an explicit dependency-update change.

### Python compilation or import fails
- Confirm `python --version` is 3.12.x.
- Delete only the reproducible environment with `rm -rf .venv`, then rerun the frozen sync.

### kiro-cli exits with an unrecognized command
- The Worker requires `kiro-cli chat --no-interactive`; `kiro-cli generate` is not supported by version 2.18.1.
- Verify with `kiro-cli chat --help` and `kiro-cli chat --list-models --format json-pretty`.

### Android build fails
- Check `java -version`, `gradle --version`, Android SDK packages, generated project Gradle Wrapper, and Android Gradle Plugin compatibility.
- Ensure Gradle cache and Android SDK paths are writable under the systemd sandbox.
- Review the sanitized Worker logs and the generated project under `${WORK_DIR}/{jobId}/project/`.
