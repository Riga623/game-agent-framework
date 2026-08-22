# game-agent-framework

[![CI](https://github.com/USERNAME/game-agent-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/USERNAME/game-agent-framework/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

A small, well-documented implementation of **GAME** — a way of designing
and building AI agents around four components: **G**oals, **A**ctions,
**M**emory, and **E**nvironment.

## What this is

Most of what an "AI agent" does boils down to one loop: construct a prompt,
send it to a model, parse the model's chosen action out of the reply,
execute that action, record what happened, repeat until done. Everything
that differs between agents — a file explorer, a README writer, a
travel-expense bot — is *what goes into* that loop, not the loop itself.

GAME names the four things that go in:

| Component | Answers | In this repo |
|---|---|---|
| **G**oal | What is the agent trying to achieve, and how? | `Goal` — a prioritized, named objective (`src/game/core.py`) |
| **A**ction | What is it allowed to do? | `Action` / `ActionRegistry` — a typed, described toolkit (`src/game/core.py`, `src/game/tools.py`) |
| **M**emory | What has happened so far? | `Memory` — the accumulating record fed back into every prompt (`src/game/core.py`) |
| **E**nvironment | Who actually runs an action and reports back? | `Environment` — executes an `Action`, never lets an exception escape (`src/game/core.py`) |

`Agent` (`src/game/agent.py`) is the loop that ties all four together. Building
a new agent means writing new goals and actions — the loop itself doesn't
change.

## Quickstart

```bash
git clone https://github.com/USERNAME/game-agent-framework.git
cd game-agent-framework
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Runs a deterministic demo with zero API keys — see "Demo mode" below.
python -m game.examples.file_explorer
python -m game.examples.readme_agent
```

## Demo mode (no API key needed)

Every example agent and the entire test suite runs with **no model, no API
key, and no network call**, via `ScriptedProvider` (`src/game/llm.py`) — a
stand-in "model" that replays a fixed script of tool calls. This is the
coded version of a technique from the design process itself: before
writing any implementation, you can validate a GAME design by simulating
the agent in a plain chat conversation, playing the environment yourself
by typing back fake tool results (see `docs/DESIGN_NOTES.md`,
*"Simulate before you implement"*). `ScriptedProvider` is that same idea,
formalized as a test fixture.

To have an example agent think for itself with a real model instead:

```bash
pip install -e ".[anthropic]"
cp .env.example .env   # then fill in your own ANTHROPIC_API_KEY
export $(grep -v '^#' .env | xargs)   # or use direnv / your own tooling
python -m game.examples.file_explorer
```

`.env` is git-ignored and will never be committed — see
[SECURITY.md](SECURITY.md).

## Project layout

```
game-agent-framework/
├── src/game/
│   ├── core.py          # Goal, Action, ActionRegistry, Memory, Environment
│   ├── tools.py          # @register_tool decorator (function -> Action, automatically)
│   ├── language.py        # AgentLanguage: (goals, memory, actions) -> Prompt; reply -> decision
│   ├── llm.py              # Pluggable model backends: ScriptedProvider, AnthropicProvider
│   ├── agent.py             # Agent — the six-step loop
│   ├── schema.py             # Prompt / LLMResponse — shared message shapes
│   └── examples/
│       ├── file_explorer.py   # manual Action registration
│       ├── readme_agent.py     # @register_tool decorator registration
│       └── sample_project/      # tiny fixture the two demos above explore
├── tests/                        # runs fully offline, no keys, no network
├── docs/DESIGN_NOTES.md            # why each piece exists — see below
└── .github/workflows/ci.yml          # lint, test, gitleaks secret scan
```

## The agent loop

```
 ┌─────────────────────────────────────────────────────────────────┐
 │  loop (until a terminal action fires, or max_iterations is hit)   │
 │                                                                     │
 │   1. construct_prompt(goals, memory, actions)  ──►  Prompt          │
 │   2. generate_response(prompt)                 ──►  LLMResponse      │
 │   3. agent_language.parse_response(response)    ──►  {tool, args}     │
 │        (a response that doesn't call a tool raises ParseError,         │
 │         which is fed back into memory as feedback, not a crash)         │
 │   4. environment.execute_action(action, args)    ──►  structured result  │
 │   5. memory.add_memory(result)                                            │
 │   6. if action.terminal: stop                                              │
 └─────────────────────────────────────────────────────────────────────────┘
```

See `src/game/agent.py` — `Agent.run()`, the method that actually runs
this loop, is under 50 lines; everything else in the package exists to
keep it that short.

## Two ways to register a tool

Both examples solve a similar problem (explore some files, then act on
what was found) but register their actions differently, on purpose:

* **`file_explorer.py`** builds `Action(...)` objects by hand — explicit,
  and a reasonable starting point.
* **`readme_agent.py`** uses `@register_tool` — the function's name,
  docstring, and type-hinted signature become the tool's name, description,
  and JSON schema automatically, so they can't drift out of sync as the
  function evolves.

See `docs/DESIGN_NOTES.md` for the reasoning behind the second approach.

## Development

```bash
pip install -e ".[dev]"
ruff check .                            # lint
pytest --cov=game --cov-report=term-missing   # tests + coverage
```

## Documentation

* [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md) — the reasoning behind each
  design decision, tied back to specific lessons (tool naming, feedback
  quality, decorator-based sync, simulation-first design).
* [CONTRIBUTING.md](CONTRIBUTING.md)
* [SECURITY.md](SECURITY.md)

## License

[MIT](LICENSE)
