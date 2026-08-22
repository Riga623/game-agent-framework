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
    assert "tool_executed" in messages[2]["content"]  # non-str content is stringified


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
