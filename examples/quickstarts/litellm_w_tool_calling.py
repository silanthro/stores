"""
This example shows how to use stores with LiteLLM with native function calls.
"""

import json

from litellm import completion

import stores

# Load the Hacker News tool index
index = stores.Index(["silanthro/hackernews"])

# Get the response from the model
response = completion(
    model="gemini/gemini-2.0-flash-001",
    messages=[
        {
            "role": "user",
            "content": "What are the top 10 posts on Hacker News today?",
        }
    ],
    tools=index.format_tools("google-gemini"),  # Format tools for Google Gemini
)

# Execute the tool call
tool_call = response.choices[0].message.tool_calls[0]
result = index.execute(
    tool_call.function.name,
    json.loads(tool_call.function.arguments),
)
print(f"Tool output: {result}")
