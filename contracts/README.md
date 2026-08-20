# Prompton Requirements Contract

## Status

- **Schema version**: 1.0
- **JSON Schema**: `requirements.schema.json`
- **Draft**: JSON Schema Draft 2020-12
- **Worker validation**: Implemented
- **Backend producer validation**: Pending in the Backend repository
- **Hermes prompt refinement**: Pending executable interface and retry policy

This directory is the Worker-side copy of the contract. The approved long-term source of truth is a shared versioned contract repository or package used by both Backend and Worker.

## Canonical Document

The Backend writes the normalized document to:

```text
jobs/{jobId}/requirements/requirements.json
```

Required root fields:
- `schemaVersion`: exactly `1.0`
- `clientPayload`: the original arbitrary Client JSON object
- `android`: normalized Android build settings
- `assets`: normalized metadata for up to five PNG/JPEG assets

Unknown fields are rejected outside `clientPayload`.

## Backend Normalization Rules

1. Preserve the original Client JSON object in `clientPayload`.
2. If the Client API level is valid, write that value to both `android.minSdk` and `android.targetSdk`.
3. If the Client API level is missing or invalid, use `minSdk=26` and `targetSdk=35`.
4. Preserve a valid Client application ID. Otherwise generate `com.prompton.generated.j{jobIdHex}`.
5. Normalize language to `Kotlin` and UI toolkit to `Jetpack Compose` when missing or invalid.
6. Normalize asset metadata to basename-only PNG/JPEG entries and reject more than five assets.
7. Validate against the shared schema before writing S3 or sending SQS.

The Worker does not apply Backend defaults. It accepts only an already normalized canonical document.

## Worker Validation Rules

- Maximum document size: 64 KiB
- UTF-8 JSON object
- Draft 2020-12 schema validation
- `android.minSdk <= android.targetSdk`
- Schema failure details expose only the JSON path and failed rule, not Client values
- Invalid documents become `INVALID_REQUIREMENTS`

## Shared Fixtures

- `fixtures/valid/`: documents both producer and consumer must accept
- `fixtures/invalid/`: documents both producer and consumer must reject

Backend CI should consume these fixtures or the identical fixtures from the future shared contract package.

## Hermes Gate

The selected flow runs Hermes in the Worker before Kiro and writes a refined prompt file. Hermes integration is not implemented because the standalone executable path, argument format, retry count, interval, and final fallback input were not supplied. Until those values are approved, the Worker continues to pass the canonical JSON directly to Kiro and production E2E remains blocked.
