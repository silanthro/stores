"""
This example shows how to use stores with Google's Gemini API with manual tool calling.
"""

import os

import dotenv
from google import genai
from google.genai import types

import stores

dotenv.load_dotenv()


def main():
    # Initialize Google Gemini client
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

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

    # Configure the model with tools
    config = types.GenerateContentConfig(
        tools=index.tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True  # Gemini automatically executes tool calls. This script shows how to manually execute tool calls.
        ),
    )

    # Get the response from the model
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Send a haiku about dreams to x@gmail.com. Don't ask questions.",
        config=config,
    )

    # Execute the tool call
    tool_call = response.candidates[0].content.parts[0].function_call
    fn_name = tool_call.name
    fn_args = tool_call.args
    result = index.execute(fn_name, fn_args)
    print(f"Tool output: {result}")


if __name__ == "__main__":
    main()
