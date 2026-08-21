# Ordered Post-Workflow Execution Clarifications

The selected order is:

1. A - Read-only external readiness evidence
2. C - Dev E2E approval-package preparation only
3. B - Deployment and rollback planning only

Do not enter API keys, AWS secrets, session tokens, passwords, private keys, or other credentials in this file.

## Question 1
Which AWS read-only execution scope should be used for readiness evidence?

A) Use the currently configured default AWS CLI profile in `us-east-1` and the dev queue/bucket identifiers from `deploy/env.example`.

B) Use a named AWS CLI profile and region. Add the non-secret profile name and region after the `[Answer]:` tag.

C) Do not call AWS. Generate an evidence-collection checklist and leave IAM and queue/DLQ checks pending.

X) Other (describe the non-secret execution scope after the `[Answer]:` tag).

[Answer]: A

## Question 2
Which host scope should be used for deployed environment and systemd evidence?

A) Treat the current machine as the deployed dev Worker host and run read-only local inspections if the files/service are present.

B) Use another host. Add only the non-secret host alias and approved access method after the `[Answer]:` tag; do not add credentials.

C) Do not access a deployed host. Validate repository templates locally and leave installed env/systemd checks pending.

X) Other (describe the host scope after the `[Answer]:` tag).

[Answer]: A

## Question 3
May a non-mutating DNS, TCP 443, and default-certificate TLS handshake be made to the configured Status API hostname?

A) Yes, from the selected execution host. Do not send an HTTP PATCH or API key.

B) No. Document network/TLS reachability as pending without making a connection.

X) Other (describe the permitted network boundary after the `[Answer]:` tag).

[Answer]: A

## Question 4
How should the dev E2E approval package be prepared?

A) Create a blank approval template with all Job ID, window, owner, model-cost, and cleanup fields unfilled.

B) Pre-fill non-secret dev resource identifiers from `deploy/env.example`; leave Job ID, test window, owners, model-cost authorization, and cleanup approval as required blanks.

C) Pre-fill supplied non-secret details. Add environment, Job ID, UTC window, owner roles, model/provider authorization status, and cleanup owner after the `[Answer]:` tag.

X) Other (describe the package scope after the `[Answer]:` tag).

[Answer]: B

## Question 5
What target scope should the deployment and rollback plan cover?

A) Dev environment only, using the current `/opt/prompton-ai-worker`, `/etc/prompton-worker/env`, and systemd template paths.

B) Dev deployment plus a separate production-promotion checklist; no deployment execution.

C) Environment-neutral plan with placeholders and no resource identifiers.

X) Other (describe the planning target after the `[Answer]:` tag).

[Answer]: A
