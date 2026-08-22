import pytest

from game.core import Action, Goal, Memory
from game.language import AgentFunctionCallingActionLanguage, ParseError
from game.schema import LLMResponse


def make_action(name="read_file", terminal=False):
    return Action(
        name=name,
        function=lambda **kwargs: kwargs,
        description="Reads a file.",
        parameters={
            "type": "object",
            "properties": {"file_name": {"type": "string"}},
            "required": ["file_name"],
        },
        terminal=terminal,
    )


def test_format_goals_orders_by_priority():
    lang = AgentFunctionCallingActionLanguage()
    goals = [
        Goal(priority=2, name="Second", description="do second"),
        Goal(priority=1, name="First", description="do first"),
    ]
    formatted = lang.format_goals(goals)
    assert formatted.index("First") < formatted.index("Second")


def test_format_actions_produces_tool_schema():
    lang = AgentFunctionCallingActionLanguage()
    tools = lang.format_actions([make_action()])
    assert tools == [
        {
            "name": "read_file",
            "description": "Reads a file.",
            "input_schema": {
                "type": "object",
                "properties": {"file_name": {"type": "string"}},
                "required": ["file_name"],
            },
        }
    ]


def test_format_memory_maps_types_to_roles():
    lang = AgentFunctionCallingActionLanguage()
    memory = Memory()
    memory.add_memory({"type": "user", "content": "hi"})
    memory.add_memory({"type": "assistant", "content": "calling read_file"})
    memory.add_memory({"type": "environment", "content": {"tool_executed": True, "result": "ok"}})

    messages = lang.format_memory(memory)
    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant", "user"]  # environment feedback comes back as "user"
    # non-str content is JSON-encoded (not Python repr'd) so it's valid JSON
    assert messages[2]["content"] == '{"tool_executed": true, "result": "ok"}'


def test_construct_prompt_combines_goals_memory_and_actions():
    lang = AgentFunctionCallingActionLanguage()
    goals = [Goal(priority=1, name="Explore", description="explore files")]
    memory = Memory()
    memory.add_memory({"type": "user", "content": "start"})

    prompt = lang.construct_prompt(goals, memory, [make_action()])

    assert "Explore" in prompt.system
    assert prompt.messages == [{"role": "user", "content": "start"}]
    assert prompt.tools[0]["name"] == "read_file"


def test_parse_response_returns_tool_and_args():
    lang = AgentFunctionCallingActionLanguage()
    response = LLMResponse(tool_name="read_file", args={"file_name": "a.txt"})

    decision = lang.parse_response(response)
    assert decision == {"tool": "read_file", "args": {"file_name": "a.txt"}}


def test_parse_response_raises_parse_error_when_no_tool_called():
    lang = AgentFunctionCallingActionLanguage()
    response = LLMResponse(tool_name=None, text="I think you should read the file.")

    with pytest.raises(ParseError) as exc_info:
        lang.parse_response(response)

    # The error message is meant to be fed back to the model, so it should
    # be specific enough to act on, not a bare "invalid response".
    assert "tool" in exc_info.value.feedback.lower()


def test_parse_response_raises_parse_error_on_multiple_tool_calls():
    """This one-action-per-iteration loop can't run two tool calls from a
    single turn — extra_tool_calls must produce a specific, recoverable
    error, not be silently ignored (see the AnthropicProvider regression
    test in tests/test_llm.py for where this data actually comes from)."""
    lang = AgentFunctionCallingActionLanguage()
    response = LLMResponse(
        tool_name="read_file",
        args={"file_name": "a.txt"},
        extra_tool_calls=[("list_files", {})],
    )

    with pytest.raises(ParseError) as exc_info:
        lang.parse_response(response)

    assert "read_file" in exc_info.value.feedback
    assert "list_files" in exc_info.value.feedback
    assert "one action per step" in exc_info.value.feedback


def test_parse_response_raises_parse_error_on_truncated_response():
    lang = AgentFunctionCallingActionLanguage()
    response = LLMResponse(tool_name="read_file", args={}, truncated=True)

    with pytest.raises(ParseError) as exc_info:
        lang.parse_response(response)

    assert "cut off" in exc_info.value.feedback.lower()
