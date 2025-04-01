"""
This example shows how to use stores with OpenAI's Chat Completions API.
"""

import json

from openai import OpenAI

import stores


# Initialize OpenAI client
client = OpenAI()

# Load the Hacker News tool index
index = stores.Index(["silanthro/hackernews"])

# Get the response from the model
completion = client.chat.completions.create(
    model="gpt-4o-mini-2024-07-18",
    messages=[
        {"role": "user", "content": "What are the top 10 posts on Hacker News today?"}
    ],
    tools=index.format_tools(
        "openai-chat-completions"
    ),  # Format tools for OpenAI Chat Completions API
)

# Execute the tool call
tool_call = completion.choices[0].message.tool_calls[0]
result = index.execute(
    tool_call.function.name,
    json.loads(tool_call.function.arguments),
)
print(f"Tool output: {result}")
