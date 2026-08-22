"""Turn (goals, memory, actions) into a prompt, and a model's reply back into a decision.

This is the piece of the framework most worth experimenting with in a
simulated conversation before writing code (see docs/DESIGN_NOTES.md,
"Simulate before you implement") — how goals are phrased, how much context
memory entries carry, and how actions are described all materially change
how well a model can decide what to do next.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .core import Action, Goal, Memory
from .schema import LLMResponse, Prompt

# Memory entries use a "type" field with these conventional values.
# "user" / "assistant" map directly to chat roles; "environment" is *our*
# addition, covering both a) the result of executing an action and b) a
# parse-failure error — both are just "here's what happened when you tried
# that" data telling the model what to do next.
_MEMORY_TYPE_TO_ROLE = {
    "user": "user",
    "assistant": "assistant",
    "environment": "user",
}


class ParseError(Exception):
    """A model's response couldn't be turned into a valid, runnable action.

    Two situations raise this: the response didn't call any tool at all, or
    it called a tool name that isn't registered. Both carry a `feedback`
    message written to be fed straight back into memory as environment
    feedback, so the agent gets a chance to self-correct on the next loop
    iteration instead of the run crashing outright — mirroring how a rich,
    specific error message (rather than a bare error code) let the
    microwave example recover in the source material.
    """

    def __init__(self, feedback: str):
        super().__init__(feedback)
        self.feedback = feedback


class AgentLanguage(ABC):
    """How an Agent talks to a model: prompt construction and response parsing.

    Swapping this is how you change *how* the agent communicates (plain
    text with a required JSON blob, vs. native function/tool calling)
    without touching the agent loop, the goals, or the actions.
    """

    @abstractmethod
    def construct_prompt(
        self, goals: list[Goal], memory: Memory, actions: list[Action]
    ) -> Prompt: ...

    @abstractmethod
    def parse_response(self, response: LLMResponse) -> dict:
        """Return {"tool": str, "args": dict}, or raise ParseError."""
        ...


class AgentFunctionCallingActionLanguage(AgentLanguage):
    """Uses the model's native tool/function-calling support.

    This is the language used by every example agent in this repo: goals
    become the system prompt, actions become tool definitions, and a
    provider's job is to map its own tool-call representation onto the
    LLMResponse.tool_name/args fields so parsing here stays provider-agnostic.
    """

    def format_goals(self, goals: list[Goal]) -> str:
        ordered = sorted(goals, key=lambda g: g.priority)
        sections = [
            f"# {goal.name} (priority {goal.priority})\n{goal.description}" for goal in ordered
        ]
        return "\n\n".join(sections)

    def format_actions(self, actions: list[Action]) -> list[dict]:
        return [
            {
                "name": action.name,
                "description": action.description,
                "input_schema": action.parameters,
            }
            for action in actions
        ]

    def format_memory(self, memory: Memory) -> list[dict]:
        messages = []
        for item in memory.get_memories():
            role = _MEMORY_TYPE_TO_ROLE.get(item["type"], "user")
            content = item["content"]
            if not isinstance(content, str):
                content = str(content)
            messages.append({"role": role, "content": content})
        return messages

    def construct_prompt(self, goals: list[Goal], memory: Memory, actions: list[Action]) -> Prompt:
        return Prompt(
            system=self.format_goals(goals),
            messages=self.format_memory(memory),
            tools=self.format_actions(actions),
        )

    def parse_response(self, response: LLMResponse) -> dict:
        if not response.tool_name:
            raise ParseError(
                "Your last response didn't call a tool. Every response must "
                "call exactly one of the available tools with valid "
                "arguments — plain text alone can't be executed."
                + (f" You said: {response.text!r}" if response.text else "")
            )
        return {"tool": response.tool_name, "args": response.args}
