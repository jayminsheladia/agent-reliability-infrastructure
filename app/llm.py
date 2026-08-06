import time
from dataclasses import dataclass

import anthropic

from app.config import settings

MODEL = "claude-opus-5"

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


@dataclass
class LLMResult:
    text: str
    tokens_used: int
    latency_ms: int


def call_llm(prompt: str, system: str | None = None) -> LLMResult:
    start = time.perf_counter()
    response = _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system or anthropic.NOT_GIVEN,
        messages=[{"role": "user", "content": prompt}],
    )
    latency_ms = int((time.perf_counter() - start) * 1000)

    text = next((block.text for block in response.content if block.type == "text"), "")
    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    return LLMResult(text=text, tokens_used=tokens_used, latency_ms=latency_ms)
