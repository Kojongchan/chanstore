"""설정 로딩. 키는 코드에 하드코딩하지 않고 .env 에서 읽는다 (PROJECT.md 비기능 요구사항)."""
from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv 미설치 시에도 OS 환경변수로 동작
    def load_dotenv(*_args, **_kwargs) -> bool:  # type: ignore
        return False


# 모듈 임포트 시 1회 .env 로드
load_dotenv()


def _clean(name: str) -> str | None:
    """환경변수를 읽어 공백/placeholder를 미설정(None)으로 정규화."""
    val = os.getenv(name, "").strip()
    if not val or val.startswith("여기에") or val.startswith("<"):
        return None
    return val


def get_elevenst_api_key() -> str | None:
    """11번가 오픈API 키. 없으면 None."""
    return _clean("ELEVENST_API_KEY")


def get_naver_credentials() -> tuple[str, str] | None:
    """네이버 오픈API (client id, secret). 둘 다 있어야 유효, 아니면 None."""
    cid = _clean("NAVER_CLIENT_ID")
    secret = _clean("NAVER_CLIENT_SECRET")
    if cid and secret:
        return cid, secret
    return None


# --- AI (상세페이지·CS) ---
# 텍스트 LLM: Anthropic(Claude) 우선, 없으면 Gemini, 둘 다 없으면 오프라인 템플릿 폴백.
DEFAULT_TEXT_MODEL = os.getenv("CHANSTORE_TEXT_MODEL", "claude-opus-4-8").strip()
# 이미지: nano banana = Google Gemini 2.5 Flash Image.
DEFAULT_IMAGE_MODEL = os.getenv("CHANSTORE_IMAGE_MODEL", "gemini-2.5-flash-image").strip()


def get_anthropic_api_key() -> str | None:
    return _clean("ANTHROPIC_API_KEY")


def get_gemini_api_key() -> str | None:
    """Gemini(=nano banana) 키. GEMINI_API_KEY 우선, 없으면 GOOGLE_API_KEY."""
    return _clean("GEMINI_API_KEY") or _clean("GOOGLE_API_KEY")
