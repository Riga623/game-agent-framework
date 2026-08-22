"""Pluggable model backends: a Prompt goes in, a normalized LLMResponse comes out.

A `generate_response` is just `Callable[[Prompt], LLMResponse]`. That's the
entire contract an Agent depends on, which is what makes it possible to
develop and test the rest of the framework — goals, actions, the loop
itself — without ever calling a real model or holding an API key.

Two providers ship here:

  * ScriptedProvider — returns pre-recorded responses in order. This is the
    coded equivalent of the "simulate the agent in a chat conversation"
    technique from the source material: instead of a human typing back
    fake tool results, a test (or a demo with no API key) scripts the
    model's side too, so the whole loop runs deterministically offline.

  * AnthropicProvider — talks to a real Claude model via the `anthropic`
    package (an optional dependency; install the `anthropic` extra). Reads
    its API key from the ANTHROPIC_API_KEY environment variable — never
    hardcode a key here or pass one as a literal.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from .schema import LLMResponse, Prompt

GenerateResponse = Callable[[Prompt], LLMResponse]


class ScriptedProvider:
    """Replays a fixed list of LLMResponses, one per call, in order.

    Raises a clear RuntimeError (not a confusing IndexError) if the agent
    asks for more decisions than were scripted — that usually means the
    real loop took an extra turn you didn't account for (e.g. a retry after
    a parse error), which is itself useful information while designing an
    agent.
    """

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self._next = 0

    def __call__(self, prompt: Prompt) -> LLMResponse:
        if self._next >= len(self._responses):
            raise RuntimeError(
                f"ScriptedProvider ran out of responses after {self._next} call(s). "
                "The agent asked for another decision than you scripted for — "
                "add another LLMResponse to the script, or check whether an "
                "unexpected retry (e.g. after a ParseError) consumed one."
            )
        response = self._responses[self._next]
        self._next += 1
        return response

    @property
    def calls_made(self) -> int:
        return self._next


def response_from_anthropic_message(message) -> LLMResponse:
    """Map an Anthropic SDK `Message` onto our provider-agnostic `LLMResponse`.

    Split out from `AnthropicProvider.__call__` specifically so this logic
    — the one piece of the framework that actually has to match a real
    external API's response shape — is unit-testable on its own, with a
    lightweight fake `message` object, without needing the `anthropic`
    package installed, an API key, or a network call. See
    `tests/test_llm.py`.

    Two things this function is careful not to get wrong:

    * If the model calls more than one tool in a single turn (Claude
      supports parallel tool use), every call is captured — the first in
      `tool_name`/`args`, the rest in `extra_tool_calls` — rather than
      silently keeping only the last one and dropping the others.
    * `message.stop_reason == "max_tokens"` sets `truncated=True`, so a
      tool call parsed out of a cut-off response is flagged as unreliable
      rather than executed as if it were complete.
    """
    tool_calls: list[tuple[str, dict]] = []
    text_parts: list[str] = []

    for block in message.content:
        if block.type == "tool_use":
            tool_calls.append((block.name, block.input))
        elif block.type == "text":
            text_parts.append(block.text)

    tool_name, args = tool_calls[0] if tool_calls else (None, {})

    return LLMResponse(
        tool_name=tool_name,
        args=args,
        text="\n".join(text_parts) or None,
        raw=message,
        extra_tool_calls=tool_calls[1:],
        truncated=getattr(message, "stop_reason", None) == "max_tokens",
    )


class AnthropicProvider:
    """Calls a real Claude model via the `anthropic` package.

    Usage:

        provider = AnthropicProvider(model="claude-sonnet-4-5")
        agent = Agent(..., generate_response=provider)

    The API key is read from the ANTHROPIC_API_KEY environment variable
    (see .env.example) — this class never accepts a key as a literal
    argument, so there's no code path that could accidentally end up with
    one hardcoded.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        max_tokens: int = 1024,
        timeout: float = 60.0,
    ):
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "AnthropicProvider requires the 'anthropic' package. "
                "Install it with: pip install 'game-agent-framework[anthropic]'"
            ) from e

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and "
                "fill in your own key, or export it in your shell. "
                "(Every example and test in this repo can also run with no "
                "key at all via ScriptedProvider — see README.md.)"
            )

        # A finite default timeout matters here specifically because this
        # call sits inside Agent.run()'s loop: a client with no timeout that
        # hangs on a stalled connection hangs the entire agent, silently,
        # with no way for a caller to notice something's wrong.
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens

    def __call__(self, prompt: Prompt) -> LLMResponse:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=prompt.system,
            messages=prompt.messages,
            tools=prompt.tools,
        )
        return response_from_anthropic_message(message)
