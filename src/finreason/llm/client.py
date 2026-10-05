"""OpenAI-compatible chat client for the college-hosted model server.

- Config from environment / .env: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_CONCURRENCY,
  LLM_THINKING (0/1, default 0) and LLM_THINK_BUDGET (extra max_tokens when thinking, default 8192).
- Thinking is toggled per request via `chat_template_kwargs.enable_thinking` (Qwen chat template);
  `Request.thinking=None` uses the client default. The effective setting is part of the cache key.
- Every response is cached on disk (outputs/cache/llm), keyed by model + messages + params +
  sample index, so reruns are free and a crashed batch resumes where it stopped.
- `chat_many` runs requests in parallel with retries and exponential backoff.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..io import OUTPUTS, ROOT

CACHE_DIR = OUTPUTS / "cache" / "llm"
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclass
class Request:
    messages: list[dict[str, str]]
    temperature: float = 0.0
    max_tokens: int = 2048
    sample: int = 0  # distinguishes repeated samples of the same prompt in the cache
    thinking: bool | None = None  # None = client default (LLM_THINKING)
    extra: dict[str, Any] = field(default_factory=dict)


def strip_reasoning(text: str) -> str:
    """Drop <think>...</think> blocks emitted by reasoning models."""
    text = _THINK.sub("", text)
    if "</think>" in text:  # opening tag was consumed by the server's chat template
        text = text.split("</think>", 1)[1]
    return text.strip()


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, concurrency: int = 4, timeout: float = 300,
                 thinking: bool = False, think_budget: int = 8192):
        from openai import OpenAI

        self.model = model
        self.concurrency = max(1, concurrency)
        self.thinking = thinking
        self.think_budget = think_budget
        self._client = OpenAI(base_url=base_url, api_key=api_key or "none", timeout=timeout, max_retries=0)
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(self.concurrency)  # caps in-flight requests globally
        self._send_seed = True  # turned off if the server rejects the `seed` parameter
        self.stats = {"calls": 0, "cache_hits": 0, "errors": 0, "prompt_tokens": 0, "completion_tokens": 0}

    @classmethod
    def from_env(cls, model: str | None = None) -> "LLMClient":
        try:
            from dotenv import load_dotenv

            load_dotenv(ROOT / ".env")
        except ImportError:
            pass
        base_url = os.environ.get("LLM_BASE_URL")
        if not base_url:
            raise RuntimeError("LLM_BASE_URL is not set (copy .env.example to .env and fill it in)")
        return cls(
            base_url=base_url,
            api_key=os.environ.get("LLM_API_KEY", ""),
            model=model or os.environ.get("LLM_MODEL", ""),
            concurrency=int(os.environ.get("LLM_CONCURRENCY", "4")),
            thinking=os.environ.get("LLM_THINKING", "0").strip().lower() in {"1", "true", "yes", "on"},
            think_budget=int(os.environ.get("LLM_THINK_BUDGET", "8192")),
        )

    def list_models(self) -> list[str]:
        return [model.id for model in self._client.models.list().data]

    def _thinking(self, request: Request) -> bool:
        return self.thinking if request.thinking is None else request.thinking

    def _cache_path(self, request: Request) -> Path:
        key = json.dumps(
            [self.model, request.messages, request.temperature, request.max_tokens, request.sample, request.extra,
             self._thinking(request)],
            sort_keys=True,
        )
        digest = hashlib.sha256(key.encode()).hexdigest()
        return CACHE_DIR / digest[:2] / f"{digest}.json"

    def chat(self, request: Request, *, retries: int = 4) -> str:
        path = self._cache_path(request)
        if path.exists():
            with self._lock:
                self.stats["cache_hits"] += 1
            return json.loads(path.read_text())["content"]
        thinking = self._thinking(request)
        max_tokens = request.max_tokens + (self.think_budget if thinking else 0)
        delay = 2.0
        for attempt in range(retries + 1):
            try:
                with self._slots:
                    response = self._client.chat.completions.create(
                        model=self.model,
                        messages=request.messages,
                        temperature=request.temperature,
                        max_tokens=max_tokens,
                        **({"seed": request.sample} if self._send_seed and request.temperature > 0 else {}),
                        **request.extra,
                        extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
                    )
                choice = response.choices[0]
                raw = choice.message.content or ""
                if thinking and choice.finish_reason == "length" and "</think>" not in raw:
                    raw = ""  # ran out of tokens mid-reasoning: no answer, don't mine code from the thoughts
                content = strip_reasoning(raw)
                with self._lock:
                    self.stats["calls"] += 1
                    if response.usage:
                        self.stats["prompt_tokens"] += response.usage.prompt_tokens or 0
                        self.stats["completion_tokens"] += response.usage.completion_tokens or 0
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"content": content, "model": self.model}))
                return content
            except Exception as error:  # network errors, 429, 5xx: back off and retry
                with self._lock:
                    self.stats["errors"] += 1
                if attempt == retries:
                    raise
                if "seed" in str(error).lower():
                    self._send_seed = False
                time.sleep(delay)
                delay = min(delay * 2, 60)
        raise AssertionError("unreachable")

    def chat_many(self, requests: list[Request]) -> list[str | None]:
        """Run requests concurrently; a request that keeps failing yields None."""

        def run(request: Request) -> str | None:
            try:
                return self.chat(request)
            except Exception:
                return None

        with ThreadPoolExecutor(self.concurrency) as pool:
            return list(pool.map(run, requests))


_CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str | None:
    """Last fenced Python block in a response (models often put a sketch first)."""
    blocks = _CODE_BLOCK.findall(text)
    if blocks:
        return blocks[-1].strip()
    if "def solve" in text:
        return text[text.index("def solve"):].strip()
    return None
