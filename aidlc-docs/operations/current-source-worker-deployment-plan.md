# Current Source Worker Deployment Plan

## Approval and fixed scope

- **Approved at**: 2026-08-21T04:29:20.788Z
- **User input**: `Worker 배포`
- **Target**: `/opt/prompton-ai-worker` and `prompton-worker.service` on the current dev Worker host.
- **Source state**: branch `feature/ai-worker-operational-readiness`, HEAD `94c53f6bcfc260582f729070ef159286b8412468`, with explicitly approved working-tree runtime changes.
- **Runtime delta**: Source and active release inventories both contain 27 files. Only `ai/generator.py`, `ai/refiner.py`, and `build/builder.py` differ; no release file is missing or extra.
- **Unchanged runtime inputs**: `pyproject.toml`, `uv.lock`, and the systemd unit match the active deployment.

## Step 1: Pre-deployment gate

- [x] Run complete pytest, Ruff, strict mypy, compileall, lock, and diff checks.
- [x] Verify Status API/no-DynamoDB source boundaries and required runtime files.
- [x] Verify environment permissions, writable paths, SDK 36/Build Tools 36, disk, and Worker idle state without exposing values.

## Step 2: Backup and install

- [x] Stop the idle Worker gracefully and verify no Kiro child remains.
- [x] Create a root-only rollback backup of the three active files and a checksum/mode manifest.
- [x] Atomically install only the three approved source files while preserving active ownership and modes.
- [x] Verify installed hashes exactly match source and all other release files remain unchanged.

## Step 3: Deployed validation and restart

- [x] Compile the deployed runtime and verify exact `claude-opus-5` plus SDK 36/Compose/Wrapper guardrails.
- [x] Verify frozen dependency state without changing the active virtual environment.
- [x] Start the Worker and verify active/running, stable PID, zero restart loop, and no startup error marker.
- [x] Confirm post-start Kiro organization authentication and idle polling state without submitting a Job.

## Step 4: Closeout

- [x] Update active operational state and audit with deployment and rollback evidence.
- [x] Run final source/deployed inventory, backup, Markdown, whitespace, secret, and Worker stability checks.

## Rollback

If install, compile, dependency, authentication, or startup verification fails: keep the Worker stopped, atomically restore the three files from the root-only backup with their recorded owner/mode, compile the restored runtime, restart the Worker, and verify the prior stable state. Do not purge or manually delete SQS messages.

## Safety boundary

Do not copy tests, docs, `.kiro`, `.git`, caches, bytecode, `.venv`, credentials, environment files, or Job data into `/opt`. Do not change the systemd unit, protected environment, dependencies, Queue, IAM, DynamoDB, external Worker, authentication provider, or AWS resources. The previously accepted duplicate-consumer risk remains unchanged. No commit or push is included.
