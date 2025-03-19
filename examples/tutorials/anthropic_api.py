"""
This example shows how to use stores with Anthropic's API.
"""

import os

import anthropic

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
    model = "claude-3-5-sonnet-20241022"
    max_tokens = 1024
    tools = index.format_tools("anthropic")
    messages = [{"role": "user", "content": user_request}]

    # Initialize the model with Anthropic
    client = anthropic.Anthropic()

    # Run the agent loop
    while True:
        # Get the response from the model
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_instruction,
            messages=messages,
            tools=tools,
        )

        # Append the assistant's response as context
        messages.append({"role": "assistant", "content": response.content})

        # Process the response, which includes both text and tool use
        for blocks in response.content:
            if blocks.type == "text":
                print(f"Assistant Response: {blocks.text}")
            elif blocks.type == "tool_use":
                print(f"Tool Call: {blocks}")
                name = blocks.name.replace("-", ".")
                args = blocks.input

                # If the REPLY tool is called, break the loop and return the message
                if blocks.name == "REPLY":
                    print(f"Assistant Response: {blocks.input['msg']}")
                    return

                # Otherwise, execute the tool call
                output = index.execute(name, args)
                messages.append(
                    {
                        "role": "user",  # Some APIs require a tool role instead
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": blocks.id,
                                "content": str(output),
                            }
                        ],
                    }
                )
                print(f"Tool Output: {output}")


if __name__ == "__main__":
    main()
