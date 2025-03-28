"""
This example shows how to use stores with OpenAI's Chat Completions API.
"""

import json
import os

import dotenv
from openai import OpenAI

import stores

dotenv.load_dotenv()


# Initialize OpenAI client
client = OpenAI()

# Load tools and set the required environment variables
index = stores.Index(
    ["silanthro/send-gmail"],
    env_var={
        "silanthro/send-gmail": {
            "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
            "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
        },
    },
)

# Get the response from the model
completion = client.chat.completions.create(
    model="gpt-4o-mini-2024-07-18",
    messages=[
        {"role": "user", "content": "Send a haiku about dreams to email@example.com"}
    ],
    tools=index.format_tools("openai-chat-completions"),
)

# Execute the tool call
tool_call = completion.choices[0].message.tool_calls[0]
result = index.execute(
    tool_call.function.name,
    json.loads(tool_call.function.arguments),
)
print(f"Tool output: {result}")
