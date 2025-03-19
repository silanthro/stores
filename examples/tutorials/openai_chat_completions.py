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

        # Check if the response contain only text and no function call, which indicates task completion for this example
        if (
            completion.choices[0].message.content
            and not completion.choices[0].message.tool_calls
        ):
            print(f"Assistant response: {completion.choices[0].message.content}")
            return  # End the agent loop

        # Otherwise, process the response, which could include both text and tool calls
        if completion.choices[0].message.content:
            print(f"Assistant response: {completion.choices[0].message.content}")
            messages.append(
                {"role": "assistant", "content": completion.choices[0].message.content}
            )

        if completion.choices[0].message.tool_calls:
            tool_calls = completion.choices[0].message.tool_calls
            for tool_call in tool_calls:
                name = tool_call.function.name.replace("-", ".")
                args = json.loads(tool_call.function.arguments)

                # If the REPLY tool is called, break the loop and return the message
                if name == "REPLY":
                    print(f"Assistant response: {args['msg']}")
                    return  # End the agent loop

                # Otherwise, execute the tool call
                print(f"Executing tool call: {name}({args})")
                output = index.execute(name, args)
                print(f"Tool output: {output}")
                messages.append(
                    {"role": "assistant", "tool_calls": [tool_call]}
                )  # Append the assistant's tool call as context
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(output),
                    }
                )  # Append the tool call result as context


if __name__ == "__main__":
    main()
