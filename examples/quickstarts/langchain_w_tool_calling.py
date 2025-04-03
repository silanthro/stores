"""
This example shows how to use stores with LangChain with native function calls.
"""

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

import stores

# Load environment variables
load_dotenv()

# Load the Hacker News tool index
index = stores.Index(["silanthro/hackernews"])

# Initialize the model with tools
model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
model_with_tools = model.bind_tools(index.tools)

# Get the response from the model
response = model_with_tools.invoke("What are the top 10 posts on Hacker News today?")

# Execute the tool call
tool_call = response.tool_calls[0]
result = index.execute(tool_call["name"], tool_call["args"])
print(f"Tool output: {result}")
