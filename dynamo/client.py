"""DynamoDB 클라이언트.

설계 근거: logical-components.md 섹션 6, domain-entities.md 섹션 4
비즈니스 규칙:
    BR-005 (상태 업데이트 원자성 - 단일 UpdateItem),
    BR-006 (artifactKey 기록 시점), BR-007 (progress 값 규칙 - 실패 시 유지),
    BR-009 (실패 상태 기록), BR-012 (로그 기록 시점), BR-013 (로그 보안)
NFR 패턴: Pattern 1 (retry), Pattern 10 (Log Sanitization)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import boto3

from config.settings import build_boto_config
from models.enums import ErrorCode, JobStatus
from utils.log_sanitizer import sanitize_log

if TYPE_CHECKING:
    from models.entities import Config

logger = logging.getLogger(__name__)


class DynamoClient:
    """Job 상태/로그 관리 래퍼.

    Attributes:
        table_name: 대상 DynamoDB 테이블명
    """

    def __init__(self, config: Config, table: Any | None = None) -> None:
        """DynamoDB 클라이언트를 초기화한다.

        Args:
            config: Worker 설정
            table: 주입할 boto3 Table 리소스 (테스트용). None이면 새로 생성
        """
        self.table_name = config.dynamodb_table_name
        if table is not None:
            self._table = table
        else:
            resource = boto3.resource(
                "dynamodb",
                region_name=config.aws_region,
                config=build_boto_config(),
            )
            self._table = resource.Table(config.dynamodb_table_name)

    def get_job_status(self, job_id: str) -> JobStatus | None:
        """Job의 현재 상태를 조회한다 (BR-001 중복 처리 방지에 사용).

        Args:
            job_id: 조회할 Job ID

        Returns:
            현재 상태. 레코드가 없거나 status 필드가 없으면 None.
            알 수 없는 상태 문자열인 경우에도 None (처리 계속 진행)
        """
        response = self._table.get_item(Key={"jobId": job_id})
        item = response.get("Item")
        if not item:
            logger.warning("Job 레코드를 찾을 수 없습니다 (jobId=%s)", job_id)
            return None

        raw_status = item.get("status")
        if not isinstance(raw_status, str):
            return None

        try:
            return JobStatus(raw_status)
        except ValueError:
            logger.warning("알 수 없는 status 값: %s (jobId=%s)", raw_status, job_id)
            return None

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: int | None = None,
        message: str | None = None,
        error_code: ErrorCode | None = None,
        artifact_key: str | None = None,
    ) -> None:
        """Job 상태를 단일 UpdateItem으로 원자적으로 갱신한다 (BR-005).

        BR-007: progress가 None이면 기존 값을 유지한다 (실패 시 마지막 값 보존).
        BR-006: artifact_key는 S3 업로드 성공이 확인된 후에만 전달해야 한다.

        Args:
            job_id: 대상 Job ID
            status: 새 상태
            progress: 진행률 (0-100). None이면 갱신하지 않음
            message: 사용자 표시 메시지. None이면 갱신하지 않음
            error_code: 에러 코드 (실패 시). None이면 갱신하지 않음
            artifact_key: APK S3 키 (성공 시). None이면 갱신하지 않음
        """
        set_clauses = ["#status = :status"]
        names: dict[str, str] = {"#status": "status"}
        values: dict[str, Any] = {":status": status.value}

        if progress is not None:
            set_clauses.append("#progress = :progress")
            names["#progress"] = "progress"
            values[":progress"] = progress

        if message is not None:
            set_clauses.append("#message = :message")
            names["#message"] = "message"
            values[":message"] = sanitize_log(message)

        if error_code is not None:
            set_clauses.append("#errorCode = :errorCode")
            names["#errorCode"] = "errorCode"
            values[":errorCode"] = error_code.value

        if artifact_key is not None:
            set_clauses.append("#artifactKey = :artifactKey")
            names["#artifactKey"] = "artifactKey"
            values[":artifactKey"] = artifact_key

        self._table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET " + ", ".join(set_clauses),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        logger.info(
            "상태 갱신 (jobId=%s, status=%s, progress=%s)", job_id, status.value, progress
        )

    def append_log(self, job_id: str, message: str) -> None:
        """logs 배열에 로그 한 줄을 추가한다 (BR-012).

        BR-013: 민감 정보를 필터링한 후 저장한다.
        로그 기록 실패는 Job 처리를 중단시키지 않는다 (부가 정보이므로 예외를 흡수).

        Args:
            job_id: 대상 Job ID
            message: 추가할 로그 메시지
        """
        safe_message = sanitize_log(message)
        try:
            self._table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=(
                    "SET #logs = list_append(if_not_exists(#logs, :empty), :entry)"
                ),
                ExpressionAttributeNames={"#logs": "logs"},
                ExpressionAttributeValues={
                    ":empty": [],
                    ":entry": [safe_message],
                },
            )
            logger.debug("로그 추가 (jobId=%s): %s", job_id, safe_message)
        except Exception:
            logger.warning(
                "로그 추가 실패 - 처리를 계속합니다 (jobId=%s)", job_id, exc_info=True
            )
