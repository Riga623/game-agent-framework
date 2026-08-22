"""game: a small, well-documented implementation of the GAME agent framework.

GAME stands for the four things every agent design decision boils down to:

    Goals       - what the agent is trying to achieve (and how)
    Actions     - the toolkit it's allowed to use to get there
    Memory      - the record of what's happened so far in this run
    Environment - the thing that actually executes an action and reports back

The core insight the framework is built around: the agent loop is just an
automated conversation. Construct a prompt from (goals, memory, actions) ->
send it to a model -> parse the model's chosen action out of the response ->
execute that action in the environment -> record the result in memory ->
repeat. See docs/DESIGN_NOTES.md for the reasoning behind each piece.
"""

from .agent import Agent
from .core import Action, ActionRegistry, Environment, Goal, Memory

__version__ = "0.1.0"

__all__ = [
    "Goal",
    "Action",
    "ActionRegistry",
    "Memory",
    "Environment",
    "Agent",
]
