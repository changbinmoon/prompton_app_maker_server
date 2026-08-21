"""Job 상태 및 에러 코드 열거형.

설계 근거: domain-entities.md 섹션 1
비즈니스 규칙: BR-004 (상태 전이 순서), BR-007 (progress 고정값), BR-008 (에러 코드 분류)
"""

from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    """Job 처리 상태.

    상태 전이 (BR-004):
        QUEUED -> ANALYZING -> GENERATING_CODE -> BUILDING -> SUCCESS
        모든 상태에서 FAILED로 전이 가능
    """

    UPLOAD_PENDING = "UPLOAD_PENDING"
    QUEUED = "QUEUED"
    ANALYZING = "ANALYZING"
    GENERATING_CODE = "GENERATING_CODE"
    BUILDING = "BUILDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class ErrorCode(str, Enum):
    """실패 원인 분류 코드 (BR-008)."""

    REQUIREMENTS_READ_FAILED = "REQUIREMENTS_READ_FAILED"
    INVALID_REQUIREMENTS = "INVALID_REQUIREMENTS"
    AI_GENERATION_FAILED = "AI_GENERATION_FAILED"
    BUILD_FAILED = "BUILD_FAILED"
    ARTIFACT_UPLOAD_FAILED = "ARTIFACT_UPLOAD_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


#: 상태별 고정 진행률 (BR-007). 이 값 외의 progress는 사용하지 않는다.
JOB_PROGRESS: dict[JobStatus, int] = {
    JobStatus.UPLOAD_PENDING: 3,
    JobStatus.QUEUED: 10,
    JobStatus.ANALYZING: 25,
    JobStatus.GENERATING_CODE: 50,
    JobStatus.BUILDING: 75,
    JobStatus.SUCCESS: 100,
}

#: 상태별 사용자 표시 메시지 (한국어)
STATUS_MESSAGES: dict[JobStatus, str] = {
    JobStatus.ANALYZING: "요구조건을 분석하고 있습니다.",
    JobStatus.GENERATING_CODE: "Android 코드를 생성하고 있습니다.",
    JobStatus.BUILDING: "APK를 빌드하고 있습니다.",
    JobStatus.SUCCESS: "앱 생성이 완료되었습니다.",
}

#: 에러 코드별 사용자 표시 메시지 (BR-009: 민감 정보 노출 금지)
ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.REQUIREMENTS_READ_FAILED: "요구조건 파일을 읽지 못했습니다.",
    ErrorCode.INVALID_REQUIREMENTS: "요구조건 형식이 올바르지 않습니다.",
    ErrorCode.AI_GENERATION_FAILED: "앱 코드 생성에 실패했습니다.",
    ErrorCode.BUILD_FAILED: "APK 빌드에 실패했습니다.",
    ErrorCode.ARTIFACT_UPLOAD_FAILED: "빌드 결과 업로드에 실패했습니다.",
    ErrorCode.INTERNAL_ERROR: "내부 오류가 발생했습니다.",
}
