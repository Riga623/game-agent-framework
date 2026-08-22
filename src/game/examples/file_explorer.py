"""File Explorer agent — manual Action registration.

Explores the files in a directory and answers questions about them. Actions
are registered by hand with explicit Action(...) objects, the way you would
before reaching for the @register_tool decorator — deliberately kept this
way (rather than converted to the decorator style like readme_agent.py) so
the two examples together show both registration paths side by side. See
docs/DESIGN_NOTES.md, "Two ways to register a tool."

Run directly for a deterministic, zero-API-key demo:

    python -m game.examples.file_explorer

Or import build_agent() to run it against a real model (requires the
`anthropic` extra and ANTHROPIC_API_KEY set).
"""

from __future__ import annotations

import os
from pathlib import Path

from ..agent import Agent
from ..core import Action, ActionRegistry, Environment, Goal
from ..language import AgentFunctionCallingActionLanguage
from ..llm import AnthropicProvider, GenerateResponse, ScriptedProvider
from ..schema import LLMResponse


def list_files() -> list[str]:
    """List files in the current directory."""
    return os.listdir(".")


def read_file(file_name: str) -> str:
    """Read a file's contents."""
    try:
        base = Path.cwd().resolve()
        target = (base / file_name).resolve()
        if not target.is_relative_to(base):
            return f"Error: {file_name} is outside the allowed directory."
        with open(target) as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: {file_name} not found."
    except Exception as e:  # noqa: BLE001 - deliberately broad, this is tool-facing feedback
        return f"Error: {e}"


def terminate(message: str) -> str:
    """Terminate the agent loop and provide a summary message."""
    return message


GOALS = [
    Goal(
        priority=1,
        name="Explore Files",
        description="Explore files in the current directory by listing and reading them",
    ),
    Goal(
        priority=2,
        name="Terminate",
        description="Terminate the session when tasks are complete with a helpful summary",
    ),
]


def build_action_registry() -> ActionRegistry:
    registry = ActionRegistry()
    registry.register(
        Action(
            name="list_files",
            function=list_files,
            description="Returns a list of files in the directory.",
            parameters={},
            terminal=False,
        )
    )
    registry.register(
        Action(
            name="read_file",
            function=read_file,
            description="Reads the content of a specified file in the directory.",
            parameters={
                "type": "object",
                "properties": {"file_name": {"type": "string"}},
                "required": ["file_name"],
            },
            terminal=False,
        )
    )
    registry.register(
        Action(
            name="terminate",
            function=terminate,
            description="Terminates the conversation. Prints the provided message for the user.",
            parameters={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            terminal=True,
        )
    )
    return registry


#: Bundled fixture directory the demo (ScriptedProvider) path explores, so
#: `python -m game.examples.file_explorer` gives the same, truthful output
#: no matter what directory it's launched from. Only used in demo mode —
#: build_agent(), and main() when a live model is driving, operate on
#: whatever the real current directory is, as the tools are designed to.
DEMO_DIRECTORY = os.path.join(os.path.dirname(__file__), "sample_project")


def demo_provider() -> ScriptedProvider:
    """A scripted stand-in model: lists files, reads one, then terminates.

    This is what makes `python -m game.examples.file_explorer` runnable
    with zero API keys — it's the coded version of the "simulate the agent
    in conversation" technique, applied as a demo/fixture instead of a
    manual chat. The two tool calls below are written to match
    DEMO_DIRECTORY's actual contents exactly, so the demo never shows a
    spurious "not found" error.
    """
    return ScriptedProvider(
        [
            LLMResponse(tool_name="list_files", args={}),
            LLMResponse(tool_name="read_file", args={"file_name": "calculator.py"}),
            LLMResponse(
                tool_name="terminate",
                args={
                    "message": (
                        "This project contains a README.md and calculator.py; "
                        "calculator.py defines simple add/subtract helper functions."
                    )
                },
            ),
        ]
    )


def build_agent(generate_response: GenerateResponse | None = None) -> Agent:
    return Agent(
        goals=GOALS,
        agent_language=AgentFunctionCallingActionLanguage(),
        action_registry=build_action_registry(),
        generate_response=generate_response or demo_provider(),
        environment=Environment(),
    )


def main() -> None:
    use_live_model = bool(os.environ.get("ANTHROPIC_API_KEY"))

    if use_live_model:
        generate_response = AnthropicProvider()
    else:
        # No key set: explore the bundled fixture directory instead of
        # wherever this happens to be launched from, so the demo is
        # deterministic and self-contained.
        os.chdir(DEMO_DIRECTORY)
        generate_response = demo_provider()

    agent = build_agent(generate_response)
    task = "Tell me what files are in this directory and summarize one of them."
    final_memory = agent.run(task, max_iterations=10)

    for item in final_memory.get_memories():
        print(f"\n{item['type'].upper()}: {item['content']}")


if __name__ == "__main__":
    main()
