# Security Test Instructions - ai-worker Status API Target

## 1. Scope and Extension Status

The optional Security Baseline extension is disabled and is N/A for extension compliance. Project-specific requirements remain mandatory: least-privilege Worker IAM, default TLS verification, protected optional API key, protected environment/workspaces, systemd hardening, and zero sensitive log disclosure.

Instruction generation does not authorize dependency downloads, scanner network access, AWS calls, IAM changes, target-host access, or live Status API requests. Run those sections only in an approved CI/test environment.

## 2. Automated Security Behavior Gate

```bash
set -euo pipefail
uv sync --frozen --extra dev
uv run pytest -q \
  tests/test_status_api_client.py \
  tests/test_orchestrator.py \
  tests/test_config.py \
  tests/test_main.py \
  tests/test_cleanup.py \
  tests/test_s3_client.py \
  tests/test_sqs_client.py
```

Expected: 106 tests pass.

Security-relevant behaviors:

- Optional key sent only through `x-api-key` and absent when blank.
- Key excluded from Config repr, exceptions, and captured logs.
- Payload, Backend body, raw external exception text, Client JSON, Hermes output, credentials, and signed URLs excluded from logs.
- Requests uses default TLS verification with no disable option.
- FAILED messages use approved safe text/error codes.
- Job workspace uses owner-only permissions where POSIX modes are available.
- Input/asset/path boundaries remain validated.

## 3. Static Status API Security Checks

```bash
uv run python - <<'PY'
from pathlib import Path

roots = ["main.py", "ai", "build", "config", "models", "s3", "sqs", "status_api", "utils", "worker", "deploy"]
files: list[Path] = []
for item in roots:
    path = Path(item)
    if path.is_file():
        files.append(path)
    else:
        files.extend(sorted(path.rglob("*.py")))
        files.extend(sorted(path.rglob("*.service")))
        files.extend(sorted(path.rglob("*.example")))
text = "\n".join(path.read_text(encoding="utf-8") for path in files)
for forbidden in (
    "verify=False",
    "disable_warnings",
    "DynamoClient",
    "DYNAMODB_TABLE_NAME",
    "get_job_status",
    "append_log",
):
    assert forbidden not in text, forbidden
client = Path("status_api/client.py").read_text(encoding="utf-8")
assert ".patch(" in client
assert ".get(" not in client
print(f"security boundary passed across {len(files)} files")
PY
```

## 4. Credential and Secret Scan

Scan production/config/deployment files. Tests are excluded because they intentionally use sentinel values.

```bash
uv run python - <<'PY'
from pathlib import Path
import re

roots = ["main.py", "ai", "build", "config", "models", "s3", "sqs", "status_api", "utils", "worker", "deploy"]
patterns = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)aws_(?:secret_access_key|session_token)\s*[:=]\s*\S+"),
)
for item in roots:
    path = Path(item)
    files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
    for file in files:
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in patterns:
            assert not pattern.search(text), f"potential secret in {file}"
print("production secret scan passed")
PY
```

A match requires review; never copy the matched value into an issue or evidence bundle.

## 5. Optional Pinned Dependency and Static Scanners

These commands download pinned ephemeral tools and contact advisory/package services. Run only with approved network access; they do not modify project dependencies.

```bash
set -euo pipefail
tmp_requirements="$(mktemp)"
trap 'rm -f "$tmp_requirements"' EXIT
uv export --frozen --all-extras --format requirements-txt \
  --output-file "$tmp_requirements"
uvx --from pip-audit==2.9.0 pip-audit \
  --requirement "$tmp_requirements"
uvx --from bandit==1.8.6 bandit -r \
  main.py ai build config models s3 sqs status_api utils worker
```

Disposition rules:

- Review every vulnerability against the exact locked version and reachable Worker behavior.
- Do not suppress a finding without owner, rationale, and expiry.
- Any Bandit High finding blocks release; review/document every Medium finding.
- Pin/version changes require a separately reviewed dependency update and new frozen lock.

## 6. Optional API Key and Environment Protection

On the authorized target host:

```bash
sudo stat -c '%U %G %a %n' /etc/prompton-worker/env
sudo grep -En '^(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN)=' \
  /etc/prompton-worker/env && exit 1 || true
```

Pass conditions:

- Mode 0640 or stricter.
- Owner/group limited to administrator and service identity.
- No static AWS key names.
- `PROMPTON_STATUS_API_KEY` may be absent/empty or securely injected; never print its value.
- systemd does not expose it through command-line arguments.

Do not attach the environment file or `systemctl show ... Environment` output to evidence.

## 7. IAM Least-Privilege Review

No Worker IAM/IaC policy file exists in this repository. Inspect the deployed Instance Profile through the authorized infrastructure process.

Required Worker actions:

- SQS: ReceiveMessage, DeleteMessage, ChangeMessageVisibility, GetQueueAttributes.
- S3: GetObject for requirements/assets, constrained ListBucket for asset prefixes, PutObject for source/artifact, and permissions needed for artifact metadata verification.

Required negative evidence:

- No Worker DynamoDB action/resource.
- No wildcard administrator policy.
- No unrelated mutation or role-management actions.
- No static credentials in user data, environment files, systemd overrides, or source.

Do not change or detach policies while performing review. Policy remediation is an infrastructure change requiring separate approval.

## 8. TLS and Network Review

Source scan and fake-session assertions must show no certificate-verification override. On the target host, perform a default-context TLS handshake only:

```bash
set -a
# shellcheck disable=SC1091
source /etc/prompton-worker/env
set +a
python3 - <<'PY'
import os
import socket
import ssl
from urllib.parse import urlparse

parsed = urlparse(os.environ["PROMPTON_API_BASE_URL"])
assert parsed.scheme == "https" and parsed.hostname
context = ssl.create_default_context()
with socket.create_connection((parsed.hostname, 443), timeout=3) as raw:
    with context.wrap_socket(raw, server_hostname=parsed.hostname) as tls:
        print("verified", parsed.hostname, tls.version())
PY
```

Pass condition: outbound TCP 443 and certificate/hostname verification succeed without proxy bypass or warning suppression.

## 9. systemd Sandbox Review

Repository checks:

```bash
systemd-analyze verify deploy/prompton-worker.service
```

On the installed target:

```bash
systemd-analyze security prompton-worker.service
sudo systemctl cat prompton-worker.service
sudo -u prompton test -w /data/jobs
sudo -u prompton test -w /data/hermes
sudo -u prompton test -w /data/gradle
```

Required values:

- `NoNewPrivileges=true`.
- `ProtectSystem=strict`.
- `ProtectHome=true`.
- `PrivateTmp=true`.
- Explicit `ReadWritePaths=/data/jobs /data/hermes /data/gradle`.
- Dedicated `prompton` user/group.

The local development host may fail direct verify only because the production `/opt` executable is absent. Use the temporary syntax procedure in `build-instructions.md`; require direct target verification before activation.

## 10. Evidence Gate

| Control | Local evidence | External evidence |
|---|---|---|
| Key confinement/log exclusion | Tests and source scan | Sanitized journald review |
| TLS verification | Source/fake assertions | Default-context target handshake |
| IAM least privilege | No runtime DynamoDB dependency | Deployed policy inspection |
| Environment protection | Template checks | Owner/group/mode and static-key-name check |
| Workspace/systemd | Unit tests and unit assertions | Installed sandbox/path inspection |
| Dependency/static scan | Optional pinned CI commands | Reviewed finding dispositions |

Security acceptance requires all applicable project-specific controls. Security Baseline extension status remains N/A and does not waive these requirements.
