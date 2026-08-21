"""Worker 예외 계층.

설계 근거: domain-entities.md 섹션 5
비즈니스 규칙: BR-008 (에러 코드 분류), BR-009 (실패 상태 기록)

각 예외는 대응하는 ErrorCode를 보유하며, user_message는 사용자에게 노출 가능한
한국어 메시지다 (스택 트레이스/내부 경로 미포함).
"""

from __future__ import annotations

from enum import Enum

from models.enums import ERROR_MESSAGES, ErrorCode


class StatusApiFailureKind(str, Enum):
    """Status API 최종 실패 분류."""

    HTTP_4XX = "HTTP_4XX"
    HTTP_5XX = "HTTP_5XX"
    HTTP_OTHER = "HTTP_OTHER"
    CONNECTION = "CONNECTION"
    TIMEOUT = "TIMEOUT"


class WorkerError(Exception):
    """Worker 기본 예외.

    Attributes:
        error_code: Backend에 보고할 승인된 에러 코드
        user_message: 사용자에게 표시할 한국어 메시지 (민감 정보 제외)
    """

    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, detail: str = "", user_message: str | None = None) -> None:
        """예외를 초기화한다.

        Args:
            detail: 내부 로그용 상세 메시지 (사용자에게 노출되지 않음)
            user_message: 사용자 표시 메시지. None이면 error_code 기본 메시지 사용
        """
        self.detail = detail
        self.user_message = user_message or ERROR_MESSAGES[self.error_code]
        super().__init__(detail or self.user_message)


class StatusApiFailure(WorkerError):
    """Status API 요청의 최종 실패.

    API key, request payload, response body, 외부 예외 문자열은 보관하지 않는다.
    """

    error_code = ErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        kind: StatusApiFailureKind,
        *,
        status_code: int | None = None,
        attempt_count: int,
    ) -> None:
        self.kind = kind
        self.status_code = status_code
        self.attempt_count = attempt_count
        detail = (
            "Status API request failed "
            f"(kind={kind.value}, status_code={status_code}, attempts={attempt_count})"
        )
        super().__init__(detail=detail)


class RequirementsReadError(WorkerError):
    """S3에서 requirements.json 읽기 실패."""

    error_code = ErrorCode.REQUIREMENTS_READ_FAILED


class InvalidRequirementsError(WorkerError):
    """requirements.json 또는 SQS 메시지 형식 오류 (BR-019, BR-020)."""

    error_code = ErrorCode.INVALID_REQUIREMENTS


class AIGenerationError(WorkerError):
    """kiro-cli 코드 생성 실패."""

    error_code = ErrorCode.AI_GENERATION_FAILED


class BuildError(WorkerError):
    """Gradle APK 빌드 실패."""

    error_code = ErrorCode.BUILD_FAILED


class ArtifactUploadError(WorkerError):
    """APK S3 업로드 실패."""

    error_code = ErrorCode.ARTIFACT_UPLOAD_FAILED


def classify_error(exc: BaseException) -> ErrorCode:
    """예외를 ErrorCode로 분류한다 (BR-008).

    WorkerError 하위 예외는 자신의 error_code를 사용하고,
    그 외 모든 예외는 INTERNAL_ERROR로 분류한다.

    Args:
        exc: 분류할 예외

    Returns:
        해당 예외에 대응하는 ErrorCode
    """
    if isinstance(exc, WorkerError):
        return exc.error_code
    return ErrorCode.INTERNAL_ERROR


def user_message_for(exc: BaseException) -> str:
    """예외에 대응하는 사용자 표시 메시지를 반환한다 (BR-009).

    내부 예외 문자열을 그대로 노출하지 않고, 사전 정의된 한국어 메시지만 반환한다.

    Args:
        exc: 대상 예외

    Returns:
        사용자에게 표시할 한국어 메시지
    """
    if isinstance(exc, WorkerError):
        return exc.user_message
    return ERROR_MESSAGES[ErrorCode.INTERNAL_ERROR]
