"""Tests for the Anthropic response-parsing logic.

response_from_anthropic_message() is deliberately a plain function taking
a duck-typed `message` object, not a method on AnthropicProvider — that's
what lets these tests exercise the one piece of the framework that talks
to a real external API, using lightweight fakes, with no `anthropic`
package installed, no API key, and no network call.
"""

from dataclasses import dataclass

from game.llm import response_from_anthropic_message


@dataclass
class FakeBlock:
    type: str
    name: str | None = None
    input: dict | None = None
    text: str | None = None


@dataclass
class FakeMessage:
    content: list
    stop_reason: str = "end_turn"


def test_single_tool_use_block():
    message = FakeMessage(
        content=[FakeBlock(type="tool_use", name="read_file", input={"file_name": "a.txt"})]
    )
    response = response_from_anthropic_message(message)

    assert response.tool_name == "read_file"
    assert response.args == {"file_name": "a.txt"}
    assert response.extra_tool_calls == []
    assert response.truncated is False


def test_text_only_response_has_no_tool_name():
    message = FakeMessage(content=[FakeBlock(type="text", text="Let me think about this...")])
    response = response_from_anthropic_message(message)

    assert response.tool_name is None
    assert response.text == "Let me think about this..."


def test_mixed_text_and_tool_use():
    message = FakeMessage(
        content=[
            FakeBlock(type="text", text="I'll read the file."),
            FakeBlock(type="tool_use", name="read_file", input={"file_name": "a.txt"}),
        ]
    )
    response = response_from_anthropic_message(message)

    assert response.text == "I'll read the file."
    assert response.tool_name == "read_file"


def test_multiple_tool_use_blocks_are_all_captured_not_dropped():
    """Regression test: earlier code kept only the LAST tool_use block and
    silently discarded the rest. Every call must survive, even if only the
    first is treated as the one to run."""
    message = FakeMessage(
        content=[
            FakeBlock(type="tool_use", name="read_file", input={"file_name": "a.txt"}),
            FakeBlock(type="tool_use", name="list_files", input={}),
            FakeBlock(type="tool_use", name="terminate", input={"message": "done"}),
        ]
    )
    response = response_from_anthropic_message(message)

    assert response.tool_name == "read_file"
    assert response.args == {"file_name": "a.txt"}
    assert response.extra_tool_calls == [
        ("list_files", {}),
        ("terminate", {"message": "done"}),
    ]


def test_truncated_response_is_flagged():
    message = FakeMessage(
        content=[FakeBlock(type="tool_use", name="read_file", input={})],
        stop_reason="max_tokens",
    )
    response = response_from_anthropic_message(message)

    assert response.truncated is True


def test_normal_completion_is_not_flagged_as_truncated():
    message = FakeMessage(
        content=[FakeBlock(type="tool_use", name="read_file", input={})],
        stop_reason="tool_use",
    )
    response = response_from_anthropic_message(message)

    assert response.truncated is False


def test_missing_stop_reason_defaults_to_not_truncated():
    """Some fake/older message-like objects might not have stop_reason at
    all — getattr with a default means this doesn't raise AttributeError."""

    @dataclass
    class MessageWithoutStopReason:
        content: list

    message = MessageWithoutStopReason(content=[FakeBlock(type="text", text="hi")])
    response = response_from_anthropic_message(message)

    assert response.truncated is False
