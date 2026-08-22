"""The G, A, M, and E pieces: Goal, Action/ActionRegistry, Memory, Environment.

These four classes are deliberately small. Each one wraps something that
used to be an ad-hoc list, dict, or if/else chain in a naive agent
implementation, so that the rest of the framework (the agent loop, the
prompt-construction logic) can depend on a stable interface instead of on
how any particular agent happens to store its state. See
docs/DESIGN_NOTES.md for why each of these exists as its own class rather
than a plain data structure.
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Goal:
    """Something the agent is trying to achieve, or how it should go about it.

    "Goal" is used loosely here: some goals describe an outcome ("explore
    the files in this directory"), others describe process or house rules
    ("terminate with a helpful summary when done"), and others can encode
    worked examples of how to reason through a tricky situation. Wrapping
    goals as objects instead of one long instructions string lets us give
    each one a priority, so the prompt-construction logic can decide which
    goals to foreground and how to order them.
    """

    priority: int
    name: str
    description: str


class Action:
    """One thing the agent is allowed to do, described the way a model needs it.

    An Action bundles four things a naive implementation tends to let drift
    out of sync with each other: the callable that actually does the work,
    the name the model will refer to it by, the natural-language description
    that tells the model when and how to use it, and the JSON schema for its
    arguments. Keeping these four together in one object is what makes it
    possible to swap an agent's toolkit without touching the agent loop.

    `terminal=True` marks an action that ends the agent's run (e.g.
    `terminate`) once executed.
    """

    def __init__(
        self,
        name: str,
        function: Callable,
        description: str,
        parameters: dict,
        terminal: bool = False,
    ):
        self.name = name
        self.function = function
        self.description = description
        self.terminal = terminal
        self.parameters = parameters

    def execute(self, **args) -> Any:
        """Execute the action's underlying function with the given arguments."""
        return self.function(**args)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Action(name={self.name!r}, terminal={self.terminal!r})"


class ActionRegistry:
    """Looks up an Action object by the name the model used to refer to it.

    When the model responds, it names an action rather than handing us a
    Python object. The registry is the bridge between "the model said
    'read_file'" and the actual Action instance (and therefore the actual
    function) that name maps to.
    """

    def __init__(self):
        self.actions: dict[str, Action] = {}

    def register(self, action: Action) -> None:
        self.actions[action.name] = action

    def get_action(self, name: str) -> Action | None:
        return self.actions.get(name)

    def get_actions(self) -> list[Action]:
        """Return all registered actions, e.g. to build the model's tool list."""
        return list(self.actions.values())

    def __contains__(self, name: str) -> bool:
        return name in self.actions


class Memory:
    """The agent's record of what's happened so far in this run.

    Structurally this is just a list of `{"type": ..., "content": ...}`
    entries (user input, assistant decisions, environment feedback) — the
    same shape as a chat conversation, because that's exactly what gets fed
    back into the model at each loop iteration. It's wrapped in a class
    rather than left as a bare list so that a subclass can later change
    *how* memory is stored (a database, a summarized/truncated window, a
    priority-ranked subset) without changing how the agent loop reads from
    it: get_memories() always returns a plain list of message-shaped dicts.
    """

    def __init__(self):
        self.items: list[dict] = []

    def add_memory(self, memory: dict) -> None:
        """Add one memory entry. Expected shape: {"type": str, "content": Any}."""
        self.items.append(memory)

    def get_memories(self, limit: int | None = None) -> list[dict]:
        """Return the conversation history, formatted for use in a prompt."""
        return self.items[:limit]

    def __len__(self) -> int:
        return len(self.items)


class Environment:
    """Executes an Action and turns whatever happens into structured feedback.

    The agent never touches the outside world directly — every side effect
    goes through here. That indirection is what lets the same Goals/Actions
    definition run against different real-world backends (local filesystem
    today, a cloud API tomorrow) without changing anything else, and it's
    what turns a raised exception into the kind of clear, structured error
    message the model actually needs in order to recover (see
    docs/DESIGN_NOTES.md, "Feedback quality").
    """

    def execute_action(self, action: Action, args: dict) -> dict:
        """Execute an action and return a structured result, never raising."""
        try:
            result = action.execute(**args)
            return self.format_result(result)
        except Exception as e:
            return {
                "tool_executed": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }

    def format_result(self, result: Any) -> dict:
        """Wrap a successful result with the metadata the agent loop expects."""
        return {
            "tool_executed": True,
            "result": result,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
