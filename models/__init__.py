"""도메인 모델 패키지.

Worker 전반에서 공유되는 열거형, 엔티티, 예외를 정의한다.
"""

from models.entities import Config, JobWorkDir, S3Paths, SQSMessage
from models.enums import JOB_PROGRESS, STATUS_MESSAGES, ErrorCode, JobStatus
from models.exceptions import (
    AIGenerationError,
    ArtifactUploadError,
    BuildError,
    InvalidRequirementsError,
    RequirementsReadError,
    WorkerError,
)

__all__ = [
    "JOB_PROGRESS",
    "STATUS_MESSAGES",
    "AIGenerationError",
    "ArtifactUploadError",
    "BuildError",
    "Config",
    "ErrorCode",
    "InvalidRequirementsError",
    "JobStatus",
    "JobWorkDir",
    "RequirementsReadError",
    "S3Paths",
    "SQSMessage",
    "WorkerError",
]
