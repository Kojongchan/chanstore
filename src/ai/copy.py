"""상세페이지 카피 생성.

입력: 상품 스펙 dict(소싱처/판매자가 아는 사실 — 이름·브랜드·스펙·셀링포인트).
출력: DetailCopy (제목/부제/셀링포인트/스펙표/주의문구 + 광고문구 위반경고).

- LLM(Claude/Gemini)이 있으면 카피를 생성하고, 없으면 스펙 기반 템플릿으로 폴백한다.
- 생성 결과는 항상 과장광고 필터(compliance)를 통과시켜 위반 표현을 '검토필요'로 표시한다.
- '경쟁사 상세를 베끼는' 것이 아니라, 내 상품 스펙으로 새로 쓰는 것이다(PLATFORM_PLAN.md §6).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .llm import LLMClient
from .compliance import sanitize_ad_text, Violation

log = logging.getLogger(__name__)

_SYSTEM = (
    "너는 한국 오픈마켓 상세페이지 카피라이터다. 주어진 상품 사실 정보만으로 "
    "정직하고 매력적인 판매 카피를 쓴다. 근거 없는 최상급/절대 표현(최고, 1위, 100% 효과, "
    "완치 등)과 과장·허위광고는 절대 쓰지 않는다. 실측·사실과 다른 내용을 지어내지 않는다."
)


@dataclass
class DetailCopy:
    title: str
    subtitle: str = ""
    bullets: list[str] = field(default_factory=list)
    spec_rows: list[tuple[str, str]] = field(default_factory=list)
    notice: str = ""
    provider: str = "offline"
    warnings: list[Violation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "bullets": self.bullets,
            "spec_rows": self.spec_rows,
            "notice": self.notice,
            "provider": self.provider,
            "warnings": [{"phrase": w.phrase, "reason": w.reason} for w in self.warnings],
        }


DEFAULT_NOTICE = (
    "· 상품 이미지는 연출컷이 포함될 수 있으며 실제와 색상·크기 차이가 있을 수 있습니다.\n"
    "· 배송/교환/반품은 판매자 정책 및 관련 법령에 따릅니다.\n"
    "· 정확한 실측·구성은 상세 스펙을 확인해 주세요."
)


def _spec_rows(specs: dict[str, Any]) -> list[tuple[str, str]]:
    return [(str(k), str(v)) for k, v in (specs or {}).items()]


def _template_copy(spec: dict) -> DetailCopy:
    name = str(spec.get("name", "")).strip()
    brand = str(spec.get("brand", "")).strip()
    features = [str(f).strip() for f in (spec.get("features") or []) if str(f).strip()]
    title = (f"{brand} {name}".strip()) or name or "상품"
    subtitle = str(spec.get("subtitle", "")).strip() or (features[0] if features else "")
    bullets = features or [f"{title} 상품입니다."]
    return DetailCopy(
        title=title,
        subtitle=subtitle,
        bullets=bullets,
        spec_rows=_spec_rows(spec.get("specs", {})),
        notice=str(spec.get("notice", "")).strip() or DEFAULT_NOTICE,
        provider="offline",
    )


def _parse_llm_json(text: str, spec: dict) -> Optional[DetailCopy]:
    """LLM 응답(JSON)을 DetailCopy 로 파싱. 실패 시 None."""
    # 코드펜스/앞뒤 잡텍스트 제거 후 첫 JSON 오브젝트 시도
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    bullets = [str(b) for b in (data.get("bullets") or []) if str(b).strip()]
    return DetailCopy(
        title=str(data.get("title") or spec.get("name") or "상품").strip(),
        subtitle=str(data.get("subtitle") or "").strip(),
        bullets=bullets or _template_copy(spec).bullets,
        spec_rows=_spec_rows(spec.get("specs", {})),
        notice=str(data.get("notice") or DEFAULT_NOTICE).strip(),
        provider="llm",
    )


def _build_prompt(spec: dict) -> str:
    return (
        "다음 상품의 오픈마켓 상세페이지 카피를 JSON으로만 출력해줘. "
        '형식: {"title": "...", "subtitle": "...", "bullets": ["...", "..."], "notice": "..."}\n'
        "- title: 40자 이내, 핵심 키워드 포함\n"
        "- subtitle: 한 줄 후킹\n"
        "- bullets: 셀링포인트 3~5개(사실 기반, 과장 금지)\n"
        "- notice: 구매 주의/고지 문구\n\n"
        f"상품 정보:\n{json.dumps(spec, ensure_ascii=False, indent=2)}"
    )


def generate_copy(spec: dict, *, llm: Optional[LLMClient] = None) -> DetailCopy:
    """상품 스펙 dict → DetailCopy. LLM 있으면 생성, 없으면 템플릿. 광고필터 항상 적용."""
    client = llm or LLMClient()
    copy_obj: Optional[DetailCopy] = None
    if client.available():
        result = client.generate(_build_prompt(spec), system=_SYSTEM, max_tokens=1500)
        if result.available and result.text:
            copy_obj = _parse_llm_json(result.text, spec)
            if copy_obj:
                copy_obj.provider = result.provider
    if copy_obj is None:
        copy_obj = _template_copy(spec)

    # 광고문구 필터 — 제목/부제/불릿을 검사해 위반은 표식 처리 + 경고 수집
    warnings: list[Violation] = []
    copy_obj.title, w = sanitize_ad_text(copy_obj.title)
    warnings += w
    copy_obj.subtitle, w = sanitize_ad_text(copy_obj.subtitle)
    warnings += w
    cleaned_bullets = []
    for b in copy_obj.bullets:
        cb, w = sanitize_ad_text(b)
        cleaned_bullets.append(cb)
        warnings += w
    copy_obj.bullets = cleaned_bullets
    copy_obj.warnings = warnings
    return copy_obj
