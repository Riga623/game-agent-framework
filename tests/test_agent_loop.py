"""End-to-end tests of the six-step agent loop, using ScriptedProvider so
nothing here touches the network or needs an API key.
"""

from game.agent import Agent
from game.core import Action, ActionRegistry, Environment, Goal
from game.language import AgentFunctionCallingActionLanguage
from game.llm import ScriptedProvider
from game.schema import LLMResponse

GOALS = [Goal(priority=1, name="Echo", description="Echo the user's input back, then terminate.")]


def build_registry() -> ActionRegistry:
    registry = ActionRegistry()
    registry.register(
        Action(
            name="echo",
            function=lambda text: text,
            description="Echoes text back.",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )
    )
    registry.register(
        Action(
            name="terminate",
            function=lambda message: message,
            description="Ends the run.",
            parameters={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            terminal=True,
        )
    )
    return registry


def build_agent(provider) -> Agent:
    return Agent(
        goals=GOALS,
        agent_language=AgentFunctionCallingActionLanguage(),
        action_registry=build_registry(),
        generate_response=provider,
        environment=Environment(),
    )


def test_agent_runs_until_terminal_action():
    provider = ScriptedProvider(
        [
            LLMResponse(tool_name="echo", args={"text": "hi"}),
            LLMResponse(tool_name="terminate", args={"message": "done"}),
        ]
    )
    agent = build_agent(provider)

    memory = agent.run("say hi", max_iterations=10)

    types = [m["type"] for m in memory.get_memories()]
    assert types == ["user", "assistant", "environment", "assistant", "environment"]
    assert provider.calls_made == 2  # stopped as soon as the terminal action ran


def test_agent_stops_at_max_iterations_even_without_terminal_action():
    provider = ScriptedProvider(
        [
            LLMResponse(tool_name="echo", args={"text": "1"}),
            LLMResponse(tool_name="echo", args={"text": "2"}),
        ]
    )
    agent = build_agent(provider)

    agent.run("loop forever", max_iterations=2)

    assert provider.calls_made == 2  # capped, not runaway


def test_agent_recovers_from_a_response_with_no_tool_call():
    """A parse failure shouldn't crash the run — it should be fed back as
    environment feedback, and the agent should get another turn to recover."""
    provider = ScriptedProvider(
        [
            LLMResponse(tool_name=None, text="I'm thinking about it..."),
            LLMResponse(tool_name="terminate", args={"message": "done"}),
        ]
    )
    agent = build_agent(provider)

    memory = agent.run("say hi", max_iterations=10)
    memories = memory.get_memories()

    # The malformed reply and the resulting error feedback are both recorded...
    assert any("Error:" in str(m["content"]) for m in memories if m["type"] == "environment")
    # ...and the agent still reached the terminal action on its next turn.
    assert memories[-2]["content"].startswith("Calling terminate")


def test_agent_recovers_from_an_unknown_tool_name():
    provider = ScriptedProvider(
        [
            LLMResponse(tool_name="fly_to_the_moon", args={}),
            LLMResponse(tool_name="terminate", args={"message": "done"}),
        ]
    )
    agent = build_agent(provider)

    memory = agent.run("do something", max_iterations=10)
    feedback = [m["content"] for m in memory.get_memories() if m["type"] == "environment"]

    assert any("no tool named 'fly_to_the_moon'" in str(f) for f in feedback)
