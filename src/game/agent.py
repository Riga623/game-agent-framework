"""The Agent: the six-step loop, running over the GAME components.

    1. construct a prompt from (goals, memory, actions)
    2. send it to the model                     -> generate_response
    3. parse the model's reply into a decision   -> agent_language.parse_response
    4. look up and execute the chosen action     -> environment.execute_action
    5. record the result in memory
    6. stop if the action was terminal (or we hit max_iterations); else loop

Everything upstream of this file (Goal, Action, Memory, Environment,
AgentLanguage, the LLM provider) exists so that this loop itself can stay
short and free of agent-specific logic. A new agent is a new set of goals
and actions, not a new loop.
"""

from __future__ import annotations

from .core import Action, ActionRegistry, Environment, Goal, Memory
from .language import AgentLanguage, ParseError


class Agent:
    def __init__(
        self,
        goals: list[Goal],
        agent_language: AgentLanguage,
        action_registry: ActionRegistry,
        generate_response,
        environment: Environment,
    ):
        self.goals = goals
        self.agent_language = agent_language
        self.actions = action_registry
        self.generate_response = generate_response
        self.environment = environment

    def construct_prompt(self, memory: Memory):
        """Step 1: build the next prompt from goals, memory, and available actions."""
        return self.agent_language.construct_prompt(
            goals=self.goals, memory=memory, actions=self.actions.get_actions()
        )

    def get_action(self, decision: dict) -> Action:
        """Look up the Action the model named, or raise a ParseError the model can act on."""
        action = self.actions.get_action(decision["tool"])
        if action is None:
            available = ", ".join(a.name for a in self.actions.get_actions())
            raise ParseError(
                f"There is no tool named '{decision['tool']}'. "
                f"Available tools are: {available}."
            )
        return action

    def should_terminate(self, action: Action) -> bool:
        """Step 6 (part 1): a terminal action ends the run once it's executed."""
        return action.terminal

    def run(
        self, user_input: str, memory: Memory | None = None, max_iterations: int = 10
    ) -> Memory:
        """Run the agent loop until a terminal action fires or max_iterations is hit.

        `max_iterations` is a hard safety cap, independent of how well the
        agent is designed — without one, a model that keeps re-trying a
        failing action (or never calls a terminal action) would run
        forever. Hitting the cap is not treated as an error: whatever
        memory has accumulated is returned either way, so the caller can
        always inspect what happened.
        """
        memory = memory if memory is not None else Memory()
        memory.add_memory({"type": "user", "content": user_input})

        for _ in range(max_iterations):
            prompt = self.construct_prompt(memory)
            response = self.generate_response(prompt)

            try:
                decision = self.agent_language.parse_response(response)
                action = self.get_action(decision)
            except ParseError as error:
                # The model's reply couldn't be turned into a runnable action.
                # Record what it *did* say, then feed back a specific,
                # actionable error as environment feedback (never a bare
                # "invalid response") so it gets a real chance to recover on
                # the next iteration instead of the run just crashing.
                memory.add_memory(
                    {"type": "assistant", "content": response.text or repr(response.raw)}
                )
                memory.add_memory({"type": "environment", "content": f"Error: {error.feedback}"})
                continue

            memory.add_memory(
                {"type": "assistant", "content": f"Calling {action.name} with {decision['args']}"}
            )

            result = self.environment.execute_action(action, decision["args"])
            memory.add_memory({"type": "environment", "content": result})

            if self.should_terminate(action):
                break

        return memory
