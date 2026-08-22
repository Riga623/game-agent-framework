# Contributing

## Getting set up

```bash
git clone https://github.com/USERNAME/game-agent-framework.git
cd game-agent-framework
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

No API key is needed for any of this — the full test suite and both
example agents run against `ScriptedProvider` (see README.md, "Demo mode").

## Before opening a pull request

```bash
ruff check .                                   # lint
pytest --cov=game --cov-report=term-missing    # tests
```

Please make sure both pass; CI runs them (plus a secret-leak scan)
automatically on every pull request.

## Guidelines

- Never commit a `.env` file or a real API key. Local secrets belong only
  in your own untracked `.env` — see `.env.example`.
- New actions/tools should have a genuinely descriptive name and
  docstring — see `docs/DESIGN_NOTES.md`, "Tool naming and description are
  not cosmetic," for why this isn't a style nitpick.
- Prefer `@register_tool` (see `game/tools.py`) for new tools over hand-
  built `Action(...)` objects, unless you have a specific reason to want
  the schema decoupled from the function signature.
- Add or update tests for any behavior change. New agent-loop behavior
  should get a `ScriptedProvider`-based test in `tests/test_agent_loop.py`
  rather than requiring a live model to exercise.

## Reporting bugs / suggesting features

Open a GitHub issue with a clear description and, for bugs, steps to
reproduce.
