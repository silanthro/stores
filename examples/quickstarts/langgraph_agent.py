"""
This example shows how to use stores with LangChain and a LangGraph agent.
"""

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

import stores

# Load environment variables
load_dotenv()

# Load the Hacker News tool index
index = stores.Index(["silanthro/hackernews"])

# Initialize the LangGraph agent
agent_model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
agent_executor = create_react_agent(agent_model, index.tools)

# Get the response from the agent. The LangGraph agent will automatically execute
# tool calls and generate a response.
response = agent_executor.invoke(
    {
        "messages": [
            HumanMessage(content="What are the top 10 posts on Hacker News today?")
        ]
    }
)
print(f"Assistant response: {response['messages'][-1].content}")
