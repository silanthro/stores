"""
This example shows how to use stores with Google's Gemini API with automatic tool calling.
"""

import os

from google import genai
from google.genai import types

import stores


def main():
    # Load custom tools and set the required environment variables
    index = stores.Index(
        ["silanthro/send-gmail"],
        env_vars={
            "silanthro/send-gmail": {
                "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
                "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
            },
        },
    )

    # Set up the user request, system instruction, model parameters, and tools
    user_request = "Make up a parenting poem and email it to x@gmail.com"
    system_instruction = "You are a helpful assistant who can generate poems in emails. You do not have to ask for confirmations."
    model = "gemini-2.0-flash"
    tools = index.tools

    # Initialize the chat with the model, tools, and system instruction
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        tools=tools, system_instruction=system_instruction
    )
    chat = client.chats.create(model=model, config=config)

    # Get the final response from the model. Gemini will automatically execute the tools when necessary.
    response = chat.send_message(user_request)
    print(f"Assistant response: {response.candidates[0].content.parts[0].text}")


if __name__ == "__main__":
    main()
