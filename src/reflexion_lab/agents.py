from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .mock_runtime import MockRuntime, Runtime
from .schemas import AttemptTrace, FailureMode, QAExample, ReflectionEntry, RunRecord


def _memory_line(reflection: ReflectionEntry) -> str:
    return f"Lesson: {reflection.lesson} Next strategy: {reflection.next_strategy}"


@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1
    runtime: Runtime = field(default_factory=MockRuntime)
    memory_limit: int = 5

    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0
        final_failure_mode: FailureMode = "wrong_final_answer"

        for attempt_id in range(1, self.max_attempts + 1):
            actor_call = self.runtime.actor_answer(
                example,
                attempt_id,
                self.agent_type,
                reflection_memory,
            )
            judge_call = self.runtime.evaluator(example, actor_call.answer)
            judge = judge_call.result
            token_count = actor_call.metrics.tokens + judge_call.metrics.tokens
            latency_ms = actor_call.metrics.latency_ms + judge_call.metrics.latency_ms

            final_answer = actor_call.answer
            final_score = judge.score
            final_failure_mode = judge.failure_mode

            reflection: ReflectionEntry | None = None
            if judge.score == 0 and self.agent_type == "reflexion" and attempt_id < self.max_attempts:
                reflection_call = self.runtime.reflector(
                    example,
                    attempt_id,
                    actor_call.answer,
                    judge,
                )
                reflection = reflection_call.entry
                reflections.append(reflection)
                reflection_memory.append(_memory_line(reflection))
                reflection_memory = reflection_memory[-self.memory_limit :]
                token_count += reflection_call.metrics.tokens
                latency_ms += reflection_call.metrics.latency_ms

            traces.append(
                AttemptTrace(
                    attempt_id=attempt_id,
                    answer=actor_call.answer,
                    score=judge.score,
                    reason=judge.reason,
                    reflection=reflection,
                    token_estimate=token_count,
                    latency_ms=latency_ms,
                )
            )
            if judge.score == 1:
                break

        return RunRecord(
            qid=example.qid,
            question=example.question,
            gold_answer=example.gold_answer,
            agent_type=self.agent_type,
            predicted_answer=final_answer,
            is_correct=bool(final_score),
            attempts=len(traces),
            token_estimate=sum(t.token_estimate for t in traces),
            latency_ms=sum(t.latency_ms for t in traces),
            failure_mode="none" if final_score == 1 else final_failure_mode,
            reflections=reflections,
            traces=traces,
        )


class ReActAgent(BaseAgent):
    def __init__(self, runtime: Runtime | None = None) -> None:
        super().__init__(
            agent_type="react",
            max_attempts=1,
            runtime=runtime or MockRuntime(),
        )


class ReflexionAgent(BaseAgent):
    def __init__(
        self,
        max_attempts: int = 3,
        runtime: Runtime | None = None,
        memory_limit: int = 5,
    ) -> None:
        super().__init__(
            agent_type="reflexion",
            max_attempts=max_attempts,
            runtime=runtime or MockRuntime(),
            memory_limit=memory_limit,
        )
