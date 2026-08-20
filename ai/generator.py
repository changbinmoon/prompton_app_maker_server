"""kiro-cli 기반 AI 코드 생성 모듈.

설계 근거: business-logic-model.md 섹션 6 (kiro-cli 연동 모델),
          logical-components.md 섹션 7
비즈니스 규칙: BR-008 (AI_GENERATION_FAILED 분류)
NFR 패턴: Pattern 4 (Fail-Fast for External Processes - 재시도 없음)

미결정 사항:
    requirements.md 섹션 9에 따라 kiro-cli의 정확한 CLI 인터페이스는 확정되지 않았다.
    호출 인자는 KIRO_CLI_ARGS_TEMPLATE로 분리해 두었으므로, 실제 인터페이스가
    확정되면 이 상수만 수정하면 된다.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from models.exceptions import AIGenerationError
from utils.log_sanitizer import sanitize_log

if TYPE_CHECKING:
    from models.entities import Config

logger = logging.getLogger(__name__)

#: kiro-cli 호출 인자 템플릿 (미확정 인터페이스 - 확정 시 이 상수만 수정)
#: 사용 가능한 치환 키: requirements, assets, output
KIRO_CLI_ARGS_TEMPLATE: tuple[str, ...] = (
    "generate",
    "--requirements",
    "{requirements}",
    "--output",
    "{output}",
)

#: 에셋이 존재할 때 추가되는 인자
KIRO_CLI_ASSETS_ARGS: tuple[str, ...] = ("--assets", "{assets}")

#: 생성 결과가 Android 프로젝트인지 확인하는 마커 (하나라도 존재하면 통과)
ANDROID_PROJECT_MARKERS: tuple[str, ...] = (
    "settings.gradle",
    "settings.gradle.kts",
    "build.gradle",
    "build.gradle.kts",
)

#: 로그에 남길 subprocess 출력 최대 길이
MAX_OUTPUT_LOG_CHARS = 4000


class AIGenerator:
    """kiro-cli subprocess를 관리하여 Android 프로젝트 코드를 생성한다."""

    def __init__(self, config: Config) -> None:
        """생성기를 초기화한다.

        Args:
            config: Worker 설정 (kiro_cli_path 사용)
        """
        self._cli_path = config.kiro_cli_path

    def generate_code(
        self,
        requirements_path: Path,
        assets_dir: Path,
        output_dir: Path,
    ) -> Path:
        """kiro-cli를 호출하여 Android 프로젝트 코드를 생성한다.

        타임아웃을 설정하지 않는다 (business-logic-model.md 섹션 6: 완료까지 대기).
        실패 시 재시도하지 않고 즉시 예외를 발생시킨다 (NFR Pattern 4).

        Args:
            requirements_path: requirements.json 로컬 경로
            assets_dir: 에셋 디렉토리 (비어 있어도 무방)
            output_dir: 생성 결과를 기록할 디렉토리

        Returns:
            생성된 프로젝트 루트 디렉토리 경로

        Raises:
            AIGenerationError: CLI 실행 실패, exit code != 0, 또는 결과 검증 실패
        """
        if not requirements_path.is_file():
            raise AIGenerationError(
                detail=f"requirements.json이 존재하지 않습니다: {requirements_path}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        command = self._build_command(requirements_path, assets_dir, output_dir)

        logger.info("kiro-cli 실행: %s", " ".join(command))

        try:
            result = subprocess.run(  # noqa: S603 - 인자는 내부에서 구성된 경로만 사용
                command,
                capture_output=True,
                text=True,
                check=False,
                cwd=str(output_dir),
            )
        except FileNotFoundError as exc:
            raise AIGenerationError(
                detail=f"kiro-cli 실행 파일을 찾을 수 없습니다: {self._cli_path}"
            ) from exc
        except OSError as exc:
            raise AIGenerationError(detail=f"kiro-cli 실행 중 OS 오류: {exc}") from exc

        self._log_output(result.stdout, result.stderr)

        if result.returncode != 0:
            raise AIGenerationError(
                detail=(
                    f"kiro-cli가 비정상 종료했습니다 (exit code={result.returncode}): "
                    f"{self._tail(result.stderr)}"
                )
            )

        self._verify_output(output_dir)
        logger.info("코드 생성 완료: %s", output_dir)
        return output_dir

    def _build_command(
        self, requirements_path: Path, assets_dir: Path, output_dir: Path
    ) -> list[str]:
        """kiro-cli 실행 커맨드를 구성한다.

        Args:
            requirements_path: requirements.json 경로
            assets_dir: 에셋 디렉토리
            output_dir: 출력 디렉토리

        Returns:
            subprocess에 전달할 인자 리스트
        """
        substitutions = {
            "requirements": str(requirements_path),
            "assets": str(assets_dir),
            "output": str(output_dir),
        }

        command = [self._cli_path]
        command.extend(arg.format(**substitutions) for arg in KIRO_CLI_ARGS_TEMPLATE)

        if self._has_assets(assets_dir):
            command.extend(arg.format(**substitutions) for arg in KIRO_CLI_ASSETS_ARGS)

        return command

    @staticmethod
    def _has_assets(assets_dir: Path) -> bool:
        """에셋 디렉토리에 파일이 하나 이상 있는지 확인한다.

        Args:
            assets_dir: 확인할 디렉토리

        Returns:
            파일이 하나 이상 존재하면 True
        """
        if not assets_dir.is_dir():
            return False
        return any(child.is_file() for child in assets_dir.iterdir())

    @staticmethod
    def _verify_output(output_dir: Path) -> None:
        """생성 결과가 Android 프로젝트 구조인지 검증한다.

        Args:
            output_dir: 검증할 디렉토리

        Raises:
            AIGenerationError: Gradle 프로젝트 마커를 찾을 수 없는 경우
        """
        for marker in ANDROID_PROJECT_MARKERS:
            if (output_dir / marker).exists():
                return

        raise AIGenerationError(
            detail=(
                f"생성 결과에서 Gradle 프로젝트 마커를 찾을 수 없습니다 "
                f"(dir={output_dir}, markers={ANDROID_PROJECT_MARKERS})"
            )
        )

    @classmethod
    def _log_output(cls, stdout: str | None, stderr: str | None) -> None:
        """subprocess 출력을 민감정보 필터링 후 로그에 남긴다 (BR-013).

        Args:
            stdout: 표준 출력
            stderr: 표준 에러
        """
        if stdout:
            logger.debug("kiro-cli stdout: %s", sanitize_log(cls._tail(stdout)))
        if stderr:
            logger.warning("kiro-cli stderr: %s", sanitize_log(cls._tail(stderr)))

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
