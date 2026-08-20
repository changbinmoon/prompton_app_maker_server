"""S3 클라이언트.

설계 근거: logical-components.md 섹션 6, component-methods.md
비즈니스 규칙:
    BR-006 (artifactKey 기록 시점 - 업로드 성공 확인),
    BR-014 (에셋 처리 - 없어도 정상, png/jpeg, 최대 5개),
    BR-015 (APK 저장 위치), BR-016 (소스 코드 저장), BR-020 (requirements.json 유효성)
NFR 패턴: Pattern 1 (retry)
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import boto3

from config.settings import build_boto_config
from models.exceptions import (
    ArtifactUploadError,
    InvalidRequirementsError,
    RequirementsReadError,
)
from models.requirements import MAX_REQUIREMENTS_FILE_BYTES, validate_requirements

if TYPE_CHECKING:
    from models.entities import Config

logger = logging.getLogger(__name__)

#: 지원하는 에셋 확장자 (BR-014: image/png, image/jpeg만 지원)
ALLOWED_ASSET_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})

#: 에셋 최대 개수 (BR-014)
MAX_ASSET_COUNT = 5


class S3Client:
    """S3 입출력 래퍼.

    Attributes:
        bucket: 기본 대상 버킷명
    """

    def __init__(self, config: Config, client: Any | None = None) -> None:
        """S3 클라이언트를 초기화한다.

        Args:
            config: Worker 설정
            client: 주입할 boto3 S3 클라이언트 (테스트용). None이면 새로 생성
        """
        self.bucket = config.s3_bucket_name
        self._client = client or boto3.client(
            "s3",
            region_name=config.aws_region,
            config=build_boto_config(),
        )

    def download_requirements(
        self, bucket: str, key: str, dest_path: Path
    ) -> dict[str, Any]:
        """requirements.json을 다운로드하고 파싱한다.

        Args:
            bucket: 소스 버킷명
            key: 소스 객체 키
            dest_path: 저장할 로컬 경로

        Returns:
            파싱된 requirements 딕셔너리

        Raises:
            RequirementsReadError: S3 다운로드 실패
            InvalidRequirementsError: JSON 파싱 실패 또는 최상위가 객체가 아닌 경우 (BR-020)
        """
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._client.download_file(bucket, key, str(dest_path))
        except Exception as exc:
            raise RequirementsReadError(
                detail=f"requirements.json 다운로드 실패 (key={key}): {exc}"
            ) from exc

        try:
            file_size = dest_path.stat().st_size
        except OSError as exc:
            raise RequirementsReadError(
                detail=f"requirements.json 파일 정보 조회 실패: {exc}"
            ) from exc

        if file_size > MAX_REQUIREMENTS_FILE_BYTES:
            raise InvalidRequirementsError(
                detail=(
                    "requirements.json 크기 제한 초과 "
                    f"(max={MAX_REQUIREMENTS_FILE_BYTES} bytes)"
                )
            )

        try:
            content = dest_path.read_text(encoding="utf-8")
            payload = json.loads(content)
        except (OSError, UnicodeDecodeError) as exc:
            raise RequirementsReadError(
                detail=f"requirements.json 로컬 읽기 실패: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise InvalidRequirementsError(
                detail=f"requirements.json JSON 파싱 실패: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise InvalidRequirementsError(
                detail="requirements.json 최상위가 JSON 객체가 아닙니다"
            )

        validate_requirements(payload)
        logger.info("requirements.json 다운로드 및 계약 검증 완료 (key=%s)", key)
        return payload

    def download_assets(self, bucket: str, prefix: str, dest_dir: Path) -> list[Path]:
        """에셋 이미지를 다운로드한다.

        BR-014: 에셋이 없어도 정상 Job이다. png/jpeg만 받고 최대 5개까지 처리한다.

        Args:
            bucket: 소스 버킷명
            prefix: 에셋 prefix (예: jobs/{jobId}/assets/)
            dest_dir: 저장할 로컬 디렉토리

        Returns:
            다운로드된 로컬 파일 경로 목록. 에셋이 없으면 빈 리스트
        """
        dest_dir.mkdir(parents=True, exist_ok=True)

        keys = self._list_asset_keys(bucket, prefix)
        if not keys:
            logger.info("에셋이 없습니다 (prefix=%s)", prefix)
            return []

        downloaded: list[Path] = []
        for key in keys:
            # 경로 조작 방지: S3 키에서 파일명만 사용한다
            filename = Path(key).name
            if not filename:
                continue

            local_path = dest_dir / filename
            try:
                self._client.download_file(bucket, key, str(local_path))
                downloaded.append(local_path)
            except Exception:
                # BR-014: 에셋은 필수 입력이 아니므로 개별 실패 시 건너뛰고 계속 진행
                logger.warning("에셋 다운로드 실패 - 건너뜁니다 (key=%s)", key, exc_info=True)

        logger.info("에셋 %d개 다운로드 완료 (prefix=%s)", len(downloaded), prefix)
        return downloaded

    def upload_source(self, project_dir: Path, key: str) -> str:
        """생성된 프로젝트를 zip으로 압축하여 업로드한다 (BR-016).

        소스 업로드 실패는 Job 실패로 처리하지 않는다. APK 산출물이 핵심이며
        소스는 디버깅 보조 자료이기 때문이다.

        Args:
            project_dir: 압축할 프로젝트 디렉토리
            key: 업로드할 S3 객체 키

        Returns:
            업로드 성공 시 S3 키, 실패 시 빈 문자열
        """
        if not project_dir.is_dir():
            logger.warning("소스 디렉토리가 없어 업로드를 건너뜁니다: %s", project_dir)
            return ""

        archive_path: Path | None = None
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                base_name = str(Path(tmp_dir) / "project")
                archive_path = Path(
                    shutil.make_archive(base_name, "zip", root_dir=str(project_dir))
                )
                self._client.upload_file(str(archive_path), self.bucket, key)
            logger.info("소스 코드 업로드 완료 (key=%s)", key)
            return key
        except Exception:
            logger.warning("소스 코드 업로드 실패 - 처리를 계속합니다", exc_info=True)
            return ""

    def upload_artifact(self, apk_path: Path, key: str) -> str:
        """빌드된 APK를 업로드하고 존재를 검증한다.

        BR-006: 업로드가 완전히 성공한 뒤에만 artifactKey를 반환한다.
        호출자는 이 반환값을 받은 후에만 DynamoDB를 SUCCESS로 변경해야 한다.

        Args:
            apk_path: 업로드할 로컬 APK 경로
            key: 업로드할 S3 객체 키 (BR-015: jobs/{jobId}/artifact/app-debug.apk)

        Returns:
            업로드 및 검증이 완료된 S3 객체 키

        Raises:
            ArtifactUploadError: APK 파일 부재, 업로드 실패, 또는 업로드 후 검증 실패
        """
        if not apk_path.is_file():
            raise ArtifactUploadError(detail=f"업로드할 APK가 없습니다: {apk_path}")

        try:
            self._client.upload_file(
                str(apk_path),
                self.bucket,
                key,
                ExtraArgs={"ContentType": "application/vnd.android.package-archive"},
            )
        except Exception as exc:
            raise ArtifactUploadError(detail=f"APK 업로드 실패 (key={key}): {exc}") from exc

        # 업로드 성공 확인 (BR-006)
        try:
            head = self._client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise ArtifactUploadError(
                detail=f"APK 업로드 후 검증 실패 (key={key}): {exc}"
            ) from exc

        remote_size = head.get("ContentLength")
        local_size = apk_path.stat().st_size
        if remote_size is not None and int(remote_size) != local_size:
            raise ArtifactUploadError(
                detail=(
                    f"APK 업로드 크기 불일치 (key={key}, "
                    f"local={local_size}, remote={remote_size})"
                )
            )

        logger.info("APK 업로드 완료 (key=%s, size=%d bytes)", key, local_size)
        return key

    def _list_asset_keys(self, bucket: str, prefix: str) -> list[str]:
        """에셋 prefix 아래의 유효한 객체 키를 조회한다.

        BR-014: 지원 확장자만 선택하고 최대 5개로 제한한다.
        조회 실패 시 예외를 전파하지 않고 빈 리스트를 반환한다 (에셋은 선택 입력).

        Args:
            bucket: 소스 버킷명
            prefix: 조회할 prefix

        Returns:
            정렬된 에셋 객체 키 목록 (최대 MAX_ASSET_COUNT개)
        """
        keys: list[str] = []
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    key = item.get("Key", "")
                    # prefix 자체(디렉토리 플레이스홀더) 제외
                    if not key or key.endswith("/"):
                        continue
                    if Path(key).suffix.lower() not in ALLOWED_ASSET_EXTENSIONS:
                        logger.debug("지원하지 않는 에셋 형식 - 제외: %s", key)
                        continue
                    keys.append(key)
        except Exception:
            logger.warning(
                "에셋 목록 조회 실패 - 에셋 없이 진행합니다 (prefix=%s)", prefix, exc_info=True
            )
            return []

        keys.sort()
        if len(keys) > MAX_ASSET_COUNT:
            logger.warning(
                "에셋이 %d개로 최대 %d개를 초과 - 앞의 %d개만 사용합니다",
                len(keys),
                MAX_ASSET_COUNT,
                MAX_ASSET_COUNT,
            )
            keys = keys[:MAX_ASSET_COUNT]

        return keys
