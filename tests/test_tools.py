from game.tools import (
    get_json_type,
    get_tool_metadata,
    register_tool,
    registry_from_tools,
    tools,
    tools_by_tag,
)


def test_get_json_type_maps_known_python_types():
    assert get_json_type(str) == "string"
    assert get_json_type(int) == "integer"
    assert get_json_type(float) == "number"
    assert get_json_type(bool) == "boolean"
    assert get_json_type(list) == "array"
    assert get_json_type(dict) == "object"


def test_get_json_type_falls_back_to_string_for_unknown_types():
    class Custom:
        pass

    assert get_json_type(Custom) == "string"


def test_get_tool_metadata_extracts_name_docstring_and_schema():
    def sample(file_path: str, limit: int = 10) -> str:
        """Reads up to `limit` lines from a file."""
        return file_path

    metadata = get_tool_metadata(sample)

    assert metadata["tool_name"] == "sample"
    assert "Reads up to" in metadata["description"]
    assert metadata["parameters"]["properties"]["file_path"] == {"type": "string"}
    assert metadata["parameters"]["properties"]["limit"] == {"type": "integer"}
    assert metadata["parameters"]["required"] == ["file_path"]  # limit has a default


def test_get_tool_metadata_skips_context_parameters():
    def sample(action_context, file_path: str):
        """Docstring."""
        return file_path

    metadata = get_tool_metadata(sample)
    assert "action_context" not in metadata["parameters"]["properties"]
    assert "file_path" in metadata["parameters"]["properties"]


def test_register_tool_populates_global_registries():
    tools.clear()
    tools_by_tag.clear()

    @register_tool(tags=["demo"])
    def greet(name: str) -> str:
        """Greets someone."""
        return f"Hello, {name}!"

    assert "greet" in tools
    assert tools["greet"]["description"] == "Greets someone."
    assert tools_by_tag["demo"] == ["greet"]

    # The decorated function still works as a normal function.
    assert greet("World") == "Hello, World!"


def test_registry_from_tools_builds_action_registry_from_tags():
    tools.clear()
    tools_by_tag.clear()

    @register_tool(tags=["math"])
    def double(n: int) -> int:
        """Doubles a number."""
        return n * 2

    @register_tool(tags=["other"])
    def noop() -> None:
        """Does nothing."""
        return None

    registry = registry_from_tools(tags=["math"])
    names = [a.name for a in registry.get_actions()]

    assert names == ["double"]
    action = registry.get_action("double")
    assert action.execute(n=21) == 42
