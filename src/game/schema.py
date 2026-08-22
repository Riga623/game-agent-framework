"""Shared message shapes passed between the agent language and the LLM provider.

Split into their own module (rather than living in `language.py` or
`llm.py`) purely to avoid a circular import: the agent language needs to
describe what it hands to a provider (`Prompt`) and what it expects back
(`LLMResponse`), and providers need those same two shapes — so neither
module can own them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Prompt:
    """Everything an LLM provider needs to produce the agent's next decision.

    `system` carries the formatted goals, `messages` is the memory
    formatted as a conversation, and `tools` is the action registry
    formatted as JSON-schema tool definitions (the same shape regardless of
    which provider ultimately consumes it — each provider adapts this
    generic shape to its own API on the way out).
    """

    system: str
    messages: list[dict]
    tools: list[dict]


@dataclass
class LLMResponse:
    """A provider's answer, normalized to a shape the rest of the framework understands.

    `tool_name`/`args` are set when the model chose to call a tool;
    `text` carries any plain-text portion of the response (present even
    alongside a tool call, and the *only* thing set if the model replied
    without calling a tool at all — which `AgentLanguage.parse_response`
    treats as a recoverable error, not a crash). `raw` keeps the original,
    provider-specific response object around for debugging.
    """

    tool_name: str | None = None
    args: dict = field(default_factory=dict)
    text: str | None = None
    raw: Any = None
