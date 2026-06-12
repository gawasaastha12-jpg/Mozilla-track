"""
Know Your Docs — Agent

This is where your hackathon work lives.

This script creates an agent that can:
1. Search your private local documents (via the RAG MCP tool)
2. Use external tools (via whatever MCP servers you added to mcpd)
3. Decide which tool to use based on the question

The agent uses tinyagent and the mcpd Python SDK to
pull tools from the running mcpd daemon.

Usage:
    uv run python agent/main.py "How does our retry logic work?"
    uv run python agent/main.py "What is Stripe's current rate limit?"
    uv run python agent/main.py "Compare our retry logic to Stripe's recommendations"

Tinyagent is used directly here to keep the starter kit simple and reliable.
"""

import argparse

from mcpd import McpdClient
from tinyagent import AgentConfig, TinyAgent


# =============================================================================
# CONFIGURATION — edit these to customize your agent
# =============================================================================

# The mcpd daemon endpoint
MCPD_URL = "http://localhost:8090"

# Tinyagent talks to the local llamafile through its OpenAI-compatible API.
# If you want to use a cloud model instead, set MODEL_ID to something like
# "openai/gpt-4o-mini" and update the API settings accordingly.
MODEL_ID = "openai/local"
MODEL_API_BASE = "http://localhost:8086/v1"
MODEL_API_KEY = "local"

# Agent instructions — this is where you control routing behavior.
# EDIT THIS to improve how your agent decides between local and external tools.
AGENT_INSTRUCTIONS = """\
You are a knowledgeable assistant with access to two types of information:

1. **Local documents** (via the `search_docs` tool): Internal documentation
   including architecture decisions, runbooks, and API specs. This is private
   information that cannot be found on the internet.

2. **Web search tools** (via MCP servers such as `ddgs`):
   Public information from the internet, including documentation for
   third-party services, industry best practices, and current technical
   standards.

Your routing strategy:
- ALWAYS check local documents FIRST when the question mentions "our", "we",
  "the team's", or refers to internal systems, policies, or configurations.
- Use `search_text` to find relevant public sources when the question asks
  about third-party services, industry standards, or information that
  wouldn't be in internal docs.
- Use `extract_content` when you need to read a specific public page in more
  detail instead of relying on a search snippet.
- For COMPARISON questions ("how does our X compare to Y"), use BOTH:
  search local docs for "our X", then use web search tools for "Y".
- If local docs don't have the answer, say so — don't hallucinate.
- Always cite your sources: say whether info came from local docs or external sources.
"""


# =============================================================================
# AGENT SETUP — you probably don't need to edit below this line
# =============================================================================


def run_agent(query: str, model_id: str) -> None:
    """Create and run the agent with tools from mcpd."""

    # Connect to mcpd and pull available tools
    print(f"Connecting to mcpd at {MCPD_URL}...")
    client = McpdClient(api_endpoint=MCPD_URL)

    # List available servers for debugging
    servers = client.servers()
    print(f"Available MCP servers: {servers}")

    # Get tools in tinyagent-compatible callable format
    tools = client.agent_tools()
    print(f"Loaded {len(tools)} tools")

    # Create the agent
    print(f"Creating tinyagent with model {model_id}...")
    agent = TinyAgent.create(
        AgentConfig(
            model_id=model_id,
            api_base=MODEL_API_BASE,
            api_key=MODEL_API_KEY,
            instructions=AGENT_INSTRUCTIONS,
            tools=tools,
        ),
    )

    # Run the query
    print(f"\nQuery: {query}")
    print("=" * 60)
    agent_trace = agent.run(query)

    # Print the result
    print("\nAgent Response:")
    print("=" * 60)
    print(getattr(agent_trace, "final_output", agent_trace))


def main():
    parser = argparse.ArgumentParser(description="Know Your Docs Agent")
    parser.add_argument(
        "query",
        nargs="?",
        default="What is our retry policy for failed payments?",
        help="Question to ask the agent",
    )
    parser.add_argument(
        "--model",
        default=MODEL_ID,
        help="Model ID for generation",
    )
    args = parser.parse_args()

    run_agent(args.query, args.model)


if __name__ == "__main__":
    main()
