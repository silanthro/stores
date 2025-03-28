"""
This example shows how to use stores with LangChain with native function calls.
"""

import os

import dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

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

# Initialize the model with tools
model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
model_with_tools = model.bind_tools(index.tools)

# Get the response from the model
response = model_with_tools.invoke(
    "Send a haiku about dreams to email@example.com. Don't ask questions."
)

# Execute the tool call
tool_call = response.tool_calls[0]
fn_name = tool_call["name"]
fn_args = tool_call["args"]
result = index.execute(fn_name, fn_args)
print(f"Tool output: {result}")
