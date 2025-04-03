"""
This example shows how to use stores with OpenAI's Agent SDK.
"""

from agents import Agent, Runner, function_tool
from dotenv import load_dotenv

import stores

# Load environment variables
load_dotenv()

# Load the Hacker News tool index
index = stores.Index(["silanthro/hackernews"])

# Set up the tools with Agents SDK's function_tool
formatted_tools = [
    # OpenAI only supports ^[a-zA-Z0-9_-]{1,64}$
    function_tool(name_override=fn.__name__.replace(".", "_"))(fn)
    for fn in index.tools
]

# Initialize OpenAI agent
agent = Agent(
    name="Hacker News Agent",
    model="gpt-4o-mini-2024-07-18",
    tools=formatted_tools,
)

# Get the response from the agent. The OpenAI agent will automatically execute
# tool calls and generate a response.
result = Runner.run_sync(agent, "What are the top 10 posts on Hacker News today?")
print(f"Agent output: {result.final_output}")
