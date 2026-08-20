"""도메인 엔티티 및 값 객체.

설계 근거: domain-entities.md 섹션 1~3
비즈니스 규칙: BR-015 (APK 저장 위치), BR-016 (소스 코드 저장), BR-019 (SQS 메시지 유효성)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from models.exceptions import InvalidRequirementsError

#: 현재 지원하는 SQS 메시지 스키마 버전 (BR-019)
SUPPORTED_SCHEMA_VERSION = "1.0"

#: 빌드 결과 APK 파일명 (BR-015: MVP에서는 항상 고정)
APK_FILENAME = "app-debug.apk"

#: 소스 코드 아카이브 파일명 (BR-016)
SOURCE_ARCHIVE_NAME = "project.zip"


@dataclass(frozen=True)
class Config:
    """환경 변수 기반 설정 객체.

    설계 근거: domain-entities.md 섹션 2
    """

    aws_region: str
    sqs_queue_url: str
    dynamodb_table_name: str
    s3_bucket_name: str
    work_dir: str
    visibility_timeout: int
    cleanup_hours: int
    log_level: str
    kiro_cli_path: str
    gradle_path: str


@dataclass(frozen=True)
class SQSMessage:
    """SQS Queue에서 수신한 Job 메시지.

    설계 근거: domain-entities.md 섹션 1
    """

    job_id: str
    requirements_bucket: str
    requirements_key: str
    assets_prefix: str
    receipt_handle: str
    schema_version: str

    @classmethod
    def from_raw(cls, body: str, receipt_handle: str) -> SQSMessage:
        """SQS 메시지 본문(JSON 문자열)을 파싱하여 SQSMessage를 생성한다.

        유효성 검증 (BR-019):
            - JSON 파싱 가능
            - 필수 필드 존재: schemaVersion, jobId, requirements.bucket,
              requirements.key, assetsPrefix
            - jobId는 UUID 형식
            - schemaVersion은 지원 버전과 일치

        Args:
            body: SQS 메시지 본문 JSON 문자열
            receipt_handle: SQS 메시지 receipt handle

        Returns:
            검증된 SQSMessage 인스턴스

        Raises:
            InvalidRequirementsError: 파싱 실패 또는 유효성 검증 실패
        """
        try:
            payload: Any = json.loads(body)
        except json.JSONDecodeError as exc:
            raise InvalidRequirementsError(
                detail=f"SQS 메시지 JSON 파싱 실패: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise InvalidRequirementsError(detail="SQS 메시지 본문이 JSON 객체가 아닙니다")

        schema_version = payload.get("schemaVersion")
        if schema_version != SUPPORTED_SCHEMA_VERSION:
            raise InvalidRequirementsError(
                detail=(
                    f"지원하지 않는 schemaVersion: {schema_version!r} "
                    f"(지원: {SUPPORTED_SCHEMA_VERSION})"
                )
            )

        job_id = payload.get("jobId")
        if not isinstance(job_id, str) or not job_id:
            raise InvalidRequirementsError(detail="jobId 필드가 없거나 비어 있습니다")
        cls._validate_uuid(job_id)

        requirements = payload.get("requirements")
        if not isinstance(requirements, dict):
            raise InvalidRequirementsError(detail="requirements 필드가 객체가 아닙니다")

        bucket = requirements.get("bucket")
        key = requirements.get("key")
        if not isinstance(bucket, str) or not bucket:
            raise InvalidRequirementsError(detail="requirements.bucket 필드가 없습니다")
        if not isinstance(key, str) or not key:
            raise InvalidRequirementsError(detail="requirements.key 필드가 없습니다")

        assets_prefix = payload.get("assetsPrefix")
        if not isinstance(assets_prefix, str):
            raise InvalidRequirementsError(detail="assetsPrefix 필드가 없습니다")

        return cls(
            job_id=job_id,
            requirements_bucket=bucket,
            requirements_key=key,
            assets_prefix=assets_prefix,
            receipt_handle=receipt_handle,
            schema_version=schema_version,
        )

    @staticmethod
    def _validate_uuid(value: str) -> None:
        """jobId가 UUID 형식인지 검증한다 (BR-019).

        Args:
            value: 검증할 문자열

        Raises:
            InvalidRequirementsError: UUID 형식이 아닌 경우
        """
        try:
            uuid.UUID(value)
        except ValueError as exc:
            raise InvalidRequirementsError(
                detail=f"jobId가 UUID 형식이 아닙니다: {value!r}"
            ) from exc


@dataclass(frozen=True)
class JobWorkDir:
    """Job별 로컬 작업 디렉토리 경로 구조.

    설계 근거: domain-entities.md 섹션 3, business-logic-model.md 섹션 4
    """

    base_path: Path
    requirements_path: Path
    assets_dir: Path
    project_dir: Path
    output_dir: Path
    apk_path: Path

    @classmethod
    def for_job(cls, work_dir_root: str, job_id: str) -> JobWorkDir:
        """Job ID 기준으로 작업 디렉토리 경로 구조를 계산한다.

        Args:
            work_dir_root: 작업 디렉토리 루트 (예: /data/jobs)
            job_id: Job 고유 ID

        Returns:
            경로가 계산된 JobWorkDir (디렉토리는 생성하지 않음)
        """
        base = Path(work_dir_root) / job_id
        output_dir = base / "output"
        return cls(
            base_path=base,
            requirements_path=base / "requirements.json",
            assets_dir=base / "assets",
            project_dir=base / "project",
            output_dir=output_dir,
            apk_path=output_dir / APK_FILENAME,
        )


@dataclass(frozen=True)
class S3Paths:
    """Job별 S3 객체 키 구조.

    설계 근거: domain-entities.md 섹션 3
    비즈니스 규칙: BR-015 (artifact 경로), BR-016 (source 경로)
    """

    requirements_key: str
    assets_prefix: str
    source_key: str
    artifact_key: str

    @classmethod
    def for_job(cls, job_id: str) -> S3Paths:
        """Job ID 기준으로 S3 경로를 계산한다.

        Args:
            job_id: Job 고유 ID

        Returns:
            계산된 S3Paths
        """
        prefix = f"jobs/{job_id}"
        return cls(
            requirements_key=f"{prefix}/requirements/requirements.json",
            assets_prefix=f"{prefix}/assets/",
            source_key=f"{prefix}/source/{SOURCE_ARCHIVE_NAME}",
            artifact_key=f"{prefix}/artifact/{APK_FILENAME}",
        )
