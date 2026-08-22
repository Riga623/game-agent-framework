"""Smoke tests for the two example agents, run entirely against their
built-in ScriptedProvider demo (no API key, no network)."""

import os

import pytest

from game.examples import file_explorer, readme_agent


def test_file_explorer_demo_runs_to_termination():
    agent = file_explorer.build_agent()
    memory = agent.run("Tell me what files are here.", max_iterations=10)

    last_action = next(
        m for m in reversed(memory.get_memories())
        if m["type"] == "assistant" and str(m["content"]).startswith("Calling")
    )
    assert last_action["content"].startswith("Calling terminate")


def test_file_explorer_read_file_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "inside.txt").write_text("safe")
    outside = tmp_path.parent / "outside_secret.txt"
    outside.write_text("should not be readable")
    try:
        result = file_explorer.read_file(os.path.join("..", outside.name))
        assert "outside the allowed directory" in result
        assert file_explorer.read_file("inside.txt") == "safe"
    finally:
        outside.unlink(missing_ok=True)


def test_readme_agent_read_project_file_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "inside.py").write_text("safe = True")
    outside = tmp_path.parent / "outside_secret.txt"
    outside.write_text("should not be readable")
    try:
        with pytest.raises(ValueError, match="outside the allowed directory"):
            readme_agent.read_project_file(os.path.join("..", outside.name))
        assert readme_agent.read_project_file("inside.py") == "safe = True"
    finally:
        outside.unlink(missing_ok=True)


def test_readme_agent_demo_runs_to_termination():
    agent = readme_agent.build_agent()
    memory = agent.run("Write a README for this project.", max_iterations=10)

    last_action = next(
        m for m in reversed(memory.get_memories())
        if m["type"] == "assistant" and str(m["content"]).startswith("Calling")
    )
    assert last_action["content"].startswith("Calling terminate")
