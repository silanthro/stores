"""
This example shows how to use stores with OpenAI's Chat Completions API.
"""

import json
import os

from openai import OpenAI

import stores


def main():
    # Load custom tools and set the required environment variables
    index = stores.Index(
        ["./custom_tools"],
        env_vars={
            "./custom_tools": {
                "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
                "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
            },
        },
    )

    # Set up the user request, system instruction, model parameters, tools, and initial messages
    user_request = "Make up a parenting poem and email it to x@gmail.com"
    system_instruction = "You are a helpful assistant who can generate poems in emails. When necessary, you have tools at your disposal. Always use the REPLY tool when you have completed the task. You do not have to ask for confirmations."
    model = "gpt-4o-mini-2024-07-18"
    tools = index.format_tools("openai-chat-completions")
    messages = [
        {"role": "developer", "content": system_instruction},
        {"role": "user", "content": user_request},
    ]

    # Initialize the model with OpenAI
    client = OpenAI()

    # Run the agent loop
    while True:
        # Get the response from the model
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
        )

        # Execute the tool calls
        tool_calls = completion.choices[0].message.tool_calls
        for tool_call in tool_calls:
            print(f"Tool Call: {tool_call}")
            name = tool_call.function.name.replace("-", ".")
            args = json.loads(tool_call.function.arguments)

            # If the REPLY tool is called, break the loop and return the message
            if name == "REPLY":
                print(f"Assistant Response: {args['msg']}")
                return

            # Otherwise, execute the tool call
            output = index.execute(name, args)
            messages.append(
                completion.choices[0].message
            )  # Append the assistant's tool call message as context
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": str(output)}
            )
            print(f"Tool Output: {output}")


if __name__ == "__main__":
    main()
