"""
This example shows how to use stores with Anthropic's API.
"""

import anthropic
from dotenv import load_dotenv

import stores

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = anthropic.Anthropic()

# Load the Hacker News tool index
index = stores.Index(["silanthro/hackernews"])

# Get the response from the model
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "What are the top 10 posts on Hacker News today?"}
    ],
    tools=index.format_tools("anthropic"),  # Format tools for Anthropic
)

# Execute the tool call
tool_call = response.content[-1]
result = index.execute(tool_call.name, tool_call.input)
print(f"Tool output: {result}")
