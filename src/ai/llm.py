"""텍스트 LLM 추상화.

우선순위: Anthropic(Claude) → Google(Gemini) → 오프라인 폴백.
- 키/패키지가 없으면 예외를 던지지 않고 available=False 인 결과로 '조용히 폴백'한다.
  (상위 로직이 템플릿 기반으로라도 결과를 만들 수 있게)
- Claude 호출은 모델 종류가 바뀌어도 400이 안 나도록 최소 파라미터
  (model/max_tokens/system/messages)만 사용한다. 기본 모델은 config.DEFAULT_TEXT_MODEL.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .. import config

log = logging.getLogger(__name__)


@dataclass
class LLMResult:
    text: str
    provider: str          # "anthropic" | "gemini" | "offline"
    model: str = ""
    available: bool = True  # False = 실제 LLM 미사용(폴백 필요)


class LLMClient:
    def __init__(
        self,
        *,
        model: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        gemini_key: Optional[str] = None,
    ) -> None:
        self.model = model or config.DEFAULT_TEXT_MODEL
        # 명시 인자 > 환경변수
        self._anthropic_key = anthropic_key if anthropic_key is not None else config.get_anthropic_api_key()
        self._gemini_key = gemini_key if gemini_key is not None else config.get_gemini_api_key()

    @property
    def provider(self) -> str:
        if self._anthropic_key:
            return "anthropic"
        if self._gemini_key:
            return "gemini"
        return "offline"

    def available(self) -> bool:
        return self.provider != "offline"

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> LLMResult:
        """프롬프트로 텍스트 생성. 실패/미설정 시 available=False 결과 반환(예외 없음)."""
        provider = self.provider
        if provider == "anthropic":
            text = self._anthropic(prompt, system, max_tokens)
            if text is not None:
                return LLMResult(text=text, provider="anthropic", model=self.model)
        elif provider == "gemini":
            text = self._gemini(prompt, system, max_tokens)
            if text is not None:
                return LLMResult(text=text, provider="gemini", model=config.DEFAULT_TEXT_MODEL)
        # 폴백
        return LLMResult(text="", provider="offline", available=False)

    # --- Anthropic ---
    def _anthropic(self, prompt: str, system: Optional[str], max_tokens: int) -> Optional[str]:
        try:
            import anthropic  # type: ignore
        except ImportError:
            log.info("[llm] anthropic 패키지 미설치 — 폴백")
            return None
        try:
            client = anthropic.Anthropic(api_key=self._anthropic_key)
            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system
            resp = client.messages.create(**kwargs)
            parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
            return "".join(parts).strip()
        except Exception as e:  # 네트워크/인증/쿼터 등 — 폴백으로 전환
            log.warning("[llm] Anthropic 호출 실패 — 폴백: %s", e)
            return None

    # --- Gemini ---
    def _gemini(self, prompt: str, system: Optional[str], max_tokens: int) -> Optional[str]:
        try:
            from google import genai  # type: ignore
        except ImportError:
            try:
                import google.generativeai as genai_legacy  # type: ignore
            except ImportError:
                log.info("[llm] google-genai 패키지 미설치 — 폴백")
                return None
            else:
                return self._gemini_legacy(genai_legacy, prompt, system, max_tokens)
        try:
            client = genai.Client(api_key=self._gemini_key)
            full = f"{system}\n\n{prompt}" if system else prompt
            resp = client.models.generate_content(
                model=config.DEFAULT_TEXT_MODEL, contents=full
            )
            return (resp.text or "").strip()
        except Exception as e:
            log.warning("[llm] Gemini 호출 실패 — 폴백: %s", e)
            return None

    def _gemini_legacy(self, genai_legacy, prompt, system, max_tokens) -> Optional[str]:
        try:
            genai_legacy.configure(api_key=self._gemini_key)
            model = genai_legacy.GenerativeModel(config.DEFAULT_TEXT_MODEL)
            full = f"{system}\n\n{prompt}" if system else prompt
            resp = model.generate_content(full)
            return (resp.text or "").strip()
        except Exception as e:
            log.warning("[llm] Gemini(legacy) 호출 실패 — 폴백: %s", e)
            return None
