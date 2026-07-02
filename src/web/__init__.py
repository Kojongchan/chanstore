"""로컬 대시보드 (3단계 로드맵).

수집·분석·소싱·상세페이지·CS를 CLI 없이 한 화면에서 쓰는 허브.
렌더링/데이터 함수(views)는 웹 프레임워크와 분리해 두어, FastAPI 없이도 테스트된다.
실행: `python dashboard.py` (fastapi/uvicorn 필요). 키 없이도 전부 동작(오프라인 폴백).
"""

from . import views

__all__ = ["views"]
