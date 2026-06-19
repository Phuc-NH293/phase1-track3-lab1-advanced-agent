from src.reflexion_lab.agents import ReActAgent, ReflexionAgent
from src.reflexion_lab.mock_runtime import MockRuntime, _extract_json
from src.reflexion_lab.reporting import build_report
from src.reflexion_lab.schemas import QAExample


def example() -> QAExample:
    return QAExample.model_validate(
        {
            "qid": "custom_test",
            "difficulty": "medium",
            "question": "What river flows through Ada Lovelace's birthplace?",
            "gold_answer": "River Thames",
            "context": [
                {"title": "Ada", "text": "Ada Lovelace was born in London."},
                {"title": "London", "text": "The River Thames flows through London."},
            ],
            "mock_wrong_answer": "London",
            "mock_failure_mode": "incomplete_multi_hop",
        }
    )


def test_reflexion_uses_memory_and_recovers() -> None:
    row = example()
    react = ReActAgent(runtime=MockRuntime()).run(row)
    reflexion = ReflexionAgent(runtime=MockRuntime()).run(row)
    assert react.is_correct is False
    assert reflexion.is_correct is True
    assert reflexion.attempts == 2
    assert len(reflexion.reflections) == 1
    assert reflexion.token_estimate > react.token_estimate


def test_report_has_required_analysis_sections() -> None:
    row = example()
    records = [
        ReActAgent(runtime=MockRuntime()).run(row),
        ReflexionAgent(runtime=MockRuntime()).run(row),
    ]
    report = build_report(records, "test.json")
    assert len(report.failure_modes) >= 3
    assert len(report.discussion) >= 250
    assert "reflection_memory" in report.extensions


def test_extract_json_accepts_markdown_fence() -> None:
    assert _extract_json('```json\n{"answer": "Paris"}\n```') == {"answer": "Paris"}
