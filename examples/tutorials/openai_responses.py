"""
This example shows how to use stores with OpenAI's Responses API.
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
response = client.responses.create(
    model="gpt-4o-mini-2024-07-18",
    input=[
        {"role": "user", "content": "Send a haiku about dreams to email@example.com"}
    ],
    tools=index.format_tools("openai-responses"),
)

# Execute the tool call
tool_call = response.output[0]
fn_name = tool_call.name
fn_args = json.loads(tool_call.arguments)
result = index.execute(fn_name, fn_args)
print(f"Tool output: {result}")
