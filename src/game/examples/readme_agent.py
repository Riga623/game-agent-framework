"""README agent — decorator-based Action registration.

Reads the Python files in a project and drafts a README. Actions are
defined with @register_tool instead of by hand, so their descriptions and
JSON schemas always match the function signature — see tools.py and
docs/DESIGN_NOTES.md, "Two ways to register a tool."

Run directly for a deterministic, zero-API-key demo:

    python -m game.examples.readme_agent
"""

from __future__ import annotations

import os
from pathlib import Path

from ..agent import Agent
from ..core import Environment, Goal
from ..language import AgentFunctionCallingActionLanguage
from ..llm import AnthropicProvider, GenerateResponse, ScriptedProvider
from ..schema import LLMResponse
from ..tools import register_tool, registry_from_tools

GOALS = [
    Goal(
        priority=1,
        name="Gather Information",
        description="Read each Python file in the project",
    ),
    Goal(
        priority=1,
        name="Terminate",
        description=(
            "Call terminate once every file has been read, and provide the "
            "full content of the README in the terminate message"
        ),
    ),
]


@register_tool(tags=["readme_agent"])
def list_project_files() -> list[str]:
    """Lists the Python (.py) files in the current project directory."""
    return sorted(f for f in os.listdir(".") if f.endswith(".py"))


@register_tool(tags=["readme_agent"])
def read_project_file(name: str) -> str:
    """Reads a file from the project. `name` must be one previously returned
    by list_project_files."""
    base = Path.cwd().resolve()
    target = (base / name).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"{name} is outside the allowed directory.")
    with open(target) as f:
        return f.read()


@register_tool(tags=["readme_agent"], terminal=True)
def terminate(message: str) -> str:
    """Terminates the session and returns the final message (the README content) to the user."""
    return f"{message}\nTerminating..."


#: Bundled fixture directory the demo (ScriptedProvider) path reads from,
#: so `python -m game.examples.readme_agent` gives the same, truthful
#: output no matter what directory it's launched from.
DEMO_DIRECTORY = os.path.join(os.path.dirname(__file__), "sample_project")


def demo_provider() -> ScriptedProvider:
    """A scripted stand-in model: lists files, reads one, then drafts a README.

    The tool calls below are written to match DEMO_DIRECTORY's actual
    contents exactly, so the demo never shows a spurious "not found" error.
    """
    return ScriptedProvider(
        [
            LLMResponse(tool_name="list_project_files", args={}),
            LLMResponse(tool_name="read_project_file", args={"name": "calculator.py"}),
            LLMResponse(
                tool_name="terminate",
                args={
                    "message": (
                        "# Calculator\n\n"
                        "A tiny module providing add(a, b) and subtract(a, b) helpers."
                    )
                },
            ),
        ]
    )


def build_agent(generate_response: GenerateResponse | None = None) -> Agent:
    return Agent(
        goals=GOALS,
        agent_language=AgentFunctionCallingActionLanguage(),
        action_registry=registry_from_tools(tags=["readme_agent"]),
        generate_response=generate_response or demo_provider(),
        environment=Environment(),
    )


def main() -> None:
    use_live_model = bool(os.environ.get("ANTHROPIC_API_KEY"))

    if use_live_model:
        generate_response = AnthropicProvider()
    else:
        # No key set: read the bundled fixture directory instead of
        # wherever this happens to be launched from, so the demo is
        # deterministic and self-contained.
        os.chdir(DEMO_DIRECTORY)
        generate_response = demo_provider()

    agent = build_agent(generate_response)
    final_memory = agent.run("Write a README for this project.", max_iterations=10)

    for item in final_memory.get_memories():
        print(f"\n{item['type'].upper()}: {item['content']}")


if __name__ == "__main__":
    main()
