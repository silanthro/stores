"""
This example shows how to use stores with Anthropic's API.
"""

import os

import anthropic
import dotenv

import stores

dotenv.load_dotenv()


# Initialize Anthropic client
client = anthropic.Anthropic()

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
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Send a haiku about dreams to email@example.com"}
    ],
    tools=index.format_tools("anthropic"),
)

# Execute the tool call
tool_call = response.content[-1]
fn_name = tool_call.name.replace("-", ".")
fn_args = tool_call.input
result = index.execute(fn_name, fn_args)
print(f"Tool output: {result}")
