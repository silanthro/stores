"""
This example shows how to use stores with LiteLLM with native function calls.
"""

import json
import os

import dotenv
from litellm import completion

import stores

dotenv.load_dotenv()


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
response = completion(
    model="gemini/gemini-2.0-flash-001",
    messages=[
        {
            "role": "user",
            "content": "Send a haiku about dreams to email@example.com. Don't ask questions.",
        }
    ],
    tools=index.format_tools("google-gemini"),
)

# Execute the tool call
tool_call = response.choices[0].message.tool_calls[0]
fn_name = tool_call.function.name
fn_args = json.loads(tool_call.function.arguments)
result = index.execute(fn_name, fn_args)
print(f"Tool output: {result}")
