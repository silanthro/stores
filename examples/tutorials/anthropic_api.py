"""
This example shows how to use stores with Anthropic's API.
"""
import os

import anthropic

import stores


def main():
    # Example request and system prompt to demonstrate the use of tools with Anthropic
    user_request = "Make up a parenting poem and email it to x@gmail.com"
    system = "You are a helpful assistant who can generate poems. When necessary, you have tools at your disposal."

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

    # Set up the initial message from the user to the model
    messages = [{"role": "user", "content": user_request}]

    # Initialize the model with Anthropic
    client = anthropic.Anthropic()
    model = "claude-3-5-haiku-20241022"

    # Get the response from the model
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
        tools=index.format_tools("anthropic"),
    )

    print(f"Assistant Response: {response.content}")
    messages.append({"role": "assistant", "content": response.content})
    
    # Execute the tool calls
    for blocks in response.content:
        if blocks.type == "tool_use":
            print(f"Tool Call: {blocks}")
            name = blocks.name.replace("-", ".")
            args = blocks.input
            output = index.execute(name, args)
            messages.append(
                {
                "role": "user", 
                "content": [
                    {
                    "type": "tool_result",
                    "tool_use_id": blocks.id,
                    "content": output
                    }
                ]
                })
            print(f"Tool Output: {output}")

    # Get the final response from the model
    final_completion = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
        tools=index.format_tools("anthropic"),
    )
    
    print(f"Assistant Response: {final_completion.content[0].text}")

if __name__ == "__main__":
    main()