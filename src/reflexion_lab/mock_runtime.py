from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .schemas import FailureMode, JudgeResult, QAExample, ReflectionEntry
from .utils import normalize_answer

load_dotenv()

FIRST_ATTEMPT_WRONG = {
    "hp2": "London",
    "hp4": "Atlantic Ocean",
    "hp6": "Red Sea",
    "hp8": "Andes",
}
FAILURE_MODE_BY_QID: dict[str, FailureMode] = {
    "hp2": "incomplete_multi_hop",
    "hp4": "wrong_final_answer",
    "hp6": "entity_drift",
    "hp8": "entity_drift",
}


@dataclass(frozen=True)
class CallMetrics:
    tokens: int = 0
    latency_ms: int = 0


@dataclass(frozen=True)
class ActorCall:
    answer: str
    metrics: CallMetrics


@dataclass(frozen=True)
class JudgeCall:
    result: JudgeResult
    metrics: CallMetrics


@dataclass(frozen=True)
class ReflectionCall:
    entry: ReflectionEntry
    metrics: CallMetrics


class Runtime(Protocol):
    mode: str

    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> ActorCall: ...

    def evaluator(self, example: QAExample, answer: str) -> JudgeCall: ...

    def reflector(
        self,
        example: QAExample,
        attempt_id: int,
        answer: str,
        judge: JudgeResult,
    ) -> ReflectionCall: ...


def _rough_token_count(*texts: str) -> int:
    """Deterministic fallback for mock mode; real mode uses provider usage."""
    return max(1, sum(len(re.findall(r"\w+|[^\w\s]", text)) for text in texts))


def _context_text(example: QAExample) -> str:
    return "\n\n".join(f"[{chunk.title}]\n{chunk.text}" for chunk in example.context)


class MockRuntime:
    """Free deterministic runtime used for learning, tests, and autograding."""

    mode = "mock"

    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> ActorCall:
        started = time.perf_counter()
        wrong = example.mock_wrong_answer or FIRST_ATTEMPT_WRONG.get(example.qid)
        if wrong is None:
            answer = example.gold_answer
        elif agent_type == "react" or (attempt_id == 1 and not reflection_memory):
            answer = wrong
        else:
            answer = example.gold_answer
        tokens = _rough_token_count(
            ACTOR_SYSTEM,
            example.question,
            _context_text(example),
            "\n".join(reflection_memory),
            answer,
        )
        elapsed = max(1, round((time.perf_counter() - started) * 1000))
        return ActorCall(answer=answer, metrics=CallMetrics(tokens, elapsed))

    def evaluator(self, example: QAExample, answer: str) -> JudgeCall:
        started = time.perf_counter()
        if normalize_answer(example.gold_answer) == normalize_answer(answer):
            result = JudgeResult(
                score=1,
                reason="Final answer matches the gold answer after normalization.",
                failure_mode="none",
            )
        elif (example.mock_failure_mode or FAILURE_MODE_BY_QID.get(example.qid)) == "incomplete_multi_hop":
            result = JudgeResult(
                score=0,
                reason="The answer stopped at an intermediate entity and did not complete the final hop.",
                missing_evidence=["Follow the intermediate entity into the next context paragraph."],
                failure_mode="incomplete_multi_hop",
            )
        else:
            result = JudgeResult(
                score=0,
                reason="The final answer selected an unsupported second-hop entity.",
                missing_evidence=["Ground the final entity in the second context paragraph."],
                spurious_claims=[answer],
                failure_mode=example.mock_failure_mode
                or FAILURE_MODE_BY_QID.get(example.qid, "wrong_final_answer"),
            )
        tokens = _rough_token_count(
            EVALUATOR_SYSTEM,
            example.question,
            example.gold_answer,
            answer,
            result.model_dump_json(),
        )
        elapsed = max(1, round((time.perf_counter() - started) * 1000))
        return JudgeCall(result=result, metrics=CallMetrics(tokens, elapsed))

    def reflector(
        self,
        example: QAExample,
        attempt_id: int,
        answer: str,
        judge: JudgeResult,
    ) -> ReflectionCall:
        started = time.perf_counter()
        strategy = (
            "Resolve the birthplace, then find the river through that city."
            if example.qid == "hp2"
            else "Trace every hop and verify the final entity against the last supporting paragraph."
        )
        entry = ReflectionEntry(
            attempt_id=attempt_id,
            failure_reason=judge.reason,
            lesson="A plausible first-hop or related entity is not enough; every requested hop must be completed.",
            next_strategy=strategy,
        )
        tokens = _rough_token_count(
            REFLECTOR_SYSTEM,
            example.question,
            answer,
            judge.model_dump_json(),
            entry.model_dump_json(),
        )
        elapsed = max(1, round((time.perf_counter() - started) * 1000))
        return ReflectionCall(entry=entry, metrics=CallMetrics(tokens, elapsed))


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError(f"LLM did not return JSON: {text[:200]!r}") from None
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("LLM JSON response must be an object.")
    return value


class LLMRuntime:
    """Calls either OpenAI-compatible chat completions or Ollama."""

    mode = "llm"

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
        self.model = model or os.getenv("LLM_MODEL", "qwen2.5:7b")
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.timeout_seconds = timeout_seconds or int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
        if self.provider == "ollama":
            self.base_url = (base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434")).rstrip("/")
        elif self.provider in {"openai", "openai_compatible"}:
            self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
            if not self.api_key:
                raise ValueError("LLM_API_KEY or OPENAI_API_KEY is required for OpenAI mode.")
        else:
            raise ValueError("LLM_PROVIDER must be 'ollama', 'openai', or 'openai_compatible'.")

    def _chat(self, system: str, user: str) -> tuple[str, CallMetrics]:
        if self.provider == "ollama":
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "stream": False,
                "format": "json",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            headers = {"Content-Type": "application/json"}
        else:
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            if self.provider == "openai":
                payload["response_format"] = {"type": "json_object"}
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP {exc.code}: {details[:500]}") from exc
        except URLError as exc:
            raise RuntimeError(
                f"Cannot connect to LLM provider at {url}. Check .env and whether the server is running."
            ) from exc
        latency_ms = max(1, round((time.perf_counter() - started) * 1000))

        if self.provider == "ollama":
            content = body["message"]["content"]
            tokens = int(body.get("prompt_eval_count", 0)) + int(body.get("eval_count", 0))
        else:
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
            tokens = int(usage.get("total_tokens", 0))
        return content, CallMetrics(tokens=tokens, latency_ms=latency_ms)

    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> ActorCall:
        memory = "\n".join(f"- {item}" for item in reflection_memory) or "(none)"
        user = (
            f"Question: {example.question}\n\n"
            f"Context:\n{_context_text(example)}\n\n"
            f"Attempt: {attempt_id}\nAgent type: {agent_type}\n"
            f"Reflection memory:\n{memory}"
        )
        content, metrics = self._chat(ACTOR_SYSTEM, user)
        answer = str(_extract_json(content).get("answer", "")).strip()
        if not answer:
            raise ValueError("Actor returned an empty answer.")
        return ActorCall(answer=answer, metrics=metrics)

    def evaluator(self, example: QAExample, answer: str) -> JudgeCall:
        user = (
            f"Question: {example.question}\n\n"
            f"Context:\n{_context_text(example)}\n\n"
            f"Gold answer: {example.gold_answer}\nPredicted answer: {answer}"
        )
        content, metrics = self._chat(EVALUATOR_SYSTEM, user)
        return JudgeCall(
            result=JudgeResult.model_validate(_extract_json(content)),
            metrics=metrics,
        )

    def reflector(
        self,
        example: QAExample,
        attempt_id: int,
        answer: str,
        judge: JudgeResult,
    ) -> ReflectionCall:
        user = (
            f"Question: {example.question}\n\n"
            f"Context:\n{_context_text(example)}\n\n"
            f"Attempt ID: {attempt_id}\nWrong answer: {answer}\n"
            f"Evaluator result: {judge.model_dump_json()}"
        )
        content, metrics = self._chat(REFLECTOR_SYSTEM, user)
        payload = _extract_json(content)
        payload["attempt_id"] = attempt_id
        return ReflectionCall(
            entry=ReflectionEntry.model_validate(payload),
            metrics=metrics,
        )


def create_runtime(mode: str = "mock") -> Runtime:
    if mode == "mock":
        return MockRuntime()
    if mode == "llm":
        return LLMRuntime()
    raise ValueError("mode must be 'mock' or 'llm'")


# Backwards-compatible helpers for the original scaffold API.
_DEFAULT_MOCK = MockRuntime()


def actor_answer(
    example: QAExample,
    attempt_id: int,
    agent_type: str,
    reflection_memory: list[str],
) -> str:
    return _DEFAULT_MOCK.actor_answer(example, attempt_id, agent_type, reflection_memory).answer


def evaluator(example: QAExample, answer: str) -> JudgeResult:
    return _DEFAULT_MOCK.evaluator(example, answer).result


def reflector(example: QAExample, attempt_id: int, judge: JudgeResult) -> ReflectionEntry:
    return _DEFAULT_MOCK.reflector(example, attempt_id, "", judge).entry
