"""
This example shows how to use stores with OpenAI's Responses API.
"""

import json

import dotenv
from openai import OpenAI

import stores

dotenv.load_dotenv()


# Initialize OpenAI client
client = OpenAI()

# Load the Hacker News tool
index = stores.Index(["silanthro/hackernews"])

# Get the response from the model
response = client.responses.create(
    model="gpt-4o-mini-2024-07-18",
    input=[
        {"role": "user", "content": "What are the top 10 posts on Hacker News today?"}
    ],
    tools=index.format_tools(
        "openai-responses"
    ),  # Format tools for OpenAI Responses API
)

# Execute the tool call
tool_call = response.output[0]
result = index.execute(
    tool_call.name,
    json.loads(tool_call.arguments),
)
print(f"Tool output: {result}")
