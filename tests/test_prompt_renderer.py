"""Tests for PromptRenderer."""

from plastic_agent_net.core.models import AgentTemplate, NodeState, PersonaVector
from plastic_agent_net.prompts.renderer import PromptRenderer


def test_render_basic():
    renderer = PromptRenderer()
    node = NodeState(template=AgentTemplate.CODER)

    system, messages = renderer.render(
        node=node,
        task_summary="Fix the bug in utils.py",
    )

    assert "coding agent" in system.lower()
    assert "JSON" in system
    assert len(messages) == 1
    assert "Fix the bug" in messages[0]["content"]


def test_render_with_persona():
    renderer = PromptRenderer()
    node = NodeState(
        template=AgentTemplate.SKEPTIC_REVIEWER,
        persona=PersonaVector(caution=0.9, skepticism=0.9),
    )

    system, messages = renderer.render(
        node=node,
        task_summary="Review patch",
    )

    assert "skeptical" in system.lower() or "cautious" in system.lower()


def test_render_with_artifacts():
    renderer = PromptRenderer()
    node = NodeState(template=AgentTemplate.CODER)

    _, messages = renderer.render(
        node=node,
        task_summary="Fix bug",
        artifact_summaries=[
            {"type": "plan", "producer": "planner1", "summary": "Do X", "round": 0},
        ],
    )

    assert "Artifacts" in messages[0]["content"]
    assert "Do X" in messages[0]["content"]


def test_render_with_tool_outputs():
    renderer = PromptRenderer()
    node = NodeState(template=AgentTemplate.VERIFIER_COORDINATOR)

    _, messages = renderer.render(
        node=node,
        task_summary="Verify branch",
        tool_outputs=[{"tool": "test", "output": "3 passed, 0 failed"}],
    )

    assert "Tool Outputs" in messages[0]["content"]
    assert "3 passed" in messages[0]["content"]


def test_render_with_messages():
    renderer = PromptRenderer()
    node = NodeState(template=AgentTemplate.CODER)

    _, messages = renderer.render(
        node=node,
        task_summary="Code fix",
        messages=[{"type": "feedback", "sender": "reviewer1", "payload": "Looks wrong"}],
    )

    assert "Messages" in messages[0]["content"]
    assert "Looks wrong" in messages[0]["content"]


def test_render_includes_output_schema():
    renderer = PromptRenderer()
    node = NodeState(template=AgentTemplate.PLANNER)

    system, _ = renderer.render(node=node, task_summary="Plan task")

    assert "sub_tasks" in system
    assert "strategy" in system
