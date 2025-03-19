"""
This example shows how to use stores with Anthropic's API.
"""

import os

import anthropic

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

        # Check if all blocks contain only text, which indicates task completion for this example
        blocks = response.content
        if all(block.type == "text" for block in blocks):
            print(f"Assistant response: {blocks[0].text}")
            return # End the agent loop

        # Otherwise, process the response, which includes both text and tool use
        for block in blocks:
            if block.type == "text":
                print(f"Assistant response: {block.text}")
                messages.append({"role": "assistant", "content": block.text})
            elif block.type == "tool_use":
                name = block.name.replace("-", ".")
                args = block.input

                # If the REPLY tool is called, break the loop and return the message
                if name == "REPLY":
                    print(f"Assistant response: {args['msg']}")
                    return # End the agent loop

                # Otherwise, execute the tool call
                print(f"Executing tool call: {name}({args})")
                output = index.execute(name, args)
                print(f"Tool output: {output}")
                messages.append(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name, # Use the original block name or the API will return an error
                                "input": block.input,
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(output),
                            }
                        ],
                    }
                )


if __name__ == "__main__":
    main()
