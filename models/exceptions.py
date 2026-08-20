"""Worker 예외 계층.

설계 근거: domain-entities.md 섹션 5
비즈니스 규칙: BR-008 (에러 코드 분류), BR-009 (실패 상태 기록)

각 예외는 대응하는 ErrorCode를 보유하며, user_message는 사용자에게 노출 가능한
한국어 메시지다 (스택 트레이스/내부 경로 미포함).
"""

from __future__ import annotations

from models.enums import ERROR_MESSAGES, ErrorCode


class WorkerError(Exception):
    """Worker 기본 예외.

    Attributes:
        error_code: DynamoDB에 기록할 에러 코드
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
