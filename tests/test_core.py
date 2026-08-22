from game.core import Action, ActionRegistry, Environment, Memory


def test_action_registry_register_and_lookup():
    registry = ActionRegistry()
    action = Action(
        name="ping",
        function=lambda: "pong",
        description="Replies pong.",
        parameters={},
    )
    registry.register(action)

    assert registry.get_action("ping") is action
    assert registry.get_action("missing") is None
    assert registry.get_actions() == [action]
    assert "ping" in registry


def test_action_execute_calls_underlying_function():
    action = Action(
        name="add",
        function=lambda a, b: a + b,
        description="Adds two numbers.",
        parameters={},
    )
    assert action.execute(a=2, b=3) == 5


def test_memory_add_and_get_preserves_order():
    memory = Memory()
    memory.add_memory({"type": "user", "content": "hello"})
    memory.add_memory({"type": "assistant", "content": "hi"})

    memories = memory.get_memories()
    assert len(memory) == 2
    assert [m["type"] for m in memories] == ["user", "assistant"]


def test_memory_get_memories_respects_limit():
    memory = Memory()
    for i in range(5):
        memory.add_memory({"type": "user", "content": str(i)})

    assert len(memory.get_memories(limit=2)) == 2


def test_environment_execute_action_success_includes_metadata():
    action = Action(name="ok", function=lambda: 42, description="", parameters={})
    result = Environment().execute_action(action, {})

    assert result["tool_executed"] is True
    assert result["result"] == 42
    assert "timestamp" in result


def test_environment_execute_action_never_raises_on_exception():
    def boom():
        raise ValueError("kaboom")

    action = Action(name="boom", function=boom, description="", parameters={})
    result = Environment().execute_action(action, {})

    assert result["tool_executed"] is False
    assert "kaboom" in result["error"]
    assert "Traceback" in result["traceback"]
