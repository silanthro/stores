"""
This example shows how to use stores with OpenAI's Responses API.
"""

import json
import os

from openai import OpenAI

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
    system_instruction = "You are a helpful assistant who can generate poems in emails. When necessary, you have tools at your disposal. Always use the REPLY tool when you have completed the task. You do not have to ask for confirmations."
    model = "gpt-4o-mini-2024-07-18"
    tools = index.format_tools("openai-responses")
    messages = [
        {"role": "developer", "content": system_instruction},
        {"role": "user", "content": user_request},
    ]

    # Initialize the model with OpenAI
    client = OpenAI()

    # Run the agent loop
    while True:
        # Get the response from the model
        response = client.responses.create(
            model=model,
            input=messages,
            tools=tools,
        )

        # Execute the tool calls
        tool_calls = response.output
        for tool_call in tool_calls:
            print(f"Tool Call: {tool_call}")
            name = tool_call.name.replace("-", ".")
            args = json.loads(tool_call.arguments)

            # If the REPLY tool is called, break the loop and return the message
            if name == "REPLY":
                print(f"Assistant Response: {args['msg']}")
                return

            # Otherwise, execute the tool call
            output = index.execute(name, args)
            messages.append(
                tool_call
            )  # Append the assistant's tool call message as context
            messages.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": str(output),
                }
            )
            print(f"Tool Output: {output}")


if __name__ == "__main__":
    main()
