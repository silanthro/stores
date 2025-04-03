"""
This example shows how to use stores with Google's Gemini API with automatic tool calling.
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

# Initialize the chat with the model
config = types.GenerateContentConfig(tools=index.tools)
chat = client.chats.create(model="gemini-2.0-flash", config=config)

# Get the response from the model. Gemini will automatically execute tool calls
# and generate a response.
response = chat.send_message("What are the top 10 posts on Hacker News today?")
print(f"Assistant response: {response.candidates[0].content.parts[0].text}")
