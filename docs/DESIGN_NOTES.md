# Design Notes

This document exists so a reviewer doesn't have to reverse-engineer *why*
the code looks the way it does. Each section names a lesson and points at
exactly where in the code it shows up.

## The loop is the whole idea

An agent is an automated conversation: construct a prompt, get a response,
turn the response into an action, execute it, feed the result back as the
next prompt, repeat. `Agent.run()` in `src/game/agent.py` is a direct
implementation of that six-step loop, and the method itself is
deliberately kept under 50 lines. Every other file in this package exists
to hand that loop clean,
well-defined inputs (`Goal`, `Action`, `Memory`, `Environment`,
`AgentLanguage`) so the loop itself never needs agent-specific
conditional logic. Building a new agent means writing new goals and
actions, not touching `agent.py`.

## Tool naming and description are not cosmetic

A model has no institutional knowledge of what `mkpz` or `x155` means —
only what you tell it, or what a genuinely descriptive name implies on its
own. Two things follow directly in this codebase:

* Every `Action` requires both a `name` and a `description` — there's no
  code path that registers a tool with only one or the other.
* `tools.py`'s `@register_tool` decorator pulls the description straight
  from the function's docstring and the name from the function itself,
  which is a stronger guarantee than "please remember to write a good
  description": the description *is* the docstring, so a vague docstring
  is immediately visible as a vague tool description, and a renamed
  function automatically renames the tool.

The framework doesn't stop you from registering a badly-named, badly
described tool — nothing could enforce that generally — but it makes the
well-described path the path of least resistance.

## Feedback quality is what lets an agent recover

Rich, specific error messages let a model self-correct; opaque ones (a bare
error code, a stack trace with no explanation) leave it stuck. Two
mechanisms in this codebase exist specifically for this:

* `Environment.execute_action()` (`src/game/core.py`) never lets an exception
  propagate out of a tool call. It always returns a structured result —
  `{"tool_executed": False, "error": ..., "traceback": ...}` on failure —
  so a broken tool call becomes information the agent can act on, not a
  crashed process.
* `ParseError` (`src/game/language.py`) plays the same role one level up, for
  when the *model's response itself* can't be turned into a valid action —
  either because it didn't call a tool at all, or called one that isn't
  registered. Both cases raise a `ParseError` carrying a specific,
  actionable `feedback` string ("There is no tool named 'X'. Available
  tools are: ..." rather than "invalid response"), which `Agent.run()`
  writes into memory as environment feedback and then gives the agent
  another turn to recover from. `tests/test_agent_loop.py::
  test_agent_recovers_from_a_response_with_no_tool_call` and
  `test_agent_recovers_from_an_unknown_tool_name` exercise exactly this
  path.

## Why a decorator for tool registration

Registering an `Action` by hand means the name, description, and parameter
schema live in a second place, separate from the function they describe —
and in practice that second place drifts out of sync with the first the
moment someone adds a parameter and forgets to update the schema.
`@register_tool` (`src/game/tools.py`) removes the second place: it introspects
the decorated function's signature (via `inspect` and `typing.
get_type_hints`) and docstring at decoration time, so the function is the
only thing you ever have to edit. `readme_agent.py` uses this style;
`file_explorer.py` deliberately still registers `Action` objects by hand,
so the two examples sit side by side as a real comparison rather than a
claim taken on faith.

## Why goals are objects, not one instructions string

A single long "here's everything you need to know" string is hard to
reason about, hard to reorder, and hard to combine from reusable pieces.
`Goal` (`src/game/core.py`) is a small frozen dataclass with a `priority`, so
`AgentFunctionCallingActionLanguage.format_goals()` can sort goals before
rendering them into the system prompt — which matters once an agent has
several goals that aren't all equally important (e.g. "explore the files"
vs. "terminate with a summary when done").

## Why Memory and Environment are classes, not a list and a function

`Memory` is structurally just a list of `{"type", "content"}` dicts today
— but wrapping it in a class means a later version could change *how*
history is stored (truncated to the last N entries, summarized, pulled
from a database) without changing the one method (`get_memories()`) the
rest of the framework depends on.

`Environment` plays a similar role for the *executing* side: today it just
calls `action.execute(**args)` inside a try/except, but every action in
the system is executed through this one chokepoint. That's what would let
a future version add things like per-action timeouts, retries, or logging
in exactly one place instead of every tool function.

## Simulate before you implement

Before writing any of this code, the fastest way to find a broken agent
design is a plain chat conversation: state the goals and actions to a
model, tell it you'll type back the result of each action as its next
message, and watch what it does. This surfaces problems — an action that
implicitly depends on state you never gave the agent, a goal that's
ambiguous about what "done" means — in minutes instead of after a full
implementation.

`llm.py`'s `ScriptedProvider` is that same idea, formalized: it's a
`generate_response` callable that plays back a fixed list of `LLMResponse`
objects instead of calling a real model, so both example agents' demo mode
and the entire test suite exercise the real `Agent.run()` loop completely
offline. It's the same technique — a stand-in for the model, so you can
control exactly what it does — just captured as code instead of a chat
transcript.

## What isn't handled (yet)

Kept out of scope, on purpose, to keep this implementation legible:

* **No automatic memory truncation.** `Memory.get_memories()` returns
  everything unless a caller passes `limit=`. A long-running agent would
  eventually need a strategy here (summarization, a sliding window); the
  `Memory` class is deliberately shaped so that could be added as a
  subclass without touching `Agent.run()`.
* **No retry/backoff around the LLM call itself.** `AnthropicProvider`
  makes one call per loop iteration and lets a network error propagate.
  Production use would likely want retries with backoff at that layer.
* **No structured `tool_result` role.** `format_memory()` sends environment
  feedback back as a `user`-role message rather than using a provider's
  native tool-result message type. That keeps `AgentLanguage` provider-
  agnostic at the cost of not using Anthropic's tool-result formatting —
  a reasonable next step for `AnthropicProvider` specifically.
