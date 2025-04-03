"""
This example shows how to use stores with a LlamaIndex agent.
"""

from dotenv import load_dotenv
from llama_index.core.agent import AgentRunner
from llama_index.core.tools import FunctionTool
from llama_index.llms.google_genai import GoogleGenAI

import stores

# Load environment variables
load_dotenv()

# Load the Hacker News tool index
index = stores.Index(["silanthro/hackernews"])

# Initialize the LlamaIndex agent with tools
llm = GoogleGenAI(model="models/gemini-2.0-flash-001")
tools = [
    FunctionTool.from_defaults(fn=fn) for fn in index.tools
]  # Use LlamaIndex FunctionTool
agent = AgentRunner.from_llm(tools, llm=llm, verbose=True)

# Get the response from the agent. The LlamaIndex agent will automatically execute
# tool calls and generate a response.
response = agent.chat("What are the top 10 posts on Hacker News today?")
print(f"Assistant response: {response}")
