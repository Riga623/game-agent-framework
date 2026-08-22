"""@register_tool: derive an Action's metadata from the function itself.

Registering an Action by hand (name=, description=, parameters={...}) works,
but it creates a second place that has to be kept in sync every time a
function's signature or docstring changes — and in practice it doesn't stay
in sync. This module makes the function the single source of truth: its
name becomes the tool name, its docstring becomes the description, and its
type-hinted signature becomes the JSON schema, all extracted automatically
via introspection.

    @register_tool(tags=["file_operations"])
    def read_file(file_path: str, encoding: str = "utf-8") -> str:
        '''Reads and returns the content of a file.

        Args:
            file_path: The path to the file to read
            encoding: The character encoding to use (default: utf-8)
        '''
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()

Adding the `encoding` parameter above required no change anywhere except the
function itself — the schema, including that it's optional (it has a
default), updates automatically.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from .core import Action, ActionRegistry

# Global registries, populated as modules import-time-decorate their tools.
tools: dict[str, dict] = {}
tools_by_tag: dict[str, list[str]] = {}

# Parameters a tool function may declare to receive framework-injected
# context (e.g. the running Agent, or a per-call ActionContext) rather than
# a value the model has to supply. These are skipped when building the
# JSON schema shown to the model.
_CONTEXT_PARAMETERS = {"action_context", "action_agent"}

_PYTHON_TO_JSON_TYPE = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def get_json_type(python_type: Any) -> str:
    """Map a Python type hint to the closest JSON Schema type name.

    Falls back to "string" for anything we don't recognize (e.g. a custom
    class, `Any`, or a typing generic we haven't special-cased) rather than
    raising — an imperfect schema is far more useful to the model than a
    registration that crashes.
    """
    return _PYTHON_TO_JSON_TYPE.get(python_type, "string")


def get_tool_metadata(
    func: Callable,
    tool_name: str | None = None,
    description: str | None = None,
    parameters_override: dict | None = None,
    terminal: bool = False,
    tags: list[str] | None = None,
) -> dict:
    """Introspect `func` and build the metadata needed to register it as a tool."""
    tool_name = tool_name or func.__name__
    description = description or (
        func.__doc__.strip() if func.__doc__ else "No description provided."
    )

    if parameters_override is None:
        signature = inspect.signature(func)
        type_hints = get_type_hints(func)

        args_schema: dict = {"type": "object", "properties": {}, "required": []}

        for param_name, param in signature.parameters.items():
            if param_name in _CONTEXT_PARAMETERS:
                continue

            param_type = type_hints.get(param_name, str)
            args_schema["properties"][param_name] = {"type": get_json_type(param_type)}

            if param.default is inspect.Parameter.empty:
                args_schema["required"].append(param_name)
    else:
        args_schema = parameters_override

    return {
        "tool_name": tool_name,
        "description": description,
        "parameters": args_schema,
        "function": func,
        "terminal": terminal,
        "tags": tags or [],
    }


def register_tool(
    tool_name: str | None = None,
    description: str | None = None,
    parameters_override: dict | None = None,
    terminal: bool = False,
    tags: list[str] | None = None,
):
    """Decorator: register a function as an agent tool, sourced from itself.

    The decorated function is returned unchanged, so it can still be called
    directly (e.g. from tests) exactly as if it weren't decorated.
    """

    def decorator(func: Callable) -> Callable:
        metadata = get_tool_metadata(
            func=func,
            tool_name=tool_name,
            description=description,
            parameters_override=parameters_override,
            terminal=terminal,
            tags=tags,
        )

        tools[metadata["tool_name"]] = {
            "description": metadata["description"],
            "parameters": metadata["parameters"],
            "function": metadata["function"],
            "terminal": metadata["terminal"],
            "tags": metadata["tags"],
        }

        for tag in metadata["tags"]:
            tools_by_tag.setdefault(tag, []).append(metadata["tool_name"])

        return func

    return decorator


def registry_from_tools(
    names: list[str] | None = None, tags: list[str] | None = None
) -> ActionRegistry:
    """Build an ActionRegistry from the @register_tool-decorated global registry.

    Pass `names` for an explicit allowlist, `tags` to pull in every tool
    carrying any of those tags, or neither to register everything that's
    been decorated so far. This is the bridge between "I wrote some
    decorated functions" and "here's the ActionRegistry an Agent needs."
    """
    if names is not None:
        selected = names
    elif tags is not None:
        selected = [name for tag in tags for name in tools_by_tag.get(tag, [])]
    else:
        selected = list(tools.keys())

    registry = ActionRegistry()
    for name in selected:
        spec = tools[name]
        registry.register(
            Action(
                name=name,
                function=spec["function"],
                description=spec["description"],
                parameters=spec["parameters"],
                terminal=spec["terminal"],
            )
        )
    return registry
