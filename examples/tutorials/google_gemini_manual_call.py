"""
This example shows how to use stores with Google's Gemini API with manual tool calling.
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

    # Set up the user request, system instruction, model parameters, tools, and initial messages
    user_request = "Make up a parenting poem and email it to x@gmail.com"
    system_instruction = "You are a helpful assistant who can generate poems in emails. You do not have to ask for confirmations."
    model = "gemini-2.0-flash"
    tools = index.tools
    messages = [
        {"role": "user", "parts": [{"text": user_request}]},
    ]

    # Initialize the model
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        tools=tools,
        system_instruction=system_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True  # Gemini automatically executes tool calls. This script shows how to manually execute tool calls.
        ),
    )

    # Run the agent loop
    while True:
        # Get the response from the model
        response = client.models.generate_content(
            model=model, contents=messages, config=config
        )

        # Check if all parts contain only text and no function call, which indicates task completion for this example
        parts = response.candidates[0].content.parts
        if all(part.text and not part.function_call for part in parts):
            print(f"Assistant response: {parts[0].text}")
            return  # End the agent loop

        # Otherwise, process the response, which could include both text and tool use
        for part in parts:
            if part.text:
                print(f"Assistant response: {part.text}")
                messages.append({"role": "assistant", "parts": [{"text": part.text}]})
            elif part.function_call:
                name = part.function_call.name
                args = part.function_call.args
                print(f"Executing tool call: {name}({args})")
                output = index.execute(name, args)
                print(f"Tool output: {output}")
                messages.append(
                    {
                        "role": "assistant",
                        "parts": [{"functionCall": part.function_call}],
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": name,
                                    "response": {"output": output},
                                },
                            }
                        ],
                    }
                )


if __name__ == "__main__":
    main()
