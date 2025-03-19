"""
This example shows how to use stores with OpenAI's Responses API.
"""

import json
import os

from openai import OpenAI

import stores


def main():
    # Load tools and set the required environment variables
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

        # Check if the response contains only text and no tool call, which indicates task completion for this example
        if len(response.output) == 1 and response.output[0].type == "text":
            print(f"Assistant response: {response.output[0].text}")
            return  # End the agent loop

        # Otherwise, process the response, which could include both text and tool calls
        for item in response.output:
            if item.type == "text":
                print(f"Assistant response: {item.text}")
                messages.append({"role": "assistant", "content": item.text})
            elif item.type == "function_call":
                name = item.name.replace("-", ".")
                args = json.loads(item.arguments)

                # If the REPLY tool is called, break the loop and return the message
                if name == "REPLY":
                    print(f"Assistant response: {args['msg']}")
                    return  # End the agent loop

                # Otherwise, execute the tool call
                print(f"Executing tool call: {name}({args})")
                output = index.execute(name, args)
                print(f"Tool output: {output}")
                messages.append(
                    item
                )  # Append the assistant's tool call message as context
                messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": str(output),
                    }
                )  # Append the tool call result as context


if __name__ == "__main__":
    main()
