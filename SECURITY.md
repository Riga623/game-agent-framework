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

## Supported versions

This is a small reference implementation with a single actively
maintained branch (`main`). Security fixes are applied there only.

## Reporting a vulnerability

Please report suspected vulnerabilities privately using GitHub's
["Report a vulnerability"](https://github.com/Riga623/game-agent-framework/security/advisories/new)
feature on this repository's **Security** tab, rather than filing a public
issue.
