"""
This example shows how to use stores with Anthropic's API.
"""
import os
from dotenv import load_dotenv

import anthropic
import json

load_dotenv()

import stores

def main():
    # Example request to demonstrate the use of tools with OpenAI
    request = "Make up a parenting poem and email it to alfredlua@gmail.com"

    # Load default and custom tools and set the required environment variables
    from stores.tools import DEFAULT_TOOLS
    index = stores.Index(
        DEFAULT_TOOLS + ["./custom_tools"],
        env_vars={
            "./custom_tools": {
                "GMAIL_ADDRESS": os.environ["GMAIL_ADDRESS"],
                "GMAIL_PASSWORD": os.environ["GMAIL_PASSWORD"],
            },    
        },
    )

    # Set up the initial message from the user to the model
    messages = [{"role": "user", "content": request}]

    # Initialize the model with OpenAI
    client = anthropic.Anthropic()

    # Get the response from the model
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        messages=messages,
        tools=index.format_tools("anthropic"),
        max_tokens=1024,
    )

    print(f"Model Response: {response.content}")
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
        model="claude-3-haiku-20240307",
        messages=messages,
        tools=index.format_tools("anthropic"),
        max_tokens=1024,
    )

    print(f"Final Model Response: {final_completion.content[0].text}")

if __name__ == "__main__":
    main()