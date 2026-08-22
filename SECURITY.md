# Security Policy

## No secrets in this repository

This framework is designed so that no API key is ever required to be
committed, or even to exist, to use or test it:

- All configuration (currently just `ANTHROPIC_API_KEY`) is read from an
  environment variable, never hardcoded — see `AnthropicProvider` in
  `src/game/llm.py`, which reads `os.environ.get("ANTHROPIC_API_KEY")` and
  never accepts a key as a literal argument.
- `.env` (where a real key would live locally) is excluded via
  `.gitignore`. Only `.env.example`, containing an empty placeholder, is
  tracked in git.
- Every example agent and the entire test suite runs against
  `ScriptedProvider` — no network call, no key needed — so nothing in CI
  or local development ever requires a credential to exist.
- Pushes and pull requests are scanned for accidentally-committed secrets
  by [Gitleaks](https://github.com/gitleaks/gitleaks) in CI (see
  `.github/workflows/ci.yml`).

If you ever spot what looks like a real credential in this repository's
history, please report it privately (see below) rather than opening a
public issue.

## Data sent to the LLM provider

When an `Action` raises an exception, `Environment.execute_action()`
(`src/game/core.py`) captures the full traceback — including local
filesystem paths — and feeds it into `Memory`, which is then sent to
whichever provider `AgentLanguage` is configured with (e.g. Anthropic, via
`AnthropicProvider`). This is a deliberate design choice (see
`docs/DESIGN_NOTES.md`, "Feedback quality is what lets an agent recover")
and not a bug, but it does mean: don't point an agent built on this
framework at a directory containing paths or filenames you don't want
included in a request to a third-party model API.

The two bundled example tools that read files (`read_file` in
`file_explorer.py`, `read_project_file` in `readme_agent.py`) restrict
reads to within the process's current working directory — `../`-style
traversal and absolute paths outside it are rejected before the file is
opened — so a misbehaving or adversarially-prompted agent can't use them
to read arbitrary files elsewhere on disk.

## Supported versions

This is a small reference implementation with a single actively
maintained branch (`main`). Security fixes are applied there only.

## Reporting a vulnerability

Please report suspected vulnerabilities privately using GitHub's
["Report a vulnerability"](https://github.com/Riga623/game-agent-framework/security/advisories/new)
feature on this repository's **Security** tab, rather than filing a public
issue.
