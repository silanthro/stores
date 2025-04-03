"""
This example shows how to use stores with Google's Gemini API with manual tool calling.
"""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

import stores

# Load environment variables
load_dotenv()

# Initialize Google Gemini client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Load the Hacker News tool index
index = stores.Index(["silanthro/hackernews"])

# Configure the model with tools
config = types.GenerateContentConfig(
    tools=index.tools,
    automatic_function_calling=types.AutomaticFunctionCallingConfig(
        disable=True  # Disable automatic function calling to manually execute tool calls
    ),
)

# Get the response from the model
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="What are the top 10 posts on Hacker News today?",
    config=config,
)

# Execute the tool call
tool_call = response.candidates[0].content.parts[0].function_call
result = index.execute(tool_call.name, tool_call.args)
print(f"Tool output: {result}")
