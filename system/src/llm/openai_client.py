"""OpenAI 呼叫包裝 + 自動故障轉移 (Auto-Failover)。

對應論文 §3.2.5：若 API 連線異常或額度不足，自動切換至模擬展示模式。
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Literal

from openai import OpenAI, OpenAIError

from config import OPENAI_API_KEY, OPENAI_MODEL, GEMINI_API_KEY, GEMINI_BASE_URL


log = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    source: Literal["live", "mock"]


_MOCK_PAYLOAD = {
    "issue": "（模擬模式）API 不可用，無法即時生成。此為展示用範本，僅顯示流程能跑通。",
    "rule": "民法第 421 條",
    "application": "範例：以本條款為例，承租人應依約給付租金，本條款符合一般約定。",
    "conclusion": "（模擬）風險可控；建議檢查押金返還條款是否明確。",
    "risk_level": "medium",
    "suggestions": ["切換到真實 API 以取得實際分析", "確認 OPENAI_API_KEY 是否有效"],
    "cited_articles": ["民法第 421 條"],
}


def _mock_response() -> LLMResponse:
    return LLMResponse(
        content=json.dumps(_MOCK_PAYLOAD, ensure_ascii=False),
        model="mock",
        source="mock",
    )


def _model_supports_custom_temperature(model: str) -> bool:
    """gpt-5 系列與 o-系列（推理模型）只接受 default temperature=1,
    傳其他值會 400。其餘 (gpt-4o / gpt-4.1 / gpt-3.5) 接受 0–2。"""
    m = model.lower()
    if m.startswith("gpt-5"):
        return False
    if m.startswith(("o1", "o3", "o4")):
        return False
    return True


def chat_json(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.2,
    timeout: float = 60.0,
    allow_mock_fallback: bool = True,
) -> LLMResponse:
    """呼叫 chat completions，強制要求 JSON 物件回應。

    失敗時若 `allow_mock_fallback=True`（預設），回傳模擬 payload，
    讓 pipeline 仍可端對端跑完；否則丟出例外。
    """
    model = model or OPENAI_MODEL
    use_gemini = model.lower().startswith("gemini")
    api_key = GEMINI_API_KEY if use_gemini else OPENAI_API_KEY
    key_name = "GEMINI_API_KEY" if use_gemini else "OPENAI_API_KEY"

    if not api_key:
        if allow_mock_fallback:
            log.warning(f"{key_name} 未設定 — 使用 mock 回應")
            return _mock_response()
        raise RuntimeError(f"{key_name} 未設定")

    # Gemini 經 OpenAI 相容介面(base_url + Gemini key)呼叫;其餘走原生 OpenAI。
    if use_gemini:
        client = OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL, timeout=timeout)
    else:
        client = OpenAI(api_key=api_key, timeout=timeout)

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    if use_gemini:
        kwargs["temperature"] = temperature  # Gemini 接受自訂 temperature
    else:
        if _model_supports_custom_temperature(model):
            kwargs["temperature"] = temperature
        # gpt-5 / o-系列保留 default temperature=1,由 reasoning_effort 控制
        if model.lower().startswith("gpt-5"):
            # IRAC + 引用稽核屬結構化任務,low effort 已足夠;可改 OPENAI_REASONING_EFFORT
            kwargs["reasoning_effort"] = os.getenv("OPENAI_REASONING_EFFORT", "low")

    # 重試暫時性錯誤(429/5xx/UNAVAILABLE,如 Gemini 高需求 503)再 fallback,
    # 避免暫時抖動被靜默轉成 mock 假數據污染評估結果。
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(**kwargs)
            return LLMResponse(
                content=resp.choices[0].message.content or "{}",
                model=model,
                source="live",
            )
        except OpenAIError as e:
            last_err = e
            msg = str(e)
            status = getattr(e, "status_code", None)
            transient = status in (429, 500, 502, 503, 529) or "503" in msg or "UNAVAILABLE" in msg or "high demand" in msg
            if transient and attempt < 2:
                time.sleep(2 * (attempt + 1))  # 2s → 4s 退避
                continue
            break
    if allow_mock_fallback:
        log.warning(f"OpenAI 呼叫失敗 ({type(last_err).__name__})：{last_err} — 切換 mock")
        return _mock_response()
    raise last_err


def parse_json(content: str) -> dict:
    """Robust JSON parser；模型偶爾包前後文，盡量救回。"""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 嘗試擷取第一個 { ... } 區塊
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"_raw": content, "_parse_error": True}
