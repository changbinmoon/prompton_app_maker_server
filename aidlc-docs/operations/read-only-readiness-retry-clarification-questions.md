# Read-Only Readiness Retry - Access Clarifications

The selected scope is B: retry read-only readiness evidence with new authorized access. The previous default profile was unable to inspect IAM policies, S3 readiness, or DLQ attributes, and the current machine was not a deployed Worker host.

Do not enter access keys, secret keys, session tokens, passwords, private keys, API keys, or other credentials in this file.

## Question 1
What AWS resource-owner access may be used?

A) Use a named AWS CLI profile. Add the non-secret profile name and region after the `[Answer]:` tag.

B) No additional AWS profile is available. Leave IAM/S3/DLQ AWS checks pending.

C) Do not call AWS; a resource owner will supply sanitized IAM/S3/DLQ evidence separately.

X) Other (describe the non-secret AWS read-only access boundary after the `[Answer]:` tag).

[Answer]: A

## Question 2
What actual deployed-host access may be used?

A) Use an approved SSH/config host alias. Add only the non-secret host alias, remote user name, and approved read-only access method after the `[Answer]:` tag. Do not add credentials.

B) No deployed-host access is available. Leave env/systemd/path checks pending.

C) Do not access a host; the host owner will supply sanitized env/systemd/path evidence separately.

X) Other (describe the non-secret host evidence boundary after the `[Answer]:` tag).

[Answer]: A

## Question 3
Which retry subset should run after validating the supplied details?

A) Both AWS resource-owner checks and deployed-host read-only checks.

B) AWS resource-owner checks only.

C) Deployed-host read-only checks only.

D) No direct calls; prepare an evidence intake checklist for resource/host owners.

X) Other (describe the permitted subset after the `[Answer]:` tag).

[Answer]: A
