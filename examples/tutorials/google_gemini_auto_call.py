"""
This example shows how to use stores with Google's Gemini API with automatic tool calling.
"""

import os

import dotenv
from google import genai
from google.genai import types

import stores

dotenv.load_dotenv()


# Initialize Google Gemini client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

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

# Initialize the chat with the model
config = types.GenerateContentConfig(tools=index.tools)
chat = client.chats.create(model="gemini-2.0-flash", config=config)

# Get the response from the model. Gemini will automatically execute the tool call.
response = chat.send_message(
    "Send a haiku about dreams to email@example.com. Don't ask questions."
)
print(f"Assistant response: {response.candidates[0].content.parts[0].text}")
