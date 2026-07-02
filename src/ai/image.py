"""상세페이지 이미지 생성 래퍼 — nano banana = Google Gemini 2.5 Flash Image.

- 키가 있으면 Gemini 이미지 모델로 생성/편집한 PNG 바이트를 저장.
- 키/패키지가 없으면 available=False 인 '플레이스홀더' 결과를 돌려줘, 상세페이지가
  이미지 자리표시(placeholder)로라도 완성되게 한다.
- '완전 무료 무제한'이 아니라 무료 할당량 + 초과 종량제이므로(PLATFORM_PLAN.md §6),
  호출 실패/쿼터초과도 조용히 폴백한다.

이미지 정책: 여기서 만드는 건 '내 판매용' 자산이다(AI 신규 생성). 경쟁사 이미지를
내려받아 재가공하지 않는다(§5).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .. import config

log = logging.getLogger(__name__)


@dataclass
class ImageResult:
    prompt: str
    provider: str                 # "gemini" | "placeholder"
    available: bool               # False = 실제 생성 안 됨(플레이스홀더)
    path: Optional[str] = None    # 저장된 파일 경로(생성 성공 시)
    placeholder_svg: str = ""     # 폴백 시 인라인 표시용 SVG
    note: str = ""


def _placeholder_svg(label: str) -> str:
    safe = (label or "이미지").replace("<", "").replace(">", "")[:40]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" role="img">'
        '<rect width="100%" height="100%" fill="#f0efe9"/>'
        '<rect x="20" y="20" width="760" height="760" fill="none" '
        'stroke="#c9c4b5" stroke-width="2" stroke-dasharray="10 8"/>'
        '<text x="50%" y="48%" text-anchor="middle" font-family="sans-serif" '
        f'font-size="30" fill="#8a8474">{safe}</text>'
        '<text x="50%" y="55%" text-anchor="middle" font-family="sans-serif" '
        'font-size="18" fill="#a8a292">AI 이미지 생성 예정 (nano banana)</text>'
        '</svg>'
    )


class ImageClient:
    def __init__(self, *, model: Optional[str] = None, gemini_key: Optional[str] = None) -> None:
        self.model = model or config.DEFAULT_IMAGE_MODEL
        self._key = gemini_key if gemini_key is not None else config.get_gemini_api_key()

    def available(self) -> bool:
        return bool(self._key)

    def generate(
        self,
        prompt: str,
        *,
        outdir: str | Path = "output/images",
        filename: str = "detail",
    ) -> ImageResult:
        """프롬프트로 이미지 생성. 실패/미설정 시 placeholder 결과(예외 없음)."""
        if self._key:
            res = self._gemini(prompt, outdir, filename)
            if res is not None:
                return res
        return ImageResult(
            prompt=prompt,
            provider="placeholder",
            available=False,
            placeholder_svg=_placeholder_svg(prompt),
            note="이미지 API 키 미설정/실패 — 플레이스홀더",
        )

    def _gemini(self, prompt: str, outdir, filename) -> Optional[ImageResult]:
        try:
            from google import genai  # type: ignore
        except ImportError:
            log.info("[image] google-genai 미설치 — 플레이스홀더")
            return None
        try:
            client = genai.Client(api_key=self._key)
            resp = client.models.generate_content(model=self.model, contents=prompt)
            data = _extract_image_bytes(resp)
            if not data:
                log.info("[image] 응답에 이미지 없음 — 플레이스홀더")
                return None
            out = Path(outdir)
            out.mkdir(parents=True, exist_ok=True)
            path = out / f"{filename}.png"
            path.write_bytes(data)
            return ImageResult(prompt=prompt, provider="gemini", available=True,
                               path=str(path), note="nano banana 생성 완료")
        except Exception as e:
            log.warning("[image] Gemini 이미지 생성 실패 — 플레이스홀더: %s", e)
            return None


def _extract_image_bytes(resp) -> Optional[bytes]:
    """Gemini 응답에서 첫 inline 이미지 바이트 추출. 구조 변화에 방어적으로."""
    try:
        for cand in getattr(resp, "candidates", []) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    return inline.data
    except Exception:
        return None
    return None
