"""Gradle 기반 APK 빌드 모듈.

설계 근거: logical-components.md 섹션 8, requirements.md FR-008
비즈니스 규칙: BR-008 (BUILD_FAILED 분류), BR-015 (APK 저장 위치)
NFR 패턴: Pattern 4 (Fail-Fast for External Processes - 재시도 없음)

전제: EC2에 Android SDK와 Gradle이 사전 설치되어 있고 ANDROID_HOME/ANDROID_SDK_ROOT가
      설정되어 있다. 프로젝트의 Gradle Wrapper가 없거나 손상됐으면 신뢰된 Gradle로
      격리 생성한 Wrapper를 설치한 뒤 빌드한다.
"""

from __future__ import annotations

import logging
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from models.exceptions import BuildError
from utils.log_sanitizer import sanitize_log

if TYPE_CHECKING:
    from models.entities import Config

logger = logging.getLogger(__name__)

#: Gradle Wrapper 실행 스크립트 이름 (Linux)
GRADLEW_SCRIPT = "gradlew"

#: Gradle Wrapper 실행 스크립트 이름 (Windows, source archive용)
GRADLEW_WINDOWS_SCRIPT = "gradlew.bat"

#: Wrapper JAR 상대 경로
GRADLE_WRAPPER_JAR = Path("gradle/wrapper/gradle-wrapper.jar")

#: Wrapper properties 상대 경로
GRADLE_WRAPPER_PROPERTIES = Path("gradle/wrapper/gradle-wrapper.properties")

#: Wrapper JAR에 반드시 포함되어야 하는 진입점
GRADLE_WRAPPER_MAIN_CLASS = "org/gradle/wrapper/GradleWrapperMain.class"

#: 격리 생성 후 프로젝트에 설치할 Wrapper 산출물
GRADLE_WRAPPER_ARTIFACTS: tuple[Path, ...] = (
    Path(GRADLEW_SCRIPT),
    Path(GRADLEW_WINDOWS_SCRIPT),
    GRADLE_WRAPPER_JAR,
    GRADLE_WRAPPER_PROPERTIES,
)

#: 생성 프로젝트에서 허용하는 공식 stable Gradle distribution URL.
TRUSTED_GRADLE_DISTRIBUTION_RE = re.compile(
    r"https://services\.gradle\.org/distributions/"
    r"gradle-(?P<version>\d+(?:\.\d+){1,2})-(?P<kind>bin|all)\.zip"
)

#: properties 파일 최대 허용 크기
MAX_WRAPPER_PROPERTIES_BYTES = 16 * 1024

#: 빌드 태스크 (FR-008)
GRADLE_BUILD_TASK = "assembleDebug"

#: Wrapper 생성 태스크
GRADLE_WRAPPER_TASK = "wrapper"

#: APK 산출물 탐색 경로 (프로젝트 루트 기준 glob)
APK_SEARCH_PATTERNS: tuple[str, ...] = (
    "app/build/outputs/apk/debug/*.apk",
    "*/build/outputs/apk/debug/*.apk",
    "**/build/outputs/apk/debug/*.apk",
)

#: 로그에 남길 subprocess 출력 최대 길이
MAX_OUTPUT_LOG_CHARS = 4000


class ApkBuilder:
    """검증된 Gradle Wrapper를 사용해 Debug APK를 빌드한다."""

    def __init__(self, config: Config) -> None:
        """빌더를 초기화한다.

        Args:
            config: Worker 설정 (gradle_path 사용)
        """
        self._gradle_path = config.gradle_path

    def build_apk(self, project_dir: Path, output_apk_path: Path) -> Path:
        """프로젝트를 빌드하고 APK를 지정 경로로 복사한다.

        처리 순서:
            1. Gradle Wrapper 무결성 확인 (없거나 손상됐으면 격리 재생성)
            2. ./gradlew assembleDebug 실행
            3. 산출 APK 탐색 후 output_apk_path로 복사

        타임아웃을 설정하지 않는다 (완료까지 대기).

        Args:
            project_dir: 빌드할 Android 프로젝트 루트
            output_apk_path: 최종 APK를 복사할 경로

        Returns:
            복사 완료된 APK 경로

        Raises:
            BuildError: 프로젝트 부재, Wrapper 생성 실패, 빌드 실패, APK 미발견
        """
        if not project_dir.is_dir():
            raise BuildError(detail=f"빌드할 프로젝트 디렉토리가 없습니다: {project_dir}")

        self._ensure_wrapper(project_dir)
        self._run_gradle_task(project_dir)

        apk_source = self._locate_apk(project_dir)
        output_apk_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(apk_source, output_apk_path)

        logger.info(
            "APK 빌드 완료 (%s -> %s, %d bytes)",
            apk_source,
            output_apk_path,
            output_apk_path.stat().st_size,
        )
        return output_apk_path

    def _ensure_wrapper(self, project_dir: Path) -> None:
        """Gradle Wrapper를 검증하고 필요하면 격리 재생성한다 (FR-008).

        생성 프로젝트의 실행 script 존재만 신뢰하지 않는다. Wrapper JAR가 읽을 수 있는
        ZIP이며 GradleWrapperMain 진입점을 포함하고, distribution URL이 공식 Gradle
        stable URL인지 확인한다. 검증 실패 시 project build script를 읽지 않는 임시
        최소 Gradle project에서 Wrapper를 생성해 산출물만 복사한다.

        Args:
            project_dir: 프로젝트 루트

        Raises:
            BuildError: Wrapper 생성 또는 생성 후 무결성 검증 실패
        """
        wrapper_spec = self._read_wrapper_spec(project_dir)
        if self._wrapper_is_valid(project_dir) and wrapper_spec is not None:
            gradlew = project_dir / GRADLEW_SCRIPT
            self._make_executable(gradlew)
            logger.info("검증된 Gradle Wrapper 사용: %s", gradlew)
            return

        logger.warning("Gradle Wrapper가 없거나 유효하지 않아 재생성합니다: %s", project_dir)
        self._generate_wrapper(project_dir, wrapper_spec)

        generated_spec = self._read_wrapper_spec(project_dir)
        if not self._wrapper_is_valid(project_dir) or generated_spec is None:
            raise BuildError(detail="Gradle Wrapper 생성 후 무결성 검증에 실패했습니다")

        self._make_executable(project_dir / GRADLEW_SCRIPT)
        logger.info("Gradle Wrapper 생성 및 무결성 검증 완료")

    def _generate_wrapper(
        self,
        project_dir: Path,
        wrapper_spec: tuple[str, str] | None,
    ) -> None:
        """격리된 최소 Gradle project에서 Wrapper를 생성해 설치한다.

        Args:
            project_dir: Wrapper를 설치할 Android 프로젝트 루트
            wrapper_spec: 공식 URL에서 추출한 (Gradle version, distribution type)

        Raises:
            BuildError: 임시 디렉토리, Gradle 실행 또는 산출물 복사 실패
        """
        try:
            with tempfile.TemporaryDirectory(
                prefix=".prompton-gradle-wrapper-",
                dir=str(project_dir.parent),
            ) as temporary_dir:
                wrapper_project = Path(temporary_dir)
                (wrapper_project / "settings.gradle").write_text(
                    "rootProject.name = 'prompton-wrapper-bootstrap'\n",
                    encoding="utf-8",
                )

                command = [self._gradle_path, GRADLE_WRAPPER_TASK, "--no-daemon"]
                if wrapper_spec is not None:
                    version, distribution_type = wrapper_spec
                    command.extend(
                        [
                            "--gradle-version",
                            version,
                            "--distribution-type",
                            distribution_type,
                        ]
                    )

                result = self._run(command, wrapper_project, "gradle wrapper")
                if result.returncode != 0:
                    raise BuildError(
                        detail=(
                            f"Gradle Wrapper 생성 실패 (exit code={result.returncode}): "
                            f"{self._tail(result.stderr or result.stdout)}"
                        )
                    )

                for relative_path in GRADLE_WRAPPER_ARTIFACTS:
                    source = wrapper_project / relative_path
                    if not source.is_file():
                        raise BuildError(
                            detail=f"Gradle Wrapper 생성 산출물이 없습니다: {relative_path}"
                        )
                    destination = project_dir / relative_path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
        except BuildError:
            raise
        except OSError as exc:
            raise BuildError(detail=f"Gradle Wrapper 격리 생성 중 OS 오류: {exc}") from exc

    @classmethod
    def _wrapper_is_valid(cls, project_dir: Path) -> bool:
        """Linux script와 Wrapper JAR의 최소 실행 무결성을 확인한다."""
        gradlew = project_dir / GRADLEW_SCRIPT
        wrapper_jar = project_dir / GRADLE_WRAPPER_JAR
        if (
            not gradlew.is_file()
            or gradlew.is_symlink()
            or not wrapper_jar.is_file()
            or wrapper_jar.is_symlink()
        ):
            return False

        try:
            with gradlew.open("rb") as script:
                if script.read(2) != b"#!":
                    return False
            with zipfile.ZipFile(wrapper_jar) as archive:
                if GRADLE_WRAPPER_MAIN_CLASS not in archive.namelist():
                    return False
                return archive.testzip() is None
        except (OSError, zipfile.BadZipFile):
            return False

    @staticmethod
    def _read_wrapper_spec(project_dir: Path) -> tuple[str, str] | None:
        """공식 distribution URL에서 Gradle version/type만 추출한다.

        생성 프로젝트의 properties는 untrusted data이므로 URL 자체를 command나 로그에
        전달하지 않고 엄격한 allowlist 정규식과 크기 제한을 적용한다.
        """
        properties = project_dir / GRADLE_WRAPPER_PROPERTIES
        if not properties.is_file() or properties.is_symlink():
            return None

        try:
            if properties.stat().st_size > MAX_WRAPPER_PROPERTIES_BYTES:
                return None
            for line in properties.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() == "distributionUrl":
                    normalized = value.strip().replace(r"\:", ":")
                    match = TRUSTED_GRADLE_DISTRIBUTION_RE.fullmatch(normalized)
                    if match is None:
                        return None
                    return match.group("version"), match.group("kind")
        except (OSError, UnicodeError):
            return None
        return None

    def _run_gradle_task(self, project_dir: Path) -> None:
        """Gradle Wrapper로 assembleDebug를 실행한다.

        Args:
            project_dir: 프로젝트 루트

        Raises:
            BuildError: 빌드 실패
        """
        gradlew = project_dir / GRADLEW_SCRIPT
        logger.info("APK 빌드 시작 (%s)", GRADLE_BUILD_TASK)

        result = self._run(
            [str(gradlew), GRADLE_BUILD_TASK, "--no-daemon", "--stacktrace"],
            project_dir,
            GRADLE_BUILD_TASK,
        )

        if result.returncode != 0:
            raise BuildError(
                detail=(
                    f"Gradle 빌드 실패 (exit code={result.returncode}): "
                    f"{self._tail(result.stderr or result.stdout)}"
                )
            )

    def _locate_apk(self, project_dir: Path) -> Path:
        """빌드 산출 APK를 탐색한다.

        Args:
            project_dir: 프로젝트 루트

        Returns:
            발견된 APK 경로 (여러 개면 가장 최근 수정된 파일)

        Raises:
            BuildError: APK를 찾을 수 없는 경우
        """
        for pattern in APK_SEARCH_PATTERNS:
            candidates = sorted(
                project_dir.glob(pattern),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                logger.info("APK 발견: %s", candidates[0])
                return candidates[0]

        raise BuildError(
            detail=(
                f"빌드 산출 APK를 찾을 수 없습니다 "
                f"(dir={project_dir}, patterns={APK_SEARCH_PATTERNS})"
            )
        )

    @classmethod
    def _run(cls, command: list[str], cwd: Path, label: str) -> subprocess.CompletedProcess[str]:
        """subprocess를 실행하고 출력을 로깅한다.

        Args:
            command: 실행할 커맨드 인자 리스트
            cwd: 작업 디렉토리
            label: 로그에 표시할 작업 이름

        Returns:
            완료된 프로세스 결과

        Raises:
            BuildError: 실행 파일 부재 또는 OS 오류
        """
        try:
            result = subprocess.run(  # noqa: S603 - 인자는 내부에서 구성된 경로만 사용
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise BuildError(detail=f"{label} 실행 파일을 찾을 수 없습니다: {command[0]}") from exc
        except OSError as exc:
            raise BuildError(detail=f"{label} 실행 중 OS 오류: {exc}") from exc

        if result.stdout:
            logger.debug("%s stdout: %s", label, sanitize_log(cls._tail(result.stdout)))
        if result.stderr:
            logger.warning("%s stderr: %s", label, sanitize_log(cls._tail(result.stderr)))

        return result

    @staticmethod
    def _make_executable(path: Path) -> None:
        """파일에 실행 권한을 부여한다.

        S3/zip 경유로 실행 비트가 유실되는 경우를 보정한다.

        Args:
            path: 대상 파일
        """
        try:
            current = path.stat().st_mode
            path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            # Windows 등 실행 비트 개념이 없는 환경에서는 무시한다
            logger.debug("실행 권한 설정 생략: %s", path, exc_info=True)

    @staticmethod
    def _tail(text: str | None) -> str:
        """출력 문자열의 끝부분만 잘라 반환한다.

        Args:
            text: 원본 문자열

        Returns:
            최대 MAX_OUTPUT_LOG_CHARS 길이의 문자열
        """
        if not text:
            return ""
        stripped = text.strip()
        if len(stripped) <= MAX_OUTPUT_LOG_CHARS:
            return stripped
        return "...(생략)... " + stripped[-MAX_OUTPUT_LOG_CHARS:]
