# Security Test Instructions

## Scope and Extension Status

The optional Security Baseline extension is disabled, so extension-specific rules are not a blocking AI-DLC gate. The project's own NFRs still require least-privilege IAM, credential-free AWS authentication, sensitive-log redaction, and owner-only work directories. These checks validate those explicit requirements.

## Existing Automated Security Behavior Tests

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync --extra dev --frozen
uv run pytest \
  tests/test_cleanup.py \
  tests/test_dynamo_client.py \
  tests/test_s3_client.py \
  tests/test_sqs_client.py
```

Relevant behavior includes AWS key, token, signed URL, bearer token, and credential assignment redaction; safe user failure messages; supported asset filtering; path basename handling; and owner-only Job work directories.

## Dependency Vulnerability Audit

Use pinned, ephemeral scanner versions without modifying project dependencies:

```bash
export PATH="$HOME/.local/bin:$PATH"
uv export --frozen --all-extras --format requirements-txt \
  --output-file /tmp/prompton-requirements.txt
uvx --from pip-audit==2.9.0 pip-audit \
  --requirement /tmp/prompton-requirements.txt
rm -f /tmp/prompton-requirements.txt
```

Review every finding for exploitability in both runtime and development dependencies. Do not suppress a finding without a documented rationale and expiry.

## Static Security Scan

```bash
export PATH="$HOME/.local/bin:$PATH"
uvx --from bandit==1.8.6 bandit -r \
  main.py ai build config dynamo models s3 sqs utils worker
```

Any High severity finding is release-blocking. Review Medium findings and document disposition.

## Credential and Secret Review

Search application and deployment files, excluding tests that intentionally contain fake credentials:

```bash
if grep -RInE \
  'AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|aws_secret_access_key|aws_session_token|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY' \
  main.py ai build config dynamo models s3 sqs utils worker deploy; then
  echo 'Potential secret material found; review required' >&2
  exit 1
fi
```

Also verify `/etc/prompton-worker/env` contains no `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or `AWS_SESSION_TOKEN`:

```bash
sudo grep -En '^(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN)=' \
  /etc/prompton-worker/env && exit 1 || true
```

## IAM Least-Privilege Test

From the EC2 instance, verify allowed actions required by the Worker and explicitly test that unrelated administrative actions are denied. Use only dedicated test resources.

Required actions:
- SQS: ReceiveMessage, DeleteMessage, ChangeMessageVisibility, GetQueueAttributes
- S3: GetObject for requirements/assets, ListBucket for the assets prefix, PutObject for source/artifact
- DynamoDB: GetItem and UpdateItem on the Job table

Prohibited policy patterns:
- `Action: "*"`
- `Resource: "*"` where a service-level API does not require it
- AdministratorAccess attached to the instance role
- Static AWS credentials in code, environment files, user data, or systemd overrides

Use IAM Access Analyzer policy validation before attachment when a deployable IAM policy document is available.

## systemd Sandbox Review

```bash
systemd-analyze verify deploy/prompton-worker.service
systemd-analyze security prompton-worker.service
sudo systemctl cat prompton-worker.service
```

Confirm:
- `NoNewPrivileges=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- `PrivateTmp=true`
- Only required writable paths are in `ReadWritePaths`
- `/data/jobs` and any configured `GRADLE_USER_HOME` are owned by the service user
- Environment file mode is 0640 or stricter

If `/data/gradle` or an Android SDK path must be writable, explicitly add the narrow path rather than weakening `ProtectSystem` globally.

## AI Tool Boundary Review

The Worker invokes kiro-cli with:
- `--no-interactive`
- `--model claude-opus-5`
- `--trust-tools=fs_read,fs_write`

Do not change this to `--trust-all-tools` for untrusted user requirements. The Job directory must remain isolated, and the service user must not have write access outside approved data paths.

## Current Execution Status

Log-redaction and input-handling tests passed within the 105-test suite. Dependency audit, Bandit, live IAM denial testing, and installed-service sandbox scoring were not executed in this local session; run them in CI or the isolated EC2 test environment before production activation.
