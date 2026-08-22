"""Smoke tests for the two example agents, run entirely against their
built-in ScriptedProvider demo (no API key, no network)."""

from game.examples import file_explorer, readme_agent


def test_file_explorer_demo_runs_to_termination():
    agent = file_explorer.build_agent()
    memory = agent.run("Tell me what files are here.", max_iterations=10)

    last_action = next(
        m for m in reversed(memory.get_memories())
        if m["type"] == "assistant" and str(m["content"]).startswith("Calling")
    )
    assert last_action["content"].startswith("Calling terminate")


def test_readme_agent_demo_runs_to_termination():
    agent = readme_agent.build_agent()
    memory = agent.run("Write a README for this project.", max_iterations=10)

    last_action = next(
        m for m in reversed(memory.get_memories())
        if m["type"] == "assistant" and str(m["content"]).startswith("Calling")
    )
    assert last_action["content"].startswith("Calling terminate")
