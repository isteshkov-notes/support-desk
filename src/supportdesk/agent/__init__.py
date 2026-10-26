"""The agent: the loop that talks to Claude and runs tools on its behalf."""

from supportdesk.agent.client import AnthropicClient, ModelClient
from supportdesk.agent.loop import AgentResult, run_agent_loop

__all__ = ["AgentResult", "AnthropicClient", "ModelClient", "run_agent_loop"]
