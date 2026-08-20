"""로그 민감정보 필터링.

설계 근거: nfr-design-patterns.md Pattern 10 (Log Sanitization)
비즈니스 규칙: BR-013 (로그 보안), NFR-006 (로그 보안)

필터 대상:
    - AWS Access Key ID / Secret Access Key
    - Session Token
    - Presigned URL 서명 파라미터
    - Bearer 토큰, API Key, 비밀번호 형태의 키=값 표현

설계 노트:
    NFR Design 문서의 AWS Secret Key 패턴은 `[A-Za-z0-9/+=]{40}` 이지만, 이 패턴만으로는
    40자 hex git commit SHA 등 정상 문자열까지 광범위하게 마스킹되어 로그 유용성이
    떨어진다. 따라서 아래 두 조건을 함께 요구하도록 정교화했다.
        1. 독립 토큰이어야 한다 (앞뒤가 단어 문자가 아님)
        2. 대문자와 소문자를 모두 포함해야 한다 (전부 소문자인 hex SHA 제외)
    실제 AWS Secret Key가 대문자를 전혀 포함하지 않을 확률은 무시할 수준이므로
    BR-013의 보호 목적은 유지된다.
"""

from __future__ import annotations

import re

#: 마스킹 대체 문자열
REDACTED = "[REDACTED]"

#: AWS Access Key ID (AKIA/ASIA 접두어 + 16자)
_AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")

#: URL 쿼리스트링 내 Session Token
_AMZ_SECURITY_TOKEN = re.compile(r"X-Amz-Security-Token=[^\s&\"']+", re.IGNORECASE)

#: URL 쿼리스트링 내 서명값
_AMZ_SIGNATURE = re.compile(r"X-Amz-Signature=[^\s&\"']+", re.IGNORECASE)

#: Presigned URL 전체 (Signature 파라미터를 포함한 http/https URL)
_PRESIGNED_URL = re.compile(
    r"https?://[^\s\"']*[?&](?:X-Amz-Signature|Signature)=[^\s\"']*", re.IGNORECASE
)

#: key=value 형태의 자격증명 (aws_secret_access_key, api_key, password, token 등)
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)\b("
    r"aws_secret_access_key|aws_session_token|secret_access_key|"
    r"secret_key|api_key|apikey|access_token|refresh_token|"
    r"password|passwd|token|secret"
    r")\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&\"']+)"
)

#: Authorization Bearer 토큰
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*")

#: AWS Secret Access Key 형태의 독립 40자 토큰 (대소문자 혼재 조건 포함)
_AWS_SECRET_KEY = re.compile(
    r"(?<![A-Za-z0-9/+=])"
    r"(?=[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=]))"
    r"(?=[A-Za-z0-9/+=]*[a-z])"
    r"(?=[A-Za-z0-9/+=]*[A-Z])"
    r"[A-Za-z0-9/+=]{40}"
)

#: 적용 순서가 중요하다. 넓은 범위(URL 전체)를 먼저 처리한 뒤 좁은 패턴을 적용한다.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    _PRESIGNED_URL,
    _AMZ_SECURITY_TOKEN,
    _AMZ_SIGNATURE,
    _AWS_ACCESS_KEY,
    _BEARER_TOKEN,
    _AWS_SECRET_KEY,
)


def sanitize_log(message: str) -> str:
    """로그 메시지에서 민감정보를 마스킹한다 (BR-013).

    Args:
        message: 원본 메시지

    Returns:
        민감정보가 [REDACTED]로 치환된 메시지.
        입력이 문자열이 아니면 문자열로 변환한 뒤 처리한다.
    """
    if not isinstance(message, str):
        message = str(message)

    if not message:
        return message

    # key=value 형태는 키 이름을 남기고 값만 마스킹한다
    sanitized = _CREDENTIAL_ASSIGNMENT.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", message
    )

    for pattern in _PATTERNS:
        sanitized = pattern.sub(REDACTED, sanitized)

    return sanitized
