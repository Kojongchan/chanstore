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


def get_elevenst_api_key() -> str | None:
    """11번가 오픈API 키. 없으면 None."""
    key = os.getenv("ELEVENST_API_KEY", "").strip()
    # .env.example 의 안내 placeholder 가 그대로 들어온 경우도 미설정으로 취급
    if not key or key.startswith("여기에"):
        return None
    return key
